"""Construction Project business logic service layer."""

from typing import Optional
from uuid import UUID
from datetime import date
from django.db import models
from django.db.models import Q, QuerySet, Prefetch
from core.numbering import create_with_retry
from apps.projects.models import (
    ConstructionProject, ProjectStateCode,
    ProjectTeamMember, ProjectRoleCode,
    ProjectZone, ZoneStateCode,
    ProjectSupplier, SupplierStateCode,
    ProjectRisk, RiskStatusCode,
    ProjectAssetUsage, AssetCategoryCode,
)
from apps.projects.schemas import (
    CreateProjectDto, UpdateProjectDto,
    CreateTeamMemberDto, UpdateTeamMemberDto,
    CreateZoneDto, UpdateZoneDto,
    CreateSupplierDto,
    CreateRiskDto, UpdateRiskDto,
    CreateAssetUsageDto, UpdateAssetUsageDto,
)
from apps.users.models import SystemUser
from apps.audit.services import audit_action
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.roles import ADMIN_ROLES
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
            if user.role_name not in ADMIN_ROLES:
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
        ).prefetch_related(
            Prefetch('teammembers', queryset=ProjectTeamMember.objects.select_related('systemuserid'))
        )

    @staticmethod
    @audit_action(action='create', entity='project', id_field='projectid')
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

        project = ConstructionProject(
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
        if dto.carinsurance:
            project.carinsurance_amount = dto.carinsurance.amount
            project.carinsurance_policycost = dto.carinsurance.policycost
            project.carinsurance_validitystartdate = dto.carinsurance.validitystartdate
            project.carinsurance_validityenddate = dto.carinsurance.validityenddate
        if dto.liabilityinsurance:
            project.liabilityinsurance_amount = dto.liabilityinsurance.amount
            project.liabilityinsurance_policycost = dto.liabilityinsurance.policycost
            project.liabilityinsurance_validitystartdate = dto.liabilityinsurance.validitystartdate
            project.liabilityinsurance_validityenddate = dto.liabilityinsurance.validityenddate

        # Assign the number + save under retry so a concurrent collision on the
        # unique projectnumber resolves to the next free value (core.numbering).
        def _save():
            project.projectnumber = ProjectService.generate_project_number()
            project.save()
            return project

        return create_with_retry(_save)

    @staticmethod
    def get_project_by_id(project_id: UUID, user: SystemUser) -> ConstructionProject:
        """Get project by ID with ownership check."""
        try:
            project = ConstructionProject.objects.select_related(
                'ownerid', 'accountid', 'opportunityid', 'createdby', 'modifiedby'
            ).prefetch_related(
            Prefetch('teammembers', queryset=ProjectTeamMember.objects.select_related('systemuserid'))
        ).get(projectid=project_id)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project with ID {project_id} not found")

        if user.role_name not in ADMIN_ROLES:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this project")

        return project

    @staticmethod
    @audit_action(action='update', entity='project', record_arg='project_id', id_field='projectid')
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
        if dto.carinsurance is not None:
            project.carinsurance_amount = dto.carinsurance.amount
            project.carinsurance_policycost = dto.carinsurance.policycost
            project.carinsurance_validitystartdate = dto.carinsurance.validitystartdate
            project.carinsurance_validityenddate = dto.carinsurance.validityenddate
        if dto.liabilityinsurance is not None:
            project.liabilityinsurance_amount = dto.liabilityinsurance.amount
            project.liabilityinsurance_policycost = dto.liabilityinsurance.policycost
            project.liabilityinsurance_validitystartdate = dto.liabilityinsurance.validitystartdate
            project.liabilityinsurance_validityenddate = dto.liabilityinsurance.validityenddate

        project.modifiedby = user
        project.save()
        return project

    @staticmethod
    @audit_action(action='delete', entity='project', record_arg='project_id', id_field='projectid')
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
        ).prefetch_related(
            Prefetch('teammembers', queryset=ProjectTeamMember.objects.select_related('systemuserid'))
        )

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
        if user.role_name not in ADMIN_ROLES:
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
        from apps.accounts.models import Account, CustomerTypeCode

        project = ProjectService.get_project_by_id(dto.projectid, user)

        # Resolve account
        if dto.create_account and dto.accountid is None:
            # Create a new Account marked as Supplier
            account = Account(
                name=dto.businessname,
                customertypecode=CustomerTypeCode.SUPPLIER,
                ownerid=user,
                createdby=user,
                modifiedby=user,
            )
            account.save()
        elif dto.accountid is not None:
            # Use existing account
            try:
                account = Account.objects.get(accountid=dto.accountid)
            except Account.DoesNotExist:
                raise ValidationError(f"Account with ID {dto.accountid} not found")
            # If account was Customer, upgrade to Both
            if account.customertypecode == CustomerTypeCode.CUSTOMER:
                account.customertypecode = CustomerTypeCode.BOTH
                account.save()
        else:
            raise ValidationError("Either accountid or create_account must be provided")

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
        if user.role_name not in ADMIN_ROLES:
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
        return ProjectTeamMember.objects.filter(
            projectid=project_id
        ).select_related('systemuserid').order_by('systemuserid__fullname')

    @staticmethod
    def add_team_member(dto: CreateTeamMemberDto, user: SystemUser) -> ProjectTeamMember:
        """Add a team member to a project."""
        project = ProjectService.get_project_by_id(dto.projectid, user)

        # Validate role
        valid_roles = [choice.value for choice in ProjectRoleCode]
        if dto.role not in valid_roles:
            raise ValidationError(f"Invalid role '{dto.role}'. Must be one of: {valid_roles}")

        # Validate SystemUser exists
        try:
            system_user = SystemUser.objects.get(systemuserid=dto.systemuserid)
        except SystemUser.DoesNotExist:
            raise ValidationError(f"User with ID {dto.systemuserid} not found")

        # Validate uniqueness within project
        if ProjectTeamMember.objects.filter(projectid=project, systemuserid=system_user).exists():
            raise ValidationError(f"User '{system_user.fullname}' is already a member of this project")

        member = ProjectTeamMember(
            projectid=project,
            systemuserid=system_user,
            role=dto.role,
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
                'projectid__ownerid', 'systemuserid'
            ).get(teammemberid=member_id)
        except ProjectTeamMember.DoesNotExist:
            raise NotFound(f"Team member with ID {member_id} not found")

        project = member.projectid
        if user.role_name not in ADMIN_ROLES:
            if project.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this team member")

        return member

    @staticmethod
    def update_team_member(member_id: UUID, dto: UpdateTeamMemberDto, user: SystemUser) -> ProjectTeamMember:
        """Update a team member."""
        member = TeamMemberService.get_team_member_by_id(member_id, user)

        if dto.role is not None:
            valid_roles = [choice.value for choice in ProjectRoleCode]
            if dto.role not in valid_roles:
                raise ValidationError(f"Invalid role '{dto.role}'. Must be one of: {valid_roles}")
            member.role = dto.role

        member.modifiedby = user
        member.save()
        return member

    @staticmethod
    def remove_team_member(member_id: UUID, user: SystemUser) -> None:
        """Hard delete a team member."""
        member = TeamMemberService.get_team_member_by_id(member_id, user)
        member.delete()


# ============================================================================
# RiskService
# ============================================================================

class RiskService:
    """CRUD service for ProjectRisk."""

    @staticmethod
    def create_risk(dto: CreateRiskDto, user: SystemUser) -> ProjectRisk:
        try:
            project = ConstructionProject.objects.get(pk=dto.projectid)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project {dto.projectid} not found")
        return ProjectRisk.objects.create(
            projectid=project,
            description=dto.description,
            production_variance=dto.production_variance or 0,
            cost_variance=dto.cost_variance or 0,
            result_variance=dto.result_variance or 0,
            statuscode=RiskStatusCode.OPEN,
            createdby=user,
            modifiedby=user,
        )

    @staticmethod
    def list_risks(project_id: UUID) -> list:
        return list(ProjectRisk.objects.filter(projectid_id=project_id))

    @staticmethod
    def get_risk(risk_id: UUID) -> ProjectRisk:
        try:
            return ProjectRisk.objects.get(pk=risk_id)
        except ProjectRisk.DoesNotExist:
            raise NotFound(f"Risk {risk_id} not found")

    @staticmethod
    def update_risk(risk_id: UUID, dto: UpdateRiskDto, user: SystemUser) -> ProjectRisk:
        risk = RiskService.get_risk(risk_id)
        if dto.description is not None:
            risk.description = dto.description
        if dto.production_variance is not None:
            risk.production_variance = dto.production_variance
        if dto.cost_variance is not None:
            risk.cost_variance = dto.cost_variance
        if dto.result_variance is not None:
            risk.result_variance = dto.result_variance
        if dto.statuscode is not None:
            risk.statuscode = dto.statuscode
        risk.modifiedby = user
        risk.save()
        return risk

    @staticmethod
    def delete_risk(risk_id: UUID) -> None:
        risk = RiskService.get_risk(risk_id)
        risk.delete()


# ============================================================================
# AssetUsageService
# ============================================================================

class AssetUsageService:
    """CRUD service for ProjectAssetUsage."""

    @staticmethod
    def create_asset_usage(dto: CreateAssetUsageDto, user: SystemUser) -> ProjectAssetUsage:
        try:
            project = ConstructionProject.objects.get(pk=dto.projectid)
        except ConstructionProject.DoesNotExist:
            raise NotFound(f"Project {dto.projectid} not found")
        valid_categories = [c.value for c in AssetCategoryCode]
        if dto.category not in valid_categories:
            raise ValidationError(f"Invalid category {dto.category}. Must be one of: {valid_categories}")
        return ProjectAssetUsage.objects.create(
            projectid=project,
            category=dto.category,
            description=dto.description,
            plannedamount=dto.plannedamount or 0,
            createdby=user,
            modifiedby=user,
        )

    @staticmethod
    def list_asset_usages(project_id: UUID) -> list:
        return list(ProjectAssetUsage.objects.filter(projectid_id=project_id))

    @staticmethod
    def get_asset_usage(usage_id: UUID) -> ProjectAssetUsage:
        try:
            return ProjectAssetUsage.objects.get(pk=usage_id)
        except ProjectAssetUsage.DoesNotExist:
            raise NotFound(f"Asset usage {usage_id} not found")

    @staticmethod
    def update_asset_usage(usage_id: UUID, dto: UpdateAssetUsageDto, user: SystemUser) -> ProjectAssetUsage:
        usage = AssetUsageService.get_asset_usage(usage_id)
        if dto.category is not None:
            valid_categories = [c.value for c in AssetCategoryCode]
            if dto.category not in valid_categories:
                raise ValidationError(f"Invalid category {dto.category}")
            usage.category = dto.category
        if dto.description is not None:
            usage.description = dto.description
        if dto.plannedamount is not None:
            usage.plannedamount = dto.plannedamount
        usage.modifiedby = user
        usage.save()
        return usage

    @staticmethod
    def delete_asset_usage(usage_id: UUID) -> None:
        usage = AssetUsageService.get_asset_usage(usage_id)
        usage.delete()


# ============================================================================
# ExecutiveSummaryService
# ============================================================================

class ExecutiveSummaryService:
    """Computes the executive summary for a ConstructionProject."""

    @staticmethod
    def compute(project_id: UUID) -> dict:
        from django.db.models import Sum, Q
        from datetime import date as _date
        from decimal import Decimal as D
        from apps.budgets.models import ImputationCode, CostTypeCode
        from apps.expenses.models import ClientEstimate, PaymentStatusCode

        project = ConstructionProject.objects.select_related('accountid', 'ownerid').get(pk=project_id)

        # ── Section 1: project_info ──────────────────────────────────────────
        def _bond(amount, policycost, start, end):
            if amount is None:
                return None
            return {'amount': amount, 'policycost': policycost,
                    'validity_start': start, 'validity_end': end}

        project_info = {
            'name': project.name,
            'client': project.accountid.name if project.accountid else None,
            'presentation_date': project.presentationdate,
            'award_date': project.awarddate,
            'start_date': project.startdate,
            'project_type': project.projecttype,
            'bidding_type': project.biddingtype,
            'contract_amount_notax': project.contractamount_notax,
            'contract_amount_withtax': project.contractamount_withtax,
            'advance_payment_notax': project.advancepayment_notax,
            'advance_payment_withtax': project.advancepayment_withtax,
            'advance_bond': _bond(
                project.advancebond_amount, project.advancebond_policycost,
                project.advancebond_validitystartdate, project.advancebond_validityenddate,
            ),
            'completion_bond': _bond(
                project.completionbond_amount, project.completionbond_policycost,
                project.completionbond_validitystartdate, project.completionbond_validityenddate,
            ),
            'defects_bond': _bond(
                project.defectsbond_amount, project.defectsbond_policycost,
                project.defectsbond_validitystartdate, project.defectsbond_validityenddate,
            ),
            'car_insurance': _bond(
                project.carinsurance_amount, project.carinsurance_policycost,
                project.carinsurance_validitystartdate, project.carinsurance_validityenddate,
            ),
            'liability_insurance': _bond(
                project.liabilityinsurance_amount, project.liabilityinsurance_policycost,
                project.liabilityinsurance_validitystartdate, project.liabilityinsurance_validityenddate,
            ),
        }

        # ── Section 2: current_status ────────────────────────────────────────
        ZERO = D('0')
        estimates_qs = ClientEstimate.objects.filter(projectid=project)

        agg = estimates_qs.aggregate(
            total_amortization=Sum('advanceamortization'),
            total_guarantee=Sum('guaranteefund'),
            total_invoiced_notax=Sum('amountnotax'),
            total_invoiced_net=Sum('totalinvoiced'),
            total_paid=Sum('amountpaid'),
            total_production=Sum('estimatedamount'),
        )

        amortized_notax = agg['total_amortization'] or ZERO
        advance_notax = project.advancepayment_notax or ZERO
        pending_notax = advance_notax - amortized_notax

        paid_guarantee = estimates_qs.filter(
            paymentstatus=PaymentStatusCode.PAID
        ).aggregate(paid=Sum('guaranteefund'))['paid'] or ZERO

        invoiced_notax = agg['total_invoiced_notax'] or ZERO
        invoiced_net = agg['total_invoiced_net'] or ZERO
        total_paid = agg['total_paid'] or ZERO
        debt_net = invoiced_net - total_paid

        # debt_notax = unpaid collectableamount
        debt_notax = estimates_qs.exclude(
            paymentstatus=PaymentStatusCode.PAID
        ).aggregate(d=Sum('collectableamount'))['d'] or ZERO

        # oldest_overdue_days: estimate invoiced 30+ days ago and not paid
        today = _date.today()
        overdue_threshold = today - __import__('datetime').timedelta(days=30)
        unpaid_old = estimates_qs.filter(
            invoicedate__lte=overdue_threshold,
        ).exclude(paymentstatus=PaymentStatusCode.PAID)
        oldest_overdue_days = 0
        for est in unpaid_old:
            days = (today - est.invoicedate).days - 30
            if days > oldest_overdue_days:
                oldest_overdue_days = days

        accumulated_guarantee = agg['total_guarantee'] or ZERO
        production_accumulated = agg['total_production'] or ZERO

        # last_updated_period: estimationperiod of latest estimate
        last_est = estimates_qs.order_by('-createdon').first()
        last_period = last_est.estimationperiod if last_est else None

        current_status = {
            'advance': {
                'amortized_notax': amortized_notax,
                'pending_notax': pending_notax,
                'amortized_net': amortized_notax * D('1.16'),
                'pending_net': pending_notax * D('1.16'),
                'last_updated_period': last_period,
            },
            'certification': {
                'invoiced_notax': invoiced_notax,
                'debt_notax': debt_notax,
                'invoiced_net': invoiced_net,
                'debt_net': max(debt_net, ZERO),
                'oldest_overdue_days': oldest_overdue_days,
                'last_updated_period': last_period,
            },
            'guarantee_retention': {
                'accumulated_notax': accumulated_guarantee,
                'paid_notax': paid_guarantee,
                'accumulated_net': accumulated_guarantee * D('1.16'),
                'paid_net': paid_guarantee * D('1.16'),
                'last_updated_period': last_period,
            },
            'production': {
                'accumulated': production_accumulated,
                'estimated': project.contractamount_notax,
                'executed_unestimated': ZERO,
            },
            'result': _compute_result(project, invoiced_notax),
        }

        # ── Section 3: technical_economic ───────────────────────────────────
        codes_qs = ImputationCode.objects.filter(projectid=project).select_related('categoryid')

        direct_codes = [c for c in codes_qs if c.costtype == CostTypeCode.DIRECT]
        indirect_codes = [c for c in codes_qs if c.costtype == CostTypeCode.INDIRECT]

        direct_study = sum((c.totalbudget for c in direct_codes), ZERO)
        direct_actual = sum((c.totalspent for c in direct_codes), ZERO)
        indirect_study = sum((c.totalbudget for c in indirect_codes), ZERO)
        indirect_actual = sum((c.totalspent for c in indirect_codes), ZERO)

        # Group by category
        from collections import defaultdict
        by_cat = defaultdict(lambda: {'budget': ZERO, 'spent': ZERO, 'name': '', 'costtype': None})
        for code in codes_qs:
            cat_id = str(code.categoryid_id)
            by_cat[cat_id]['name'] = code.categoryid.name
            by_cat[cat_id]['costtype'] = code.costtype
            by_cat[cat_id]['budget'] += code.totalbudget
            by_cat[cat_id]['spent'] += code.totalspent

        by_category = [
            {
                'name': v['name'],
                'costtype': v['costtype'],
                'study': v['budget'],
                'accumulated': v['spent'],
                'pending': v['budget'] - v['spent'],
                'deviation_ratio': (
                    (v['spent'] - v['budget']) / v['budget']
                    if v['budget'] else ZERO
                ),
            }
            for v in by_cat.values()
        ]

        main_items = [
            {
                'name': 'Producción',
                'study': project.contractamount_notax,
                'contract': project.contractamount_notax,
                'accumulated': production_accumulated,
                'type': 'PRODUCTION',
            },
            {
                'name': 'Costo Directo',
                'study': direct_study,
                'contract': direct_study,
                'accumulated': direct_actual,
                'type': 'DIRECT_COST',
            },
            {
                'name': 'Costo Indirecto',
                'study': indirect_study,
                'contract': indirect_study,
                'accumulated': indirect_actual,
                'type': 'INDIRECT_COST',
            },
        ]

        technical_economic = {
            'main_items': main_items,
            'result_by_family': {
                'direct_cost': {
                    'study': direct_study,
                    'current_contract': direct_study,
                    'accumulated': direct_actual,
                    'pending': direct_study - direct_actual,
                    'deviation_ratio': (
                        (direct_actual - direct_study) / direct_study
                        if direct_study else ZERO
                    ),
                },
                'indirect_cost': {
                    'study': indirect_study,
                    'current_contract': indirect_study,
                    'accumulated': indirect_actual,
                    'pending': indirect_study - indirect_actual,
                    'deviation_ratio': (
                        (indirect_actual - indirect_study) / indirect_study
                        if indirect_study else ZERO
                    ),
                },
                'production': {
                    'study': project.contractamount_notax,
                    'current_contract': project.contractamount_notax,
                    'accumulated': production_accumulated,
                    'pending': project.contractamount_notax - production_accumulated,
                },
                'by_category': by_category,
            },
        }

        # ── Section 4: risks ─────────────────────────────────────────────────
        risks = list(ProjectRisk.objects.filter(projectid=project))

        # ── Section 5: asset_usages ──────────────────────────────────────────
        asset_usages_raw = ProjectAssetUsage.objects.filter(projectid=project)
        asset_usages = [
            {
                'assetusageid': u.assetusageid,
                'category': u.category,
                'description': u.description,
                'planned': u.plannedamount,
                'accumulated_actual': ZERO,  # v1: no actual tracking yet
                'pending': u.plannedamount,
                'deviation_pct': ZERO,
            }
            for u in asset_usages_raw
        ]

        return {
            'project_info': project_info,
            'current_status': current_status,
            'technical_economic': technical_economic,
            'risks': risks,
            'asset_usages': asset_usages,
        }


def _compute_result(project, invoiced_notax):
    from decimal import Decimal as D
    from apps.budgets.models import ImputationCode
    ZERO = D('0')

    codes = ImputationCode.objects.filter(projectid=project)
    total_planned = sum((c.totalbudget for c in codes), ZERO)
    total_actual_cost = sum((c.totalspent for c in codes), ZERO)

    planned = project.contractamount_notax - total_planned
    actual = invoiced_notax - total_actual_cost
    if planned:
        variance_pct = ((actual - planned) / abs(planned) * D('100')).quantize(D('0.01'))
    else:
        variance_pct = ZERO
    return {
        'planned': planned,
        'actual': actual,
        'variance_pct': variance_pct,
    }
