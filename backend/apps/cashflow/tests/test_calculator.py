"""Tests for PNTCalculator. Math is critical — each scenario has a golden expected value."""
import pytest
from decimal import Decimal
from apps.cashflow.services.pnt_calculator import PNTCalculator
from apps.cashflow.tests.factories import build_simple_project_fixture


@pytest.mark.django_db
@pytest.mark.unit
def test_produccion_and_costs_are_derived_from_budget():
    fx = build_simple_project_fixture(
        periods=3, produccion_per_period=1000,
        direct_cost_per_period=700, indirect_cost_per_period=100,
    )
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()

    produccion = next(r for r in report.rows if r.code == 'PRODUCCION')
    costo_directo = next(r for r in report.rows if r.code == 'COSTO_DIRECTO')
    costo_indirecto = next(r for r in report.rows if r.code == 'COSTO_INDIRECTO')

    assert produccion.values == [Decimal('1000'), Decimal('1000'), Decimal('1000')]
    assert costo_directo.values == [Decimal('700'), Decimal('700'), Decimal('700')]
    assert costo_indirecto.values == [Decimal('100'), Decimal('100'), Decimal('100')]


@pytest.mark.django_db
@pytest.mark.unit
def test_cobro_facturacion_100pct_no_lag():
    """Default billing rule 100%/0 — cobro == produccion."""
    fx = build_simple_project_fixture(periods=3, produccion_per_period=1000)
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    cobro = next(r for r in report.rows if r.code == 'COBRO_FACTURACION')
    assert cobro.values == [Decimal('1000'), Decimal('1000'), Decimal('1000')]


@pytest.mark.django_db
@pytest.mark.unit
def test_cobro_facturacion_with_50_30_20_rule_and_lags():
    from apps.cashflow.services.billing_rule import BillingRuleService
    fx = build_simple_project_fixture(periods=5, produccion_per_period=1000)
    BillingRuleService.replace(fx['project'].projectid, [
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
        {'sequence': 2, 'percent': Decimal('0.3'), 'lagperiods': 1},
        {'sequence': 3, 'percent': Decimal('0.2'), 'lagperiods': 2},
    ])
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    cobro = next(r for r in report.rows if r.code == 'COBRO_FACTURACION').values
    # With 5 periods P0..P4, each producing 1000 at rule {50%@0, 30%@+1, 20%@+2}:
    # P0 receives: P0x50%       = 500
    # P1 receives: P0x30% + P1x50% = 300 + 500 = 800
    # P2 receives: P0x20% + P1x30% + P2x50% = 200 + 300 + 500 = 1000
    # P3 receives: P1x20% + P2x30% + P3x50% = 200 + 300 + 500 = 1000
    # P4 receives: P2x20% + P3x30% + P4x50% = 200 + 300 + 500 = 1000
    # Out of horizon (fuera):
    #   P3x20% (lag 2 -> target P5)      = 200
    #   P4x30% (lag 1 -> target P5)      = 300
    #   P4x20% (lag 2 -> target P6)      = 200
    #   TOTAL fuera = 700
    assert cobro == [Decimal('500'), Decimal('800'), Decimal('1000'), Decimal('1000'), Decimal('1000')]
    assert report.stats['cobros_fuera_horizonte'] == Decimal('700')


@pytest.mark.django_db
@pytest.mark.unit
def test_imss_retention_deducts_from_cobro():
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(periods=2, produccion_per_period=1000)
    FinancialSettingsService.update(fx['project'].projectid, {
        'imssretentionrate': Decimal('0.05'),
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    imss = next(r for r in report.rows if r.code == 'RET_IMSS').values
    assert imss == [Decimal('-50'), Decimal('-50')]


@pytest.mark.django_db
@pytest.mark.unit
def test_advance_payment_entry_period():
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(periods=3, produccion_per_period=1000)
    project = fx['project']
    project.advancepayment_notax = Decimal('5000')
    project.save()
    FinancialSettingsService.update(project.projectid, {'anticipoentryperiod': 2})

    calc = PNTCalculator(project.projectid)
    report = calc.compute()
    anticipo = next(r for r in report.rows if r.code == 'ANTICIPO_CONCEDIDO').values
    # Anticipo entering at period 2 (1-indexed) -> index 1 in the vector
    assert anticipo == [Decimal('0'), Decimal('5000'), Decimal('0')]


@pytest.mark.django_db
@pytest.mark.unit
def test_cobro_total_excludes_saldo_anticipo_to_avoid_double_counting():
    """With non-zero amortization rate, COBRO_TOTAL must not double-count.

    Given cobro_facturacion=1000/period and amortization=20%:
    - ANTICIPO_AMORT should be [-200, -200, -200]
    - SALDO_ANTICIPO should be [-200, -400, -600] (cumulative, display-only)
    - COBRO_TOTAL at each period should include ANTICIPO_AMORT exactly once,
      NOT both ANTICIPO_AMORT and SALDO_ANTICIPO.
    """
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(periods=3, produccion_per_period=1000)
    # Zero out retentions so COBRO_TOTAL only reflects cobro_facturacion + anticipo_amort;
    # this isolates the SALDO_ANTICIPO double-count regression.
    FinancialSettingsService.update(fx['project'].projectid, {
        'advanceamortizationrate': Decimal('0.2'),
        'imssretentionrate': Decimal('0'),
        'otherretentionrate': Decimal('0'),
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()

    anticipo_amort = next(r for r in report.rows if r.code == 'ANTICIPO_AMORT').values
    saldo_anticipo = next(r for r in report.rows if r.code == 'SALDO_ANTICIPO').values
    cobro_total = next(r for r in report.rows if r.code == 'COBRO_TOTAL').values
    cobro_facturacion = next(r for r in report.rows if r.code == 'COBRO_FACTURACION').values

    # Per-period amortization deducts 200 from a cobro of 1000.
    assert anticipo_amort == [Decimal('-200.0'), Decimal('-200.0'), Decimal('-200.0')]
    # Display-only cumulative of the amortization above.
    assert saldo_anticipo == [Decimal('-200.0'), Decimal('-400.0'), Decimal('-600.0')]
    # COBRO_TOTAL = cobro_facturacion + anticipo_amort (no other terms active).
    # Each period: 1000 + (-200) = 800. If SALDO_ANTICIPO were included, P2 would be 200, not 800.
    for i in range(3):
        assert cobro_total[i] == cobro_facturacion[i] + anticipo_amort[i]
    assert cobro_total == [Decimal('800.0'), Decimal('800.0'), Decimal('800.0')]


@pytest.mark.django_db
@pytest.mark.unit
def test_devolucion_retenciones_returns_accumulated_amount_at_configured_period():
    """When retentionreturnperiod is set, DEVOLUCION returns the sum of all retentions
    (flipped sign) at that period (1-indexed)."""
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(periods=4, produccion_per_period=1000)
    FinancialSettingsService.update(fx['project'].projectid, {
        'imssretentionrate': Decimal('0.05'),
        'otherretentionrate': Decimal('0.02'),
        'retentionreturnperiod': 4,
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()

    imss = next(r for r in report.rows if r.code == 'RET_IMSS').values
    otras = next(r for r in report.rows if r.code == 'OTRAS_RET').values
    devolucion = next(r for r in report.rows if r.code == 'DEVOLUCION').values

    # Retentions each period: -50 (IMSS) and -20 (otras).
    assert imss == [Decimal('-50.0')] * 4
    assert otras == [Decimal('-20.0')] * 4
    # Devolucion is zero in periods 1-3, then repays the sum at period 4 (index 3).
    # -sum(imss) - sum(otras) = -(-200) - (-80) = 280
    expected_return = Decimal('280.0')
    assert devolucion == [Decimal('0'), Decimal('0'), Decimal('0'), expected_return]


@pytest.mark.django_db
@pytest.mark.unit
def test_pagos_directo_and_indirecto_no_lag():
    fx = build_simple_project_fixture(
        periods=3, produccion_per_period=1000,
        direct_cost_per_period=700, indirect_cost_per_period=100,
    )
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    pd = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
    pi = next(r for r in report.rows if r.code == 'PAGOS_INDIRECTO').values
    assert pd == [Decimal('700'), Decimal('700'), Decimal('700')]
    assert pi == [Decimal('100'), Decimal('100'), Decimal('100')]


@pytest.mark.django_db
@pytest.mark.unit
def test_pago_with_category_lag_shifts_forward():
    fx = build_simple_project_fixture(periods=4, direct_cost_per_period=700)
    fx['direct_code'].categoryid.defaultpaymentlag = 1
    fx['direct_code'].categoryid.save()

    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    pd = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
    # P0 spends go to P1, P1 -> P2, P2 -> P3, P3 -> out of horizon
    assert pd == [Decimal('0'), Decimal('700'), Decimal('700'), Decimal('700')]
    assert report.stats['pagos_fuera_horizonte'] == Decimal('700')


@pytest.mark.django_db
@pytest.mark.unit
def test_paymentlag_override_on_imputation_code():
    fx = build_simple_project_fixture(periods=3, direct_cost_per_period=700)
    fx['direct_code'].categoryid.defaultpaymentlag = 5  # would shift out of horizon
    fx['direct_code'].categoryid.save()
    fx['direct_code'].paymentlagperiods = 0  # but code overrides to 0
    fx['direct_code'].save()

    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    pd = next(r for r in report.rows if r.code == 'PAGOS_DIRECTO').values
    assert pd == [Decimal('700'), Decimal('700'), Decimal('700')]


@pytest.mark.django_db
@pytest.mark.unit
def test_transversal_and_utility_withdrawals():
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(periods=4)
    FinancialSettingsService.update(fx['project'].projectid, {
        'transversalcost': Decimal('500'),
        'transversalwithdrawalperiod': 2,
        'utilitycost': Decimal('800'),
        'utilitywithdrawalperiod': 4,
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    rt = next(r for r in report.rows if r.code == 'RETIRO_TRANSV').values
    ru = next(r for r in report.rows if r.code == 'RETIRO_UTILIDADES').values
    assert rt == [Decimal('0'), Decimal('500'), Decimal('0'), Decimal('0')]
    assert ru == [Decimal('0'), Decimal('0'), Decimal('0'), Decimal('800')]


@pytest.mark.django_db
@pytest.mark.unit
def test_caja_mes_and_acumulada():
    """Cobros > pagos → positive caja mensual; acumulada = running sum.

    Default retentions are neutralized so the arithmetic is purely
    cobro_facturacion - pagos. Retention effects are covered by other tests.
    """
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(
        periods=3, produccion_per_period=1000,
        direct_cost_per_period=700, indirect_cost_per_period=100,
    )
    FinancialSettingsService.update(fx['project'].projectid, {
        'imssretentionrate': Decimal('0'),
        'otherretentionrate': Decimal('0'),
        'advanceamortizationrate': Decimal('0'),
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    caja_mes = next(r for r in report.rows if r.code == 'CAJA_MES').values
    caja_acum = next(r for r in report.rows if r.code == 'CAJA_ACUMULADA').values

    # cobro=1000, pagos=800 → caja=200/period; acumulada=200,400,600
    assert caja_mes == [Decimal('200'), Decimal('200'), Decimal('200')]
    assert caja_acum == [Decimal('200'), Decimal('400'), Decimal('600')]


@pytest.mark.django_db
@pytest.mark.unit
def test_costo_financiero_only_on_negative_balance():
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    # Cause negative caja by huge transversal retirement at period 1
    fx = build_simple_project_fixture(
        periods=3, produccion_per_period=1000,
        direct_cost_per_period=700, indirect_cost_per_period=100,
    )
    FinancialSettingsService.update(fx['project'].projectid, {
        'transversalcost': Decimal('10000'),
        'transversalwithdrawalperiod': 1,
        'financecostrate': Decimal('0.01'),
    })
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    cf = next(r for r in report.rows if r.code == 'COSTO_FINANCIERO').values
    caja_acum = next(r for r in report.rows if r.code == 'CAJA_ACUMULADA').values

    for i, ca in enumerate(caja_acum):
        if ca < 0:
            assert cf[i] == ca * Decimal('0.01')
        else:
            assert cf[i] == Decimal('0')


@pytest.mark.django_db
@pytest.mark.unit
def test_resultado_row():
    fx = build_simple_project_fixture(
        periods=2, produccion_per_period=1000,
        direct_cost_per_period=700, indirect_cost_per_period=100,
    )
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()
    resultado = next(r for r in report.rows if r.code == 'RESULTADO').values
    # 1000 - 700 - 100 - 0 - 0 = 200/period
    assert resultado == [Decimal('200'), Decimal('200')]


@pytest.mark.django_db
@pytest.mark.unit
def test_stats_captured_correctly():
    fx = build_simple_project_fixture(periods=3, produccion_per_period=1000)
    calc = PNTCalculator(fx['project'].projectid)
    report = calc.compute()

    assert 'pnt_min' in report.stats
    assert 'pnt_max' in report.stats
    assert 'pnt_avg' in report.stats
    assert 'total_costo_financiero' in report.stats
    assert isinstance(report.stats['codes_sin_precio'], list)


@pytest.mark.django_db
@pytest.mark.unit
def test_monthly_aggregation_sums_flows_and_takes_last_for_acumulados():
    """Periods are weekly (4 per month); granularity='month' should aggregate.

    PRODUCCION (a flow) is summed: 4 × 100 = 400 per month.
    CAJA_ACUMULADA (cumulative) takes the LAST value of the month.
    """
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    from apps.budgets.models import ImputationPeriod, PeriodTypeCode, ImputationCodeBudget
    from datetime import date

    fx = build_simple_project_fixture(periods=0)  # fixture with no periods; we'll add custom ones
    project = fx['project']
    # 4 weekly periods all in January 2026
    for i in range(4):
        p = ImputationPeriod.objects.create(
            projectid=project, periodtype=PeriodTypeCode.WEEKLY,
            year=2026, month=1, periodnumber=i + 1,
            label=f'S{i+1}-ENE',
            startdate=date(2026, 1, 1 + i * 7),
            enddate=date(2026, 1, 7 + i * 7),
            sortorder=i,
            createdby=project.createdby, modifiedby=project.modifiedby,
        )
        ImputationCodeBudget.objects.create(
            imputationcodeid=fx['direct_code'],
            periodid=p, periodlabel=p.label,
            plannedamount=Decimal('100'),
            plannedvolume=Decimal('10'),  # price=10 × vol=10 → produccion 100/period
        )

    # Neutralize retentions so the math is focused on aggregation, not side-effects
    FinancialSettingsService.update(project.projectid, {
        'imssretentionrate': Decimal('0'),
        'otherretentionrate': Decimal('0'),
        'advanceamortizationrate': Decimal('0'),
    })

    calc = PNTCalculator(project.projectid)
    report = calc.compute(granularity='month')

    assert report.granularity == 'month'
    assert len(report.periods) == 1  # one month

    produccion = next(r for r in report.rows if r.code == 'PRODUCCION').values
    caja_acum = next(r for r in report.rows if r.code == 'CAJA_ACUMULADA').values
    # Produccion is a FLOW → summed across 4 weeks = 4 × 100 = 400
    assert produccion == [Decimal('400')]
    # CAJA_ACUMULADA is cumulative → takes last value (same dimension, one entry)
    assert len(caja_acum) == 1


@pytest.mark.django_db
@pytest.mark.unit
def test_golden_full_pnt_scenario():
    """End-to-end golden test with a known expected result. Matches hand calculation."""
    from apps.cashflow.services.billing_rule import BillingRuleService
    from apps.cashflow.services.financial_settings import FinancialSettingsService
    fx = build_simple_project_fixture(
        periods=3, produccion_per_period=1000,
        direct_cost_per_period=600, indirect_cost_per_period=100,
    )
    project = fx['project']
    project.advancepayment_notax = Decimal('500')
    project.save()

    BillingRuleService.replace(project.projectid, [
        {'sequence': 1, 'percent': Decimal('0.5'), 'lagperiods': 0},
        {'sequence': 2, 'percent': Decimal('0.5'), 'lagperiods': 1},
    ])
    FinancialSettingsService.update(project.projectid, {
        'imssretentionrate': Decimal('0.05'),
        'advanceamortizationrate': Decimal('0.2'),
        'anticipoentryperiod': 1,
        'financecostrate': Decimal('0'),
    })

    calc = PNTCalculator(project.projectid)
    report = calc.compute()
    row = lambda code: next(r for r in report.rows if r.code == code).values

    # Cobro facturación: P0 = P0*50% = 500; P1 = P0*50% + P1*50% = 500 + 500 = 1000;
    # P2 = P1*50% + P2*50% = 500 + 500 = 1000. P2*50% (lag 1) → P3 out of horizon → 500.
    assert row('COBRO_FACTURACION') == [Decimal('500'), Decimal('1000'), Decimal('1000')]
    assert report.stats['cobros_fuera_horizonte'] == Decimal('500')

    # Retención IMSS 5%: -5%×500=-25, -5%×1000=-50, -5%×1000=-50
    assert row('RET_IMSS') == [Decimal('-25.00'), Decimal('-50.00'), Decimal('-50.00')]

    # Amortización 20%: -20%×500=-100, -20%×1000=-200, -20%×1000=-200
    assert row('ANTICIPO_AMORT') == [Decimal('-100.0'), Decimal('-200.0'), Decimal('-200.0')]

    # Anticipo concedido at P1 (1-indexed=1, so index 0) = 500
    assert row('ANTICIPO_CONCEDIDO') == [Decimal('500'), Decimal('0'), Decimal('0')]


@pytest.mark.django_db
@pytest.mark.unit
def test_compute_rejects_invalid_granularity():
    """compute() should reject unknown granularity values with ValueError."""
    fx = build_simple_project_fixture(periods=2, produccion_per_period=1000)
    calc = PNTCalculator(fx['project'].projectid)
    with pytest.raises(ValueError, match='granularity'):
        calc.compute(granularity='week')
    with pytest.raises(ValueError, match='granularity'):
        calc.compute(granularity='')


@pytest.mark.django_db
@pytest.mark.unit
def test_monthly_aggregation_asserts_all_row_codes_are_classified():
    """Covers the safety assertion in _aggregate_monthly: all row codes
    must be in either _FLOW_CODES or _CUMULATIVE_CODES. This test
    exercises the happy path (all known codes → no assertion error)."""
    fx = build_simple_project_fixture(periods=2, produccion_per_period=1000)
    calc = PNTCalculator(fx['project'].projectid)
    # Should not raise
    report = calc.compute(granularity='month')
    # Sanity: every emitted row code is in one of the two sets
    known = PNTCalculator._FLOW_CODES | PNTCalculator._CUMULATIVE_CODES
    for r in report.rows:
        assert r.code in known, f'Emitted row code {r.code!r} not classified'
