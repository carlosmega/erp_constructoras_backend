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
