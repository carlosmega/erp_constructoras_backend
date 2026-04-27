"""Tests for proyeccion services."""

import pytest
from uuid import uuid4
from decimal import Decimal

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
    UnitCostBreakdown,
    IndirectCostDetail,
    OfferAlternative,
    ExternalCostItem,
    SupplyCatalogItem,
    EquipmentYield,
    WorkPlanEntry,
    BreakdownCategoryCode,
    FamilyTemplateSet,
    FamilyTemplateItem,
)
from apps.proyeccion.services import (
    ConceptCatalogService,
    UnitCostBreakdownService,
    IndirectCostDetailService,
    OfferAlternativeService,
    ExternalCostService,
    WorkPlanService,
    SupplyCatalogService,
    EquipmentYieldService,
    ConceptPriceCatalogService,
    FamilyTemplateService,
)
from apps.proyeccion.schemas import (
    CreateConceptFamilyDto,
    UpdateConceptFamilyDto,
    CreateConceptSubfamilyDto,
    UpdateConceptSubfamilyDto,
    CreateBudgetConceptDto,
    UpdateBudgetConceptDto,
    CreateUnitCostBreakdownDto,
    UpdateUnitCostBreakdownDto,
    CreateIndirectCostDetailDto,
    UpdateIndirectCostDetailDto,
    CreateOfferAlternativeDto,
    UpdateOfferAlternativeDto,
    UpdateExternalCostItemDto,
    CreateSupplyCatalogItemDto,
    UpdateSupplyCatalogItemDto,
    CreateEquipmentYieldDto,
    UpdateEquipmentYieldDto,
    CreateWorkPlanEntryDto,
    UpdateWorkPlanEntryDto,
    SaveProjectAsTemplateDto,
    ApplyFamilyTemplateDto,
    CreateConceptPriceCatalogItemDto,
    UpdateConceptPriceCatalogItemDto,
    CreateConceptPriceReferenceDto,
)
from apps.users.tests.factories import SalespersonFactory, SystemUserFactory
from .factories import (
    ConceptPriceCatalogItemFactory,
    ConceptPriceReferenceFactory,
    EstimationProjectFactory,
    ConceptFamilyFactory,
    ConceptSubfamilyFactory,
    BudgetConceptFactory,
    UnitCostBreakdownFactory,
    IndirectCostDetailFactory,
    IndirectCostTemplateFactory,
    OfferAlternativeFactory,
    ExternalCostItemFactory,
    SupplyCatalogItemFactory,
    EquipmentYieldFactory,
    WorkPlanEntryFactory,
    FamilyTemplateSetFactory,
    FamilyTemplateItemFactory,
)
from core.exceptions import ValidationError, NotFound


# =============================================================================
# ConceptCatalogService - Families
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestConceptCatalogServiceFamilies:
    """Tests for ConceptCatalogService family methods."""

    def test_list_families(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        ConceptFamilyFactory(projectid=project)
        ConceptFamilyFactory(projectid=project)
        other_project = EstimationProjectFactory()
        ConceptFamilyFactory(projectid=other_project)

        result = ConceptCatalogService.list_families(project.estimationprojectid, user)
        assert result.count() == 2

    def test_create_family(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        dto = CreateConceptFamilyDto(
            projectid=project.estimationprojectid,
            name='Terraceria',
            code='T01',
            sortorder=1,
        )

        family = ConceptCatalogService.create_family(dto, user)

        assert family.familyid is not None
        assert family.name == 'Terraceria'
        assert family.code == 'T01'
        assert family.sortorder == 1
        assert family.createdby == user

    def test_update_family(self):
        family = ConceptFamilyFactory(name='Original', code='F01')
        user = family.projectid.ownerid
        dto = UpdateConceptFamilyDto(name='Updated Name')

        updated = ConceptCatalogService.update_family(family.familyid, dto, user)

        assert updated.name == 'Updated Name'
        assert updated.code == family.code  # unchanged
        assert updated.modifiedby == user

    def test_update_family_not_found(self):
        user = SalespersonFactory()
        dto = UpdateConceptFamilyDto(name='Nope')

        with pytest.raises(NotFound):
            ConceptCatalogService.update_family(uuid4(), dto, user)

    def test_delete_family(self):
        family = ConceptFamilyFactory()
        user = family.projectid.ownerid

        deleted = ConceptCatalogService.delete_family(family.familyid, user)

        assert deleted.statecode == 1
        assert deleted.modifiedby == user

    def test_delete_family_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            ConceptCatalogService.delete_family(uuid4(), user)


# =============================================================================
# ConceptCatalogService - Subfamilies
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestConceptCatalogServiceSubfamilies:
    """Tests for ConceptCatalogService subfamily methods."""

    def test_list_subfamilies(self):
        family = ConceptFamilyFactory()
        ConceptSubfamilyFactory(familyid=family, projectid=family.projectid)
        ConceptSubfamilyFactory(familyid=family, projectid=family.projectid)

        result = ConceptCatalogService.list_subfamilies(family.familyid, family.projectid.ownerid)
        assert result.count() == 2

    def test_create_subfamily(self):
        family = ConceptFamilyFactory()
        user = family.projectid.ownerid
        dto = CreateConceptSubfamilyDto(
            familyid=family.familyid,
            projectid=family.projectid_id,
            name='Excavation',
            code='EX01',
            sortorder=1,
        )

        subfamily = ConceptCatalogService.create_subfamily(dto, user)

        assert subfamily.subfamilyid is not None
        assert subfamily.name == 'Excavation'
        assert subfamily.code == 'EX01'
        assert subfamily.familyid == family

    def test_create_subfamily_resolves_projectid_from_family(self):
        """When projectid is falsy (empty UUID sentinel), service resolves from parent family."""
        family = ConceptFamilyFactory()
        user = family.projectid.ownerid

        # The service checks `if not dto.projectid` -- we test it directly
        # by calling the service with a manually constructed dto-like object
        class FakeDto:
            familyid = family.familyid
            projectid = None
            name = 'Test SF'
            code = 'TSF1'
            sortorder = 0

        subfamily = ConceptCatalogService.create_subfamily(FakeDto(), user)

        assert subfamily.projectid == family.projectid

    def test_create_subfamily_family_not_found_for_projectid_resolution(self):
        """When projectid is falsy and family doesn't exist, raises NotFound."""
        user = SalespersonFactory()
        fake_family_id = uuid4()

        class FakeDto:
            familyid = fake_family_id
            projectid = None
            name = 'Missing'
            code = 'XX'
            sortorder = 0

        with pytest.raises(NotFound):
            ConceptCatalogService.create_subfamily(FakeDto(), user)

    def test_update_subfamily(self):
        subfamily = ConceptSubfamilyFactory(name='Original')
        user = subfamily.projectid.ownerid
        dto = UpdateConceptSubfamilyDto(name='Updated')

        updated = ConceptCatalogService.update_subfamily(subfamily.subfamilyid, dto, user)

        assert updated.name == 'Updated'
        assert updated.modifiedby == user

    def test_update_subfamily_not_found(self):
        user = SalespersonFactory()
        dto = UpdateConceptSubfamilyDto(name='Nope')

        with pytest.raises(NotFound):
            ConceptCatalogService.update_subfamily(uuid4(), dto, user)


# =============================================================================
# ConceptCatalogService - Concepts
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestConceptCatalogServiceConcepts:
    """Tests for ConceptCatalogService concept methods."""

    def test_list_concepts(self):
        project = EstimationProjectFactory()
        subfamily = ConceptSubfamilyFactory(
            familyid__projectid=project,
            projectid=project,
        )
        BudgetConceptFactory(subfamilyid=subfamily, projectid=project)
        BudgetConceptFactory(subfamilyid=subfamily, projectid=project)

        result = ConceptCatalogService.list_concepts(
            project.estimationprojectid, project.ownerid,
        )
        assert result.count() == 2

    def test_list_concepts_filter_by_subfamily(self):
        project = EstimationProjectFactory()
        family = ConceptFamilyFactory(projectid=project)
        sf1 = ConceptSubfamilyFactory(familyid=family, projectid=project)
        sf2 = ConceptSubfamilyFactory(familyid=family, projectid=project)
        BudgetConceptFactory(subfamilyid=sf1, projectid=project)
        BudgetConceptFactory(subfamilyid=sf1, projectid=project)
        BudgetConceptFactory(subfamilyid=sf2, projectid=project)

        result = ConceptCatalogService.list_concepts(
            project.estimationprojectid, project.ownerid,
            subfamilyid=sf1.subfamilyid,
        )
        assert result.count() == 2

    def test_get_concept(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid

        result = ConceptCatalogService.get_concept(concept.conceptid, user)

        assert result.conceptid == concept.conceptid
        assert result.description == concept.description

    def test_get_concept_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            ConceptCatalogService.get_concept(uuid4(), user)

    def test_create_concept(self):
        subfamily = ConceptSubfamilyFactory()
        project = subfamily.projectid
        user = project.ownerid

        dto = CreateBudgetConceptDto(
            projectid=project.estimationprojectid,
            subfamilyid=subfamily.subfamilyid,
            description='Excavacion a cielo abierto',
            unit='m3',
            quantity=Decimal('500'),
        )

        concept = ConceptCatalogService.create_concept(dto, user)

        assert concept.conceptid is not None
        assert concept.description == 'Excavacion a cielo abierto'
        assert concept.unit == 'm3'
        assert concept.quantity == Decimal('500')
        assert concept.sequencenumber == 1
        assert concept.code.startswith('F')
        assert concept.directunitcost == Decimal('0')

    def test_create_concept_auto_increments_sequence(self):
        subfamily = ConceptSubfamilyFactory()
        project = subfamily.projectid
        user = project.ownerid

        dto1 = CreateBudgetConceptDto(
            projectid=project.estimationprojectid,
            subfamilyid=subfamily.subfamilyid,
            description='Concept A',
            unit='m2',
            quantity=Decimal('10'),
        )
        dto2 = CreateBudgetConceptDto(
            projectid=project.estimationprojectid,
            subfamilyid=subfamily.subfamilyid,
            description='Concept B',
            unit='m2',
            quantity=Decimal('20'),
        )

        c1 = ConceptCatalogService.create_concept(dto1, user)
        c2 = ConceptCatalogService.create_concept(dto2, user)

        assert c2.sequencenumber == c1.sequencenumber + 1

    def test_create_concept_subfamily_not_found(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = CreateBudgetConceptDto(
            projectid=project.estimationprojectid,
            subfamilyid=uuid4(),
            description='Bad',
            unit='m2',
            quantity=Decimal('1'),
        )

        with pytest.raises(ValidationError):
            ConceptCatalogService.create_concept(dto, user)

    def test_update_concept(self):
        concept = BudgetConceptFactory(description='Original')
        user = concept.projectid.ownerid

        dto = UpdateBudgetConceptDto(description='Updated', quantity=Decimal('200'))
        updated = ConceptCatalogService.update_concept(concept.conceptid, dto, user)

        assert updated.description == 'Updated'
        assert updated.quantity == Decimal('200')

    def test_update_concept_not_found(self):
        user = SalespersonFactory()
        dto = UpdateBudgetConceptDto(description='Nope')

        with pytest.raises(NotFound):
            ConceptCatalogService.update_concept(uuid4(), dto, user)

    def test_delete_concept(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid

        deleted = ConceptCatalogService.delete_concept(concept.conceptid, user)

        assert deleted.statecode == 1

    def test_delete_concept_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            ConceptCatalogService.delete_concept(uuid4(), user)

    def test_recalculate_concept(self):
        concept = BudgetConceptFactory(quantity=Decimal('10'))
        user = concept.projectid.ownerid

        UnitCostBreakdownFactory(
            conceptid=concept,
            quantity=Decimal('2'), unitprice=Decimal('50'), yieldvalue=Decimal('1'),
            amount=Decimal('100'),
        )
        UnitCostBreakdownFactory(
            conceptid=concept,
            quantity=Decimal('3'), unitprice=Decimal('100'), yieldvalue=Decimal('1'),
            amount=Decimal('300'),
        )

        result = ConceptCatalogService.recalculate_concept(concept.conceptid, user)

        assert result.directunitcost == Decimal('400')
        assert result.unitprice == Decimal('400')
        assert result.totalamount == Decimal('4000')


# =============================================================================
# UnitCostBreakdownService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestUnitCostBreakdownService:
    """Tests for UnitCostBreakdownService."""

    def test_list_breakdowns(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid
        UnitCostBreakdownFactory(conceptid=concept)
        UnitCostBreakdownFactory(conceptid=concept)

        result = UnitCostBreakdownService.list_breakdowns(concept.conceptid, user)
        assert result.count() == 2

    def test_create_breakdown(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid

        dto = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MATERIALS,
            description='Cemento Portland',
            unit='ton',
            quantity=Decimal('5'),
            unitprice=Decimal('2000'),
            yieldvalue=Decimal('1.05'),
        )

        breakdown = UnitCostBreakdownService.create_breakdown(dto, user)

        assert breakdown.breakdownid is not None
        assert breakdown.description == 'Cemento Portland'
        assert breakdown.linenumber == 1
        assert breakdown.amount == Decimal('5') * Decimal('2000') * Decimal('1.05')

    def test_create_breakdown_auto_increments_linenumber(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid

        dto1 = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MATERIALS,
            description='Item A',
            unit='kg',
        )
        dto2 = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=BreakdownCategoryCode.MATERIALS,
            description='Item B',
            unit='kg',
        )

        b1 = UnitCostBreakdownService.create_breakdown(dto1, user)
        b2 = UnitCostBreakdownService.create_breakdown(dto2, user)

        assert b1.linenumber == 1
        assert b2.linenumber == 2

    def test_create_breakdown_invalid_category(self):
        concept = BudgetConceptFactory()
        user = concept.projectid.ownerid

        dto = CreateUnitCostBreakdownDto(
            conceptid=concept.conceptid,
            categorycode=999,
            description='Invalid',
            unit='kg',
        )

        with pytest.raises(ValidationError, match='Invalid category code'):
            UnitCostBreakdownService.create_breakdown(dto, user)

    def test_update_breakdown(self):
        breakdown = UnitCostBreakdownFactory(
            quantity=Decimal('10'), unitprice=Decimal('50'), yieldvalue=Decimal('1'),
        )
        user = breakdown.conceptid.projectid.ownerid

        dto = UpdateUnitCostBreakdownDto(
            quantity=Decimal('20'),
            unitprice=Decimal('100'),
        )

        updated = UnitCostBreakdownService.update_breakdown(breakdown.breakdownid, dto, user)

        assert updated.quantity == Decimal('20')
        assert updated.unitprice == Decimal('100')
        assert updated.amount == Decimal('20') * Decimal('100') * Decimal('1')

    def test_update_breakdown_not_found(self):
        user = SalespersonFactory()
        dto = UpdateUnitCostBreakdownDto(quantity=Decimal('1'))

        with pytest.raises(NotFound):
            UnitCostBreakdownService.update_breakdown(uuid4(), dto, user)

    def test_delete_breakdown(self):
        breakdown = UnitCostBreakdownFactory()
        user = breakdown.conceptid.projectid.ownerid

        deleted = UnitCostBreakdownService.delete_breakdown(breakdown.breakdownid, user)

        assert deleted.statecode == 1

    def test_delete_breakdown_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            UnitCostBreakdownService.delete_breakdown(uuid4(), user)

    def test_auto_generate_hm_epp(self):
        concept = BudgetConceptFactory()
        UnitCostBreakdownFactory(
            conceptid=concept,
            categorycode=BreakdownCategoryCode.LABOR,
            amount=Decimal('1000'),
        )
        user = concept.projectid.ownerid

        created = UnitCostBreakdownService.auto_generate_hm_epp(concept.conceptid, user)

        assert len(created) == 2
        expected_amount = Decimal('1000') * Decimal('0.03')
        assert created[0].categorycode == BreakdownCategoryCode.MINOR_TOOLS
        assert created[0].amount == expected_amount
        assert created[1].categorycode == BreakdownCategoryCode.PPE
        assert created[1].amount == expected_amount

    def test_auto_generate_hm_epp_no_labor(self):
        concept = BudgetConceptFactory()
        UnitCostBreakdownFactory(
            conceptid=concept,
            categorycode=BreakdownCategoryCode.MATERIALS,
            amount=Decimal('1000'),
        )
        user = concept.projectid.ownerid

        created = UnitCostBreakdownService.auto_generate_hm_epp(concept.conceptid, user)

        assert len(created) == 0


# =============================================================================
# IndirectCostDetailService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestIndirectCostDetailService:
    """Tests for IndirectCostDetailService."""

    def test_list_details(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        IndirectCostDetailFactory(projectid=project, categorycode='C1')
        IndirectCostDetailFactory(projectid=project, categorycode='C2')

        result = IndirectCostDetailService.list_details(
            project.estimationprojectid, user,
        )
        assert result.count() == 2

    def test_list_details_filter_by_category(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        IndirectCostDetailFactory(projectid=project, categorycode='C1')
        IndirectCostDetailFactory(projectid=project, categorycode='C1')
        IndirectCostDetailFactory(projectid=project, categorycode='C2')

        result = IndirectCostDetailService.list_details(
            project.estimationprojectid, user, categorycode='C1',
        )
        assert result.count() == 2

    def test_create_detail(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = CreateIndirectCostDetailDto(
            projectid=project.estimationprojectid,
            categorycode='C1',
            description='Superintendente de obra',
            monthlycost=Decimal('45000'),
            units=Decimal('1'),
            months=Decimal('12'),
        )

        detail = IndirectCostDetailService.create_detail(dto, user)

        assert detail.indirectcostid is not None
        assert detail.description == 'Superintendente de obra'
        assert detail.linenumber == 1
        assert detail.amount == Decimal('45000') * Decimal('1') * Decimal('12')

    def test_create_detail_auto_increments_linenumber(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto1 = CreateIndirectCostDetailDto(
            projectid=project.estimationprojectid,
            categorycode='C1',
            description='Item 1',
            monthlycost=Decimal('1000'),
            months=Decimal('1'),
        )
        dto2 = CreateIndirectCostDetailDto(
            projectid=project.estimationprojectid,
            categorycode='C1',
            description='Item 2',
            monthlycost=Decimal('2000'),
            months=Decimal('1'),
        )

        d1 = IndirectCostDetailService.create_detail(dto1, user)
        d2 = IndirectCostDetailService.create_detail(dto2, user)

        assert d1.linenumber == 1
        assert d2.linenumber == 2

    def test_update_detail(self):
        detail = IndirectCostDetailFactory(
            monthlycost=Decimal('5000'), units=Decimal('1'), months=Decimal('6'),
        )
        user = detail.projectid.ownerid

        dto = UpdateIndirectCostDetailDto(
            monthlycost=Decimal('8000'),
            months=Decimal('10'),
        )

        updated = IndirectCostDetailService.update_detail(detail.indirectcostid, dto, user)

        assert updated.monthlycost == Decimal('8000')
        assert updated.months == Decimal('10')
        assert updated.amount == Decimal('8000') * Decimal('1') * Decimal('10')

    def test_update_detail_not_found(self):
        user = SalespersonFactory()
        dto = UpdateIndirectCostDetailDto(description='Nope')

        with pytest.raises(NotFound):
            IndirectCostDetailService.update_detail(uuid4(), dto, user)

    def test_delete_detail(self):
        detail = IndirectCostDetailFactory()
        user = detail.projectid.ownerid

        deleted = IndirectCostDetailService.delete_detail(detail.indirectcostid, user)

        assert deleted.statecode == 1

    def test_delete_detail_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            IndirectCostDetailService.delete_detail(uuid4(), user)

    def test_get_total(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        IndirectCostDetailFactory(projectid=project, amount=Decimal('10000'))
        IndirectCostDetailFactory(projectid=project, amount=Decimal('20000'))
        IndirectCostDetailFactory(projectid=project, amount=Decimal('5000'), statecode=1)

        total = IndirectCostDetailService.get_total(project.estimationprojectid, user)

        assert total == Decimal('30000')

    def test_get_total_empty(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        total = IndirectCostDetailService.get_total(project.estimationprojectid, user)

        assert total == Decimal('0')

    def test_apply_template(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        IndirectCostTemplateFactory(
            projectsize=1, categorycode='C1',
            description='Template item 1',
            monthlycost=Decimal('5000'), units=Decimal('1'), months=Decimal('6'),
        )
        IndirectCostTemplateFactory(
            projectsize=1, categorycode='C2',
            description='Template item 2',
            monthlycost=Decimal('3000'), units=Decimal('2'), months=Decimal('6'),
        )

        created = IndirectCostDetailService.apply_template(
            project.estimationprojectid, 1, user,
        )

        assert len(created) == 2
        assert created[0].categorycode == 'C1'
        assert created[0].amount == Decimal('5000') * Decimal('1') * Decimal('6')
        assert created[1].categorycode == 'C2'

    def test_apply_template_invalid_size(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        with pytest.raises(ValidationError, match='Invalid project size'):
            IndirectCostDetailService.apply_template(
                project.estimationprojectid, 99, user,
            )

    def test_apply_template_no_templates_found(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        with pytest.raises(ValidationError, match='No templates found'):
            IndirectCostDetailService.apply_template(
                project.estimationprojectid, 0, user,
            )

    def test_prorate_to_concepts(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        subfamily = ConceptSubfamilyFactory(
            familyid__projectid=project, projectid=project,
        )

        c1 = BudgetConceptFactory(
            subfamilyid=subfamily, projectid=project,
            directunitcost=Decimal('100'), quantity=Decimal('10'),
        )
        c2 = BudgetConceptFactory(
            subfamilyid=subfamily, projectid=project,
            directunitcost=Decimal('200'), quantity=Decimal('5'),
        )

        IndirectCostDetailFactory(projectid=project, amount=Decimal('2000'))

        updated = IndirectCostDetailService.prorate_to_concepts(
            project.estimationprojectid, user,
        )

        assert len(updated) == 2
        # total_direct = 100*10 + 200*5 = 2000
        # c1 proportion = 1000/2000 = 0.5, c1_indirect = 2000*0.5 = 1000, per unit = 100
        # c2 proportion = 1000/2000 = 0.5, c2_indirect = 2000*0.5 = 1000, per unit = 200
        c1.refresh_from_db()
        c2.refresh_from_db()
        assert c1.indirectunitcost == Decimal('100')
        assert c2.indirectunitcost == Decimal('200')


# =============================================================================
# OfferAlternativeService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestOfferAlternativeService:
    """Tests for OfferAlternativeService."""

    def test_list_alternatives(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        OfferAlternativeFactory(projectid=project)
        OfferAlternativeFactory(projectid=project)

        result = OfferAlternativeService.list_alternatives(
            project.estimationprojectid, user,
        )
        assert result.count() == 2

    def test_list_alternatives_excludes_soft_deleted(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        active = OfferAlternativeFactory(projectid=project)
        to_delete = OfferAlternativeFactory(projectid=project)
        OfferAlternativeService.delete_alternative(to_delete.alternativeid, user)

        result = OfferAlternativeService.list_alternatives(
            project.estimationprojectid, user,
        )
        assert result.count() == 1
        assert result.first().alternativeid == active.alternativeid

    def test_create_alternative(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = CreateOfferAlternativeDto(
            projectid=project.estimationprojectid,
            name='Option A',
            transversalpercent=Decimal('5'),
            profitpercent=Decimal('10'),
        )

        alt = OfferAlternativeService.create_alternative(dto, user)

        assert alt.alternativeid is not None
        assert alt.name == 'Option A'
        assert alt.alternativenumber == 1
        expected_coeff = Decimal('1') + Decimal('5') / Decimal('100') + Decimal('10') / Decimal('100')
        assert alt.coefficient == expected_coeff

    def test_create_alternative_max_4(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        for i in range(4):
            OfferAlternativeFactory(projectid=project, alternativenumber=i + 1)

        dto = CreateOfferAlternativeDto(
            projectid=project.estimationprojectid,
            name='Fifth',
        )

        with pytest.raises(ValidationError, match='Maximum 4'):
            OfferAlternativeService.create_alternative(dto, user)

    def test_update_alternative(self):
        alt = OfferAlternativeFactory(
            transversalpercent=Decimal('5'),
            profitpercent=Decimal('10'),
            directcosttotal=Decimal('100000'),
            indirectcosttotal=Decimal('30000'),
        )
        user = alt.projectid.ownerid

        dto = UpdateOfferAlternativeDto(
            profitpercent=Decimal('15'),
        )

        updated = OfferAlternativeService.update_alternative(alt.alternativeid, dto, user)

        expected_coeff = Decimal('1') + Decimal('5') / Decimal('100') + Decimal('15') / Decimal('100')
        assert updated.coefficient == expected_coeff
        assert updated.constructioncost == Decimal('130000')

    def test_update_alternative_not_found(self):
        user = SalespersonFactory()
        dto = UpdateOfferAlternativeDto(name='Nope')

        with pytest.raises(NotFound):
            OfferAlternativeService.update_alternative(uuid4(), dto, user)

    def test_delete_alternative(self):
        alt = OfferAlternativeFactory()
        user = alt.projectid.ownerid

        deleted = OfferAlternativeService.delete_alternative(alt.alternativeid, user)

        assert deleted.statecode == 1

    def test_delete_alternative_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            OfferAlternativeService.delete_alternative(uuid4(), user)

    def test_choose_alternative(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        alt1 = OfferAlternativeFactory(projectid=project, ischosen=True)
        alt2 = OfferAlternativeFactory(projectid=project, ischosen=False)

        result = OfferAlternativeService.choose_alternative(alt2.alternativeid, user)

        assert result.ischosen is True
        alt1.refresh_from_db()
        assert alt1.ischosen is False

    def test_choose_alternative_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            OfferAlternativeService.choose_alternative(uuid4(), user)


# =============================================================================
# ExternalCostService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestExternalCostService:
    """Tests for ExternalCostService."""

    def test_list_costs(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        ExternalCostItemFactory(projectid=project)
        ExternalCostItemFactory(projectid=project)

        result = ExternalCostService.list_costs(project.estimationprojectid, user)
        assert result.count() == 2

    def test_initialize_checklist(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        items = ExternalCostService.initialize_checklist(
            project.estimationprojectid, user,
        )

        assert len(items) == 20
        assert items[0].itemname == 'Fianza de sostenimiento de oferta'

    def test_initialize_checklist_already_exists(self):
        project = EstimationProjectFactory()
        user = project.ownerid
        ExternalCostItemFactory(projectid=project)

        with pytest.raises(ValidationError, match='already initialized'):
            ExternalCostService.initialize_checklist(
                project.estimationprojectid, user,
            )

    def test_update_cost(self):
        item = ExternalCostItemFactory(amount=Decimal('0'))
        user = SalespersonFactory()

        dto = UpdateExternalCostItemDto(
            applies=1,
            amount=Decimal('50000'),
        )

        updated = ExternalCostService.update_cost(item.externalcostid, dto, user)

        assert updated.applies == 1
        assert updated.amount == Decimal('50000')

    def test_update_cost_not_found(self):
        user = SalespersonFactory()
        dto = UpdateExternalCostItemDto(applies=1)

        with pytest.raises(NotFound):
            ExternalCostService.update_cost(uuid4(), dto, user)


# =============================================================================
# WorkPlanService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestWorkPlanService:
    """Tests for WorkPlanService."""

    def test_list_entries(self):
        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(
            subfamilyid__familyid__projectid=project,
            projectid=project,
        )
        user = project.ownerid
        WorkPlanEntryFactory(conceptid=concept, projectid=project, periodnumber=1)
        WorkPlanEntryFactory(conceptid=concept, projectid=project, periodnumber=2)

        result = WorkPlanService.list_entries(project.estimationprojectid, user)
        assert result.count() == 2

    def test_list_entries_filter_by_concept(self):
        project = EstimationProjectFactory()
        subfamily = ConceptSubfamilyFactory(
            familyid__projectid=project, projectid=project,
        )
        c1 = BudgetConceptFactory(subfamilyid=subfamily, projectid=project)
        c2 = BudgetConceptFactory(subfamilyid=subfamily, projectid=project)
        user = project.ownerid

        WorkPlanEntryFactory(conceptid=c1, projectid=project, periodnumber=1)
        WorkPlanEntryFactory(conceptid=c2, projectid=project, periodnumber=1)

        result = WorkPlanService.list_entries(
            project.estimationprojectid, user, conceptid=c1.conceptid,
        )
        assert result.count() == 1

    def test_create_entry(self):
        concept = BudgetConceptFactory(unitprice=Decimal('150'))
        user = concept.projectid.ownerid

        dto = CreateWorkPlanEntryDto(
            conceptid=concept.conceptid,
            projectid=concept.projectid_id,
            periodnumber=1,
            periodlabel='S1',
            distributedquantity=Decimal('25'),
        )

        entry = WorkPlanService.create_entry(dto, user)

        assert entry.workplanentryid is not None
        assert entry.distributedquantity == Decimal('25')
        assert entry.distributedamount == Decimal('25') * Decimal('150')

    def test_create_entry_concept_not_found(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = CreateWorkPlanEntryDto(
            conceptid=uuid4(),
            projectid=project.estimationprojectid,
            periodnumber=1,
            periodlabel='S1',
            distributedquantity=Decimal('10'),
        )

        with pytest.raises(NotFound):
            WorkPlanService.create_entry(dto, user)

    def test_update_entry(self):
        concept = BudgetConceptFactory(unitprice=Decimal('200'))
        entry = WorkPlanEntryFactory(
            conceptid=concept, projectid=concept.projectid,
            distributedquantity=Decimal('10'),
        )
        user = concept.projectid.ownerid

        dto = UpdateWorkPlanEntryDto(distributedquantity=Decimal('50'))
        updated = WorkPlanService.update_entry(entry.workplanentryid, dto, user)

        assert updated.distributedquantity == Decimal('50')
        assert updated.distributedamount == Decimal('50') * Decimal('200')

    def test_update_entry_not_found(self):
        user = SalespersonFactory()
        dto = UpdateWorkPlanEntryDto(distributedquantity=Decimal('1'))

        with pytest.raises(NotFound):
            WorkPlanService.update_entry(uuid4(), dto, user)

    def test_delete_entry(self):
        entry = WorkPlanEntryFactory()
        user = entry.projectid.ownerid

        WorkPlanService.delete_entry(entry.workplanentryid, user)

        assert not WorkPlanEntry.objects.filter(
            workplanentryid=entry.workplanentryid,
        ).exists()

    def test_delete_entry_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            WorkPlanService.delete_entry(uuid4(), user)

    def test_planned_and_actual_coexist(self):
        """PLANNED and ACTUAL entries for same (concept, period) must both be allowed."""
        from apps.proyeccion.models import WorkPlanEntryType

        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(
            projectid=project, quantity=Decimal('100'), unitprice=Decimal('10')
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1,
            entrytype=WorkPlanEntryType.PLANNED, distributedquantity=Decimal('40'),
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1,
            entrytype=WorkPlanEntryType.ACTUAL, distributedquantity=Decimal('30'),
        )
        user = SalespersonFactory()
        assert WorkPlanService.list_entries(
            project.estimationprojectid, user, entrytype=WorkPlanEntryType.PLANNED
        ).count() == 1
        assert WorkPlanService.list_entries(
            project.estimationprojectid, user, entrytype=WorkPlanEntryType.ACTUAL
        ).count() == 1

    def test_get_matrix_structure(self):
        """get_matrix returns tree with family → subfamily → concept + planned/actual blocks."""
        from apps.proyeccion.models import WorkPlanEntryType

        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(
            projectid=project, quantity=Decimal('100'), unitprice=Decimal('10')
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='S1',
            entrytype=WorkPlanEntryType.PLANNED, distributedquantity=Decimal('50'),
            distributedamount=Decimal('500'),
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1, periodlabel='S1',
            entrytype=WorkPlanEntryType.ACTUAL, distributedquantity=Decimal('25'),
            distributedamount=Decimal('250'),
        )
        user = SalespersonFactory()

        matrix = WorkPlanService.get_matrix(project.estimationprojectid, user)
        assert len(matrix['periods']) == 1
        assert len(matrix['families']) == 1
        fam = matrix['families'][0]
        row = fam['subfamilies'][0]['concepts'][0]
        assert row['planned']['total_qty'] == Decimal('50')
        assert row['actual']['total_qty'] == Decimal('25')
        assert fam['totals']['planned_amount'] == Decimal('500')
        assert fam['totals']['actual_amount'] == Decimal('250')
        # Per-period amount = qty * unitprice (SUMPRODUCT)
        assert fam['totals']['planned_by_period_amount']['1'] == Decimal('500')
        assert fam['totals']['actual_by_period_amount']['1'] == Decimal('250')

    def test_get_summary_percentages(self):
        from apps.proyeccion.models import WorkPlanEntryType

        project = EstimationProjectFactory()
        concept = BudgetConceptFactory(
            projectid=project,
            quantity=Decimal('100'),
            unitprice=Decimal('10'),
            totalamount=Decimal('1000'),
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1,
            entrytype=WorkPlanEntryType.PLANNED, distributedquantity=Decimal('80'),
            distributedamount=Decimal('800'),
        )
        WorkPlanEntryFactory(
            conceptid=concept, projectid=project, periodnumber=1,
            entrytype=WorkPlanEntryType.ACTUAL, distributedquantity=Decimal('40'),
            distributedamount=Decimal('400'),
        )
        user = SalespersonFactory()
        summary = WorkPlanService.get_summary(project.estimationprojectid, user)
        assert len(summary['families']) == 1
        fam = summary['families'][0]
        assert fam['percent_planned'] == pytest.approx(0.8)
        assert fam['percent_actual'] == pytest.approx(0.4)


# =============================================================================
# SupplyCatalogService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestSupplyCatalogService:
    """Tests for SupplyCatalogService."""

    def test_list_items(self):
        user = SalespersonFactory()
        SupplyCatalogItemFactory()
        SupplyCatalogItemFactory()
        SupplyCatalogItemFactory(statecode=1)  # inactive

        result = SupplyCatalogService.list_items(user)
        assert result.count() == 2

    def test_list_items_filter_by_type(self):
        user = SalespersonFactory()
        SupplyCatalogItemFactory(supplytype=0)
        SupplyCatalogItemFactory(supplytype=0)
        SupplyCatalogItemFactory(supplytype=1)

        result = SupplyCatalogService.list_items(user, supplytype=0)
        assert result.count() == 2

    def test_list_items_search(self):
        user = SalespersonFactory()
        SupplyCatalogItemFactory(description='Cemento Portland')
        SupplyCatalogItemFactory(description='Arena lavada')
        SupplyCatalogItemFactory(description='Cemento blanco')

        result = SupplyCatalogService.list_items(user, search='cemento')
        assert result.count() == 2

    def test_create_item(self):
        user = SalespersonFactory()

        dto = CreateSupplyCatalogItemDto(
            code='MAT-001',
            description='Varilla corrugada 3/8',
            unit='kg',
            supplytype=0,
            referenceprice=Decimal('18.50'),
        )

        item = SupplyCatalogService.create_item(dto, user)

        assert item.supplyid is not None
        assert item.code == 'MAT-001'
        assert item.description == 'Varilla corrugada 3/8'
        assert item.referenceprice == Decimal('18.50')
        assert item.createdby == user

    def test_update_item(self):
        item = SupplyCatalogItemFactory(description='Original')
        user = SalespersonFactory()

        dto = UpdateSupplyCatalogItemDto(description='Updated')
        updated = SupplyCatalogService.update_item(item.supplyid, dto, user)

        assert updated.description == 'Updated'
        assert updated.modifiedby == user

    def test_update_item_not_found(self):
        user = SalespersonFactory()
        dto = UpdateSupplyCatalogItemDto(description='Nope')

        with pytest.raises(NotFound):
            SupplyCatalogService.update_item(uuid4(), dto, user)

    def test_delete_item(self):
        item = SupplyCatalogItemFactory()
        user = SalespersonFactory()

        deleted = SupplyCatalogService.delete_item(item.supplyid, user)

        assert deleted.statecode == 1

    def test_delete_item_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            SupplyCatalogService.delete_item(uuid4(), user)


# =============================================================================
# EquipmentYieldService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestEquipmentYieldService:
    """Tests for EquipmentYieldService."""

    def test_list_yields(self):
        user = SalespersonFactory()
        EquipmentYieldFactory()
        EquipmentYieldFactory()
        EquipmentYieldFactory(statecode=1)  # inactive

        result = EquipmentYieldService.list_yields(user)
        assert result.count() == 2

    def test_list_yields_filter_by_category(self):
        user = SalespersonFactory()
        EquipmentYieldFactory(category='Excavation')
        EquipmentYieldFactory(category='Excavation')
        EquipmentYieldFactory(category='Hauling')

        result = EquipmentYieldService.list_yields(user, category='Excavation')
        assert result.count() == 2

    def test_create_yield(self):
        user = SalespersonFactory()

        dto = CreateEquipmentYieldDto(
            category='Excavation',
            description='CAT 320 Excavator',
            monthlycost=Decimal('80000'),
            numberofequipment=2,
            theoreticalyield=Decimal('120'),
            effectivehours=Decimal('8'),
            fuelconsumption=Decimal('20'),
            effectivedays=Decimal('22'),
            trafficfactor=Decimal('0.85'),
        )

        equip = EquipmentYieldService.create_yield(dto, user)

        assert equip.equipmentyieldid is not None
        assert equip.realyield == Decimal('120') * Decimal('0.85')
        assert equip.dailyfuelconsumption == Decimal('20') * Decimal('8')
        expected_monthly_cubic = Decimal('120') * Decimal('0.85') * Decimal('8') * Decimal('22') * 2
        assert equip.monthlycubicmeters == expected_monthly_cubic
        assert equip.costpercubicmeter == Decimal('80000') / expected_monthly_cubic

    def test_create_yield_zero_monthly_cubic(self):
        user = SalespersonFactory()

        dto = CreateEquipmentYieldDto(
            category='Test',
            description='Zero yield equipment',
            monthlycost=Decimal('50000'),
            theoreticalyield=Decimal('0'),
            effectivehours=Decimal('0'),
            effectivedays=Decimal('0'),
        )

        equip = EquipmentYieldService.create_yield(dto, user)

        assert equip.monthlycubicmeters == Decimal('0')
        assert equip.costpercubicmeter == Decimal('0')

    def test_update_yield(self):
        equip = EquipmentYieldFactory()
        user = SalespersonFactory()

        dto = UpdateEquipmentYieldDto(
            theoreticalyield=Decimal('200'),
            trafficfactor=Decimal('0.9'),
        )

        updated = EquipmentYieldService.update_yield(equip.equipmentyieldid, dto, user)

        assert updated.theoreticalyield == Decimal('200')
        assert updated.trafficfactor == Decimal('0.9')
        assert updated.realyield == Decimal('200') * Decimal('0.9')

    def test_update_yield_not_found(self):
        user = SalespersonFactory()
        dto = UpdateEquipmentYieldDto(description='Nope')

        with pytest.raises(NotFound):
            EquipmentYieldService.update_yield(uuid4(), dto, user)

    def test_delete_yield(self):
        equip = EquipmentYieldFactory()
        user = SalespersonFactory()

        deleted = EquipmentYieldService.delete_yield(equip.equipmentyieldid, user)

        assert deleted.statecode == 1

    def test_delete_yield_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            EquipmentYieldService.delete_yield(uuid4(), user)


# =============================================================================
# ConceptPriceCatalogService (existing tests preserved below)
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceList:
    """Tests for ConceptPriceCatalogService.list_items."""

    def test_list_returns_active_items(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(statecode=0)
        ConceptPriceCatalogItemFactory(statecode=0)
        ConceptPriceCatalogItemFactory(statecode=1)  # inactive

        result = ConceptPriceCatalogService.list_items(user)
        assert result.count() == 2

    def test_list_filter_by_source(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.HISTORICO)
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.HISTORICO)
        ConceptPriceCatalogItemFactory(source=CatalogSourceCode.SICT)

        result = ConceptPriceCatalogService.list_items(
            user, source=CatalogSourceCode.HISTORICO,
        )
        assert result.count() == 2

    def test_list_filter_by_unit(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(unit='m2')
        ConceptPriceCatalogItemFactory(unit='m2')
        ConceptPriceCatalogItemFactory(unit='pza')

        result = ConceptPriceCatalogService.list_items(user, unit='m2')
        assert result.count() == 2

    def test_list_search_by_description(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(description='Firme de concreto fc 200')
        ConceptPriceCatalogItemFactory(description='Muro de tablaroca')
        ConceptPriceCatalogItemFactory(description='Concreto premezclado')

        result = ConceptPriceCatalogService.list_items(user, search='concreto')
        assert result.count() == 2

    def test_list_search_by_code(self):
        user = SalespersonFactory()
        ConceptPriceCatalogItemFactory(code='HIST-00042')
        ConceptPriceCatalogItemFactory(code='HIST-00043')

        result = ConceptPriceCatalogService.list_items(user, search='00042')
        assert result.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceCreate:
    """Tests for ConceptPriceCatalogService.create_item."""

    def test_create_with_auto_code(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            description='Demolicion de muro de block',
            unit='m2',
            source=CatalogSourceCode.HISTORICO,
        )

        item = ConceptPriceCatalogService.create_item(dto, user)

        assert item.catalogitemid is not None
        assert item.code.startswith('HIST-')
        assert item.description == 'Demolicion de muro de block'
        assert item.unit == 'm2'
        assert item.createdby == user

    def test_create_with_explicit_code(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            code='CUSTOM-001',
            description='Test concept',
            unit='pza',
        )

        item = ConceptPriceCatalogService.create_item(dto, user)
        assert item.code == 'CUSTOM-001'

    def test_create_sict_source(self):
        user = SalespersonFactory()
        dto = CreateConceptPriceCatalogItemDto(
            description='Terraceria compactada',
            unit='m3',
            source=CatalogSourceCode.SICT,
        )

        item = ConceptPriceCatalogService.create_item(dto, user)
        assert item.source == CatalogSourceCode.SICT
        assert item.code.startswith('SICT-')

    def test_auto_code_increments(self):
        user = SalespersonFactory()
        dto1 = CreateConceptPriceCatalogItemDto(
            description='Concepto A', unit='m2',
            source=CatalogSourceCode.MANUAL,
        )
        dto2 = CreateConceptPriceCatalogItemDto(
            description='Concepto B', unit='m2',
            source=CatalogSourceCode.MANUAL,
        )

        item1 = ConceptPriceCatalogService.create_item(dto1, user)
        item2 = ConceptPriceCatalogService.create_item(dto2, user)

        num1 = int(item1.code.split('-')[-1])
        num2 = int(item2.code.split('-')[-1])
        assert num2 == num1 + 1


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceUpdate:
    """Tests for ConceptPriceCatalogService.update_item."""

    def test_update_description(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory(description='Original')

        dto = UpdateConceptPriceCatalogItemDto(description='Updated')
        updated = ConceptPriceCatalogService.update_item(
            item.catalogitemid, dto, user,
        )

        assert updated.description == 'Updated'
        assert updated.modifiedby == user

    def test_update_partial(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory(
            description='Original', unit='m2',
        )

        dto = UpdateConceptPriceCatalogItemDto(unit='ml')
        updated = ConceptPriceCatalogService.update_item(
            item.catalogitemid, dto, user,
        )

        assert updated.unit == 'ml'
        assert updated.description == 'Original'  # unchanged

    def test_update_not_found(self):
        user = SalespersonFactory()
        dto = UpdateConceptPriceCatalogItemDto(description='Nope')

        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.update_item(uuid4(), dto, user)


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceDelete:
    """Tests for ConceptPriceCatalogService.delete_item."""

    def test_soft_delete(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        deleted = ConceptPriceCatalogService.delete_item(
            item.catalogitemid, user,
        )

        assert deleted.statecode == 1
        assert deleted.modifiedby == user

    def test_delete_not_found(self):
        user = SalespersonFactory()
        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.delete_item(uuid4(), user)

    def test_soft_deleted_excluded_from_list(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceCatalogService.delete_item(item.catalogitemid, user)

        result = ConceptPriceCatalogService.list_items(user)
        assert result.count() == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceReferenceService:
    """Tests for ConceptPriceCatalogService reference methods."""

    def test_list_references(self):
        item = ConceptPriceCatalogItemFactory()
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Alpha')
        ConceptPriceReferenceFactory(catalogitemid=item, projectname='Beta')
        ConceptPriceReferenceFactory(
            catalogitemid=item, projectname='Inactive', statecode=1,
        )

        refs = ConceptPriceCatalogService.list_references(item.catalogitemid)
        assert refs.count() == 2

    def test_create_reference(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        dto = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Cumbres Elite',
            unitprice=Decimal('1500.00'),
            quantity=Decimal('10'),
            totalamount=Decimal('15000.00'),
        )

        ref = ConceptPriceCatalogService.create_reference(dto, user)

        assert ref.referenceid is not None
        assert ref.projectname == 'Cumbres Elite'
        assert ref.unitprice == Decimal('1500.00')
        assert ref.createdby == user

    def test_create_reference_updates_parent_stats(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()

        dto1 = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Project A',
            unitprice=Decimal('100.00'),
        )
        dto2 = CreateConceptPriceReferenceDto(
            catalogitemid=item.catalogitemid,
            projectname='Project B',
            unitprice=Decimal('300.00'),
        )

        ConceptPriceCatalogService.create_reference(dto1, user)
        ConceptPriceCatalogService.create_reference(dto2, user)

        item.refresh_from_db()
        assert item.averageprice == Decimal('200')
        assert item.minprice == Decimal('100.00')
        assert item.maxprice == Decimal('300.00')
        assert item.referencecount == 2

    def test_delete_reference(self):
        user = SalespersonFactory()
        ref = ConceptPriceReferenceFactory()

        deleted = ConceptPriceCatalogService.delete_reference(
            ref.referenceid, user,
        )

        assert deleted.statecode == 1

    def test_delete_reference_updates_parent_stats(self):
        user = SalespersonFactory()
        item = ConceptPriceCatalogItemFactory()
        ref1 = ConceptPriceReferenceFactory(
            catalogitemid=item, unitprice=Decimal('100'),
        )
        ConceptPriceReferenceFactory(
            catalogitemid=item, unitprice=Decimal('200'),
        )
        item.update_price_stats()
        item.save()
        assert item.referencecount == 2

        ConceptPriceCatalogService.delete_reference(ref1.referenceid, user)

        item.refresh_from_db()
        assert item.referencecount == 1
        assert item.averageprice == Decimal('200')

    def test_delete_reference_not_found(self):
        user = SalespersonFactory()
        with pytest.raises(Exception, match='not found'):
            ConceptPriceCatalogService.delete_reference(uuid4(), user)


@pytest.mark.unit
@pytest.mark.django_db
class TestConceptPriceCatalogServiceBulkImport:
    """Tests for ConceptPriceCatalogService.bulk_import."""

    def test_bulk_import_creates_items_and_refs(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Firme de concreto fc 200',
                'unit': 'm2',
                'source': CatalogSourceCode.HISTORICO,
                'references': [
                    {'projectname': 'Cumbres Elite', 'unitprice': Decimal('445.00')},
                    {'projectname': 'Valle', 'unitprice': Decimal('368.75')},
                ],
            },
            {
                'description': 'Pintura vinilica en muros',
                'unit': 'm2',
                'source': CatalogSourceCode.HISTORICO,
                'references': [
                    {'projectname': 'Cumbres Elite', 'unitprice': Decimal('88.00')},
                ],
            },
        ]

        result = ConceptPriceCatalogService.bulk_import(items, user)

        assert result['created'] == 2
        assert result['references_created'] == 3

    def test_bulk_import_skips_zero_prices(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Concepto con precios mixtos',
                'unit': 'pza',
                'references': [
                    {'projectname': 'A', 'unitprice': Decimal('100')},
                    {'projectname': 'B', 'unitprice': Decimal('0')},  # should skip
                    {'projectname': 'C', 'unitprice': Decimal('-5')},  # should skip
                ],
            },
        ]

        result = ConceptPriceCatalogService.bulk_import(items, user)

        assert result['created'] == 1
        assert result['references_created'] == 1

    def test_bulk_import_computes_stats(self):
        user = SalespersonFactory()
        items = [
            {
                'description': 'Concepto stats test',
                'unit': 'm2',
                'references': [
                    {'projectname': 'A', 'unitprice': Decimal('100')},
                    {'projectname': 'B', 'unitprice': Decimal('200')},
                    {'projectname': 'C', 'unitprice': Decimal('300')},
                ],
            },
        ]

        ConceptPriceCatalogService.bulk_import(items, user)

        item = ConceptPriceCatalogItem.objects.get(
            description='Concepto stats test',
        )
        assert item.averageprice == Decimal('200')
        assert item.minprice == Decimal('100')
        assert item.maxprice == Decimal('300')
        assert item.referencecount == 3

    def test_bulk_import_auto_generates_codes(self):
        user = SalespersonFactory()
        items = [
            {'description': 'Concepto 1', 'unit': 'm2', 'references': [
                {'projectname': 'A', 'unitprice': Decimal('100')},
            ]},
            {'description': 'Concepto 2', 'unit': 'm2', 'references': [
                {'projectname': 'A', 'unitprice': Decimal('200')},
            ]},
        ]

        ConceptPriceCatalogService.bulk_import(items, user)

        codes = list(
            ConceptPriceCatalogItem.objects
            .filter(description__startswith='Concepto')
            .values_list('code', flat=True)
            .order_by('code')
        )
        assert len(codes) == 2
        assert all(c.startswith('HIST-') for c in codes)


# =============================================================================
# FamilyTemplateService
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestFamilyTemplateService:
    """Tests for FamilyTemplateService."""

    def test_list_template_sets(self):
        user = SalespersonFactory()
        FamilyTemplateSetFactory()
        FamilyTemplateSetFactory()
        FamilyTemplateSetFactory(statecode=1)  # inactive

        result = FamilyTemplateService.list_template_sets(user)
        assert result.count() == 2

    def test_list_template_sets_filter_by_category(self):
        user = SalespersonFactory()
        FamilyTemplateSetFactory(category='civil')
        FamilyTemplateSetFactory(category='civil')
        FamilyTemplateSetFactory(category='mining')

        result = FamilyTemplateService.list_template_sets(user, category='civil')
        assert result.count() == 2

    def test_list_template_sets_search(self):
        user = SalespersonFactory()
        FamilyTemplateSetFactory(name='Edificacion residencial')
        FamilyTemplateSetFactory(name='Carreteras')
        FamilyTemplateSetFactory(name='Edificacion comercial')

        result = FamilyTemplateService.list_template_sets(user, search='edificacion')
        assert result.count() == 2

    def test_get_template_set(self):
        ts = FamilyTemplateSetFactory()
        user = SalespersonFactory()

        result = FamilyTemplateService.get_template_set(ts.templatesetid, user)

        assert result.templatesetid == ts.templatesetid

    def test_get_template_set_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            FamilyTemplateService.get_template_set(uuid4(), user)

    def test_create_template_set(self):
        from apps.proyeccion.schemas import CreateFamilyTemplateSetDto

        user = SalespersonFactory()
        dto = CreateFamilyTemplateSetDto(
            name='Custom Template',
            description='A test template',
            category='custom',
        )

        ts = FamilyTemplateService.create_template_set(dto, user)

        assert ts.templatesetid is not None
        assert ts.name == 'Custom Template'
        assert ts.issystem is False
        assert ts.createdby == user

    def test_delete_template_set(self):
        ts = FamilyTemplateSetFactory(issystem=False)
        user = SalespersonFactory()

        deleted = FamilyTemplateService.delete_template_set(ts.templatesetid, user)

        assert deleted.statecode == 1

    def test_delete_template_set_system_not_allowed(self):
        ts = FamilyTemplateSetFactory(issystem=True)
        user = SalespersonFactory()

        with pytest.raises(ValidationError):
            FamilyTemplateService.delete_template_set(ts.templatesetid, user)

    def test_delete_template_set_not_found(self):
        user = SalespersonFactory()

        with pytest.raises(NotFound):
            FamilyTemplateService.delete_template_set(uuid4(), user)

    def test_save_project_as_template(self):
        project = EstimationProjectFactory()
        family = ConceptFamilyFactory(projectid=project, code='F01', name='Terraceria')
        ConceptSubfamilyFactory(
            familyid=family, projectid=project, code='SF01', name='Excavacion',
        )
        ConceptSubfamilyFactory(
            familyid=family, projectid=project, code='SF02', name='Relleno',
        )
        user = project.ownerid

        dto = SaveProjectAsTemplateDto(
            projectid=project.estimationprojectid,
            name='From Project',
            category='civil',
        )

        ts = FamilyTemplateService.save_project_as_template(dto, user)

        assert ts.templatesetid is not None
        assert ts.name == 'From Project'
        items = FamilyTemplateItem.objects.filter(templatesetid=ts)
        assert items.count() == 2
        assert items.filter(familycode='F01').count() == 2

    def test_save_project_as_template_no_families(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = SaveProjectAsTemplateDto(
            projectid=project.estimationprojectid,
            name='Empty',
            category='custom',
        )

        with pytest.raises(ValidationError):
            FamilyTemplateService.save_project_as_template(dto, user)

    def test_apply_template_to_project(self):
        ts = FamilyTemplateSetFactory()
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F01', familyname='Terraceria',
            subfamilycode='SF01', subfamilyname='Excavacion',
            familysortorder=1, subfamilysortorder=1,
        )
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F01', familyname='Terraceria',
            subfamilycode='SF02', subfamilyname='Relleno',
            familysortorder=1, subfamilysortorder=2,
        )
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F02', familyname='Estructura',
            subfamilycode='SF01', subfamilyname='Cimentacion',
            familysortorder=2, subfamilysortorder=1,
        )

        project = EstimationProjectFactory()
        user = project.ownerid

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        assert len(created) == 2  # 2 families
        families = ConceptFamily.objects.filter(projectid=project)
        assert families.count() == 2
        subfamilies = ConceptSubfamily.objects.filter(projectid=project)
        assert subfamilies.count() == 3

    def test_apply_template_skips_existing_family_codes(self):
        ts = FamilyTemplateSetFactory()
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F01', familyname='Terraceria',
            subfamilycode='SF01', subfamilyname='Excavacion',
        )
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F02', familyname='Estructura',
            subfamilycode='SF01', subfamilyname='Cimentacion',
        )

        project = EstimationProjectFactory()
        user = project.ownerid
        # Pre-create F01 family
        ConceptFamilyFactory(projectid=project, code='F01')

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        # Only F02 should be created (F01 was skipped)
        assert len(created) == 1
        assert created[0].code == 'F02'

    def test_apply_template_not_found(self):
        project = EstimationProjectFactory()
        user = project.ownerid

        dto = ApplyFamilyTemplateDto(
            templatesetid=uuid4(),
            projectid=project.estimationprojectid,
        )

        with pytest.raises(NotFound):
            FamilyTemplateService.apply_template_to_project(dto, user)

    def test_apply_template_filter_by_familycodes(self):
        ts = FamilyTemplateSetFactory()
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F01', familyname='Terraceria',
            subfamilycode='SF01', subfamilyname='Excavacion',
        )
        FamilyTemplateItemFactory(
            templatesetid=ts, familycode='F02', familyname='Estructura',
            subfamilycode='SF01', subfamilyname='Cimentacion',
        )

        project = EstimationProjectFactory()
        user = project.ownerid

        dto = ApplyFamilyTemplateDto(
            templatesetid=ts.templatesetid,
            projectid=project.estimationprojectid,
            familycodes=['F01'],
        )

        created = FamilyTemplateService.apply_template_to_project(dto, user)

        # Only F01 should be created
        assert len(created) == 1
        assert created[0].code == 'F01'


# =============================================================================
# UnitCostBreakdownService - Duplicate Line
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestDuplicateBreakdownLine:
    """Tests for UnitCostBreakdownService.duplicate_line"""

    def test_duplicates_all_fields(self):
        """Verify all fields are copied from original."""
        line = UnitCostBreakdownFactory(
            description='Diesel',
            unit='Lt',
            quantity=Decimal('1'),
            unitprice=Decimal('23.09'),
            yieldvalue=Decimal('0.862'),
            amount=Decimal('19.90'),
            categorycode=BreakdownCategoryCode.MATERIALS,
        )
        user = line.conceptid.projectid.ownerid

        result = UnitCostBreakdownService.duplicate_line(line.breakdownid, user)

        assert result.breakdownid != line.breakdownid
        assert result.conceptid == line.conceptid
        assert result.categorycode == line.categorycode
        assert result.description == 'Diesel'
        assert result.unit == 'Lt'
        assert result.quantity == Decimal('1')
        assert result.unitprice == Decimal('23.09')
        assert result.yieldvalue == Decimal('0.862')
        assert result.amount == Decimal('19.90')

    def test_assigns_next_linenumber(self):
        """Line number should be max+1 in same category."""
        concept = BudgetConceptFactory()
        UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=1)
        line2 = UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=2)
        user = concept.projectid.ownerid

        result = UnitCostBreakdownService.duplicate_line(line2.breakdownid, user)

        assert result.linenumber == 3

    def test_does_not_affect_other_categories(self):
        """Duplicating in one category should not affect linenumber in another."""
        concept = BudgetConceptFactory()
        mat_line = UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=5)
        UnitCostBreakdownFactory(conceptid=concept, categorycode=BreakdownCategoryCode.LABOR, linenumber=10)
        user = concept.projectid.ownerid

        result = UnitCostBreakdownService.duplicate_line(mat_line.breakdownid, user)

        assert result.linenumber == 6  # max in MATERIALS is 5
        assert result.categorycode == BreakdownCategoryCode.MATERIALS

    def test_copies_supply_reference(self):
        """Should copy supply FK if present."""
        supply = SupplyCatalogItemFactory()
        line = UnitCostBreakdownFactory(supplyid=supply)
        user = line.conceptid.projectid.ownerid

        result = UnitCostBreakdownService.duplicate_line(line.breakdownid, user)

        assert result.supplyid == supply


# =============================================================================
# UnitCostBreakdownService - Copy From Concept
# =============================================================================

@pytest.mark.unit
@pytest.mark.django_db
class TestCopyFromConcept:
    """Tests for UnitCostBreakdownService.copy_from_concept"""

    def test_copies_all_lines_from_source(self):
        """All active lines from source should appear in target."""
        source = BudgetConceptFactory()
        target = BudgetConceptFactory(projectid=source.projectid)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.MATERIALS)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.LABOR)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.MACHINERY)
        user = source.projectid.ownerid

        result = UnitCostBreakdownService.copy_from_concept(
            target.conceptid, source.conceptid, user
        )

        assert len(result) == 3
        for line in UnitCostBreakdown.objects.filter(conceptid=target, statecode=0):
            assert line.conceptid == target

    def test_preserves_existing_lines_in_target(self):
        """Existing lines in target should not be removed."""
        source = BudgetConceptFactory()
        target = BudgetConceptFactory(projectid=source.projectid)
        existing = UnitCostBreakdownFactory(conceptid=target, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=1)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.MATERIALS)
        user = source.projectid.ownerid

        UnitCostBreakdownService.copy_from_concept(target.conceptid, source.conceptid, user)

        all_target = UnitCostBreakdown.objects.filter(conceptid=target, statecode=0)
        assert all_target.count() == 2
        assert all_target.filter(breakdownid=existing.breakdownid).exists()

    def test_increments_linenumber_from_existing_max(self):
        """New lines should start from max existing linenumber + 1."""
        source = BudgetConceptFactory()
        target = BudgetConceptFactory(projectid=source.projectid)
        UnitCostBreakdownFactory(conceptid=target, categorycode=BreakdownCategoryCode.MATERIALS, linenumber=5)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.MATERIALS)
        UnitCostBreakdownFactory(conceptid=source, categorycode=BreakdownCategoryCode.MATERIALS)
        user = source.projectid.ownerid

        UnitCostBreakdownService.copy_from_concept(target.conceptid, source.conceptid, user)

        copied = UnitCostBreakdown.objects.filter(
            conceptid=target, statecode=0
        ).exclude(linenumber=5).order_by('linenumber')
        assert list(copied.values_list('linenumber', flat=True)) == [6, 7]

    def test_raises_error_if_source_empty(self):
        """Should raise ValidationError if source has no active lines."""
        source = BudgetConceptFactory()
        target = BudgetConceptFactory(projectid=source.projectid)
        user = source.projectid.ownerid

        with pytest.raises(ValidationError):
            UnitCostBreakdownService.copy_from_concept(
                target.conceptid, source.conceptid, user
            )

    def test_ignores_inactive_source_lines(self):
        """Should not copy lines with statecode != 0."""
        source = BudgetConceptFactory()
        target = BudgetConceptFactory(projectid=source.projectid)
        UnitCostBreakdownFactory(conceptid=source, statecode=0)
        UnitCostBreakdownFactory(conceptid=source, statecode=1)  # inactive
        user = source.projectid.ownerid

        result = UnitCostBreakdownService.copy_from_concept(
            target.conceptid, source.conceptid, user
        )

        assert len(result) == 1
