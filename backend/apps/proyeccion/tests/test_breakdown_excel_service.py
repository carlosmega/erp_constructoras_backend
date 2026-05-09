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


class TestConceptMatching:
    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_concept_by_exact_code(self, db):
        concept = BudgetConceptFactory(code="EXC-100")
        index = BreakdownExcelService._build_concept_index(concept.projectid_id)
        assert BreakdownExcelService._match_concept("EXC-100", index) == concept.conceptid

    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_concept_via_fimp_derivation(self, db):
        # `seed_cdu_carretera.py` creates concepts with codes like FIMP-S03-12
        concept = BudgetConceptFactory(code="FIMP-S03-12")
        index = BreakdownExcelService._build_concept_index(concept.projectid_id)
        # Excel may store the friendly subfamily reference
        assert BreakdownExcelService._match_concept("FIMP-S03-12", index) == concept.conceptid

    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_concept_returns_none_when_not_found(self, db):
        concept = BudgetConceptFactory(code="EXC-100")
        index = BreakdownExcelService._build_concept_index(concept.projectid_id)
        assert BreakdownExcelService._match_concept("NOPE-999", index) is None


class TestSupplyMatching:
    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_supply_by_exact_code(self, db):
        from apps.proyeccion.tests.factories import SupplyCatalogItemFactory
        supply = SupplyCatalogItemFactory(code="MAT-CEM-001")
        index = BreakdownExcelService._build_supply_index()
        result = BreakdownExcelService._match_supply("MAT-CEM-001", index)
        assert result is not None
        assert result.supplyid == supply.supplyid

    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_supply_returns_none_when_not_found(self, db):
        index = BreakdownExcelService._build_supply_index()
        assert BreakdownExcelService._match_supply("NOPE", index) is None

    @_pytest.mark.django_db
    @_pytest.mark.unit
    def test_match_supply_is_case_sensitive(self, db):
        from apps.proyeccion.tests.factories import SupplyCatalogItemFactory
        SupplyCatalogItemFactory(code="MAT-001")
        index = BreakdownExcelService._build_supply_index()
        assert BreakdownExcelService._match_supply("mat-001", index) is None


class TestExcelParsing:
    @staticmethod
    def _make_xlsx(rows, project_uuid="00000000-0000-0000-0000-000000000000"):
        """Build an in-memory xlsx file with the CDU sheet.

        rows: list of 8-tuples (CONCEPTO, CATEGORIA, INSUMO_CODIGO,
              INSUMO_DESCRIPCION, UNIDAD, RENDIMIENTO, PRECIO_UNITARIO, IMPORTE)
        """
        import io
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "CDU"
        ws.cell(row=1, column=1, value="Proyecto")
        ws.cell(row=2, column=1, value=project_uuid)
        ws.cell(row=3, column=1, value="CONCEPTO")
        ws.cell(row=3, column=2, value="CATEGORIA")
        ws.cell(row=3, column=3, value="INSUMO_CODIGO")
        ws.cell(row=3, column=4, value="INSUMO_DESCRIPCION")
        ws.cell(row=3, column=5, value="UNIDAD")
        ws.cell(row=3, column=6, value="RENDIMIENTO")
        ws.cell(row=3, column=7, value="PRECIO_UNITARIO")
        ws.cell(row=3, column=8, value="IMPORTE")
        for i, row in enumerate(rows, start=4):
            for j, val in enumerate(row, start=1):
                ws.cell(row=i, column=j, value=val)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    @_pytest.mark.unit
    def test_parse_extracts_data_rows(self):
        f = self._make_xlsx([
            ("EXC-100", "MATERIALES", "MAT-001", "Cemento", "ton", 0.5, 3000, 1500),
            ("EXC-100", "MANO_OBRA", "MO-001", "Albañil", "jornal", 1, 800, 800),
        ])
        result = BreakdownExcelService._parse_excel(f)
        assert len(result.rows) == 2
        assert result.rows[0].concepto == "EXC-100"
        assert result.rows[0].categoria == "MATERIALES"
        assert result.rows[0].rendimiento == _pytest.approx(0.5)
        assert result.uploaded_uuid == "00000000-0000-0000-0000-000000000000"

    @_pytest.mark.unit
    def test_parse_inherits_concepto_when_blank(self):
        f = self._make_xlsx([
            ("EXC-100", "MATERIALES", "MAT-001", "Cemento", "ton", 0.5, 3000, 1500),
            ("",        "MANO_OBRA",  "MO-001",  "Albañil", "jornal", 1, 800, 800),
        ])
        result = BreakdownExcelService._parse_excel(f)
        assert result.rows[1].concepto == "EXC-100"

    @_pytest.mark.unit
    def test_parse_skips_fully_empty_rows(self):
        f = self._make_xlsx([
            ("EXC-100", "MATERIALES", "MAT-001", "Cemento", "ton", 0.5, 3000, 1500),
            ("", "", "", "", "", "", "", ""),
            ("EXC-100", "MANO_OBRA",  "MO-001",  "Albañil", "jornal", 1, 800, 800),
        ])
        result = BreakdownExcelService._parse_excel(f)
        assert len(result.rows) == 2

    @_pytest.mark.unit
    def test_parse_skips_concepto_only_rows(self):
        """Filas con solo CONCEPTO (header visual) son saltadas."""
        f = self._make_xlsx([
            ("EXC-100", "", "", "", "", "", "", ""),
            ("EXC-100", "MATERIALES", "MAT-001", "Cemento", "ton", 0.5, 3000, 1500),
        ])
        result = BreakdownExcelService._parse_excel(f)
        assert len(result.rows) == 1

    @_pytest.mark.unit
    def test_parse_raises_when_sheet_missing(self):
        import io
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = "Hoja1"
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        with _pytest.raises(ValueError, match="hoja 'CDU'"):
            BreakdownExcelService._parse_excel(buf)

    @_pytest.mark.unit
    def test_parse_raises_when_only_headers(self):
        f = self._make_xlsx([])
        with _pytest.raises(ValueError, match="Excel vacío"):
            BreakdownExcelService._parse_excel(f)


class TestAnalyze:
    @_pytest.mark.django_db
    @_pytest.mark.integration
    def test_analyze_happy_path_existing_concept_and_supplies(self):
        from apps.proyeccion.tests.factories import (
            BudgetConceptFactory, SupplyCatalogItemFactory,
            EstimationProjectFactory,
        )
        user = SystemUserFactory()
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, code="EXC-100", description="Excavación")
        SupplyCatalogItemFactory(code="MAT-001", description="Cemento", unit="ton", referenceprice=3000)
        SupplyCatalogItemFactory(code="MO-001", description="Albañil", unit="jornal", referenceprice=800)

        f = TestExcelParsing._make_xlsx([
            ("EXC-100", "MATERIALES", "MAT-001", "Cemento", "ton", 0.5, 3000, 1500),
            ("EXC-100", "MANO_OBRA",  "MO-001",  "Albañil",  "jornal", 1, 800, 800),
        ], project_uuid=str(project.estimationprojectid))

        result = BreakdownExcelService.analyze(project.estimationprojectid, f, user)

        assert result.summary.concepts_count == 1
        assert result.summary.lines_count == 2
        assert result.summary.new_supplies_count == 0
        assert result.summary.errors_count == 0
        assert len(result.concepts) == 1
        assert result.concepts[0].code == "EXC-100"
        assert len(result.concepts[0].lines) == 2
        # HM/EPP preview = 3% of labor (800)
        assert result.concepts[0].hm_preview == Decimal('24.00')
        assert result.concepts[0].epp_preview == Decimal('24.00')
        # total preview = lines + HM + EPP = 1500 + 800 + 24 + 24 = 2348
        assert result.concepts[0].total_preview == Decimal('2348.00')
        assert result.project_uuid_match is True
