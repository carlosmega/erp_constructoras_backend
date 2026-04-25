import pytest
from decimal import Decimal
from apps.proyeccion.services import (
    EstimationPNTCalculator, EstimationFinancialSettingsService,
)
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, EstimationBillingRuleFactory, build_pnt_ready_project,
    ConceptFamilyFactory, ConceptSubfamilyFactory,
)


def _make_concept_for_project(project, code='C-001', description='Test', unit='m2'):
    """Helper: create a BudgetConcept attached to project with required relations."""
    from apps.proyeccion.models import BudgetConcept
    family = ConceptFamilyFactory(projectid=project)
    subfamily = ConceptSubfamilyFactory(familyid=family, projectid=project)
    return BudgetConcept.objects.create(
        projectid=project,
        subfamilyid=subfamily,
        code=code,
        sequencenumber=1,
        description=description,
        unit=unit,
        quantity=Decimal('1'),
    )


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorInit:
    def test_raises_when_no_periods(self):
        project = EstimationProjectFactory()
        with pytest.raises(ValueError, match='Plan de Obra'):
            EstimationPNTCalculator(project.estimationprojectid)

    def test_loads_periods_in_order(self):
        project, periods = build_pnt_ready_project(periods=3)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        assert calc.N == 3
        assert [p.periodnumber for p in calc.periods] == [1, 2, 3]

    def test_default_billing_rule_when_none_persisted(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        # Default implícito: 100%/lag 0
        assert len(calc.billing_rules) == 1
        assert calc.billing_rules[0].percent == Decimal('1')
        assert calc.billing_rules[0].lagperiods == 0

    def test_loads_persisted_billing_rules(self):
        project, _ = build_pnt_ready_project(periods=2)
        EstimationBillingRuleFactory(projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=0)
        EstimationBillingRuleFactory(projectid=project, sequence=2, percent=Decimal('0.5'), lagperiods=1)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        assert len(calc.billing_rules) == 2
        assert calc.billing_rules[0].sequence == 1


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorOverrides:
    def test_apply_overrides_modifies_in_memory_only(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        original_rate = calc.settings.imssretentionrate
        calc._apply_overrides({'imssretentionrate': '0.20'})
        assert calc.settings.imssretentionrate == Decimal('0.20')
        # Refetch from DB — must be unchanged
        from apps.proyeccion.models import EstimationFinancialSettings
        fresh = EstimationFinancialSettings.objects.get(projectid=project)
        assert fresh.imssretentionrate == original_rate

    def test_overrides_billing_rules(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        calc._apply_overrides({
            'billing_rules': [
                {'sequence': 1, 'percent': '0.6', 'lagperiods': 0},
                {'sequence': 2, 'percent': '0.4', 'lagperiods': 2},
            ],
        })
        assert len(calc.billing_rules) == 2
        assert calc.billing_rules[1].lagperiods == 2

    def test_overrides_ignore_non_whitelisted(self):
        project, _ = build_pnt_ready_project(periods=2)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        calc._apply_overrides({'unknown_key': 'whatever', 'settingsid': 'x'})
        # No exception, no change
        assert calc.settings.imssretentionrate == Decimal('0.0500')


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorCobros:
    def test_cobro_facturacion_default_rule_lag_zero(self):
        project, periods = build_pnt_ready_project(periods=4)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        for i, amt in enumerate([100, 200, 300, 400]):
            WorkPlanEntry.objects.create(
                conceptid=concept, projectid=project,
                periodnumber=i + 1, periodlabel=f'P{i + 1:02d}',
                entrytype=0,
                distributedquantity=Decimal('1'),
                distributedamount=Decimal(amt),
            )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        cobro_fact = next(r for r in report.rows if r.code == 'COBRO_FACTURACION').values
        assert cobro_fact == [Decimal('100'), Decimal('200'), Decimal('300'), Decimal('400')]

    def test_cobro_facturacion_two_tranches_with_lag(self):
        project, _ = build_pnt_ready_project(periods=4)
        EstimationBillingRuleFactory(projectid=project, sequence=1, percent=Decimal('0.5'), lagperiods=0)
        EstimationBillingRuleFactory(projectid=project, sequence=2, percent=Decimal('0.5'), lagperiods=1)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        cobro_fact = next(r for r in report.rows if r.code == 'COBRO_FACTURACION').values
        assert cobro_fact[0] == Decimal('500')
        assert cobro_fact[1] == Decimal('500')
        assert cobro_fact[2] == Decimal('0')
        assert cobro_fact[3] == Decimal('0')

    def test_anticipo_concedido_in_specific_period(self):
        project, _ = build_pnt_ready_project(periods=4)
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'advanceamountnotax': Decimal('500'), 'advanceentryperiod': 2},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        ant = next(r for r in report.rows if r.code == 'ANTICIPO_CONCEDIDO').values
        assert ant == [Decimal('0'), Decimal('500'), Decimal('0'), Decimal('0')]

    def test_retencion_imss_is_negative_fraction_of_facturacion(self):
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        ret = next(r for r in report.rows if r.code == 'RET_IMSS').values
        assert ret[0] == Decimal('-50.0000')

    def test_devolucion_returns_at_specified_period(self):
        project, _ = build_pnt_ready_project(periods=4)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'imssretentionrate': Decimal('0.05'), 'retentionreturnperiod': 4},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        dev = next(r for r in report.rows if r.code == 'DEVOLUCION').values
        assert dev[3] == Decimal('50.0000')
        assert sum(dev) == Decimal('50.0000')

    def test_saldo_anticipo_is_cumulative_amortization(self):
        project, _ = build_pnt_ready_project(periods=3)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        for i in range(3):
            WorkPlanEntry.objects.create(
                conceptid=concept, projectid=project, periodnumber=i + 1, periodlabel=f'P{i+1:02d}',
                entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
            )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'advanceamortizationrate': Decimal('0.10')},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        saldo = next(r for r in report.rows if r.code == 'SALDO_ANTICIPO').values
        assert saldo == [Decimal('-10.0000'), Decimal('-20.0000'), Decimal('-30.0000')]

    def test_cobro_total_excludes_saldo_anticipo(self):
        """SALDO_ANTICIPO is reported but NOT summed into COBRO_TOTAL (avoid double-count)."""
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import WorkPlanEntry
        concept = _make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
        )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'imssretentionrate': Decimal('0'), 'otherretentionrate': Decimal('0'),
             'advanceamortizationrate': Decimal('0.5')},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        cobro_total = next(r for r in report.rows if r.code == 'COBRO_TOTAL').values
        assert cobro_total[0] == Decimal('50.0000')
