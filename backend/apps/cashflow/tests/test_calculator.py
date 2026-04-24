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
