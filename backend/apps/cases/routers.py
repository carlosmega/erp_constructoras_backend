"""
API routers (endpoints) for Case Management.

Implements REST API endpoints using Django Ninja.
Routers are thin - they call services for business logic.
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.cases.schemas import (
    CaseSchema,
    CaseListItemSchema,
    CreateCaseDto,
    UpdateCaseDto,
    ResolveCaseDto,
    CancelCaseDto,
)
from apps.cases.services import CaseService
from core.permissions import require_permission, Permission


# ============================================================================
# Cases Router
# ============================================================================

cases_router = Router(tags=["Cases"])


@cases_router.get("/", response=List[CaseListItemSchema])
@require_permission(Permission.CASE_READ)
def list_cases(
    request: HttpRequest,
    statecode: Optional[int] = None,
    search: Optional[str] = None,
):
    """
    List cases with filtering.
    Requires: CASE_READ permission
    """
    cases = CaseService.list_cases(
        user=request.user,
        search=search,
        statecode=statecode,
    )
    return list(cases)


@cases_router.post("/", response={201: CaseSchema})
@require_permission(Permission.CASE_CREATE)
def create_case(request: HttpRequest, payload: CreateCaseDto):
    """
    Create new case.
    Requires: CASE_CREATE permission
    """
    case = CaseService.create_case(payload, request.user)
    return 201, case


@cases_router.get("/{case_id}", response=CaseSchema)
@require_permission(Permission.CASE_READ)
def get_case(request: HttpRequest, case_id: UUID):
    """
    Get case by ID.
    Requires: CASE_READ permission
    """
    case = CaseService.get_case_by_id(case_id, request.user)
    return case


@cases_router.patch("/{case_id}", response=CaseSchema)
@require_permission(Permission.CASE_UPDATE)
def update_case(request: HttpRequest, case_id: UUID, payload: UpdateCaseDto):
    """
    Update case.
    Requires: CASE_UPDATE permission
    """
    case = CaseService.update_case(case_id, payload, request.user)
    return case


@cases_router.delete("/{case_id}", response={204: None})
@require_permission(Permission.CASE_DELETE)
def delete_case(request: HttpRequest, case_id: UUID):
    """
    Delete case (soft delete by cancelling).
    Requires: CASE_DELETE permission
    """
    CaseService.delete_case(case_id, request.user)
    return 204, None


@cases_router.post("/{case_id}/resolve", response=CaseSchema)
@require_permission(Permission.CASE_UPDATE)
def resolve_case(request: HttpRequest, case_id: UUID, payload: ResolveCaseDto):
    """
    Resolve a case.
    Requires: CASE_UPDATE permission
    """
    case = CaseService.resolve_case(case_id, payload, request.user)
    return case


@cases_router.post("/{case_id}/cancel", response=CaseSchema)
@require_permission(Permission.CASE_UPDATE)
def cancel_case(request: HttpRequest, case_id: UUID, payload: CancelCaseDto):
    """
    Cancel a case.
    Requires: CASE_UPDATE permission
    """
    case = CaseService.cancel_case(case_id, payload, request.user)
    return case


@cases_router.post("/{case_id}/reopen", response=CaseSchema)
@require_permission(Permission.CASE_UPDATE)
def reopen_case(request: HttpRequest, case_id: UUID):
    """
    Reopen a resolved or cancelled case.
    Requires: CASE_UPDATE permission
    """
    case = CaseService.reopen_case(case_id, request.user)
    return case
