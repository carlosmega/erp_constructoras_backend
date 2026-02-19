"""
API routers (endpoints) for Lead Management.

Implements REST API endpoints using Django Ninja.
Routers are thin - they call services for business logic.

Phase 5 Implementation (User Story 3)
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.leads.schemas import (
    LeadSchema,
    LeadListSchema,
    CreateLeadDto,
    UpdateLeadDto,
    QualifyLeadDto,
    DisqualifyLeadDto,
    LeadStatsSchema,
)
from apps.leads.services import LeadService
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import (
    require_permission,
    require_authenticated,
    Permission
)
from core.pagination import paginate_queryset, create_paginated_response

PaginatedLeadList = create_paginated_response(LeadListSchema)

# ============================================================================
# Leads Router
# ============================================================================

leads_router = Router(tags=["Leads"])


@leads_router.get("/", response=PaginatedLeadList)
@require_permission(Permission.LEAD_READ)
def list_leads(
    request: HttpRequest,
    page: int = 1,
    page_size: int = 50,
    statecode: Optional[int] = None,
    statuscode: Optional[int] = None,
    leadqualitycode: Optional[int] = None,
    leadsourcecode: Optional[int] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
):
    """
    List leads with filtering and pagination.
    Requires: LEAD_READ permission

    Args:
        request: HTTP request
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (default: 50, max: 100)
        statecode: Filter by state code (optional)
        statuscode: Filter by status code (optional)
        leadqualitycode: Filter by quality rating (optional)
        leadsourcecode: Filter by source (optional)
        search: Search in fullname, email, company (optional)
        ownerid: Filter by owner UUID (optional, admin/manager only)

    Returns:
        Paginated list of leads
    """
    # Convert ownerid string to UUID if provided
    owner_uuid = UUID(ownerid) if ownerid else None

    leads = LeadService.list_leads(
        user=request.user,
        statecode=statecode,
        statuscode=statuscode,
        leadqualitycode=leadqualitycode,
        leadsourcecode=leadsourcecode,
        search=search,
        ownerid=owner_uuid,
    )

    return paginate_queryset(leads, page=page, page_size=page_size, request_url=request.path)


@leads_router.post("/", response={201: LeadSchema})
@require_permission(Permission.LEAD_CREATE)
def create_lead(request: HttpRequest, payload: CreateLeadDto):
    """
    Create new lead.
    Requires: LEAD_CREATE permission

    Args:
        request: HTTP request
        payload: Lead creation data

    Returns:
        Created LeadSchema

    Raises:
        ValidationError: If validation fails
    """
    lead = LeadService.create_lead(payload, request.user)
    return 201, lead


@leads_router.get("/stats", response=LeadStatsSchema)
@require_permission(Permission.LEAD_READ)
def get_lead_stats(request: HttpRequest):
    """
    Get lead statistics for dashboard.
    Requires: LEAD_READ permission

    Args:
        request: HTTP request

    Returns:
        LeadStatsSchema with aggregated statistics
    """
    stats = LeadService.get_lead_stats(request.user)
    return stats


@leads_router.get("/{lead_id}", response=LeadSchema)
@require_permission(Permission.LEAD_READ)
def get_lead(request: HttpRequest, lead_id: UUID):
    """
    Get lead by ID.
    Requires: LEAD_READ permission

    Args:
        request: HTTP request
        lead_id: UUID of lead

    Returns:
        LeadSchema

    Raises:
        NotFound: If lead doesn't exist
        PermissionDenied: If user doesn't have access
    """
    lead = LeadService.get_lead_by_id(lead_id, request.user)
    return lead


@leads_router.patch("/{lead_id}", response=LeadSchema)
@require_permission(Permission.LEAD_UPDATE)
def update_lead(request: HttpRequest, lead_id: UUID, payload: UpdateLeadDto):
    """
    Update lead.
    Requires: LEAD_UPDATE permission

    Args:
        request: HTTP request
        lead_id: UUID of lead
        payload: Update data (partial)

    Returns:
        Updated LeadSchema

    Raises:
        NotFound: If lead doesn't exist
        PermissionDenied: If user doesn't have access
        ValidationError: If validation fails or lead is not in Open state
    """
    lead = LeadService.update_lead(lead_id, payload, request.user)
    return lead


@leads_router.delete("/{lead_id}", response={204: None})
@require_permission(Permission.LEAD_DELETE)
def delete_lead(request: HttpRequest, lead_id: UUID):
    """
    Delete lead (soft delete by disqualifying).
    Requires: LEAD_DELETE permission

    Args:
        request: HTTP request
        lead_id: UUID of lead

    Raises:
        NotFound: If lead doesn't exist
        PermissionDenied: If user doesn't have access
    """
    LeadService.delete_lead(lead_id, request.user)
    return 204, None


@leads_router.post("/{lead_id}/qualify", response=LeadSchema)
@require_permission(Permission.LEAD_QUALIFY)
def qualify_lead(request: HttpRequest, lead_id: UUID, payload: QualifyLeadDto):
    """
    Qualify a lead (convert to Opportunity).
    Requires: LEAD_QUALIFY permission

    Creates Account and/or Contact if requested, then creates Opportunity.
    Sets lead state to Qualified.

    Args:
        request: HTTP request
        lead_id: UUID of lead
        payload: Qualification parameters

    Returns:
        Updated LeadSchema with qualifyingopportunityid set

    Raises:
        NotFound: If lead doesn't exist
        PermissionDenied: If user doesn't have access
        ValidationError: If lead cannot be qualified
    """
    lead = LeadService.qualify_lead(lead_id, payload, request.user)

    return lead


@leads_router.post("/{lead_id}/disqualify", response=LeadSchema)
@require_permission(Permission.LEAD_UPDATE)
def disqualify_lead(request: HttpRequest, lead_id: UUID, payload: DisqualifyLeadDto):
    """
    Disqualify a lead (mark as lost/cannot contact/not interested).
    Requires: LEAD_UPDATE permission

    Args:
        request: HTTP request
        lead_id: UUID of lead
        payload: Disqualification parameters

    Returns:
        Updated LeadSchema

    Raises:
        NotFound: If lead doesn't exist
        PermissionDenied: If user doesn't have access
        ValidationError: If lead cannot be disqualified or invalid status code
    """
    lead = LeadService.disqualify_lead(lead_id, payload, request.user)

    return lead
