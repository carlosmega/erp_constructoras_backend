"""Construction Project business logic service layer."""

from typing import Optional
from uuid import UUID
from datetime import date
from django.db import models
from django.db.models import Q, QuerySet
from apps.projects.models import (
    ConstructionProject, ProjectStateCode,
    ProjectTeamMember, ProjectRoleCode,
    ProjectZone, ZoneStateCode,
    ProjectSupplier, SupplierStateCode,
)
from apps.projects.schemas import (
    CreateProjectDto, UpdateProjectDto,
    CreateTeamMemberDto, UpdateTeamMemberDto,
    CreateZoneDto, UpdateZoneDto,
    CreateSupplierDto,
)
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import filter_by_ownership


# ============================================================================
# ProjectService
# ============================================================================

class ProjectService:
    """Service class for ConstructionProject entity business logic."""

    @staticmethod
    def list_projects(
        user: SystemUser,
        statecode: Optional[int] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
    ) -> QuerySet[ConstructionProject]:
        """List projects with filtering."""
        queryset = ConstructionProject.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if ownerid:
            if user.role_name not in ["System Administrator", "Sales Manager"]:
                raise PermissionDenied("You cannot view other users' projects")
            queryset = queryset.filter(ownerid=ownerid)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(projectnumber__icontains=search) |
                Q(accountid__name__icontains=search)
            )

        return queryset.select_related(
            'ownerid', 'accountid', 'opportunityid', 'createdby', 'modifiedby'
        ).prefetch_related('teammembers')

    @staticmethod
    def create_project(dto: CreateProjectDto, user: SystemUser) -> ConstructionProject:
        """Create a new construction project."""
        from apps.accounts.models import Account

        # Validate account exists
        try:
            account = Account.objects.get(accountid=dto.accountid)
        except Account.DoesNotExist:
            raise ValidationError(f"Account with ID {dto.accountid} not found")

        # Validate opportunity if provided
        opportunity = None
        if dto.opportunityid:
            from apps.opportunities.models import Opportunity
            try:
                opportunity = Opportunity.objects.get(opportunityid=dto.opportunityid)
            except Opportunity.DoesNotExist:
                raise ValidationError(f"Opportunity with ID {dto.opportunityid} not found")

        # Resolve owner
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        project_number = ProjectService.generate_project_number()

        project = ConstructionProject(
            projectnumber=project_number,
            name=dto.name,
            description=dto.description,
            statecode=ProjectStateCode.DRAFT,
            accountid=account,
            opportunityid=opportunity,
            presentationdate=dto.presentationdate,
            awarddate=dto.awarddate,
            startdate=dto.startdate,
            contractenddate=dto.contractenddate,
            expectedenddate=dto.expectedenddate,
            durationmonths=dto.durationmonths,
            projecttype=dto.projecttype,
            biddingtype=dto.biddingtype,
            contractamount_notax=dto.contractamount_notax,
            contractamount_withtax=dto.contractamount_withtax,
            advancepayment_notax=dto.advancepayment_notax,
            advancepayment_withtax=dto.advancepayment_withtax,
            exchangerate_mxn_usd=dto.exchangerate_mxn_usd,
            projectemail=dto.projectemail,
            emailprotocol=dto.emailprotocol,
            periodtype=dto.periodtype,
            alertthreshold_warning=dto.alertthreshold_warning,
            alertthreshold_critical=dto.alertthreshold_critical,
            alertthreshold_exceeded=dto.alertthreshold_exceeded,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )

        # Flatten bond fields
        if dto.advancebond:
            project.advancebond_amount = dto.advancebond.amount
            project.advancebond_policycost = dto.advancebond.policycost
            project.advancebond_validitystartdate = dto.advancebond.validitystartdate
            project.advancebond_validityenddate = dto.advancebond.validityenddate
        if dto.completionbond:
            project.completionbond_amount = dto.completionbond.amount
            project.completionbond_policycost = dto.completionbond.policycost
            project.completionbond_validitystartdate = dto.completionbond.validitystartdate
            project.completionbond_validityenddate = dto.completionbond.validityenddate
        if dto.defectsbond:
            project.defectsbond_amount = dto.defectsbond.amount
            project.defectsbond_policycost = dto.defectsbond.policycost
            project.defectsbond_validitystartdate = dto.defectsbond.validitystartdate
            project.defectsbond_validityenddate = dto.defectsbond.validityenddate

        project.save()
        return project

    @staticmethod
    def get_project_by_id(project_id: UUID, user: SystemUser) -> ConstructionProject:
        """Get project by ID with ownership check."""
        try:
            project = ConstructionProject.objects.select_related(
                'ownerid', 'accountid', 'opportunityid', 'createdby', 'modifiedby'
            ).prefetch_related('teammembers').get(projectid=project_id)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project with ID {project_id} not found")

        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this project")

        return project

    @staticmethod
    def update_project(project_id: UUID, dto: UpdateProjectDto, user: SystemUser) -> ConstructionProject:
        """Update an existing project (partial update)."""
        project = ProjectService.get_project_by_id(project_id, user)

        simple_fields = [
            'name', 'description', 'statecode',
            'presentationdate', 'awarddate', 'startdate', 'contractenddate',
            'expectedenddate', 'durationmonths',
            'projecttype', 'biddingtype',
            'contractamount_notax', 'contractamount_withtax',
            'advancepayment_notax', 'advancepayment_withtax',
            'exchangerate_mxn_usd',
            'projectemail', 'emailconfigured', 'emailprotocol',
            'periodtype',
            'alertthreshold_warning', 'alertthreshold_critical', 'alertthreshold_exceeded',
        ]

        for field in simple_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(project, field, value)

        # Handle account FK update
        if dto.accountid is not None:
            from apps.accounts.models import Account
            try:
                account = Account.objects.get(accountid=dto.accountid)
            except Account.DoesNotExist:
                raise ValidationError(f"Account with ID {dto.accountid} not found")
            project.accountid = account

        # Handle opportunity FK update
        if dto.opportunityid is not None:
            from apps.opportunities.models import Opportunity
            try:
                opportunity = Opportunity.objects.get(opportunityid=dto.opportunityid)
            except Opportunity.DoesNotExist:
                raise ValidationError(f"Opportunity with ID {dto.opportunityid} not found")
            project.opportunityid = opportunity

        # Handle bond updates
        if dto.advancebond is not None:
            project.advancebond_amount = dto.advancebond.amount
            project.advancebond_policycost = dto.advancebond.policycost
            project.advancebond_validitystartdate = dto.advancebond.validitystartdate
            project.advancebond_validityenddate = dto.advancebond.validityenddate
        if dto.completionbond is not None:
            project.completionbond_amount = dto.completionbond.amount
            project.completionbond_policycost = dto.completionbond.policycost
            project.completionbond_validitystartdate = dto.completionbond.validitystartdate
            project.completionbond_validityenddate = dto.completionbond.validityenddate
        if dto.defectsbond is not None:
            project.defectsbond_amount = dto.defectsbond.amount
            project.defectsbond_policycost = dto.defectsbond.policycost
            project.defectsbond_validitystartdate = dto.defectsbond.validitystartdate
            project.defectsbond_validityenddate = dto.defectsbond.validityenddate

        project.modifiedby = user
        project.save()
        return project

    @staticmethod
    def delete_project(project_id: UUID, user: SystemUser) -> ConstructionProject:
        """Soft delete a project (set statecode to Canceled)."""
        project = ProjectService.get_project_by_id(project_id, user)
        project.statecode = ProjectStateCode.CANCELED
        project.modifiedby = user
        project.save()
        return project

    @staticmethod
    def search_projects(query: str, user: SystemUser) -> QuerySet[ConstructionProject]:
        """Search projects by name, number, or account name."""
        queryset = ConstructionProject.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(projectnumber__icontains=query) |
                Q(accountid__name__icontains=query)
            )

        return queryset.select_related(
            'ownerid', 'accountid', 'opportunityid', 'createdby', 'modifiedby'
        ).prefetch_related('teammembers')

    @staticmethod
    def generate_project_number() -> str:
        """Auto-generate project number in PRY-YYYY-NNN format."""
        current_year = date.today().year
        prefix = f"PRY-{current_year}-"

        last_project = (
            ConstructionProject.objects
            .filter(projectnumber__startswith=prefix)
            .order_by('-projectnumber')
            .first()
        )

        if last_project:
            last_seq = int(last_project.projectnumber.split('-')[-1])
            next_seq = last_seq + 1
        else:
            next_seq = 1

        return f"{prefix}{next_seq:03d}"


# ============================================================================
# ZoneService
# ============================================================================

class ZoneService:
    """Service class for ProjectZone entity business logic."""

    @staticmethod
    def list_zones(project_id: UUID, user: SystemUser) -> QuerySet[ProjectZone]:
        """List all zones for a project."""
        # Validate project access
        ProjectService.get_project_by_id(project_id, user)
        return ProjectZone.objects.filter(projectid=project_id).order_by('sortorder', 'name')

    @staticmethod
    def create_zone(dto: CreateZoneDto, user: SystemUser) -> ProjectZone:
        """Create a new zone within a project."""
        project = ProjectService.get_project_by_id(dto.projectid, user)

        # Validate prefix is uppercase and max 3 chars
        prefix = dto.prefix.upper()
        if len(prefix) > 3:
            raise ValidationError("Zone prefix must be at most 3 characters")

        # Check unique prefix within project
        if ProjectZone.objects.filter(projectid=project, prefix=prefix).exists():
            raise ValidationError(f"Zone with prefix '{prefix}' already exists in this project")

        # Auto-set sortorder if not provided
        sortorder = dto.sortorder
        if sortorder is None:
            max_order = (
                ProjectZone.objects
                .filter(projectid=project)
                .aggregate(max_order=models.Max('sortorder'))
            )['max_order']
            sortorder = (max_order or 0) + 1

        zone = ProjectZone(
            projectid=project,
            name=dto.name,
            prefix=prefix,
            description=dto.description,
            sortorder=sortorder,
            createdby=user,
            modifiedby=user,
        )
        zone.save()
        return zone

    @staticmethod
    def get_zone_by_id(zone_id: UUID, user: SystemUser) -> ProjectZone:
        """Get zone by ID with project ownership check."""
        try:
            zone = ProjectZone.objects.select_related('projectid__ownerid').get(zoneid=zone_id)
        except ProjectZone.DoesNotExist:
            raise NotFound(f"Zone with ID {zone_id} not found")

        # Check project ownership
        project = zone.projectid
        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this zone")

        return zone

    @staticmethod
    def update_zone(zone_id: UUID, dto: UpdateZoneDto, user: SystemUser) -> ProjectZone:
        """Update a zone."""
        zone = ZoneService.get_zone_by_id(zone_id, user)

        if dto.name is not None:
            zone.name = dto.name
        if dto.description is not None:
            zone.description = dto.description
        if dto.statecode is not None:
            zone.statecode = dto.statecode
        if dto.sortorder is not None:
            zone.sortorder = dto.sortorder
        if dto.prefix is not None:
            new_prefix = dto.prefix.upper()
            if len(new_prefix) > 3:
                raise ValidationError("Zone prefix must be at most 3 characters")
            # Check uniqueness excluding current zone
            if (ProjectZone.objects
                    .filter(projectid=zone.projectid, prefix=new_prefix)
                    .exclude(zoneid=zone_id)
                    .exists()):
                raise ValidationError(f"Zone with prefix '{new_prefix}' already exists in this project")
            zone.prefix = new_prefix

        zone.modifiedby = user
        zone.save()
        return zone

    @staticmethod
    def delete_zone(zone_id: UUID, user: SystemUser) -> ProjectZone:
        """Soft delete a zone (set statecode to Inactive)."""
        zone = ZoneService.get_zone_by_id(zone_id, user)
        zone.statecode = ZoneStateCode.INACTIVE
        zone.modifiedby = user
        zone.save()
        return zone


# ============================================================================
# SupplierService
# ============================================================================

class SupplierService:
    """Service class for ProjectSupplier entity business logic."""

    @staticmethod
    def list_suppliers(project_id: UUID, user: SystemUser) -> QuerySet[ProjectSupplier]:
        """List all suppliers for a project."""
        ProjectService.get_project_by_id(project_id, user)
        return ProjectSupplier.objects.filter(
            projectid=project_id
        ).select_related('accountid').order_by('suppliernumber')

    @staticmethod
    def add_supplier(dto: CreateSupplierDto, user: SystemUser) -> ProjectSupplier:
        """Add a supplier to a project."""
        from apps.accounts.models import Account

        project = ProjectService.get_project_by_id(dto.projectid, user)

        # Validate account exists
        try:
            account = Account.objects.get(accountid=dto.accountid)
        except Account.DoesNotExist:
            raise ValidationError(f"Account with ID {dto.accountid} not found")

        # Check unique RFC within project
        if ProjectSupplier.objects.filter(projectid=project, rfc=dto.rfc).exists():
            raise ValidationError(f"Supplier with RFC '{dto.rfc}' already exists in this project")

        # Auto-generate supplier number
        max_number = (
            ProjectSupplier.objects
            .filter(projectid=project)
            .aggregate(max_num=models.Max('suppliernumber'))
        )['max_num']
        next_number = (max_number or 0) + 1

        supplier = ProjectSupplier(
            projectid=project,
            accountid=account,
            suppliernumber=next_number,
            rfc=dto.rfc,
            businessname=dto.businessname,
            notes=dto.notes,
            createdby=user,
            modifiedby=user,
        )
        supplier.save()
        return supplier

    @staticmethod
    def get_supplier_by_id(supplier_id: UUID, user: SystemUser) -> ProjectSupplier:
        """Get supplier by ID with project ownership check."""
        try:
            supplier = ProjectSupplier.objects.select_related(
                'projectid__ownerid', 'accountid'
            ).get(projectsupplierid=supplier_id)
        except ProjectSupplier.DoesNotExist:
            raise NotFound(f"Supplier with ID {supplier_id} not found")

        project = supplier.projectid
        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this supplier")

        return supplier

    @staticmethod
    def remove_supplier(supplier_id: UUID, user: SystemUser) -> ProjectSupplier:
        """Soft delete a supplier (set statecode to Inactive)."""
        supplier = SupplierService.get_supplier_by_id(supplier_id, user)
        supplier.statecode = SupplierStateCode.INACTIVE
        supplier.modifiedby = user
        supplier.save()
        return supplier


# ============================================================================
# TeamMemberService
# ============================================================================

class TeamMemberService:
    """Service class for ProjectTeamMember entity business logic."""

    @staticmethod
    def list_team_members(project_id: UUID, user: SystemUser) -> QuerySet[ProjectTeamMember]:
        """List all team members for a project."""
        ProjectService.get_project_by_id(project_id, user)
        return ProjectTeamMember.objects.filter(projectid=project_id).order_by('name')

    @staticmethod
    def add_team_member(dto: CreateTeamMemberDto, user: SystemUser) -> ProjectTeamMember:
        """Add a team member to a project."""
        project = ProjectService.get_project_by_id(dto.projectid, user)

        # Validate role
        valid_roles = [choice.value for choice in ProjectRoleCode]
        if dto.role not in valid_roles:
            raise ValidationError(f"Invalid role '{dto.role}'. Must be one of: {valid_roles}")

        member = ProjectTeamMember(
            projectid=project,
            name=dto.name,
            role=dto.role,
            phone=dto.phone,
            email=dto.email,
            createdby=user,
            modifiedby=user,
        )
        member.save()
        return member

    @staticmethod
    def get_team_member_by_id(member_id: UUID, user: SystemUser) -> ProjectTeamMember:
        """Get team member by ID with project ownership check."""
        try:
            member = ProjectTeamMember.objects.select_related(
                'projectid__ownerid'
            ).get(teammemberid=member_id)
        except ProjectTeamMember.DoesNotExist:
            raise NotFound(f"Team member with ID {member_id} not found")

        project = member.projectid
        if user.role_name not in ["System Administrator", "Sales Manager"]:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this team member")

        return member

    @staticmethod
    def update_team_member(member_id: UUID, dto: UpdateTeamMemberDto, user: SystemUser) -> ProjectTeamMember:
        """Update a team member."""
        member = TeamMemberService.get_team_member_by_id(member_id, user)

        if dto.name is not None:
            member.name = dto.name
        if dto.role is not None:
            valid_roles = [choice.value for choice in ProjectRoleCode]
            if dto.role not in valid_roles:
                raise ValidationError(f"Invalid role '{dto.role}'. Must be one of: {valid_roles}")
            member.role = dto.role
        if dto.phone is not None:
            member.phone = dto.phone
        if dto.email is not None:
            member.email = dto.email

        member.modifiedby = user
        member.save()
        return member

    @staticmethod
    def remove_team_member(member_id: UUID, user: SystemUser) -> None:
        """Hard delete a team member."""
        member = TeamMemberService.get_team_member_by_id(member_id, user)
        member.delete()
