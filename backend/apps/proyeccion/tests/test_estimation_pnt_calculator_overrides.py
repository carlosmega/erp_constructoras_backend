import pytest
from decimal import Decimal
from apps.proyeccion.services import EstimationPNTCalculator
from apps.proyeccion.tests.factories import (
    build_pnt_ready_project,
    EstimationBillingRuleFactory,
    make_concept_for_project,
)


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorOverridesEffect:
    def test_override_imss_changes_ret_imss(self):
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import WorkPlanEntry
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        base = calc.compute()
        sim = calc.compute(overrides={'imssretentionrate': '0.20'})
        ret_base = next(r for r in base.rows if r.code == 'RET_IMSS').values[0]
        ret_sim = next(r for r in sim.rows if r.code == 'RET_IMSS').values[0]
        assert ret_base == Decimal('-50.0000')   # 5% x 1000
        assert ret_sim == Decimal('-200.0000')   # 20% x 1000

    def test_override_billing_rules_replaces_set(self):
        project, _ = build_pnt_ready_project(periods=4)
        EstimationBillingRuleFactory(projectid=project, sequence=1, percent=Decimal('1.0'), lagperiods=0)
        from apps.proyeccion.models import WorkPlanEntry
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        sim = calc.compute(overrides={
            'billing_rules': [
                {'sequence': 1, 'percent': '0.5', 'lagperiods': 0},
                {'sequence': 2, 'percent': '0.5', 'lagperiods': 1},
            ],
        })
        cobro = next(r for r in sim.rows if r.code == 'COBRO_FACTURACION').values
        assert cobro[0] == Decimal('500')
        assert cobro[1] == Decimal('500')

    def test_override_does_not_persist(self):
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import EstimationFinancialSettings
        calc = EstimationPNTCalculator(project.estimationprojectid)
        original = calc.settings.imssretentionrate
        calc.compute(overrides={'imssretentionrate': '0.50'})
        # Refetch from DB
        fresh = EstimationFinancialSettings.objects.get(projectid=project)
        assert fresh.imssretentionrate == original
