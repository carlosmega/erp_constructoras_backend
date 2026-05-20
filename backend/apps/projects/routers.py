"""API routers for Construction Project Management."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from apps.projects.schemas import (
    ConstructionProjectSchema, CreateProjectDto, UpdateProjectDto,
    ProjectZoneSchema, CreateZoneDto, UpdateZoneDto,
    ProjectSupplierSchema, CreateSupplierDto,
    ProjectTeamMemberSchema, CreateTeamMemberDto, UpdateTeamMemberDto,
    ProjectRiskSchema, CreateRiskDto, UpdateRiskDto,
    ProjectAssetUsageSchema, CreateAssetUsageDto, UpdateAssetUsageDto,
    ExecutiveSummarySchema,
)
from apps.projects.services import (
    ProjectService, ZoneService, SupplierService, TeamMemberService,
    RiskService, AssetUsageService, ExecutiveSummaryService,
)
from core.permissions import require_permission, Permission


# ============================================================================
# Projects Router
# ============================================================================

projects_router = Router(tags=["Projects"])


@projects_router.get("/", response=List[ConstructionProjectSchema])
@require_permission(Permission.PROJECT_READ)
def list_projects(
    request: HttpRequest,
    statecode: Optional[int] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
    accountid: Optional[str] = None,
):
    """List construction projects with filtering."""
    owner_uuid = UUID(ownerid) if ownerid else None
    projects = ProjectService.list_projects(
        user=request.user, statecode=statecode, search=search, ownerid=owner_uuid
    )
    if accountid:
        projects = projects.filter(accountid_id=accountid)
    return list(projects)


@projects_router.post("/", response={201: ConstructionProjectSchema})
@require_permission(Permission.PROJECT_CREATE)
def create_project(request: HttpRequest, payload: CreateProjectDto):
    """Create a new construction project."""
    project = ProjectService.create_project(payload, request.user)
    return 201, project


@projects_router.get("/search/", response=List[ConstructionProjectSchema])
@require_permission(Permission.PROJECT_READ)
def search_projects(request: HttpRequest, q: Optional[str] = None):
    """Search projects by name, number, or account name."""
    projects = ProjectService.search_projects(q or '', request.user)
    return list(projects)


@projects_router.get("/{project_id}", response=ConstructionProjectSchema)
@require_permission(Permission.PROJECT_READ)
def get_project(request: HttpRequest, project_id: UUID):
    """Get a construction project by ID."""
    project = ProjectService.get_project_by_id(project_id, request.user)
    return project


@projects_router.patch("/{project_id}", response=ConstructionProjectSchema)
@require_permission(Permission.PROJECT_UPDATE)
def update_project(request: HttpRequest, project_id: UUID, payload: UpdateProjectDto):
    """Update a construction project."""
    project = ProjectService.update_project(project_id, payload, request.user)
    return project


@projects_router.delete("/{project_id}", response={204: None})
@require_permission(Permission.PROJECT_DELETE)
def delete_project(request: HttpRequest, project_id: UUID):
    """Soft delete a construction project (set to Canceled)."""
    ProjectService.delete_project(project_id, request.user)
    return 204, None


# ============================================================================
# Zones Router
# ============================================================================

zones_router = Router(tags=["Project Zones"])


@projects_router.get("/{project_id}/zones/", response=List[ProjectZoneSchema])
@require_permission(Permission.PROJECT_READ)
def list_zones(request: HttpRequest, project_id: UUID):
    """List all zones for a project."""
    zones = ZoneService.list_zones(project_id, request.user)
    return list(zones)


@projects_router.post("/{project_id}/zones/", response={201: ProjectZoneSchema})
@require_permission(Permission.PROJECT_UPDATE)
def create_zone(request: HttpRequest, project_id: UUID, payload: CreateZoneDto):
    """Create a new zone within a project."""
    payload.projectid = project_id
    zone = ZoneService.create_zone(payload, request.user)
    return 201, zone


@zones_router.patch("/{zone_id}", response=ProjectZoneSchema)
@require_permission(Permission.PROJECT_UPDATE)
def update_zone(request: HttpRequest, zone_id: UUID, payload: UpdateZoneDto):
    """Update a zone."""
    zone = ZoneService.update_zone(zone_id, payload, request.user)
    return zone


@zones_router.delete("/{zone_id}", response={204: None})
@require_permission(Permission.PROJECT_UPDATE)
def delete_zone(request: HttpRequest, zone_id: UUID):
    """Soft delete a zone."""
    ZoneService.delete_zone(zone_id, request.user)
    return 204, None


# ============================================================================
# Suppliers Router
# ============================================================================

suppliers_router = Router(tags=["Project Suppliers"])


@projects_router.get("/{project_id}/suppliers/", response=List[ProjectSupplierSchema])
@require_permission(Permission.PROJECT_READ)
def list_suppliers(request: HttpRequest, project_id: UUID):
    """List all suppliers for a project."""
    suppliers = SupplierService.list_suppliers(project_id, request.user)
    return list(suppliers)


@projects_router.post("/{project_id}/suppliers/", response={201: ProjectSupplierSchema})
@require_permission(Permission.PROJECT_UPDATE)
def add_supplier(request: HttpRequest, project_id: UUID, payload: CreateSupplierDto):
    """Add a supplier to a project."""
    payload.projectid = project_id
    supplier = SupplierService.add_supplier(payload, request.user)
    return 201, supplier


@suppliers_router.delete("/{supplier_id}", response={204: None})
@require_permission(Permission.PROJECT_UPDATE)
def remove_supplier(request: HttpRequest, supplier_id: UUID):
    """Soft delete a supplier."""
    SupplierService.remove_supplier(supplier_id, request.user)
    return 204, None


# ============================================================================
# Team Members Router
# ============================================================================

team_members_router = Router(tags=["Project Team Members"])


@projects_router.get("/{project_id}/team-members/", response=List[ProjectTeamMemberSchema])
@require_permission(Permission.PROJECT_READ)
def list_team_members(request: HttpRequest, project_id: UUID):
    """List all team members for a project."""
    members = TeamMemberService.list_team_members(project_id, request.user)
    return list(members)


@projects_router.post("/{project_id}/team-members/", response={201: ProjectTeamMemberSchema})
@require_permission(Permission.PROJECT_UPDATE)
def add_team_member(request: HttpRequest, project_id: UUID, payload: CreateTeamMemberDto):
    """Add a team member to a project."""
    payload.projectid = project_id
    member = TeamMemberService.add_team_member(payload, request.user)
    return 201, member


@team_members_router.patch("/{member_id}", response=ProjectTeamMemberSchema)
@require_permission(Permission.PROJECT_UPDATE)
def update_team_member(request: HttpRequest, member_id: UUID, payload: UpdateTeamMemberDto):
    """Update a team member."""
    member = TeamMemberService.update_team_member(member_id, payload, request.user)
    return member


@team_members_router.delete("/{member_id}", response={204: None})
@require_permission(Permission.PROJECT_UPDATE)
def remove_team_member(request: HttpRequest, member_id: UUID):
    """Hard delete a team member."""
    TeamMemberService.remove_team_member(member_id, request.user)
    return 204, None


# ============================================================================
# Risks Router  (mounted under /projects/{project_id}/risks/)
# ============================================================================

risks_router = Router(tags=["Project Risks"])


@projects_router.get("/{project_id}/risks/", response=List[ProjectRiskSchema])
@require_permission(Permission.PROJECT_READ)
def list_risks(request: HttpRequest, project_id: UUID):
    """List all risks for a project."""
    return RiskService.list_risks(project_id)


@projects_router.post("/{project_id}/risks/", response={201: ProjectRiskSchema})
@require_permission(Permission.PROJECT_UPDATE)
def create_risk(request: HttpRequest, project_id: UUID, payload: CreateRiskDto):
    """Add a risk to a project."""
    payload.projectid = project_id
    risk = RiskService.create_risk(payload, request.user)
    return 201, risk


@risks_router.patch("/{risk_id}", response=ProjectRiskSchema)
@require_permission(Permission.PROJECT_UPDATE)
def update_risk(request: HttpRequest, risk_id: UUID, payload: UpdateRiskDto):
    """Update a project risk."""
    return RiskService.update_risk(risk_id, payload, request.user)


@risks_router.delete("/{risk_id}", response={204: None})
@require_permission(Permission.PROJECT_UPDATE)
def delete_risk(request: HttpRequest, risk_id: UUID):
    """Delete a project risk."""
    RiskService.delete_risk(risk_id)
    return 204, None


# ============================================================================
# Asset Usages Router  (mounted under /projects/{project_id}/asset-usages/)
# ============================================================================

asset_usages_router = Router(tags=["Project Asset Usages"])


@projects_router.get("/{project_id}/asset-usages/", response=List[ProjectAssetUsageSchema])
@require_permission(Permission.PROJECT_READ)
def list_asset_usages(request: HttpRequest, project_id: UUID):
    """List all asset usages for a project."""
    return AssetUsageService.list_asset_usages(project_id)


@projects_router.post("/{project_id}/asset-usages/", response={201: ProjectAssetUsageSchema})
@require_permission(Permission.PROJECT_UPDATE)
def create_asset_usage(request: HttpRequest, project_id: UUID, payload: CreateAssetUsageDto):
    """Add an asset usage to a project."""
    payload.projectid = project_id
    usage = AssetUsageService.create_asset_usage(payload, request.user)
    return 201, usage


@asset_usages_router.patch("/{usage_id}", response=ProjectAssetUsageSchema)
@require_permission(Permission.PROJECT_UPDATE)
def update_asset_usage(request: HttpRequest, usage_id: UUID, payload: UpdateAssetUsageDto):
    """Update a project asset usage."""
    return AssetUsageService.update_asset_usage(usage_id, payload, request.user)


@asset_usages_router.delete("/{usage_id}", response={204: None})
@require_permission(Permission.PROJECT_UPDATE)
def delete_asset_usage(request: HttpRequest, usage_id: UUID):
    """Delete a project asset usage."""
    AssetUsageService.delete_asset_usage(usage_id)
    return 204, None


# ============================================================================
# Executive Summary endpoint
# ============================================================================

@projects_router.get("/{project_id}/executive-summary/", response=ExecutiveSummarySchema)
@require_permission(Permission.PROJECT_READ)
def get_executive_summary(request: HttpRequest, project_id: UUID):
    """Compute and return the executive summary for a construction project."""
    return ExecutiveSummaryService.compute(project_id)
