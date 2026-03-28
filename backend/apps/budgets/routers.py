"""API routers for Budget Management."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.budgets.schemas import (
    CostCategorySchema,
    CreateCostCategoryDto,
    UpdateCostCategoryDto,
    ImputationCodeSchema,
    CreateImputationCodeDto,
    UpdateImputationCodeDto,
    ImputationPeriodSchema,
    ExtendPeriodsDto,
)
from apps.budgets.services import (
    CostCategoryService,
    ImputationCodeService,
    PeriodService,
)
from core.permissions import require_permission, Permission


# =============================================================================
# Categories Router
# =============================================================================

categories_router = Router(tags=["Cost Categories"])


@categories_router.get("/projects/{project_id}/categories/", response=List[CostCategorySchema])
@require_permission(Permission.BUDGET_READ)
def list_categories(request: HttpRequest, project_id: UUID):
    """List all cost categories for a project."""
    categories = CostCategoryService.list_categories(project_id, request.user)
    return list(categories)


@categories_router.post("/projects/{project_id}/categories/", response={201: List[CostCategorySchema]})
@require_permission(Permission.BUDGET_CREATE)
def create_or_seed_categories(request: HttpRequest, project_id: UUID, payload: Optional[CreateCostCategoryDto] = None):
    """Create a single category or seed all defaults (if no payload)."""
    if payload:
        category = CostCategoryService.create_category(payload, request.user)
        return 201, [category]
    else:
        categories = CostCategoryService.seed_default_categories(project_id, request.user)
        return 201, categories


# =============================================================================
# Imputation Codes Router
# =============================================================================

imputation_codes_router = Router(tags=["Imputation Codes"])


@imputation_codes_router.get("/projects/{project_id}/codes/", response=List[ImputationCodeSchema])
@require_permission(Permission.BUDGET_READ)
def list_codes(
    request: HttpRequest,
    project_id: UUID,
    costtype: Optional[int] = None,
    categoryid: Optional[UUID] = None,
    zoneid: Optional[UUID] = None,
):
    """List imputation codes for a project with optional filtering."""
    codes = ImputationCodeService.list_codes(
        project_id, request.user, costtype=costtype, categoryid=categoryid, zoneid=zoneid
    )
    return list(codes)


@imputation_codes_router.post("/projects/{project_id}/codes/", response={201: ImputationCodeSchema})
@require_permission(Permission.BUDGET_CREATE)
def create_code(request: HttpRequest, project_id: UUID, payload: CreateImputationCodeDto):
    """Create a new imputation code."""
    code = ImputationCodeService.create_code(payload, request.user)
    return 201, code


@imputation_codes_router.get("/codes/{code_id}/", response=ImputationCodeSchema)
@require_permission(Permission.BUDGET_READ)
def get_code(request: HttpRequest, code_id: UUID):
    """Get an imputation code by ID."""
    code = ImputationCodeService.get_code_by_id(code_id, request.user)
    return code


@imputation_codes_router.patch("/codes/{code_id}/", response=ImputationCodeSchema)
@require_permission(Permission.BUDGET_UPDATE)
def update_code(request: HttpRequest, code_id: UUID, payload: UpdateImputationCodeDto):
    """Update an imputation code."""
    code = ImputationCodeService.update_code(code_id, payload, request.user)
    return code


# =============================================================================
# Periods Router
# =============================================================================

periods_router = Router(tags=["Imputation Periods"])


@periods_router.get("/projects/{project_id}/periods/", response=List[ImputationPeriodSchema])
@require_permission(Permission.BUDGET_READ)
def list_periods(request: HttpRequest, project_id: UUID):
    """List all periods for a project."""
    periods = PeriodService.list_periods(project_id, request.user)
    return list(periods)


@periods_router.post("/projects/{project_id}/periods/init/", response={201: List[ImputationPeriodSchema]})
@require_permission(Permission.BUDGET_CREATE)
def initialize_periods(request: HttpRequest, project_id: UUID):
    """Initialize periods for a project based on start/end dates."""
    periods = PeriodService.initialize_periods(project_id, request.user)
    return 201, periods


@periods_router.post("/projects/{project_id}/periods/extend/", response={201: List[ImputationPeriodSchema]})
@require_permission(Permission.BUDGET_CREATE)
def extend_periods(request: HttpRequest, project_id: UUID, payload: ExtendPeriodsDto):
    """Extend periods by N months."""
    periods = PeriodService.extend_periods(project_id, payload.months, request.user)
    return 201, periods


@periods_router.patch("/periods/{period_id}/close/", response=ImputationPeriodSchema)
@require_permission(Permission.BUDGET_UPDATE)
def close_period(request: HttpRequest, period_id: UUID):
    """Close a period."""
    period = PeriodService.close_period(period_id, request.user)
    return period


@periods_router.patch("/periods/{period_id}/reopen/", response=ImputationPeriodSchema)
@require_permission(Permission.BUDGET_UPDATE)
def reopen_period(request: HttpRequest, period_id: UUID):
    """Reopen a closed period."""
    period = PeriodService.reopen_period(period_id, request.user)
    return period
