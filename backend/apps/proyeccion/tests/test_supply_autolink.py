"""Tests for auto-linking CDU breakdown lines to the supply catalog.

Covers:
- SupplyCatalogService.match_or_create_supply (the flexible match-or-create engine)
- create_breakdown / update_breakdown auto-link on save
- backfill of existing unlinked lines
"""

import pytest
from decimal import Decimal

from apps.proyeccion.models import (
    SupplyCatalogItem,
    UnitCostBreakdown,
    BreakdownCategoryCode,
    SupplyTypeCode,
)
from apps.proyeccion.services import SupplyCatalogService, UnitCostBreakdownService
from apps.proyeccion.schemas import CreateUnitCostBreakdownDto, UpdateUnitCostBreakdownDto
from .factories import (
    EstimationProjectFactory,
    BudgetConceptFactory,
    SupplyCatalogItemFactory,
    UnitCostBreakdownFactory,
)


@pytest.mark.unit
@pytest.mark.django_db
class TestMatchOrCreateSupply:
    """SupplyCatalogService.match_or_create_supply — flexible match-or-create."""

    def test_creates_new_supply_when_catalog_empty(self):
        project = EstimationProjectFactory()
        supply = SupplyCatalogService.match_or_create_supply(
            description='Diesel Excavadora',
            categorycode=BreakdownCategoryCode.MATERIALS,
            unit='LT',
            unitprice=Decimal('27.56'),
            user=project.ownerid,
        )
        assert supply is not None
        assert supply.supplytype == SupplyTypeCode.MATERIAL
        assert supply.code.startswith('MAT-')
        assert supply.referenceprice == Decimal('27.56')
        assert SupplyCatalogItem.objects.filter(supplyid=supply.supplyid).exists()

    def test_reuses_on_normalized_match_ignoring_case_accents_spaces(self):
        project = EstimationProjectFactory()
        existing = SupplyCatalogItemFactory(
            code='MAT-0001', description='Diésel Excavadora', unit='LT',
            supplytype=SupplyTypeCode.MATERIAL,
        )
        before = SupplyCatalogItem.objects.count()
        supply = SupplyCatalogService.match_or_create_supply(
            description='diesel  excavadora',  # lower, no accent, double space
            categorycode=BreakdownCategoryCode.MATERIALS,
            unit='LT', unitprice=Decimal('27.56'), user=project.ownerid,
        )
        assert supply.supplyid == existing.supplyid
        assert SupplyCatalogItem.objects.count() == before  # no new row

    def test_reuses_existing_generalization_flexible(self):
        """A generic catalog item ('Diesel') is reused for a more specific line."""
        project = EstimationProjectFactory()
        generic = SupplyCatalogItemFactory(
            code='MAT-0001', description='Diesel', unit='LT',
            supplytype=SupplyTypeCode.MATERIAL,
        )
        before = SupplyCatalogItem.objects.count()
        supply = SupplyCatalogService.match_or_create_supply(
            description='Diesel Excavadora',
            categorycode=BreakdownCategoryCode.MATERIALS,
            unit='LT', unitprice=Decimal('27.56'), user=project.ownerid,
        )
        assert supply.supplyid == generic.supplyid
        assert SupplyCatalogItem.objects.count() == before

    def test_does_not_merge_different_descriptors_same_head(self):
        """'Aceite de Motor' and 'Aceite Hidraulico' are distinct -> separate rows."""
        project = EstimationProjectFactory()
        SupplyCatalogItemFactory(
            code='MAT-0001', description='Aceite de Motor', unit='LT',
            supplytype=SupplyTypeCode.MATERIAL,
        )
        before = SupplyCatalogItem.objects.count()
        supply = SupplyCatalogService.match_or_create_supply(
            description='Aceite Hidraulico',
            categorycode=BreakdownCategoryCode.MATERIALS,
            unit='LT', unitprice=Decimal('150'), user=project.ownerid,
        )
        assert SupplyCatalogItem.objects.count() == before + 1  # created new
        assert 'hidraulico' in supply.description.lower()

    def test_type_gating_does_not_cross_supply_types(self):
        """Same text under a different category must not reuse the other type."""
        project = EstimationProjectFactory()
        material = SupplyCatalogItemFactory(
            code='MAT-0001', description='Traslado', unit='VIAJE',
            supplytype=SupplyTypeCode.MATERIAL,
        )
        supply = SupplyCatalogService.match_or_create_supply(
            description='Traslado',
            categorycode=BreakdownCategoryCode.HAULING,  # -> HAULING type
            unit='VIAJE', unitprice=Decimal('25000'), user=project.ownerid,
        )
        assert supply.supplyid != material.supplyid
        assert supply.supplytype == SupplyTypeCode.HAULING
        assert supply.code.startswith('ACA-')

    @pytest.mark.parametrize('category,expected_type,prefix', [
        (BreakdownCategoryCode.MATERIALS, SupplyTypeCode.MATERIAL, 'MAT-'),
        (BreakdownCategoryCode.HAULING, SupplyTypeCode.HAULING, 'ACA-'),
        (BreakdownCategoryCode.MACHINERY, SupplyTypeCode.MACHINERY, 'EQ-'),
        (BreakdownCategoryCode.LABOR, SupplyTypeCode.LABOR, 'MO-'),
        (BreakdownCategoryCode.SUBCONTRACTS, SupplyTypeCode.SUBCONTRACT, 'SUB-'),
    ])
    def test_category_maps_to_type_and_code_prefix(self, category, expected_type, prefix):
        project = EstimationProjectFactory()
        supply = SupplyCatalogService.match_or_create_supply(
            description=f'Insumo {prefix}',
            categorycode=category, unit='U', unitprice=Decimal('1'),
            user=project.ownerid,
        )
        assert supply.supplytype == expected_type
        assert supply.code.startswith(prefix)

    def test_skips_formula_categories_minor_tools_and_ppe(self):
        project = EstimationProjectFactory()
        for cat in (BreakdownCategoryCode.MINOR_TOOLS, BreakdownCategoryCode.PPE):
            result = SupplyCatalogService.match_or_create_supply(
                description='Herramienta Menor (3% M.O.)',
                categorycode=cat, unit='%', unitprice=Decimal('1364.69'),
                user=project.ownerid,
            )
            assert result is None
        assert SupplyCatalogItem.objects.count() == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestBreakdownAutoLink:
    """create_breakdown / update_breakdown auto-link when no explicit supplyid."""

    def test_create_breakdown_auto_links_supply(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        dto = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MATERIALS,
            description='Diesel Excavadora', unit='LT',
            quantity=Decimal('3200'), unitprice=Decimal('27.56'), yieldvalue=Decimal('1'),
        )
        line = UnitCostBreakdownService.create_breakdown(dto, project.ownerid)
        line.refresh_from_db()
        assert line.supplyid_id is not None
        assert line.supplyid.code.startswith('MAT-')
        # line description preserved (non-destructive)
        assert line.description == 'Diesel Excavadora'

    def test_create_breakdown_respects_explicit_supplyid(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        chosen = SupplyCatalogItemFactory(code='MAT-0001', description='Cemento',
                                          supplytype=SupplyTypeCode.MATERIAL)
        dto = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MATERIALS,
            description='Arena', unit='M3', quantity=Decimal('1'),
            unitprice=Decimal('100'), yieldvalue=Decimal('1'),
            supplyid=chosen.supplyid,
        )
        line = UnitCostBreakdownService.create_breakdown(dto, project.ownerid)
        line.refresh_from_db()
        assert line.supplyid_id == chosen.supplyid

    def test_create_breakdown_skips_autolink_for_formula_category(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        dto = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MINOR_TOOLS,
            description='Herramienta Menor (3% M.O.)', unit='%',
            quantity=Decimal('1'), unitprice=Decimal('50'), yieldvalue=Decimal('1'),
        )
        line = UnitCostBreakdownService.create_breakdown(dto, project.ownerid)
        line.refresh_from_db()
        assert line.supplyid_id is None

    def test_update_breakdown_auto_links_unlinked_line(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        line = UnitCostBreakdownFactory(
            conceptid=concept, supplyid=None,
            categorycode=BreakdownCategoryCode.MATERIALS, description='Diesel Excavadora',
            unit='LT', quantity=Decimal('100'), unitprice=Decimal('27'), amount=Decimal('2700'),
        )
        dto = UpdateUnitCostBreakdownDto(quantity=Decimal('120'))
        UnitCostBreakdownService.update_breakdown(line.breakdownid, dto, project.ownerid)
        line.refresh_from_db()
        assert line.supplyid_id is not None
        assert line.supplyid.code.startswith('MAT-')

    def test_update_breakdown_keeps_existing_supply(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        chosen = SupplyCatalogItemFactory(code='MAT-0001', description='Cemento',
                                          supplytype=SupplyTypeCode.MATERIAL)
        line = UnitCostBreakdownFactory(
            conceptid=concept, supplyid=chosen,
            categorycode=BreakdownCategoryCode.MATERIALS, description='Cemento gris',
            unit='KG', quantity=Decimal('1'), unitprice=Decimal('5'), amount=Decimal('5'),
        )
        dto = UpdateUnitCostBreakdownDto(quantity=Decimal('2'))
        UnitCostBreakdownService.update_breakdown(line.breakdownid, dto, project.ownerid)
        line.refresh_from_db()
        assert line.supplyid_id == chosen.supplyid  # not re-matched


@pytest.mark.unit
@pytest.mark.django_db
class TestBackfillSupplies:
    """SupplyExplosionService.backfill_supplies — remediate existing unlinked lines."""

    def test_backfill_links_unlinked_lines_and_is_idempotent(self):
        from apps.proyeccion.services import SupplyExplosionService

        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(projectid=project, quantity=Decimal('10'))
        # 2 real-insumo lines (no supply) + 1 formula line (HM)
        UnitCostBreakdownFactory(
            conceptid=concept, supplyid=None,
            categorycode=BreakdownCategoryCode.MATERIALS, description='Diesel',
            unit='LT', quantity=Decimal('100'), unitprice=Decimal('27'), amount=Decimal('2700'),
        )
        UnitCostBreakdownFactory(
            conceptid=concept, supplyid=None,
            categorycode=BreakdownCategoryCode.MACHINERY, description='Renta Excavadora',
            unit='MES', quantity=Decimal('1'), unitprice=Decimal('110000'), amount=Decimal('110000'),
        )
        formula = UnitCostBreakdownFactory(
            conceptid=concept, supplyid=None,
            categorycode=BreakdownCategoryCode.MINOR_TOOLS, description='Herramienta Menor (3% M.O.)',
            unit='%', quantity=Decimal('1'), unitprice=Decimal('50'), amount=Decimal('50'),
        )

        result = SupplyExplosionService.backfill_supplies(project.estimationprojectid, project.ownerid)

        assert result['linked'] == 2
        assert result['created'] == 2
        assert result['skipped'] == 1  # the formula line
        # real lines now linked; formula stays unlinked
        linked = UnitCostBreakdown.objects.filter(
            conceptid__projectid=project, statecode=0, supplyid__isnull=False
        ).count()
        assert linked == 2
        formula.refresh_from_db()
        assert formula.supplyid_id is None

        # consolidated explosion now non-empty
        cons = SupplyExplosionService.generate_consolidated(project.estimationprojectid, project.ownerid)
        assert len(cons) == 2

        # idempotent: re-run links/creates nothing more
        again = SupplyExplosionService.backfill_supplies(project.estimationprojectid, project.ownerid)
        assert again['linked'] == 0
        assert again['created'] == 0


@pytest.mark.contract
class TestBackfillEndpoint:
    """POST .../supply-explosion/backfill-supplies/ wiring + auth."""

    def test_backfill_endpoint_links_unlinked_lines(self, admin_auth_client, system_admin):
        project = EstimationProjectFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        concept = BudgetConceptFactory(
            projectid=project, quantity=Decimal('10'),
            createdby=system_admin, modifiedby=system_admin)
        UnitCostBreakdownFactory(
            conceptid=concept, supplyid=None,
            categorycode=BreakdownCategoryCode.MATERIALS, description='Diesel',
            unit='LT', quantity=Decimal('100'), unitprice=Decimal('27'), amount=Decimal('2700'),
        )
        resp = admin_auth_client.post(
            f'/api/proyeccion/projects/{project.estimationprojectid}/supply-explosion/backfill-supplies/'
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body['linked'] == 1
        assert body['created'] == 1
        assert body['skipped'] == 0
