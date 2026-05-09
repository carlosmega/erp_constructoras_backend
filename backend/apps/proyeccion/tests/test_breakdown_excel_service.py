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


import pytest as _pytest

from apps.proyeccion.services import BreakdownExcelService


class TestCategoryMapping:
    @_pytest.mark.unit
    @_pytest.mark.parametrize("excel_cat,expected_supplytype,expected_categorycode", [
        ("MATERIALES", 0, 1),       # Material → Materials
        ("MANO_OBRA", 1, 4),         # Labor → Labor
        ("MAQUINARIA", 2, 3),        # Machinery → Machinery
        ("ACARREOS", 4, 2),          # Hauling → Hauling
        ("SUBCONTRATOS", 3, 5),      # Subcontract → Subcontracts
        ("materiales", 0, 1),        # case-insensitive
        ("Mano Obra", 1, 4),         # spaces and case
        ("  MANO_OBRA  ", 1, 4),     # trim
    ])
    def test_normalize_category_supplytype(self, excel_cat, expected_supplytype, expected_categorycode):
        result = BreakdownExcelService.normalize_category(excel_cat)
        assert result.supplytype == expected_supplytype
        assert result.category_code == expected_categorycode

    @_pytest.mark.unit
    @_pytest.mark.parametrize("rejected", ["HM", "EPP", "HERRAMIENTA_MENOR", "PPE"])
    def test_normalize_category_rejects_hm_epp(self, rejected):
        with _pytest.raises(ValueError, match="HM/EPP se calculan automáticamente"):
            BreakdownExcelService.normalize_category(rejected)

    @_pytest.mark.unit
    def test_normalize_category_rejects_unknown(self):
        with _pytest.raises(ValueError, match="Categoría no reconocida"):
            BreakdownExcelService.normalize_category("DESCONOCIDO")
