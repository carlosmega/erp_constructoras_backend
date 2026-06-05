"""API routers for Proyección (Budget Estimation) module."""

import base64
import json

from ninja import Router, File, UploadedFile
from ninja.errors import HttpError
from typing import List, Optional
from uuid import UUID
from decimal import Decimal
from django.http import HttpRequest

from apps.proyeccion.schemas import (
    EstimationProjectSchema,
    CreateEstimationProjectDto,
    UpdateEstimationProjectDto,
    ConvertEstimationResponseDto,
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
    CduReportSchema,
    IndirectCostDetailSchema,
    CreateIndirectCostDetailDto,
    UpdateIndirectCostDetailDto,
    ComputeBondsOverridesDto,
    SetChecklistStateDto,
    ApplyTemplateDto,
    OfferAlternativeSchema,
    CreateOfferAlternativeDto,
    UpdateOfferAlternativeDto,
    AlternativeBaseCostsSchema,
    SupplyExplosionItemSchema,
    SupplyExplosionConsolidatedSchema,
    SetSupplyLagDto,
    WorkPlanEntrySchema,
    CreateWorkPlanEntryDto,
    UpdateWorkPlanEntryDto,
    BulkWorkPlanDto,
    WorkPlanMatrixSchema,
    WorkPlanSummarySchema,
    TemporalDistributionSchema,
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
    AnalyzeExcelResponseSchema,
    ImportExcelRequestDto,
    ImportExcelResponseSchema,
    AnalyzeConceptExcelResponseSchema,
    ImportConceptExcelRequestDto,
    ImportConceptExcelResponseSchema,
    AnalyzeBreakdownsResponseSchema,
    ImportBreakdownsRequestDto,
    ImportBreakdownsResponseSchema,
    AnalyzeIndirectsResponseSchema,
    ImportIndirectsRequestDto,
    ImportIndirectsResponseSchema,
    AutoGenerateSkeletonDto,
    FinancialSettingsDto,
    UpdateFinancialSettingsDto,
    BillingRuleDto,
    ReplaceBillingRulesDto,
    PNTReportDto,
    ProjectionPeriodDto,
    RegenerateResult,
    DistributionPayloadDto,
    BulkEditRequest,
    BulkEditOkResponse,
    ConflictResponse,
    AutofillRequest,
    AutofillResponse,
    ResetLineRequest,
    PresenceResponse,
    HeartbeatRequest,
)
from apps.proyeccion.services import (
    EstimationConversionService,
    EstimationProjectService,
    ConceptCatalogService,
    ConceptExcelService,
    UnitCostBreakdownService,
    IndirectCostDetailService,
    OfferAlternativeService,
    SupplyExplosionService,
    WorkPlanService,
    TemporalDistributionService,
    SupplyCatalogService,
    EquipmentYieldService,
    ConceptPriceCatalogService,
    FamilyTemplateService,
    EstimationFinancialSettingsService,
    EstimationBillingRuleService,
    EstimationPNTCalculator,
    PeriodService,
    CostDistributionService,
    VersionConflict,
    PresenceService,
)
from apps.proyeccion.models import (
    IndirectCostTemplate,
    EstimationProject,
    ProjectionPeriod,
)
from core.permissions import Permission, require_permission
from core.exceptions import NotFound


# =============================================================================
# Pagination guard
# =============================================================================

# Hard upper bound to prevent ``?limit=999999`` style abuse. Existing callers
# that don't pass any ``limit`` keep the legacy "return everything" behavior.
MAX_LIMIT = 1000


def _apply_limit(items, limit: Optional[int], offset: Optional[int]):
    """Optionally slice an iterable for the heavy list endpoints.

    Backwards-compatible: when ``limit`` is None, returns the full list (legacy
    behavior). When provided, ``limit`` is clamped to ``MAX_LIMIT`` and an
    optional ``offset`` is applied. Used as a defensive guard until proper
    cursor pagination is rolled out (see docs/deuda/007).
    """
    if limit is None and offset is None:
        return items if isinstance(items, list) else list(items)
    start = max(0, offset or 0)
    if limit is None:
        return list(items[start:])
    end = start + max(0, min(limit, MAX_LIMIT))
    return list(items[start:end])


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


@estimation_projects_router.post("/{project_id}/convert/", response=ConvertEstimationResponseDto)
def convert_to_project(request: HttpRequest, project_id: UUID):
    """Convert an accepted estimation into a ConstructionProject.

    Pulls every field (contract amount, anticipo, dates, categories, periods,
    budgets) from the estimation itself; no request body needed. Locks the
    estimation as CONVERTED on success. Returns 409 with ``{projectid}`` if the
    estimation was already converted.
    """
    from apps.budgets.models import CostCategory, CostTypeCode, ImputationCode, ImputationPeriod

    project = EstimationConversionService.convert(project_id, user=request.user)

    summary = {
        'periods_created': ImputationPeriod.objects.filter(projectid=project).count(),
        'direct_codes_created': ImputationCode.objects.filter(
            projectid=project, costtype=CostTypeCode.DIRECT,
        ).count(),
        'indirect_codes_created': ImputationCode.objects.filter(
            projectid=project, costtype=CostTypeCode.INDIRECT,
        ).count(),
        'contract_amount': str(project.contractamount_notax),
    }
    return ConvertEstimationResponseDto(
        projectid=project.projectid,
        projectnumber=project.projectnumber,
        estimation_locked=True,
        summary=summary,
    )


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


@concept_families_router.delete(
    "/concept-subfamilies/{subfamily_id}/",
    response=ConceptSubfamilySchema,
)
# TODO: Add @require_permission decorator during integration
def delete_subfamily(request: HttpRequest, subfamily_id: UUID):
    """Soft delete a concept subfamily."""
    subfamily = ConceptCatalogService.delete_subfamily(subfamily_id, request.user)
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
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """List budget concepts for a project, optionally filtered by subfamily.

    ``limit`` and ``offset`` are optional defensive guards (max ``MAX_LIMIT``).
    Omit both to keep the legacy "return everything" behavior consumers expect.
    """
    concepts = ConceptCatalogService.list_concepts(project_id, request.user, subfamilyid=subfamilyid)
    return _apply_limit(concepts, limit, offset)


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
def list_breakdowns(
    request: HttpRequest,
    concept_id: UUID,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """List all unit cost breakdown lines for a concept.

    ``limit`` and ``offset`` are optional defensive guards (max ``MAX_LIMIT``).
    """
    breakdowns = UnitCostBreakdownService.list_breakdowns(concept_id, request.user)
    return _apply_limit(breakdowns, limit, offset)


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


@budget_concepts_router.post(
    "/concepts/{concept_id}/breakdowns/bulk/",
    response={201: List[UnitCostBreakdownSchema]},
)
def bulk_create_breakdowns(
    request: HttpRequest, concept_id: UUID, payload: List[CreateUnitCostBreakdownDto]
):
    """Create multiple breakdown lines for a concept in a single request."""
    for dto in payload:
        dto.conceptid = concept_id
    lines = UnitCostBreakdownService.bulk_create_breakdowns(concept_id, payload, request.user)
    return 201, lines


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
    "/concepts/{concept_id}/breakdowns/auto-generate-hm-epp/",
    response={201: List[UnitCostBreakdownSchema]},
)
# TODO: Add @require_permission decorator during integration
def auto_generate_hm_epp(request: HttpRequest, concept_id: UUID):
    """Auto generate Minor Tools (HM) and PPE breakdown lines from labor cost."""
    lines = UnitCostBreakdownService.auto_generate_hm_epp(concept_id, request.user)
    return 201, lines


@budget_concepts_router.post(
    "/concepts/{concept_id}/breakdowns/auto-generate-skeleton/",
    response={201: List[UnitCostBreakdownSchema]},
)
def auto_generate_skeleton(request: HttpRequest, concept_id: UUID, payload: AutoGenerateSkeletonDto):
    """Auto-generate skeleton breakdown lines based on subfamily and unit matching rules."""
    lines = UnitCostBreakdownService.auto_generate_skeleton(
        concept_id, payload.subfamilyname, payload.unit, request.user,
        description=payload.description,
    )
    return 201, lines


@budget_concepts_router.post(
    "/breakdowns/{breakdown_id}/duplicate/",
    response={201: UnitCostBreakdownSchema},
)
def duplicate_breakdown_line(request: HttpRequest, breakdown_id: UUID):
    """Duplicate a breakdown line within the same concept and category."""
    service = UnitCostBreakdownService()
    result = service.duplicate_line(breakdown_id, request.user)
    return 201, result


@budget_concepts_router.post(
    "/concepts/{concept_id}/breakdowns/copy-from/{source_concept_id}/",
    response={201: List[UnitCostBreakdownSchema]},
)
def copy_breakdowns_from_concept(
    request: HttpRequest, concept_id: UUID, source_concept_id: UUID
):
    """Copy all breakdown lines from source concept to target concept."""
    service = UnitCostBreakdownService()
    result = service.copy_from_concept(concept_id, source_concept_id, request.user)
    return 201, result


# --- Excel Import Endpoints ---

@budget_concepts_router.get(
    "/projects/{project_id}/concepts/export-excel/",
)
def export_concepts_excel(request: HttpRequest, project_id: UUID):
    """Export all active concepts for a project as an 8-column .xlsx file."""
    from django.http import HttpResponse
    binary = ConceptExcelService.export(project_id, request.user)
    response = HttpResponse(
        binary,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="conceptos-{project_id}.xlsx"'
    )
    return response


@budget_concepts_router.post(
    "/projects/{project_id}/concepts/analyze-excel/",
    response=AnalyzeConceptExcelResponseSchema,
)
def analyze_excel(request: HttpRequest, project_id: UUID, file: UploadedFile = File(...)):
    """Analyze an uploaded 8-column Excel file and classify rows as new/skip/error."""
    return ConceptExcelService.analyze(project_id, file, request.user)


@budget_concepts_router.post(
    "/projects/{project_id}/concepts/import-excel/",
    response=ImportConceptExcelResponseSchema,
)
def import_excel(request: HttpRequest, project_id: UUID, payload: ImportConceptExcelRequestDto):
    """Import new concepts from a previously analyzed 8-column Excel file."""
    return ConceptExcelService.import_(project_id, payload, request.user)


# --- CDU (Unit Cost Breakdown) Excel Endpoints ---

@budget_concepts_router.get(
    "/projects/{project_id}/breakdowns/export-excel/",
)
def export_breakdown_excel(request: HttpRequest, project_id: UUID):
    """Export the project's CDU (unit cost breakdowns) to an .xlsx file."""
    from django.http import HttpResponse
    from apps.proyeccion.services import BreakdownExcelService
    binary = BreakdownExcelService.export(project_id, request.user)
    response = HttpResponse(
        binary,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="cdu-{project_id}.xlsx"'
    )
    return response


@budget_concepts_router.get(
    "/projects/{project_id}/cdu-report/",
    response=CduReportSchema,
)
def cdu_report(request: HttpRequest, project_id: UUID):
    """Full CDU (all concepts + breakdown lines + CDU totals) for PDF/print reports."""
    from apps.proyeccion.services import UnitCostBreakdownService
    return UnitCostBreakdownService.get_project_cdu_report(project_id, request.user)


@budget_concepts_router.post(
    "/projects/{project_id}/breakdowns/analyze-excel/",
    response=AnalyzeBreakdownsResponseSchema,
)
def analyze_breakdown_excel(
    request: HttpRequest,
    project_id: UUID,
    file: UploadedFile = File(...),
):
    """Analyze a CDU Excel file and return a preview without persisting."""
    from apps.proyeccion.services import BreakdownExcelService
    return BreakdownExcelService.analyze(project_id, file, request.user)


@budget_concepts_router.post(
    "/projects/{project_id}/breakdowns/import-excel/",
    response=ImportBreakdownsResponseSchema,
)
def import_breakdown_excel(
    request: HttpRequest,
    project_id: UUID,
    payload: ImportBreakdownsRequestDto,
):
    """Persist a previously analyzed CDU Excel import."""
    from apps.proyeccion.services import BreakdownExcelService
    return BreakdownExcelService.import_(project_id, payload, request.user)


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


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/compute-bonds/",
    response=List[IndirectCostDetailSchema],
)
# TODO: Add @require_permission decorator during integration
def compute_bond_and_tax_lines(request: HttpRequest, project_id: UUID, payload: ComputeBondsOverridesDto):
    """Calcula (upsert) las líneas de fianzas, seguros e impuestos del estudio."""
    lines = IndirectCostDetailService.compute_bond_and_tax_lines(
        project_id, request.user, overrides=payload
    )
    return lines


@indirect_cost_details_router.patch(
    "/indirect-cost-details/{detail_id}/checklist/",
    response=IndirectCostDetailSchema,
)
# TODO: Add @require_permission decorator during integration
def set_indirect_checklist_state(request: HttpRequest, detail_id: UUID, payload: SetChecklistStateDto):
    """Setea applies/percentofsale (vista checklist de externos) y recalcula importe."""
    return IndirectCostDetailService.set_checklist_state(
        detail_id, request.user, applies=payload.applies, percentofsale=payload.percentofsale)


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/seed-externals/",
    response=List[IndirectCostDetailSchema],
)
# TODO: Add @require_permission decorator during integration
def seed_external_checklist(request: HttpRequest, project_id: UUID):
    """Siembra las líneas del checklist de externos (C7/C8) en applies=NA."""
    return IndirectCostDetailService.seed_external_checklist(project_id, request.user)


@indirect_cost_details_router.get(
    "/projects/{project_id}/indirect-cost-details/total/",
    response=Decimal,
)
# TODO: Add @require_permission decorator during integration
def get_indirect_cost_total(request: HttpRequest, project_id: UUID):
    """Get total indirect cost amount for a project."""
    total = IndirectCostDetailService.get_total(project_id, request.user)
    return total


# --- Indirect Costs Excel Round-Trip Endpoints ---


@indirect_cost_details_router.get(
    "/projects/{project_id}/indirect-cost-details/export-excel/",
)
def export_indirect_excel(request: HttpRequest, project_id: UUID):
    """Export the project's indirect costs to an .xlsx file."""
    from django.http import HttpResponse
    from apps.proyeccion.services import IndirectExcelService
    binary = IndirectExcelService.export(project_id, request.user)
    response = HttpResponse(
        binary,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="indirectos-{project_id}.xlsx"'
    )
    return response


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/analyze-excel/",
    response=AnalyzeIndirectsResponseSchema,
)
def analyze_indirect_excel(
    request: HttpRequest,
    project_id: UUID,
    file: UploadedFile = File(...),
):
    """Analyze an indirect costs Excel file and return a preview without persisting."""
    from apps.proyeccion.services import IndirectExcelService
    return IndirectExcelService.analyze(project_id, file, request.user)


@indirect_cost_details_router.post(
    "/projects/{project_id}/indirect-cost-details/import-excel/",
    response=ImportIndirectsResponseSchema,
)
def import_indirect_excel(
    request: HttpRequest,
    project_id: UUID,
    payload: ImportIndirectsRequestDto,
):
    """Persist a previously analyzed indirect costs Excel import (REPLACE strategy)."""
    from apps.proyeccion.services import IndirectExcelService
    return IndirectExcelService.import_(project_id, payload, request.user)


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


@offer_alternatives_router.get(
    "/projects/{project_id}/alternative-base-costs/",
    response=AlternativeBaseCostsSchema,
)
# TODO: Add @require_permission decorator during integration
def get_alternative_base_costs(request: HttpRequest, project_id: UUID):
    """Costos base (directo/indirecto) del proyecto para el resumen en vivo del form."""
    return OfferAlternativeService.get_base_costs(project_id)


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


@supply_explosion_router.patch(
    "/projects/{project_id}/supply-explosion/lag/",
    response=dict,
)
# TODO: Add @require_permission decorator during integration
def set_supply_lag(request: HttpRequest, project_id: UUID, payload: SetSupplyLagDto):
    """Setea el lag de pago de un insumo (bulk a todas sus líneas)."""
    n = SupplyExplosionService.set_supply_lag(
        project_id, payload.supplyid, payload.paymentlagperiods, request.user)
    return {"updated": n}


@supply_explosion_router.get(
    "/projects/{project_id}/supply-explosion/export-excel/",
)
def export_supply_explosion_excel(request: HttpRequest, project_id: UUID):
    """Export both Auxiliar and Consolidado supply explosion views to an .xlsx file.

    Returns a workbook with two sheets:
      - 'Auxiliar': per-concept supply breakdown with full context.
      - 'Consolidado': aggregated supplies with totals and incidence %.
    """
    from django.http import HttpResponse
    binary = SupplyExplosionService.export_excel(project_id, request.user)
    response = HttpResponse(
        binary,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
    response["Content-Disposition"] = (
        f'attachment; filename="explosion-insumos-{project_id}.xlsx"'
    )
    return response


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
    entrytype: Optional[int] = None,
):
    """List work plan entries for a project, optionally filtered by concept and/or entrytype."""
    entries = WorkPlanService.list_entries(
        project_id, request.user, conceptid=conceptid, entrytype=entrytype
    )
    return list(entries)


@workplan_router.get(
    "/projects/{project_id}/workplan/matrix/",
    response=WorkPlanMatrixSchema,
)
def get_workplan_matrix(request: HttpRequest, project_id: UUID):
    """Return the full Plan de Obra matrix (family → subfamily → concept × period).

    Includes planned and actual blocks plus per-family and grand totals (replica of the Excel view).
    """
    return WorkPlanService.get_matrix(project_id, request.user)


@workplan_router.get(
    "/projects/{project_id}/workplan/summary/",
    response=WorkPlanSummarySchema,
)
def get_workplan_summary(request: HttpRequest, project_id: UUID):
    """Return per-family summary: contract, planned, actual amounts + percent advance."""
    return WorkPlanService.get_summary(project_id, request.user)


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
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """List supply catalog items with optional search and type filter.

    ``limit`` and ``offset`` are optional defensive guards (max ``MAX_LIMIT``).
    """
    items = SupplyCatalogService.list_items(request.user, search=search, supplytype=supplytype)
    return _apply_limit(items, limit, offset)


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


# =============================================================================
# 14. Temporal Distribution Router
# =============================================================================

distribution_router = Router(tags=["Temporal Distribution"])


@distribution_router.get(
    "/projects/{project_id}/projection-periods/",
    response=List[ProjectionPeriodDto],
)
def list_projection_periods(request: HttpRequest, project_id: UUID):
    """List all projection periods for an estimation project."""
    EstimationProjectService.get_project(project_id, request.user)  # raises NotFound if missing
    return list(
        ProjectionPeriod.objects.filter(projectid=project_id).order_by('periodnumber')
    )


@distribution_router.post(
    "/projects/{project_id}/projection-periods/regenerate/",
    response={200: RegenerateResult, 400: dict, 409: dict},
)
def regenerate_projection_periods(request: HttpRequest, project_id: UUID, confirm: bool = False):
    """Regenerate periods from estimatedstart/end + periodtype. Idempotent.

    Returns 409 if manual edits would be lost and confirm=false.
    """
    project = EstimationProjectService.get_project(project_id, request.user)
    try:
        result = PeriodService.regenerate_projection_periods(project, confirm=confirm)
    except ValueError as e:
        msg = str(e)
        if 'manual distribution edits' in msg:
            return 409, {'error': 'confirm_required', 'detail': msg}
        return 400, {'error': 'invalid', 'detail': msg}
    return 200, result


@distribution_router.get(
    "/projects/{project_id}/cost-distribution/",
    response=DistributionPayloadDto,
)
def get_cost_distribution(request: HttpRequest, project_id: UUID):
    """Full distribution matrix + rollups for the project."""
    project = EstimationProjectService.get_project(project_id, request.user)
    return CostDistributionService.build_payload(project)


@distribution_router.patch(
    "/projects/{project_id}/cost-distribution/bulk/",
    response={200: BulkEditOkResponse, 409: ConflictResponse, 400: dict},
)
def patch_cost_distribution_bulk(request: HttpRequest, project_id: UUID, payload: BulkEditRequest):
    """Apply multiple cell edits and/or per-line lag edits atomically."""
    project = EstimationProjectService.get_project(project_id, request.user)
    edits = [{
        'lineid': str(e.lineid), 'linetype': e.linetype, 'periodnumber': e.periodnumber,
        'fraction': e.fraction, 'expected_version': e.expected_version,
    } for e in payload.edits]
    lag_edits = [{
        'lineid': str(le.lineid), 'linetype': le.linetype,
        'paymentlagperiods': le.paymentlagperiods,
        'expected_lineversion': le.expected_lineversion,
    } for le in payload.lag_edits]
    try:
        result = CostDistributionService.apply_bulk_edits(
            project, user=request.user, edits=edits, lag_edits=lag_edits,
        )
    except VersionConflict as exc:
        return 409, {'error': 'version_conflict', 'conflicts': exc.conflicts}
    except ValueError as exc:
        return 400, {'error': 'invalid', 'detail': str(exc)}
    rebuilt = CostDistributionService.build_payload(project)
    return 200, {
        'updated': result['updated'],
        'new_versions': result['new_versions'],
        'lag_updated': result['lag_updated'],
        'new_lineversions': result['new_lineversions'],
        'rollups': rebuilt['rollups'],
        'totals': rebuilt['totals'],
    }


@distribution_router.post(
    "/projects/{project_id}/cost-distribution/autofill/",
    response={200: AutofillResponse, 400: dict},
)
def autofill_cost_distribution(request: HttpRequest, project_id: UUID, payload: AutofillRequest):
    """Fill distribution automatically with a given strategy + scope."""
    project = EstimationProjectService.get_project(project_id, request.user)
    try:
        result = CostDistributionService.autofill(
            project,
            strategy=payload.strategy,
            only_empty=payload.only_empty,
            scope=payload.scope,
        )
    except ValueError as e:
        return 400, {'error': 'invalid', 'detail': str(e)}
    rebuilt = CostDistributionService.build_payload(project)
    return 200, {
        'lines_affected': result['lines_affected'],
        'warnings': result['warnings'],
        'rollups': rebuilt['rollups'],
        'totals': rebuilt['totals'],
    }


@distribution_router.post(
    "/projects/{project_id}/cost-distribution/reset-line/",
    response={200: dict},
)
def reset_cost_distribution_line(request: HttpRequest, project_id: UUID, payload: ResetLineRequest):
    """Revert a line to derived values (discards manual edits for that line)."""
    project = EstimationProjectService.get_project(project_id, request.user)
    result = CostDistributionService.reset_line(
        project, lineid=str(payload.lineid), linetype=payload.linetype,
    )
    return 200, result


@distribution_router.get(
    "/projects/{project_id}/cost-distribution/presence/",
    response=PresenceResponse,
)
def get_presence(request: HttpRequest, project_id: UUID):
    """List active users viewing/editing the distribution tab."""
    project = EstimationProjectService.get_project(project_id, request.user)
    actives = PresenceService.list_active(project)
    return {
        'active_users': [
            {
                'userid': str(p.userid.systemuserid),
                'username': str(p.userid),
                'mode': p.mode,
                'last_seen': p.last_seen,
            }
            for p in actives
        ]
    }


@distribution_router.post(
    "/projects/{project_id}/cost-distribution/presence/heartbeat/",
    response={200: dict},
)
def presence_heartbeat(request: HttpRequest, project_id: UUID, payload: HeartbeatRequest):
    """Refresh user presence; call every ~30s from the frontend."""
    project = EstimationProjectService.get_project(project_id, request.user)
    PresenceService.heartbeat(project, request.user, mode=payload.mode)
    return 200, {'ok': True}


# =============================================================================
# 15. Estimation PNT (Cashflow) Router — financial settings, billing rules, PNT
# =============================================================================

pnt_router = Router(tags=["Estimation PNT (Cashflow)"])


def _serialize_settings(s) -> dict:
    return {
        'settingsid': s.settingsid,
        'projectid': s.projectid_id,
        'advanceamountnotax': s.advanceamountnotax,
        'advanceentryperiod': s.advanceentryperiod,
        'advanceamortizationrate': s.advanceamortizationrate,
        'imssretentionrate': s.imssretentionrate,
        'otherretentionrate': s.otherretentionrate,
        'retentionreturnperiod': s.retentionreturnperiod,
        'directpaymentlag': s.directpaymentlag,
        'indirectpaymentlag': s.indirectpaymentlag,
        'financecostrate': s.financecostrate,
        'createdon': s.createdon,
        'modifiedon': s.modifiedon,
    }


@pnt_router.get(
    "/projects/{project_id}/financial-settings/",
    response=FinancialSettingsDto,
)
@require_permission(Permission.ESTIMATION_PNT_READ)
def get_financial_settings(request: HttpRequest, project_id: UUID):
    """Get (or lazily create with defaults) the financial settings for a project."""
    try:
        EstimationProject.objects.get(pk=project_id)
    except EstimationProject.DoesNotExist:
        raise NotFound(f"EstimationProject with ID {project_id} not found")
    settings = EstimationFinancialSettingsService.get_or_create(project_id)
    return _serialize_settings(settings)


@pnt_router.patch(
    "/projects/{project_id}/financial-settings/",
    response=FinancialSettingsDto,
)
@require_permission(Permission.ESTIMATION_PNT_UPDATE_SETTINGS)
def patch_financial_settings(
    request: HttpRequest, project_id: UUID, payload: UpdateFinancialSettingsDto
):
    """Update whitelisted financial settings fields for a project."""
    try:
        EstimationProject.objects.get(pk=project_id)
    except EstimationProject.DoesNotExist:
        raise NotFound(f"EstimationProject with ID {project_id} not found")
    dto = payload.dict(exclude_unset=True)
    updated = EstimationFinancialSettingsService.update(project_id, dto, user=request.user)
    return _serialize_settings(updated)


def _serialize_rule(r) -> dict:
    return {
        'sequence': r.sequence,
        'percent': r.percent,
        'lagperiods': r.lagperiods,
    }


@pnt_router.get(
    "/projects/{project_id}/billing-rules/",
    response=list[BillingRuleDto],
)
@require_permission(Permission.ESTIMATION_PNT_READ)
def get_billing_rules(request: HttpRequest, project_id: UUID):
    """List billing rules for a project (ordered by sequence)."""
    try:
        EstimationProject.objects.get(pk=project_id)
    except EstimationProject.DoesNotExist:
        raise NotFound(f"EstimationProject with ID {project_id} not found")
    rules = EstimationBillingRuleService.list(project_id)
    return [_serialize_rule(r) for r in rules]


@pnt_router.put(
    "/projects/{project_id}/billing-rules/",
    response=list[BillingRuleDto],
)
@require_permission(Permission.ESTIMATION_PNT_UPDATE_BILLING_RULES)
def put_billing_rules(
    request: HttpRequest, project_id: UUID, payload: ReplaceBillingRulesDto
):
    """Replace the full set of billing rules for a project (atomic, validates Σ=100%)."""
    try:
        EstimationProject.objects.get(pk=project_id)
    except EstimationProject.DoesNotExist:
        raise NotFound(f"EstimationProject with ID {project_id} not found")
    try:
        rules = EstimationBillingRuleService.replace(
            project_id,
            [r.dict() for r in payload.rules],
            user=request.user,
        )
    except ValueError as e:
        raise HttpError(400, str(e))
    return [_serialize_rule(r) for r in rules]


def _serialize_pnt_report(report) -> dict:
    return {
        'projectid': report.projectid,
        'granularity': report.granularity,
        'periods': report.periods,
        'rows': [
            {
                'code': r.code,
                'label': r.label,
                'section': r.section,
                'values': r.values,
                'emphasis': r.emphasis,
                'out_of_horizon': r.out_of_horizon,
                'total': r.total,
            }
            for r in report.rows
        ],
        'stats': report.stats,
        'generated_at': report.generated_at,
    }


@pnt_router.get(
    "/projects/{project_id}/pnt/",
    response=PNTReportDto,
)
@require_permission(Permission.ESTIMATION_PNT_READ)
def get_pnt(
    request: HttpRequest,
    project_id: UUID,
    granularity: str = 'period',
    overrides: str | None = None,
):
    """Compute the PNT report. 409 when no periods. Optional base64-JSON overrides."""
    try:
        EstimationProject.objects.get(pk=project_id)
    except EstimationProject.DoesNotExist:
        raise NotFound(f"EstimationProject with ID {project_id} not found")
    overrides_dict = None
    if overrides:
        try:
            overrides_dict = json.loads(base64.b64decode(overrides).decode())
        except Exception:
            raise HttpError(400, 'overrides must be base64-encoded JSON')
    try:
        calc = EstimationPNTCalculator(project_id)
    except ValueError as e:
        # No periods → 409
        raise HttpError(409, json.dumps({'detail': str(e), 'code': 'no_periods'}))
    try:
        report = calc.compute(overrides=overrides_dict, granularity=granularity)
    except ValueError as e:
        raise HttpError(400, str(e))
    return _serialize_pnt_report(report)
