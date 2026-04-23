"""
API routers (endpoints) for Opportunity Management.
Phase 6 Implementation
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.opportunities.schemas import (
    OpportunitySchema,
    CreateOpportunityDto,
    UpdateOpportunityDto,
    CloseOpportunityDto,
    OpportunityStatsSchema,
)
from apps.opportunities.services import OpportunityService
from core.pagination import paginate_queryset, create_paginated_response
from core.permissions import require_permission, Permission

opportunities_router = Router(tags=["Opportunities"])

PaginatedOpportunityList = create_paginated_response(OpportunitySchema)


@opportunities_router.get("/", response=List[OpportunitySchema])
@require_permission(Permission.OPPORTUNITY_READ)
def list_opportunities(
    request: HttpRequest,
    statecode: Optional[int] = None,
    salesstage: Optional[int] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
):
    """List opportunities with filtering. Requires: OPPORTUNITY_READ permission"""
    owner_uuid = UUID(ownerid) if ownerid else None
    opps = OpportunityService.list_opportunities(
        user=request.user, statecode=statecode, salesstage=salesstage,
        search=search, ownerid=owner_uuid
    )
    return list(opps)


@opportunities_router.get("/paginated/", response=PaginatedOpportunityList)
@require_permission(Permission.OPPORTUNITY_READ)
def list_opportunities_paginated(
    request: HttpRequest,
    page: int = 1,
    page_size: int = 50,
    statecode: Optional[int] = None,
    salesstage: Optional[int] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
):
    """List opportunities with offset-based pagination (opt-in alternative to `/`)."""
    owner_uuid = UUID(ownerid) if ownerid else None
    queryset = OpportunityService.list_opportunities(
        user=request.user, statecode=statecode, salesstage=salesstage,
        search=search, ownerid=owner_uuid,
    )
    return paginate_queryset(queryset, page=page, page_size=page_size, request_url=request.path)


@opportunities_router.post("/", response={201: OpportunitySchema})
@require_permission(Permission.OPPORTUNITY_CREATE)
def create_opportunity(request: HttpRequest, payload: CreateOpportunityDto):
    """Create new opportunity. Requires: OPPORTUNITY_CREATE permission"""
    opp = OpportunityService.create_opportunity(payload, request.user)
    return 201, opp


@opportunities_router.get("/stats", response=OpportunityStatsSchema)
@require_permission(Permission.OPPORTUNITY_READ)
def get_opportunity_stats(request: HttpRequest):
    """Get opportunity statistics. Requires: OPPORTUNITY_READ permission"""
    stats = OpportunityService.get_opportunity_stats(request.user)
    return stats


@opportunities_router.get("/{opportunity_id}", response=OpportunitySchema)
@require_permission(Permission.OPPORTUNITY_READ)
def get_opportunity(request: HttpRequest, opportunity_id: UUID):
    """Get opportunity by ID. Requires: OPPORTUNITY_READ permission"""
    opp = OpportunityService.get_opportunity_by_id(opportunity_id, request.user)
    return opp


@opportunities_router.patch("/{opportunity_id}", response=OpportunitySchema)
@require_permission(Permission.OPPORTUNITY_UPDATE)
def update_opportunity(request: HttpRequest, opportunity_id: UUID, payload: UpdateOpportunityDto):
    """Update opportunity. Requires: OPPORTUNITY_UPDATE permission"""
    opp = OpportunityService.update_opportunity(opportunity_id, payload, request.user)
    return opp


@opportunities_router.delete("/{opportunity_id}", response={204: None})
@require_permission(Permission.OPPORTUNITY_DELETE)
def delete_opportunity(request: HttpRequest, opportunity_id: UUID):
    """Delete opportunity. Requires: OPPORTUNITY_DELETE permission"""
    OpportunityService.delete_opportunity(opportunity_id, request.user)
    return 204, None


@opportunities_router.post("/{opportunity_id}/close", response=OpportunitySchema)
@require_permission(Permission.OPPORTUNITY_CLOSE)
def close_opportunity(request: HttpRequest, opportunity_id: UUID, payload: CloseOpportunityDto):
    """Close opportunity (Win/Loss). Requires: OPPORTUNITY_CLOSE permission"""
    opp = OpportunityService.close_opportunity(opportunity_id, payload, request.user)
    return opp
