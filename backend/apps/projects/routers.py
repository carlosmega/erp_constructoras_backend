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
)
from apps.projects.services import (
    ProjectService, ZoneService, SupplierService, TeamMemberService,
)


# ============================================================================
# Projects Router
# ============================================================================

projects_router = Router(tags=["Projects"])


@projects_router.get("/", response=List[ConstructionProjectSchema])
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def list_projects(
    request: HttpRequest,
    statecode: Optional[int] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
):
    """List construction projects with filtering."""
    owner_uuid = UUID(ownerid) if ownerid else None
    projects = ProjectService.list_projects(
        user=request.user, statecode=statecode, search=search, ownerid=owner_uuid
    )
    return list(projects)


@projects_router.post("/", response={201: ConstructionProjectSchema})
# TODO: Add @require_permission(Permission.PROJECT_CREATE) when permissions are registered
def create_project(request: HttpRequest, payload: CreateProjectDto):
    """Create a new construction project."""
    project = ProjectService.create_project(payload, request.user)
    return 201, project


@projects_router.get("/search/", response=List[ConstructionProjectSchema])
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def search_projects(request: HttpRequest, q: Optional[str] = None):
    """Search projects by name, number, or account name."""
    projects = ProjectService.search_projects(q or '', request.user)
    return list(projects)


@projects_router.get("/{project_id}", response=ConstructionProjectSchema)
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def get_project(request: HttpRequest, project_id: UUID):
    """Get a construction project by ID."""
    project = ProjectService.get_project_by_id(project_id, request.user)
    return project


@projects_router.patch("/{project_id}", response=ConstructionProjectSchema)
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def update_project(request: HttpRequest, project_id: UUID, payload: UpdateProjectDto):
    """Update a construction project."""
    project = ProjectService.update_project(project_id, payload, request.user)
    return project


@projects_router.delete("/{project_id}", response={204: None})
# TODO: Add @require_permission(Permission.PROJECT_DELETE) when permissions are registered
def delete_project(request: HttpRequest, project_id: UUID):
    """Soft delete a construction project (set to Canceled)."""
    ProjectService.delete_project(project_id, request.user)
    return 204, None


# ============================================================================
# Zones Router
# ============================================================================

zones_router = Router(tags=["Project Zones"])


@projects_router.get("/{project_id}/zones/", response=List[ProjectZoneSchema])
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def list_zones(request: HttpRequest, project_id: UUID):
    """List all zones for a project."""
    zones = ZoneService.list_zones(project_id, request.user)
    return list(zones)


@projects_router.post("/{project_id}/zones/", response={201: ProjectZoneSchema})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def create_zone(request: HttpRequest, project_id: UUID, payload: CreateZoneDto):
    """Create a new zone within a project."""
    payload.projectid = project_id
    zone = ZoneService.create_zone(payload, request.user)
    return 201, zone


@zones_router.patch("/{zone_id}", response=ProjectZoneSchema)
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def update_zone(request: HttpRequest, zone_id: UUID, payload: UpdateZoneDto):
    """Update a zone."""
    zone = ZoneService.update_zone(zone_id, payload, request.user)
    return zone


@zones_router.delete("/{zone_id}", response={204: None})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def delete_zone(request: HttpRequest, zone_id: UUID):
    """Soft delete a zone."""
    ZoneService.delete_zone(zone_id, request.user)
    return 204, None


# ============================================================================
# Suppliers Router
# ============================================================================

suppliers_router = Router(tags=["Project Suppliers"])


@projects_router.get("/{project_id}/suppliers/", response=List[ProjectSupplierSchema])
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def list_suppliers(request: HttpRequest, project_id: UUID):
    """List all suppliers for a project."""
    suppliers = SupplierService.list_suppliers(project_id, request.user)
    return list(suppliers)


@projects_router.post("/{project_id}/suppliers/", response={201: ProjectSupplierSchema})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def add_supplier(request: HttpRequest, project_id: UUID, payload: CreateSupplierDto):
    """Add a supplier to a project."""
    payload.projectid = project_id
    supplier = SupplierService.add_supplier(payload, request.user)
    return 201, supplier


@suppliers_router.delete("/{supplier_id}", response={204: None})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def remove_supplier(request: HttpRequest, supplier_id: UUID):
    """Soft delete a supplier."""
    SupplierService.remove_supplier(supplier_id, request.user)
    return 204, None


# ============================================================================
# Team Members Router
# ============================================================================

team_members_router = Router(tags=["Project Team Members"])


@projects_router.get("/{project_id}/team-members/", response=List[ProjectTeamMemberSchema])
# TODO: Add @require_permission(Permission.PROJECT_READ) when permissions are registered
def list_team_members(request: HttpRequest, project_id: UUID):
    """List all team members for a project."""
    members = TeamMemberService.list_team_members(project_id, request.user)
    return list(members)


@projects_router.post("/{project_id}/team-members/", response={201: ProjectTeamMemberSchema})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def add_team_member(request: HttpRequest, project_id: UUID, payload: CreateTeamMemberDto):
    """Add a team member to a project."""
    payload.projectid = project_id
    member = TeamMemberService.add_team_member(payload, request.user)
    return 201, member


@team_members_router.patch("/{member_id}", response=ProjectTeamMemberSchema)
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def update_team_member(request: HttpRequest, member_id: UUID, payload: UpdateTeamMemberDto):
    """Update a team member."""
    member = TeamMemberService.update_team_member(member_id, payload, request.user)
    return member


@team_members_router.delete("/{member_id}", response={204: None})
# TODO: Add @require_permission(Permission.PROJECT_UPDATE) when permissions are registered
def remove_team_member(request: HttpRequest, member_id: UUID):
    """Hard delete a team member."""
    TeamMemberService.remove_team_member(member_id, request.user)
    return 204, None
