import pytest
from decimal import Decimal
from apps.proyeccion.services import (
    EstimationPNTCalculator, EstimationFinancialSettingsService,
)
from apps.proyeccion.tests.factories import (
    EstimationProjectFactory, EstimationBillingRuleFactory, build_pnt_ready_project,
    ConceptFamilyFactory, ConceptSubfamilyFactory, make_concept_for_project,
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
        concept = make_concept_for_project(project)
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
        concept = make_concept_for_project(project)
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
        concept = make_concept_for_project(project)
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
        concept = make_concept_for_project(project)
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
        concept = make_concept_for_project(project)
        for i in range(3):
            WorkPlanEntry.objects.create(
                conceptid=concept, projectid=project, periodnumber=i + 1, periodlabel=f'P{i+1:02d}',
                entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
            )
        # Anticipo grande para que el cap no se active y se vea la acumulación pura.
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'advanceamountnotax': Decimal('1000'), 'advanceamortizationrate': Decimal('0.10')},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        saldo = next(r for r in report.rows if r.code == 'SALDO_ANTICIPO').values
        assert saldo == [Decimal('-10.0000'), Decimal('-20.0000'), Decimal('-30.0000')]
        # Cap NO se activó → stat no marcado
        assert report.stats.get('advance_fully_amortized_period') is None

    def test_cobro_total_excludes_saldo_anticipo(self):
        """SALDO_ANTICIPO is reported but NOT summed into COBRO_TOTAL (avoid double-count)."""
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import WorkPlanEntry
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
        )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'imssretentionrate': Decimal('0'), 'otherretentionrate': Decimal('0'),
             'advanceamountnotax': Decimal('1000'),  # cap holgado
             'advanceentryperiod': 99,  # anticipo entra fuera del horizonte → ANTICIPO_CONCEDIDO=0
             'advanceamortizationrate': Decimal('0.5')},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        cobro_total = next(r for r in report.rows if r.code == 'COBRO_TOTAL').values
        assert cobro_total[0] == Decimal('50.0000')

    def test_amortizacion_capped_at_advance_amount(self):
        """Una vez que el saldo acumulado iguala el monto del anticipo, no más amortización."""
        project, _ = build_pnt_ready_project(periods=4)
        from apps.proyeccion.models import WorkPlanEntry
        concept = make_concept_for_project(project)
        # 4 periodos con distributedamount=100 cada uno → cobro_facturacion = [100, 100, 100, 100]
        for i in range(4):
            WorkPlanEntry.objects.create(
                conceptid=concept, projectid=project, periodnumber=i + 1, periodlabel=f'P{i+1:02d}',
                entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('100'),
            )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'advanceamountnotax': Decimal('25'),  # cap chico
             'advanceamortizationrate': Decimal('0.10')},  # 10% × 100 = 10/periodo
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        amort = next(r for r in report.rows if r.code == 'ANTICIPO_AMORT').values
        saldo = next(r for r in report.rows if r.code == 'SALDO_ANTICIPO').values
        # P1: cum=-10, dentro de cap (-25). actual=-10
        # P2: cum=-20, dentro de cap. actual=-10
        # P3: cum=-30 excedería; cap=-25; actual=-5 (solo lo necesario para llegar a -25)
        # P4: ya en cap → actual=0
        assert amort == [Decimal('-10.0000'), Decimal('-10.0000'), Decimal('-5.0000'), Decimal('0')]
        # Saldo acumulado: -10, -20, -25, -25 (no avanza más allá del cap)
        assert saldo == [Decimal('-10.0000'), Decimal('-20.0000'), Decimal('-25.0000'), Decimal('-25.0000')]
        # Stat: completó amortización en P3 (índice 2 → label 'P03')
        assert report.stats['advance_fully_amortized_period'] == 'P03'

    def test_amortizacion_zero_when_no_advance(self):
        """Sin monto de anticipo, no hay amortización (independiente de la tasa)."""
        project, _ = build_pnt_ready_project(periods=2)
        from apps.proyeccion.models import WorkPlanEntry
        concept = make_concept_for_project(project)
        WorkPlanEntry.objects.create(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='P01',
            entrytype=0, distributedquantity=Decimal('1'), distributedamount=Decimal('1000'),
        )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            # advanceamountnotax queda en default 0
            {'advanceamortizationrate': Decimal('0.20')},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        amort = next(r for r in report.rows if r.code == 'ANTICIPO_AMORT').values
        assert all(v == Decimal('0') for v in amort)
        assert report.stats.get('advance_fully_amortized_period') is None


@pytest.mark.django_db
@pytest.mark.unit
class TestEstimationPNTCalculatorPagosYCaja:
    def _wire_costs(self, project, periods):
        """Helper: distribute 1000 direct + 200 indirect uniformly across N periods via CostDistribution."""
        from apps.proyeccion.models import (
            UnitCostBreakdown, IndirectCostDetail, CostDistribution,
        )
        concept = make_concept_for_project(project)
        breakdown = UnitCostBreakdown.objects.create(
            conceptid=concept, categorycode=1, linenumber=1, description='Mat',
            unit='kg', quantity=Decimal('1'), unitprice=Decimal('1000'),
            yieldvalue=Decimal('1'), amount=Decimal('1000'),
        )
        indirect = IndirectCostDetail.objects.create(
            projectid=project, categorycode='C1', linenumber=1, description='Personal',
            monthlycost=Decimal('200'), units=Decimal('1'), months=Decimal('1'),
            amount=Decimal('200'),
        )
        n = len(periods)
        frac = Decimal('1') / Decimal(n)
        for p in periods:
            CostDistribution.objects.create(
                projectid=project, linetype=0, breakdownid=breakdown,
                periodnumber=p.periodnumber, fraction=frac, isderived=True,
            )
            CostDistribution.objects.create(
                projectid=project, linetype=1, indirectcostid=indirect,
                periodnumber=p.periodnumber, fraction=frac, isderived=True,
            )

    def test_pagos_directo_with_lag(self):
        project, periods = build_pnt_ready_project(periods=4)
        self._wire_costs(project, periods)
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'directpaymentlag': 1, 'indirectpaymentlag': 0},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        pagos_dir = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
        # Direct = -250 per period, shifted by 1 → P1=0, P2=-250, P3=-250, P4=-250 (last 250 falls "outside")
        assert pagos_dir[0] == Decimal('0')
        assert pagos_dir[1] == Decimal('-250')
        assert pagos_dir[2] == Decimal('-250')
        assert pagos_dir[3] == Decimal('-250')

    def test_pagos_indirecto_with_zero_lag(self):
        project, periods = build_pnt_ready_project(periods=4)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        pagos_ind = next(r for r in report.rows if r.code == 'PAGOS_INDIRECTO').values
        assert all(v == Decimal('-50') for v in pagos_ind)

    def test_pagos_directo_with_per_line_lag(self):
        """A breakdown with paymentlagperiods=2 lands its cost 2 periods later."""
        from apps.proyeccion.models import UnitCostBreakdown, CostDistribution
        project, periods = build_pnt_ready_project(periods=4)
        concept = make_concept_for_project(project)
        breakdown = UnitCostBreakdown.objects.create(
            conceptid=concept, categorycode=1, linenumber=1, description='Mat',
            unit='kg', quantity=Decimal('1'), unitprice=Decimal('1000'),
            yieldvalue=Decimal('1'), amount=Decimal('1000'),
            paymentlagperiods=2,
        )
        n = len(periods)
        frac = Decimal('1') / Decimal(n)
        for p in periods:
            CostDistribution.objects.create(
                projectid=project, linetype=0, breakdownid=breakdown,
                periodnumber=p.periodnumber, fraction=frac, isderived=True,
            )
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'directpaymentlag': 0},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        pagos_dir = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
        # Direct = -250 per period. With per-line lag 2: P1→P3, P2→P4, P3 and P4 overflow.
        assert pagos_dir[0] == Decimal('0')
        assert pagos_dir[1] == Decimal('0')
        assert pagos_dir[2] == Decimal('-250')
        assert pagos_dir[3] == Decimal('-250')

    def test_pagos_directo_uses_global_lag_when_line_lag_is_none(self):
        """Lines with paymentlagperiods=None fall back to the global directpaymentlag."""
        project, periods = build_pnt_ready_project(periods=4)
        self._wire_costs(project, periods)
        EstimationFinancialSettingsService.update(
            project.estimationprojectid,
            {'directpaymentlag': 1},
            user=None,
        )
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        pagos_dir = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
        # Direct = -250 per period. Global lag 1: P1=0, P2=-250, P3=-250, P4=-250
        assert pagos_dir[0] == Decimal('0')
        assert pagos_dir[1] == Decimal('-250')
        assert pagos_dir[2] == Decimal('-250')
        assert pagos_dir[3] == Decimal('-250')

    def test_retiro_transv_distributed_per_period_no_lag(self):
        project, periods = build_pnt_ready_project(periods=4)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        retiro_t = next(r for r in report.rows if r.code == 'RETIRO_TRANSV').values
        # base_cost per period = 250 (dir) + 50 (ind) = 300; transversal = 5%
        # retiro = -300 * 0.05 = -15 per period (rounded by compute_rollups)
        assert all(v == Decimal('-15.00') for v in retiro_t)

    def test_caja_acumulada_is_cumsum_of_caja_mes(self):
        project, periods = build_pnt_ready_project(periods=2)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        caja_mes = next(r for r in report.rows if r.code == 'CAJA_MES').values
        caja_acc = next(r for r in report.rows if r.code == 'CAJA_ACUMULADA').values
        assert caja_acc[0] == caja_mes[0]
        assert caja_acc[1] == caja_mes[0] + caja_mes[1]

    def test_costo_financiero_only_on_negative_caja(self):
        project, periods = build_pnt_ready_project(periods=3)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        cf = next(r for r in report.rows if r.code == 'COSTO_FINANCIERO').values
        caja_acc = next(r for r in report.rows if r.code == 'CAJA_ACUMULADA').values
        for v_cf, v_acc in zip(cf, caja_acc):
            if v_acc < 0:
                assert v_cf == v_acc * Decimal('0.001000')
            else:
                assert v_cf == Decimal('0')

    def test_resultado_equals_prod_minus_cd_minus_ci_minus_retiros(self):
        project, periods = build_pnt_ready_project(periods=2)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        prod = next(r for r in report.rows if r.code == 'PRODUCCION').values
        cd = next(r for r in report.rows if r.code == 'COSTO_DIRECTO').values
        ci = next(r for r in report.rows if r.code == 'COSTO_INDIRECTO').values
        rt = next(r for r in report.rows if r.code == 'RETIRO_TRANSV_RES').values
        ru = next(r for r in report.rows if r.code == 'RETIRO_UTIL_RES').values
        resultado = next(r for r in report.rows if r.code == 'RESULTADO').values
        for i in range(2):
            expected = prod[i] + cd[i] + ci[i] + rt[i] + ru[i]
            assert resultado[i] == expected

    def test_stats_include_pnt_min_max_avg(self):
        project, periods = build_pnt_ready_project(periods=2)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        assert 'pnt_min' in report.stats
        assert 'pnt_max' in report.stats
        assert 'pnt_avg' in report.stats
        assert 'total_costo_financiero' in report.stats
        assert 'pagos_fuera_horizonte' in report.stats

    def test_row_taxonomy_complete(self):
        """Assert the 22 expected row codes appear exactly once."""
        project, periods = build_pnt_ready_project(periods=2)
        self._wire_costs(project, periods)
        calc = EstimationPNTCalculator(project.estimationprojectid)
        report = calc.compute()
        expected = {
            'RESULTADO', 'PRODUCCION', 'COSTO_DIRECTO', 'COSTO_INDIRECTO',
            'RETIRO_TRANSV_RES', 'RETIRO_UTIL_RES',
            'COBRO_TOTAL', 'COBRO_FACTURACION', 'ANTICIPO_CONCEDIDO',
            'ANTICIPO_AMORT', 'RET_IMSS', 'OTRAS_RET', 'DEVOLUCION', 'SALDO_ANTICIPO',
            'PAGOS_DIRECTO', 'PAGOS_INDIRECTO', 'RETIRO_TRANSV', 'RETIRO_UTILIDADES',
            'PAGOS_TOTALES',
            'CAJA_MES', 'CAJA_ACUMULADA', 'COSTO_FINANCIERO',
        }
        actual = {r.code for r in report.rows}
        assert actual == expected, f"Missing: {expected - actual}; Extra: {actual - expected}"


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_pagos_lag_uses_line_value_when_set():
    """A line with paymentlagperiods=2 lands its cost 2 periods later."""
    from apps.proyeccion.services import EstimationPNTCalculator
    from decimal import Decimal
    calc = EstimationPNTCalculator.__new__(EstimationPNTCalculator)
    calc.N = 5
    by_line = {'line-A': [Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')]}
    lag_by_line = {'line-A': 2}
    out, fuera = calc._apply_pagos_lag(by_line, lag_by_line, default_lag=0)
    assert out == [Decimal('0'), Decimal('0'), Decimal('-100'), Decimal('0'), Decimal('0')]
    assert fuera == Decimal('0')


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_pagos_lag_falls_back_to_default_when_line_lag_is_none():
    """A line with paymentlagperiods=None uses the default_lag argument."""
    from apps.proyeccion.services import EstimationPNTCalculator
    from decimal import Decimal
    calc = EstimationPNTCalculator.__new__(EstimationPNTCalculator)
    calc.N = 4
    by_line = {'line-A': [Decimal('200'), Decimal('0'), Decimal('0'), Decimal('0')]}
    lag_by_line = {'line-A': None}
    out, fuera = calc._apply_pagos_lag(by_line, lag_by_line, default_lag=1)
    assert out == [Decimal('0'), Decimal('-200'), Decimal('0'), Decimal('0')]
    assert fuera == Decimal('0')


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_pagos_lag_routes_overflow_to_fuera_horizonte():
    """Lag that pushes a cost beyond the last period accumulates in fuera."""
    from apps.proyeccion.services import EstimationPNTCalculator
    from decimal import Decimal
    calc = EstimationPNTCalculator.__new__(EstimationPNTCalculator)
    calc.N = 3
    by_line = {'line-A': [Decimal('0'), Decimal('0'), Decimal('50')]}
    lag_by_line = {'line-A': 2}
    out, fuera = calc._apply_pagos_lag(by_line, lag_by_line, default_lag=0)
    assert out == [Decimal('0'), Decimal('0'), Decimal('0')]
    assert fuera == Decimal('-50')


@pytest.mark.unit
@pytest.mark.django_db
def test_apply_pagos_lag_iterates_multiple_lines_with_different_lags():
    """Two lines with different lags both land correctly."""
    from apps.proyeccion.services import EstimationPNTCalculator
    from decimal import Decimal
    calc = EstimationPNTCalculator.__new__(EstimationPNTCalculator)
    calc.N = 4
    by_line = {
        'line-A': [Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0')],
        'line-B': [Decimal('200'), Decimal('0'), Decimal('0'), Decimal('0')],
    }
    lag_by_line = {'line-A': 1, 'line-B': 3}
    out, fuera = calc._apply_pagos_lag(by_line, lag_by_line, default_lag=0)
    assert out == [Decimal('0'), Decimal('-100'), Decimal('0'), Decimal('-200')]
    assert fuera == Decimal('0')
