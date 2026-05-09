"""Tests for BreakdownExcelService and refactored regenerate_hm_epp."""
from decimal import Decimal

import pytest

from apps.proyeccion.services import UnitCostBreakdownService
from apps.proyeccion.models import UnitCostBreakdown, BreakdownCategoryCode
from apps.proyeccion.tests.factories import (
    BudgetConceptFactory,
    UnitCostBreakdownFactory,
)
from apps.users.tests.factories import SystemUserFactory


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_hm_epp_creates_3pct_lines_when_labor_exists():
    user = SystemUserFactory()
    concept = BudgetConceptFactory()

    UnitCostBreakdownFactory(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.LABOR,
        amount=Decimal('1000'),
        quantity=Decimal('1'),
        unitprice=Decimal('1000'),
        yieldvalue=Decimal('1'),
    )

    UnitCostBreakdownService.regenerate_hm_epp(concept.conceptid, user)

    hm = UnitCostBreakdown.objects.filter(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.MINOR_TOOLS,
    ).get()
    epp = UnitCostBreakdown.objects.filter(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.PPE,
    ).get()

    assert hm.amount == Decimal('30.00')
    assert epp.amount == Decimal('30.00')
    assert hm.quantity == Decimal('0.03')
    assert hm.unitprice == Decimal('1000.00')


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_hm_epp_skips_when_no_labor():
    user = SystemUserFactory()
    concept = BudgetConceptFactory()

    UnitCostBreakdownFactory(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.MATERIALS,
        amount=Decimal('500'),
    )

    UnitCostBreakdownService.regenerate_hm_epp(concept.conceptid, user)

    assert not UnitCostBreakdown.objects.filter(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.MINOR_TOOLS,
    ).exists()
    assert not UnitCostBreakdown.objects.filter(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.PPE,
    ).exists()


@pytest.mark.django_db
@pytest.mark.unit
def test_regenerate_hm_epp_replaces_existing_lines():
    """Si HM/EPP ya existen, regenerar los reemplaza."""
    user = SystemUserFactory()
    concept = BudgetConceptFactory()

    UnitCostBreakdownFactory(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.LABOR,
        amount=Decimal('2000'),
        quantity=Decimal('1'),
        unitprice=Decimal('2000'),
        yieldvalue=Decimal('1'),
    )
    UnitCostBreakdownFactory(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.MINOR_TOOLS,
        amount=Decimal('999'),
    )

    UnitCostBreakdownService.regenerate_hm_epp(concept.conceptid, user)

    hm_lines = UnitCostBreakdown.objects.filter(
        conceptid=concept,
        categorycode=BreakdownCategoryCode.MINOR_TOOLS,
    )
    assert hm_lines.count() == 1
    assert hm_lines.first().amount == Decimal('60.00')
