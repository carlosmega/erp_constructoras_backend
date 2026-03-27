"""API routers for Proyección (Budget Estimation) module."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from django.http import HttpRequest

from apps.proyeccion.schemas import (
    EstimationProjectSchema,
    CreateEstimationProjectDto,
    UpdateEstimationProjectDto,
    ConvertToProjectDto,
    ConceptFamilySchema,
    CreateConceptFamilyDto,
    UpdateConceptFamilyDto,
    ConceptSubfamilySchema,
    CreateConceptSubfamilyDto,
    UpdateConceptSubfamilyDto,
    BudgetConceptSchema,
    CreateBudgetConceptDto,
    UpdateBudgetConceptDto,
    UnitCostBreakdownSchema,
    CreateUnitCostBreakdownDto,
    UpdateUnitCostBreakdownDto,
    IndirectCostDetailSchema,
    CreateIndirectCostDetailDto,
    UpdateIndirectCostDetailDto,
    ApplyTemplateDto,
    OfferAlternativeSchema,
    CreateOfferAlternativeDto,
    UpdateOfferAlternativeDto,
    ExternalCostItemSchema,
    UpdateExternalCostItemDto,
    SupplyExplosionItemSchema,
    SupplyExplosionConsolidatedSchema,
    WorkPlanEntrySchema,
    CreateWorkPlanEntryDto,
    UpdateWorkPlanEntryDto,
    BulkWorkPlanDto,
    TemporalDistributionSchema,
    CashFlowEntrySchema,
    ProjectBudgetSummarySchema,
    SupplyCatalogItemSchema,
    CreateSupplyCatalogItemDto,
    UpdateSupplyCatalogItemDto,
    EquipmentYieldSchema,
    CreateEquipmentYieldDto,
    UpdateEquipmentYieldDto,
    IndirectCostTemplateSchema,
    ConceptPriceCatalogItemSchema,
    ConceptPriceCatalogItemListSchema,
    CreateConceptPriceCatalogItemDto,
    UpdateConceptPriceCatalogItemDto,
    ConceptPriceReferenceSchema,
    CreateConceptPriceReferenceDto,
    FamilyTemplateSetSchema,
    FamilyTemplateSetListSchema,
    CreateFamilyTemplateSetDto,
    SaveProjectAsTemplateDto,
    ApplyFamilyTemplateDto,
)
from apps.proyeccion.services import (
    EstimationProjectService,
    ConceptCatalogService,
    UnitCostBreakdownService,
    IndirectCostDetailService,
    OfferAlternativeService,
    ExternalCostService,
    SupplyExplosionService,
    WorkPlanService,
    TemporalDistributionService,
    CashFlowService,
    SupplyCatalogService,
    EquipmentYieldService,
    ConceptPriceCatalogService,
    FamilyTemplateService,
)
from apps.proyeccion.models import IndirectCostTemplate


# =============================================================================
# 0. Estimation Projects Router
# =============================================================================

estimation_projects_router = Router(tags=["Estimation Projects"])


@estimation_projects_router.get("/", response=List[EstimationProjectSchema])
def list_estimation_projects(request: HttpRequest, statecode: Optional[int] = None, search: Optional[str] = None):
    """List all estimation projects with optional filters."""
    projects = EstimationProjectService.list_projects(request.user, statecode=statecode, search=search)
    return list(projects)


@estimation_projects_router.post("/", response={201: EstimationProjectSchema})
def create_estimation_project(request: HttpRequest, payload: CreateEstimationProjectDto):
    """Create a new estimation project."""
    project = EstimationProjectService.create_project(payload, request.user)
    return 201, project


@estimation_projects_router.get("/{project_id}/", response=EstimationProjectSchema)
def get_estimation_project(request: HttpRequest, project_id: UUID):
    """Get a single estimation project by ID."""
    return EstimationProjectService.get_project(project_id, request.user)


@estimation_projects_router.patch("/{project_id}/", response=EstimationProjectSchema)
def update_estimation_project(request: HttpRequest, project_id: UUID, payload: UpdateEstimationProjectDto):
    """Update an estimation project."""
    return EstimationProjectService.update_project(project_id, payload, request.user)


@estimation_projects_router.delete("/{project_id}/", response=EstimationProjectSchema)
def delete_estimation_project(request: HttpRequest, project_id: UUID):
    """Soft-delete an estimation project (set to Canceled)."""
    return EstimationProjectService.delete_project(project_id, request.user)


@estimation_projects_router.post("/{project_id}/convert/", response=EstimationProjectSchema)
def convert_to_project(request: HttpRequest, project_id: UUID, payload: ConvertToProjectDto):
    """Convert an estimation project into a ConstructionProject with budgets."""
    return EstimationProjectService.convert_to_project(project_id, payload, request.user)


# =============================================================================
# 1. Concept Families Router
# =============================================================================

concept_families_router = Router(tags=["Concept Catalog"])


@concept_families_router.get(
    "/projects/{project_id}/concept-families/",
    response=List[ConceptFamilySchema],
)
# TODO: Add @require_permission decorator during integration
def list_families(request: HttpRequest, project_id: UUID):
    """List all concept families for a project."""
    families = ConceptCatalogService.list_families(project_id, request.user)
    return list(families)


@concept_families_router.post(
    "/projects/{project_id}/concept-families/",
    response={201: ConceptFamilySchema},
)
# TODO: Add @require_permission decorator during integration
def create_family(request: HttpRequest, project_id: UUID, payload: CreateConceptFamilyDto):
    """Create a new concept family."""
    payload.projectid = project_id
    family = ConceptCatalogService.create_family(payload, request.user)
    return 201, family


@concept_families_router.patch(
    "/concept-families/{family_id}/",
    response=ConceptFamilySchema,
)
# TODO: Add @require_permission decorator during integration
def update_family(request: HttpRequest, family_id: UUID, payload: UpdateConceptFamilyDto):
    """Update a concept family."""
    family = ConceptCatalogService.update_family(family_id, payload, request.user)
    return family


@concept_families_router.delete(
    "/concept-families/{family_id}/",
    response=ConceptFamilySchema,
)
# TODO: Add @require_permission decorator during integration
def delete_family(request: HttpRequest, family_id: UUID):
    """Soft delete a concept family."""
    family = ConceptCatalogService.delete_family(family_id, request.user)
    return family


@concept_families_router.get(
    "/concept-families/{family_id}/subfamilies/",
    response=List[ConceptSubfamilySchema],
)
# TODO: Add @require_permission decorator during integration
def list_subfamilies(request: HttpRequest, family_id: UUID):
    """List all subfamilies for a given family."""
    subfamilies = ConceptCatalogService.list_subfamilies(family_id, request.user)
    return list(subfamilies)


@concept_families_router.post(
    "/concept-families/{family_id}/subfamilies/",
    response={201: ConceptSubfamilySchema},
)
# TODO: Add @require_permission decorator during integration
def create_subfamily(request: HttpRequest, family_id: UUID, payload: CreateConceptSubfamilyDto):
    """Create a new concept subfamily."""
    payload.familyid = family_id
    subfamily = ConceptCatalogService.create_subfamily(payload, request.user)
    return 201, subfamily


@concept_families_router.patch(
    "/concept-subfamilies/{subfamily_id}/",
    response=ConceptSubfamilySchema,
)
# TODO: Add @require_permission decorator during integration
def update_subfamily(request: HttpRequest, subfamily_id: UUID, payload: UpdateConceptSubfamilyDto):
    """Update a concept subfamily."""
    subfamily = ConceptCatalogService.update_subfamily(subfamily_id, payload, request.user)
    return subfamily


# =============================================================================
# 2. Budget Concepts Router
# =============================================================================

budget_concepts_router = Router(tags=["Budget Concepts"])


@budget_concepts_router.get(
    "/projects/{project_id}/concepts/",
    response=List[BudgetConceptSchema],
)
# TODO: Add @require_permission decorator during integration
def list_concepts(
    request: HttpRequest,
    project_id: UUID,
    subfamilyid: Optional[UUID] = None,
):
    """List budget concepts for a project, optionally filtered by subfamily."""
    concepts = ConceptCatalogService.list_concepts(project_id, request.user, subfamilyid=subfamilyid)
    return list(concepts)


@budget_concepts_router.post(
    "/projects/{project_id}/concepts/",
    response={201: BudgetConceptSchema},
)
# TODO: Add @require_permission decorator during integration
def create_concept(request: HttpRequest, project_id: UUID, payload: CreateBudgetConceptDto):
    """Create a new budget concept."""
    payload.projectid = project_id
    concept = ConceptCatalogService.create_concept(payload, request.user)
    return 201, concept


@budget_concepts_router.get(
    "/concepts/{concept_id}/",
    response=BudgetConceptSchema,
)
# TODO: Add @require_permission decorator during integration
def get_concept(request: HttpRequest, concept_id: UUID):
    """Get a single budget concept by ID."""
    concept = ConceptCatalogService.get_concept(concept_id, request.user)
    return concept


@budget_concepts_router.patch(
    "/concepts/{concept_id}/",
    response=BudgetConceptSchema,
)
# TODO: Add @require_permission decorator during integration
def update_concept(request: HttpRequest, concept_id: UUID, payload: UpdateBudgetConceptDto):
    """Update a budget concept."""
    concept = ConceptCatalogService.update_concept(concept_id, payload, request.user)
    return concept


@budget_concepts_router.delete(
    "/concepts/{concept_id}/",
    response=BudgetConceptSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_concept(request: HttpRequest, concept_id: UUID):
    """Soft delete a budget concept."""
    concept = ConceptCatalogService.delete_concept(concept_id, request.user)
    return concept


@budget_concepts_router.post(
    "/concepts/{concept_id}/recalculate/",
    response=BudgetConceptSchema,
)
# TODO: Add @require_permission decorator during integration
def recalculate_concept(request: HttpRequest, concept_id: UUID):
    """Recalculate a concept's costs from its breakdown lines."""
    concept = ConceptCatalogService.recalculate_concept(concept_id, request.user)
    return concept


@budget_concepts_router.get(
    "/concepts/{concept_id}/breakdowns/",
    response=List[UnitCostBreakdownSchema],
)
# TODO: Add @require_permission decorator during integration
def list_breakdowns(request: HttpRequest, concept_id: UUID):
    """List all unit cost breakdown lines for a concept."""
    breakdowns = UnitCostBreakdownService.list_breakdowns(concept_id, request.user)
    return list(breakdowns)


@budget_concepts_router.post(
    "/concepts/{concept_id}/breakdowns/",
    response={201: UnitCostBreakdownSchema},
)
# TODO: Add @require_permission decorator during integration
def create_breakdown(request: HttpRequest, concept_id: UUID, payload: CreateUnitCostBreakdownDto):
    """Create a new unit cost breakdown line."""
    payload.conceptid = concept_id
    breakdown = UnitCostBreakdownService.create_breakdown(payload, request.user)
    return 201, breakdown


@budget_concepts_router.patch(
    "/breakdowns/{breakdown_id}/",
    response=UnitCostBreakdownSchema,
)
# TODO: Add @require_permission decorator during integration
def update_breakdown(request: HttpRequest, breakdown_id: UUID, payload: UpdateUnitCostBreakdownDto):
    """Update a unit cost breakdown line."""
    breakdown = UnitCostBreakdownService.update_breakdown(breakdown_id, payload, request.user)
    return breakdown


@budget_concepts_router.delete(
    "/breakdowns/{breakdown_id}/",
    response=UnitCostBreakdownSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_breakdown(request: HttpRequest, breakdown_id: UUID):
    """Soft delete a unit cost breakdown line."""
    breakdown = UnitCostBreakdownService.delete_breakdown(breakdown_id, request.user)
    return breakdown


@budget_concepts_router.post(
    "/concepts/{concept_id}/auto-hm-epp/",
    response={201: List[UnitCostBreakdownSchema]},
)
# TODO: Add @require_permission decorator during integration
def auto_generate_hm_epp(request: HttpRequest, concept_id: UUID):
    """Auto generate Minor Tools (HM) and PPE breakdown lines from labor cost."""
    lines = UnitCostBreakdownService.auto_generate_hm_epp(concept_id, request.user)
    return 201, lines


# =============================================================================
# 3. Indirect Cost Details Router
# =============================================================================

indirect_cost_details_router = Router(tags=["Indirect Cost Details"])


@indirect_cost_details_router.get(
    "/projects/{project_id}/indirect-cost-details/",
    response=List[IndirectCostDetailSchema],
)
# TODO: Add @require_permission decorator during integration
def list_indirect_cost_details(
    request: HttpRequest,
    project_id: UUID,
    categorycode: Optional[str] = None,
):
    """List indirect cost details for a project, optionally filtered by category."""
    details = IndirectCostDetailService.list_details(project_id, request.user, categorycode=categorycode)
    return list(details)


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/",
    response={201: IndirectCostDetailSchema},
)
# TODO: Add @require_permission decorator during integration
def create_indirect_cost_detail(request: HttpRequest, project_id: UUID, payload: CreateIndirectCostDetailDto):
    """Create a new indirect cost detail line."""
    payload.projectid = project_id
    detail = IndirectCostDetailService.create_detail(payload, request.user)
    return 201, detail


@indirect_cost_details_router.patch(
    "/indirect-cost-details/{detail_id}/",
    response=IndirectCostDetailSchema,
)
# TODO: Add @require_permission decorator during integration
def update_indirect_cost_detail(request: HttpRequest, detail_id: UUID, payload: UpdateIndirectCostDetailDto):
    """Update an indirect cost detail line."""
    detail = IndirectCostDetailService.update_detail(detail_id, payload, request.user)
    return detail


@indirect_cost_details_router.delete(
    "/indirect-cost-details/{detail_id}/",
    response=IndirectCostDetailSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_indirect_cost_detail(request: HttpRequest, detail_id: UUID):
    """Soft delete an indirect cost detail line."""
    detail = IndirectCostDetailService.delete_detail(detail_id, request.user)
    return detail


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/apply-template/",
    response={201: List[IndirectCostDetailSchema]},
)
# TODO: Add @require_permission decorator during integration
def apply_indirect_cost_template(request: HttpRequest, project_id: UUID, payload: ApplyTemplateDto):
    """Apply an indirect cost template to a project."""
    details = IndirectCostDetailService.apply_template(project_id, payload.projectsize, request.user)
    return 201, details


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/prorate/",
    response=List[BudgetConceptSchema],
)
# TODO: Add @require_permission decorator during integration
def prorate_indirect_costs(request: HttpRequest, project_id: UUID):
    """Prorate indirect costs proportionally across all active concepts."""
    concepts = IndirectCostDetailService.prorate_to_concepts(project_id, request.user)
    return list(concepts)


@indirect_cost_details_router.get(
    "/projects/{project_id}/indirect-cost-details/total/",
    response=Decimal,
)
# TODO: Add @require_permission decorator during integration
def get_indirect_cost_total(request: HttpRequest, project_id: UUID):
    """Get total indirect cost amount for a project."""
    total = IndirectCostDetailService.get_total(project_id, request.user)
    return total


# =============================================================================
# 4. Offer Alternatives Router
# =============================================================================

offer_alternatives_router = Router(tags=["Offer Alternatives"])


@offer_alternatives_router.get(
    "/projects/{project_id}/alternatives/",
    response=List[OfferAlternativeSchema],
)
# TODO: Add @require_permission decorator during integration
def list_alternatives(request: HttpRequest, project_id: UUID):
    """List all offer alternatives for a project."""
    alternatives = OfferAlternativeService.list_alternatives(project_id, request.user)
    return list(alternatives)


@offer_alternatives_router.post(
    "/projects/{project_id}/alternatives/",
    response={201: OfferAlternativeSchema},
)
# TODO: Add @require_permission decorator during integration
def create_alternative(request: HttpRequest, project_id: UUID, payload: CreateOfferAlternativeDto):
    """Create a new offer alternative."""
    payload.projectid = project_id
    alternative = OfferAlternativeService.create_alternative(payload, request.user)
    return 201, alternative


@offer_alternatives_router.patch(
    "/alternatives/{alternative_id}/",
    response=OfferAlternativeSchema,
)
# TODO: Add @require_permission decorator during integration
def update_alternative(request: HttpRequest, alternative_id: UUID, payload: UpdateOfferAlternativeDto):
    """Update an offer alternative."""
    alternative = OfferAlternativeService.update_alternative(alternative_id, payload, request.user)
    return alternative


@offer_alternatives_router.delete(
    "/alternatives/{alternative_id}/",
    response=OfferAlternativeSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_alternative(request: HttpRequest, alternative_id: UUID):
    """Soft delete an offer alternative."""
    alternative = OfferAlternativeService.delete_alternative(alternative_id, request.user)
    return alternative


@offer_alternatives_router.post(
    "/alternatives/{alternative_id}/choose/",
    response=OfferAlternativeSchema,
)
# TODO: Add @require_permission decorator during integration
def choose_alternative(request: HttpRequest, alternative_id: UUID):
    """Mark an alternative as chosen and unmark all others for the same project."""
    alternative = OfferAlternativeService.choose_alternative(alternative_id, request.user)
    return alternative


# =============================================================================
# 5. External Costs Router
# =============================================================================

external_costs_router = Router(tags=["External Costs"])


@external_costs_router.get(
    "/projects/{project_id}/external-costs/",
    response=List[ExternalCostItemSchema],
)
# TODO: Add @require_permission decorator during integration
def list_external_costs(request: HttpRequest, project_id: UUID):
    """List all external cost items for a project."""
    costs = ExternalCostService.list_costs(project_id, request.user)
    return list(costs)


@external_costs_router.post(
    "/projects/{project_id}/external-costs/init/",
    response={201: List[ExternalCostItemSchema]},
)
# TODO: Add @require_permission decorator during integration
def initialize_external_cost_checklist(request: HttpRequest, project_id: UUID):
    """Initialize the default external cost checklist for a project."""
    items = ExternalCostService.initialize_checklist(project_id, request.user)
    return 201, items


@external_costs_router.patch(
    "/external-costs/{cost_id}/",
    response=ExternalCostItemSchema,
)
# TODO: Add @require_permission decorator during integration
def update_external_cost(request: HttpRequest, cost_id: UUID, payload: UpdateExternalCostItemDto):
    """Update an external cost item."""
    cost = ExternalCostService.update_cost(cost_id, payload, request.user)
    return cost


# =============================================================================
# 6. Supply Explosion Router
# =============================================================================

supply_explosion_router = Router(tags=["Supply Explosion"])


@supply_explosion_router.get(
    "/projects/{project_id}/supply-explosion/auxiliary/",
    response=List[SupplyExplosionItemSchema],
)
# TODO: Add @require_permission decorator during integration
def get_auxiliary_supply_explosion(request: HttpRequest, project_id: UUID):
    """Get auxiliary supply explosion (per concept, per breakdown line)."""
    lines = SupplyExplosionService.generate_auxiliary(project_id, request.user)
    return lines


@supply_explosion_router.get(
    "/projects/{project_id}/supply-explosion/consolidated/",
    response=List[SupplyExplosionConsolidatedSchema],
)
# TODO: Add @require_permission decorator during integration
def get_consolidated_supply_explosion(request: HttpRequest, project_id: UUID):
    """Get consolidated supply explosion grouped by supply code."""
    lines = SupplyExplosionService.generate_consolidated(project_id, request.user)
    return lines


# =============================================================================
# 7. Work Plan Router
# =============================================================================

workplan_router = Router(tags=["Work Plan"])


@workplan_router.get(
    "/projects/{project_id}/workplan/",
    response=List[WorkPlanEntrySchema],
)
# TODO: Add @require_permission decorator during integration
def list_workplan_entries(
    request: HttpRequest,
    project_id: UUID,
    conceptid: Optional[UUID] = None,
):
    """List work plan entries for a project, optionally filtered by concept."""
    entries = WorkPlanService.list_entries(project_id, request.user, conceptid=conceptid)
    return list(entries)


@workplan_router.post(
    "/projects/{project_id}/workplan/",
    response={201: WorkPlanEntrySchema},
)
# TODO: Add @require_permission decorator during integration
def create_workplan_entry(request: HttpRequest, project_id: UUID, payload: CreateWorkPlanEntryDto):
    """Create a work plan entry."""
    payload.projectid = project_id
    entry = WorkPlanService.create_entry(payload, request.user)
    return 201, entry


@workplan_router.patch(
    "/workplan/{entry_id}/",
    response=WorkPlanEntrySchema,
)
# TODO: Add @require_permission decorator during integration
def update_workplan_entry(request: HttpRequest, entry_id: UUID, payload: UpdateWorkPlanEntryDto):
    """Update a work plan entry."""
    entry = WorkPlanService.update_entry(entry_id, payload, request.user)
    return entry


@workplan_router.delete(
    "/workplan/{entry_id}/",
    response={204: None},
)
# TODO: Add @require_permission decorator during integration
def delete_workplan_entry(request: HttpRequest, entry_id: UUID):
    """Delete a work plan entry."""
    WorkPlanService.delete_entry(entry_id, request.user)
    return 204, None


@workplan_router.post(
    "/projects/{project_id}/workplan/bulk-distribute/",
    response={201: List[WorkPlanEntrySchema]},
)
# TODO: Add @require_permission decorator during integration
def bulk_distribute_workplan(request: HttpRequest, project_id: UUID, payload: BulkWorkPlanDto):
    """Bulk create/update work plan entries."""
    payload.projectid = project_id
    entries = WorkPlanService.bulk_distribute(project_id, payload.entries, request.user)
    return 201, entries


# =============================================================================
# 8. Analysis Router
# =============================================================================

analysis_router = Router(tags=["Budget Analysis"])


@analysis_router.get(
    "/projects/{project_id}/temporal-distribution/",
    response=List[TemporalDistributionSchema],
)
# TODO: Add @require_permission decorator during integration
def get_temporal_distribution(request: HttpRequest, project_id: UUID):
    """Get temporal distribution of invoiced, cost, and result per period."""
    distribution = TemporalDistributionService.calculate(project_id, request.user)
    return distribution


@analysis_router.get(
    "/projects/{project_id}/cashflow/",
    response=List[CashFlowEntrySchema],
)
# TODO: Add @require_permission decorator during integration
def get_cashflow(
    request: HttpRequest,
    project_id: UUID,
    advancepercent: Decimal = Decimal('0'),
    paymentdelay: int = 0,
    paymentfrequency: int = 1,
):
    """Get cashflow projection based on work plan and payment parameters."""
    entries = CashFlowService.calculate(
        project_id,
        request.user,
        advance_percent=advancepercent,
        payment_delay=paymentdelay,
        payment_frequency=paymentfrequency,
    )
    return entries


@analysis_router.get(
    "/projects/{project_id}/budget-summary/",
    response=ProjectBudgetSummarySchema,
)
# TODO: Add @require_permission decorator during integration
def get_budget_summary(request: HttpRequest, project_id: UUID):
    """Get project budget summary with totals and chosen alternative info."""
    from apps.proyeccion.models import (
        BudgetConcept as BudgetConceptModel,
        ConceptFamily as ConceptFamilyModel,
        ConceptSubfamily as ConceptSubfamilyModel,
        OfferAlternative as OfferAlternativeModel,
    )
    from django.db.models import Sum, F, Count
    from django.db import models

    concepts = BudgetConceptModel.objects.filter(
        projectid=project_id,
        statecode=0,
    )

    totals = concepts.aggregate(
        totaldirectcost=Sum(F('directunitcost') * F('quantity'), output_field=models.DecimalField()),
        totalindirectcost=Sum(F('indirectunitcost') * F('quantity'), output_field=models.DecimalField()),
        totalconcepts=Count('conceptid'),
    )

    direct = totals['totaldirectcost'] or Decimal('0')
    indirect = totals['totalindirectcost'] or Decimal('0')

    chosen = OfferAlternativeModel.objects.filter(
        projectid=project_id,
        ischosen=True,
    ).first()

    return {
        'projectid': project_id,
        'totalconcepts': totals['totalconcepts'],
        'totaldirectcost': direct,
        'totalindirectcost': indirect,
        'totalconstructioncost': direct + indirect,
        'chosensaleprice': chosen.salepricetotal if chosen else None,
        'profitpercent': chosen.profitpercent if chosen else None,
    }


# =============================================================================
# 9. Supply Catalog Router
# =============================================================================

supply_catalog_router = Router(tags=["Supply Catalog"])


@supply_catalog_router.get(
    "/supply-catalog/",
    response=List[SupplyCatalogItemSchema],
)
# TODO: Add @require_permission decorator during integration
def list_supply_catalog_items(
    request: HttpRequest,
    search: Optional[str] = None,
    supplytype: Optional[int] = None,
):
    """List supply catalog items with optional search and type filter."""
    items = SupplyCatalogService.list_items(request.user, search=search, supplytype=supplytype)
    return list(items)


@supply_catalog_router.post(
    "/supply-catalog/",
    response={201: SupplyCatalogItemSchema},
)
# TODO: Add @require_permission decorator during integration
def create_supply_catalog_item(request: HttpRequest, payload: CreateSupplyCatalogItemDto):
    """Create a new supply catalog item."""
    item = SupplyCatalogService.create_item(payload, request.user)
    return 201, item


@supply_catalog_router.patch(
    "/supply-catalog/{item_id}/",
    response=SupplyCatalogItemSchema,
)
# TODO: Add @require_permission decorator during integration
def update_supply_catalog_item(request: HttpRequest, item_id: UUID, payload: UpdateSupplyCatalogItemDto):
    """Update a supply catalog item."""
    item = SupplyCatalogService.update_item(item_id, payload, request.user)
    return item


@supply_catalog_router.delete(
    "/supply-catalog/{item_id}/",
    response=SupplyCatalogItemSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_supply_catalog_item(request: HttpRequest, item_id: UUID):
    """Soft delete a supply catalog item."""
    item = SupplyCatalogService.delete_item(item_id, request.user)
    return item


# =============================================================================
# 10. Equipment Yields Router
# =============================================================================

equipment_yields_router = Router(tags=["Equipment Yields"])


@equipment_yields_router.get(
    "/equipment-yields/",
    response=List[EquipmentYieldSchema],
)
# TODO: Add @require_permission decorator during integration
def list_equipment_yields(
    request: HttpRequest,
    category: Optional[str] = None,
):
    """List equipment yields with optional category filter."""
    yields = EquipmentYieldService.list_yields(request.user, category=category)
    return list(yields)


@equipment_yields_router.post(
    "/equipment-yields/",
    response={201: EquipmentYieldSchema},
)
# TODO: Add @require_permission decorator during integration
def create_equipment_yield(request: HttpRequest, payload: CreateEquipmentYieldDto):
    """Create a new equipment yield record."""
    eq_yield = EquipmentYieldService.create_yield(payload, request.user)
    return 201, eq_yield


@equipment_yields_router.patch(
    "/equipment-yields/{yield_id}/",
    response=EquipmentYieldSchema,
)
# TODO: Add @require_permission decorator during integration
def update_equipment_yield(request: HttpRequest, yield_id: UUID, payload: UpdateEquipmentYieldDto):
    """Update an equipment yield record."""
    eq_yield = EquipmentYieldService.update_yield(yield_id, payload, request.user)
    return eq_yield


@equipment_yields_router.delete(
    "/equipment-yields/{yield_id}/",
    response=EquipmentYieldSchema,
)
# TODO: Add @require_permission decorator during integration
def delete_equipment_yield(request: HttpRequest, yield_id: UUID):
    """Soft delete an equipment yield record."""
    eq_yield = EquipmentYieldService.delete_yield(yield_id, request.user)
    return eq_yield


# =============================================================================
# 11. Indirect Cost Templates Router
# =============================================================================

indirect_cost_templates_router = Router(tags=["Indirect Cost Templates"])


@indirect_cost_templates_router.get(
    "/indirect-cost-templates/",
    response=List[IndirectCostTemplateSchema],
)
# TODO: Add @require_permission decorator during integration
def list_indirect_cost_templates(
    request: HttpRequest,
    projectsize: Optional[int] = None,
):
    """List indirect cost templates, optionally filtered by project size."""
    queryset = IndirectCostTemplate.objects.filter(statecode=0)
    if projectsize is not None:
        queryset = queryset.filter(projectsize=projectsize)
    return list(queryset.select_related('createdby', 'modifiedby'))


# =============================================================================
# 12. Concept Price Catalog Router
# =============================================================================

concept_price_catalog_router = Router(tags=["Concept Price Catalog"])


@concept_price_catalog_router.get(
    "/concept-price-catalog/",
    response=List[ConceptPriceCatalogItemListSchema],
)
def list_concept_price_catalog(
    request: HttpRequest,
    search: Optional[str] = None,
    source: Optional[int] = None,
    unit: Optional[str] = None,
):
    """List concept price catalog items with optional filters."""
    items = ConceptPriceCatalogService.list_items(
        request.user, search=search, source=source, unit=unit,
    )
    return list(items)


# --- Price References (static paths BEFORE {item_id} to avoid routing conflicts) ---

@concept_price_catalog_router.post(
    "/concept-price-catalog/references/",
    response={201: ConceptPriceReferenceSchema},
)
def create_concept_price_reference(
    request: HttpRequest, payload: CreateConceptPriceReferenceDto,
):
    """Create a new price reference."""
    ref = ConceptPriceCatalogService.create_reference(payload, request.user)
    return 201, ref


@concept_price_catalog_router.delete(
    "/concept-price-catalog/references/{reference_id}/",
    response=ConceptPriceReferenceSchema,
)
def delete_concept_price_reference(request: HttpRequest, reference_id: UUID):
    """Soft delete a price reference."""
    return ConceptPriceCatalogService.delete_reference(reference_id, request.user)


# --- Catalog Item CRUD (dynamic {item_id} paths AFTER static paths) ---

@concept_price_catalog_router.get(
    "/concept-price-catalog/{item_id}/",
    response=ConceptPriceCatalogItemSchema,
)
def get_concept_price_catalog_item(request: HttpRequest, item_id: UUID):
    """Get a single catalog item with all its price references."""
    return ConceptPriceCatalogService.get_item(item_id)


@concept_price_catalog_router.post(
    "/concept-price-catalog/",
    response={201: ConceptPriceCatalogItemListSchema},
)
def create_concept_price_catalog_item(
    request: HttpRequest, payload: CreateConceptPriceCatalogItemDto,
):
    """Create a new concept price catalog item."""
    item = ConceptPriceCatalogService.create_item(payload, request.user)
    return 201, item


@concept_price_catalog_router.patch(
    "/concept-price-catalog/{item_id}/",
    response=ConceptPriceCatalogItemListSchema,
)
def update_concept_price_catalog_item(
    request: HttpRequest, item_id: UUID, payload: UpdateConceptPriceCatalogItemDto,
):
    """Update a concept price catalog item."""
    return ConceptPriceCatalogService.update_item(item_id, payload, request.user)


@concept_price_catalog_router.delete(
    "/concept-price-catalog/{item_id}/",
    response=ConceptPriceCatalogItemListSchema,
)
def delete_concept_price_catalog_item(request: HttpRequest, item_id: UUID):
    """Soft delete a concept price catalog item."""
    return ConceptPriceCatalogService.delete_item(item_id, request.user)


@concept_price_catalog_router.get(
    "/concept-price-catalog/{item_id}/references/",
    response=List[ConceptPriceReferenceSchema],
)
def list_concept_price_references(request: HttpRequest, item_id: UUID):
    """List price references for a catalog item."""
    return list(ConceptPriceCatalogService.list_references(item_id))


# =============================================================================
# 13. Family Templates Router
# =============================================================================

family_templates_router = Router(tags=["Family Templates"])


@family_templates_router.get(
    "/family-templates/",
    response=List[FamilyTemplateSetListSchema],
)
def list_family_templates(
    request: HttpRequest, category: Optional[str] = None, search: Optional[str] = None
):
    """List all active family template sets."""
    return list(FamilyTemplateService.list_template_sets(request.user, category=category, search=search))


# Static action paths BEFORE {template_set_id} to avoid routing conflicts
@family_templates_router.post(
    "/family-templates/save-from-project/",
    response={201: FamilyTemplateSetSchema},
)
def save_project_as_template(request: HttpRequest, payload: SaveProjectAsTemplateDto):
    """Save a project's family/subfamily structure as a reusable template."""
    ts = FamilyTemplateService.save_project_as_template(payload, request.user)
    return 201, ts


@family_templates_router.post(
    "/family-templates/apply-to-project/",
    response={201: List[ConceptFamilySchema]},
)
def apply_template_to_project(request: HttpRequest, payload: ApplyFamilyTemplateDto):
    """Apply a family template to a project, creating families and subfamilies."""
    created = FamilyTemplateService.apply_template_to_project(payload, request.user)
    return 201, list(created)


# Dynamic {template_set_id} paths AFTER static paths
@family_templates_router.get(
    "/family-templates/{template_set_id}/",
    response=FamilyTemplateSetSchema,
)
def get_family_template(request: HttpRequest, template_set_id: UUID):
    """Get a single template set with all its items."""
    return FamilyTemplateService.get_template_set(template_set_id, request.user)


@family_templates_router.delete(
    "/family-templates/{template_set_id}/",
    response=FamilyTemplateSetListSchema,
)
def delete_family_template(request: HttpRequest, template_set_id: UUID):
    """Soft-delete a template set. System templates cannot be deleted."""
    return FamilyTemplateService.delete_template_set(template_set_id, request.user)
