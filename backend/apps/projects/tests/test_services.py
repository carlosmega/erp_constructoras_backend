"""
Unit tests for Construction Project services.

Tests CRUD operations, ownership filtering, search, zone management,
supplier management, and team member management.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4

from apps.projects.models import (
    ConstructionProject, ProjectStateCode, ProjectTypeCode, BiddingTypeCode,
    PeriodTypeCode, ProjectRoleCode,
    ProjectTeamMember,
    ProjectZone, ZoneStateCode,
    ProjectSupplier, SupplierStateCode,
)
from apps.projects.services import (
    ProjectService, ZoneService, SupplierService, TeamMemberService,
)
from apps.projects.schemas import (
    CreateProjectDto, UpdateProjectDto, ProjectBondDto,
    CreateZoneDto, UpdateZoneDto,
    CreateSupplierDto,
    CreateTeamMemberDto, UpdateTeamMemberDto,
)
from apps.projects.tests.factories import (
    ConstructionProjectFactory, ActiveProjectFactory,
    ProjectZoneFactory, ProjectSupplierFactory, ProjectTeamMemberFactory,
)
from apps.accounts.tests.factories import AccountFactory
from apps.users.tests.factories import SalespersonFactory, SystemAdminFactory, SalesManagerFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


# ============================================================================
# ProjectService Tests
# ============================================================================

@pytest.mark.unit
class TestCreateProject:
    """Tests for ProjectService.create_project method."""

    def test_create_project_minimal(self, db, salesperson):
        account = AccountFactory(ownerid=salesperson)
        today = date.today()

        dto = CreateProjectDto(
            name='Test Project',
            accountid=account.accountid,
            startdate=today,
            contractenddate=today + timedelta(days=365),
            durationmonths=12,
            projecttype=ProjectTypeCode.PRIVATE,
            biddingtype=BiddingTypeCode.DIRECT_AWARD,
            contractamount_notax=Decimal('1000000.00'),
            contractamount_withtax=Decimal('1160000.00'),
        )

        project = ProjectService.create_project(dto, salesperson)

        assert project.projectid is not None
        assert project.name == 'Test Project'
        assert project.statecode == ProjectStateCode.DRAFT
        assert project.ownerid == salesperson
        assert project.createdby == salesperson
        assert project.projectnumber.startswith('PRY-')
        assert project.accountid == account

    def test_create_project_full(self, db, salesperson):
        account = AccountFactory(ownerid=salesperson)
        today = date.today()

        dto = CreateProjectDto(
            name='Full Project',
            description='A complete project',
            accountid=account.accountid,
            presentationdate=today - timedelta(days=60),
            awarddate=today - timedelta(days=30),
            startdate=today,
            contractenddate=today + timedelta(days=365),
            expectedenddate=today + timedelta(days=350),
            durationmonths=12,
            projecttype=ProjectTypeCode.PUBLIC,
            biddingtype=BiddingTypeCode.OPEN_BID,
            contractamount_notax=Decimal('5000000.00'),
            contractamount_withtax=Decimal('5800000.00'),
            advancepayment_notax=Decimal('500000.00'),
            advancepayment_withtax=Decimal('580000.00'),
            exchangerate_mxn_usd=Decimal('17.5000'),
            advancebond=ProjectBondDto(
                amount=Decimal('100000.00'),
                policycost=Decimal('5000.00'),
                validitystartdate=today,
                validityenddate=today + timedelta(days=180),
            ),
            periodtype=PeriodTypeCode.FORTNIGHTLY,
            alertthreshold_warning=Decimal('80.00'),
            alertthreshold_critical=Decimal('90.00'),
            alertthreshold_exceeded=Decimal('100.00'),
        )

        project = ProjectService.create_project(dto, salesperson)

        assert project.name == 'Full Project'
        assert project.description == 'A complete project'
        assert project.projecttype == ProjectTypeCode.PUBLIC
        assert project.advancebond_amount == Decimal('100000.00')
        assert project.advancebond_policycost == Decimal('5000.00')
        assert project.periodtype == PeriodTypeCode.FORTNIGHTLY

    def test_create_project_auto_number_generation(self, db, salesperson):
        account = AccountFactory(ownerid=salesperson)
        today = date.today()

        dto = CreateProjectDto(
            name='Project 1',
            accountid=account.accountid,
            startdate=today,
            contractenddate=today + timedelta(days=365),
            durationmonths=12,
            projecttype=ProjectTypeCode.PRIVATE,
            biddingtype=BiddingTypeCode.DIRECT_AWARD,
            contractamount_notax=Decimal('1000000.00'),
            contractamount_withtax=Decimal('1160000.00'),
        )

        p1 = ProjectService.create_project(dto, salesperson)
        dto.name = 'Project 2'
        p2 = ProjectService.create_project(dto, salesperson)

        # Both should have sequential numbers
        assert p1.projectnumber.startswith(f'PRY-{today.year}-')
        assert p2.projectnumber.startswith(f'PRY-{today.year}-')
        num1 = int(p1.projectnumber.split('-')[-1])
        num2 = int(p2.projectnumber.split('-')[-1])
        assert num2 == num1 + 1

    def test_create_project_invalid_account(self, db, salesperson):
        today = date.today()
        dto = CreateProjectDto(
            name='Test',
            accountid=uuid4(),
            startdate=today,
            contractenddate=today + timedelta(days=365),
            durationmonths=12,
            projecttype=ProjectTypeCode.PRIVATE,
            biddingtype=BiddingTypeCode.DIRECT_AWARD,
            contractamount_notax=Decimal('1000000.00'),
            contractamount_withtax=Decimal('1160000.00'),
        )

        with pytest.raises(ValidationError, match='Account.*not found'):
            ProjectService.create_project(dto, salesperson)

    def test_create_project_invalid_owner(self, db, salesperson):
        account = AccountFactory(ownerid=salesperson)
        today = date.today()
        dto = CreateProjectDto(
            name='Test',
            accountid=account.accountid,
            startdate=today,
            contractenddate=today + timedelta(days=365),
            durationmonths=12,
            projecttype=ProjectTypeCode.PRIVATE,
            biddingtype=BiddingTypeCode.DIRECT_AWARD,
            contractamount_notax=Decimal('1000000.00'),
            contractamount_withtax=Decimal('1160000.00'),
            ownerid=uuid4(),
        )

        with pytest.raises(ValidationError, match='Owner.*not found'):
            ProjectService.create_project(dto, salesperson)


@pytest.mark.unit
class TestListProjects:
    """Tests for ProjectService.list_projects method."""

    def test_list_projects_salesperson_sees_own_only(self, db, salesperson, salesperson2):
        p1 = ConstructionProjectFactory(ownerid=salesperson)
        p2 = ConstructionProjectFactory(ownerid=salesperson)
        p3 = ConstructionProjectFactory(ownerid=salesperson2)

        projects = ProjectService.list_projects(salesperson)

        assert projects.count() == 2
        assert p1 in projects
        assert p2 in projects
        assert p3 not in projects

    def test_list_projects_admin_sees_all(self, db, system_admin, salesperson):
        ConstructionProjectFactory(ownerid=salesperson)
        ConstructionProjectFactory(ownerid=system_admin)

        projects = ProjectService.list_projects(system_admin)
        assert projects.count() == 2

    def test_list_projects_filter_by_state(self, db, salesperson):
        ConstructionProjectFactory(ownerid=salesperson, statecode=ProjectStateCode.DRAFT)
        ConstructionProjectFactory(ownerid=salesperson, statecode=ProjectStateCode.DRAFT)
        ActiveProjectFactory(ownerid=salesperson)

        draft = ProjectService.list_projects(salesperson, statecode=ProjectStateCode.DRAFT)
        active = ProjectService.list_projects(salesperson, statecode=ProjectStateCode.ACTIVE)

        assert draft.count() == 2
        assert active.count() == 1

    def test_list_projects_search(self, db, salesperson):
        ConstructionProjectFactory(ownerid=salesperson, name='Highway Bridge Project')
        ConstructionProjectFactory(ownerid=salesperson, name='Office Building Renovation')

        results = ProjectService.list_projects(salesperson, search='Highway')
        assert results.count() == 1

    def test_list_projects_search_by_project_number(self, db, salesperson):
        ConstructionProjectFactory(ownerid=salesperson, projectnumber='PRY-2026-500')
        ConstructionProjectFactory(ownerid=salesperson, projectnumber='PRY-2026-501')

        results = ProjectService.list_projects(salesperson, search='PRY-2026-500')
        assert results.count() == 1

    def test_list_projects_filter_by_owner_admin(self, db, system_admin, salesperson):
        ConstructionProjectFactory.create_batch(2, ownerid=salesperson)
        ConstructionProjectFactory(ownerid=system_admin)

        projects = ProjectService.list_projects(system_admin, ownerid=salesperson.systemuserid)
        assert projects.count() == 2

    def test_list_projects_filter_by_owner_forbidden(self, db, salesperson, salesperson2):
        ConstructionProjectFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="cannot view other users"):
            ProjectService.list_projects(salesperson, ownerid=salesperson2.systemuserid)


@pytest.mark.unit
class TestGetProjectById:
    """Tests for ProjectService.get_project_by_id method."""

    def test_get_project_by_id_owner(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        retrieved = ProjectService.get_project_by_id(project.projectid, salesperson)
        assert retrieved.projectid == project.projectid

    def test_get_project_by_id_admin(self, db, system_admin, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        retrieved = ProjectService.get_project_by_id(project.projectid, system_admin)
        assert retrieved.projectid == project.projectid

    def test_get_project_by_id_not_owner(self, db, salesperson, salesperson2):
        project = ConstructionProjectFactory(ownerid=salesperson2)
        with pytest.raises(PermissionDenied, match="don't have access"):
            ProjectService.get_project_by_id(project.projectid, salesperson)

    def test_get_project_by_id_not_found(self, db, salesperson):
        with pytest.raises(NotFound, match='not found'):
            ProjectService.get_project_by_id(uuid4(), salesperson)


@pytest.mark.unit
class TestUpdateProject:
    """Tests for ProjectService.update_project method."""

    def test_update_project_partial(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, name='Old Name')

        dto = UpdateProjectDto(name='New Name')
        updated = ProjectService.update_project(project.projectid, dto, salesperson)

        assert updated.name == 'New Name'
        assert updated.modifiedby == salesperson

    def test_update_project_state_change(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, statecode=ProjectStateCode.DRAFT)

        dto = UpdateProjectDto(statecode=ProjectStateCode.ACTIVE)
        updated = ProjectService.update_project(project.projectid, dto, salesperson)

        assert updated.statecode == ProjectStateCode.ACTIVE

    def test_update_project_bond(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        today = date.today()

        dto = UpdateProjectDto(
            advancebond=ProjectBondDto(
                amount=Decimal('200000.00'),
                policycost=Decimal('10000.00'),
                validitystartdate=today,
                validityenddate=today + timedelta(days=90),
            )
        )
        updated = ProjectService.update_project(project.projectid, dto, salesperson)

        assert updated.advancebond_amount == Decimal('200000.00')
        assert updated.advancebond_policycost == Decimal('10000.00')


@pytest.mark.unit
class TestDeleteProject:
    """Tests for ProjectService.delete_project method."""

    def test_delete_project_soft(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson, statecode=ProjectStateCode.ACTIVE)

        deleted = ProjectService.delete_project(project.projectid, salesperson)

        assert deleted.statecode == ProjectStateCode.CANCELED
        # Record still exists
        assert ConstructionProject.objects.filter(projectid=project.projectid).exists()


@pytest.mark.unit
class TestSearchProjects:
    """Tests for ProjectService.search_projects method."""

    def test_search_by_name(self, db, salesperson):
        ConstructionProjectFactory(ownerid=salesperson, name='Bridge Construction')
        ConstructionProjectFactory(ownerid=salesperson, name='Office Renovation')

        results = ProjectService.search_projects('Bridge', salesperson)
        assert results.count() == 1

    def test_search_empty_query(self, db, salesperson):
        ConstructionProjectFactory(ownerid=salesperson)
        ConstructionProjectFactory(ownerid=salesperson)

        results = ProjectService.search_projects('', salesperson)
        assert results.count() == 2


@pytest.mark.unit
class TestGenerateProjectNumber:
    """Tests for ProjectService.generate_project_number method."""

    def test_generate_first_project_number(self, db):
        number = ProjectService.generate_project_number()
        current_year = date.today().year
        assert number == f'PRY-{current_year}-001'

    def test_generate_sequential_project_numbers(self, db, salesperson):
        # Create first project
        ConstructionProjectFactory(
            ownerid=salesperson,
            projectnumber=f'PRY-{date.today().year}-005'
        )
        number = ProjectService.generate_project_number()
        assert number == f'PRY-{date.today().year}-006'


# ============================================================================
# ZoneService Tests
# ============================================================================

@pytest.mark.unit
class TestZoneService:
    """Tests for ZoneService CRUD operations."""

    def test_list_zones(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectZoneFactory(projectid=project, prefix='Z01', sortorder=1)
        ProjectZoneFactory(projectid=project, prefix='Z02', sortorder=2)

        zones = ZoneService.list_zones(project.projectid, salesperson)
        assert zones.count() == 2

    def test_create_zone(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto = CreateZoneDto(
            projectid=project.projectid,
            name='Zone A',
            prefix='ZNA',
            description='Main zone',
        )
        zone = ZoneService.create_zone(dto, salesperson)

        assert zone.zoneid is not None
        assert zone.name == 'Zone A'
        assert zone.prefix == 'ZNA'
        assert zone.statecode == ZoneStateCode.ACTIVE

    def test_create_zone_auto_sortorder(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectZoneFactory(projectid=project, prefix='Z01', sortorder=5)

        dto = CreateZoneDto(
            projectid=project.projectid,
            name='New Zone',
            prefix='Z02',
        )
        zone = ZoneService.create_zone(dto, salesperson)
        assert zone.sortorder == 6

    def test_create_zone_prefix_uppercased(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto = CreateZoneDto(
            projectid=project.projectid,
            name='Zone',
            prefix='abc',
        )
        zone = ZoneService.create_zone(dto, salesperson)
        assert zone.prefix == 'ABC'

    def test_create_zone_duplicate_prefix(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectZoneFactory(projectid=project, prefix='Z01')

        dto = CreateZoneDto(
            projectid=project.projectid,
            name='Duplicate',
            prefix='Z01',
        )
        with pytest.raises(ValidationError, match='already exists'):
            ZoneService.create_zone(dto, salesperson)

    def test_create_zone_prefix_too_long(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto = CreateZoneDto(
            projectid=project.projectid,
            name='Zone',
            prefix='ABCD',
        )
        with pytest.raises(ValidationError, match='at most 3 characters'):
            ZoneService.create_zone(dto, salesperson)

    def test_update_zone(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        zone = ProjectZoneFactory(projectid=project, name='Old Name', prefix='OLD')

        dto = UpdateZoneDto(name='New Name')
        updated = ZoneService.update_zone(zone.zoneid, dto, salesperson)
        assert updated.name == 'New Name'

    def test_update_zone_prefix_uniqueness(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectZoneFactory(projectid=project, prefix='AAA')
        zone2 = ProjectZoneFactory(projectid=project, prefix='BBB')

        dto = UpdateZoneDto(prefix='AAA')
        with pytest.raises(ValidationError, match='already exists'):
            ZoneService.update_zone(zone2.zoneid, dto, salesperson)

    def test_delete_zone_soft(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        zone = ProjectZoneFactory(projectid=project)

        deleted = ZoneService.delete_zone(zone.zoneid, salesperson)
        assert deleted.statecode == ZoneStateCode.INACTIVE


# ============================================================================
# SupplierService Tests
# ============================================================================

@pytest.mark.unit
class TestSupplierService:
    """Tests for SupplierService CRUD operations."""

    def test_list_suppliers(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectSupplierFactory(projectid=project, suppliernumber=1)
        ProjectSupplierFactory(projectid=project, suppliernumber=2)

        suppliers = SupplierService.list_suppliers(project.projectid, salesperson)
        assert suppliers.count() == 2

    def test_add_supplier(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        account = AccountFactory(ownerid=salesperson)

        dto = CreateSupplierDto(
            projectid=project.projectid,
            accountid=account.accountid,
            rfc='XAXX010101000',
            businessname='Test Supplier Inc',
        )
        supplier = SupplierService.add_supplier(dto, salesperson)

        assert supplier.projectsupplierid is not None
        assert supplier.suppliernumber == 1
        assert supplier.rfc == 'XAXX010101000'
        assert supplier.businessname == 'Test Supplier Inc'

    def test_add_supplier_auto_numbering(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        account1 = AccountFactory(ownerid=salesperson)
        account2 = AccountFactory(ownerid=salesperson)

        dto1 = CreateSupplierDto(
            projectid=project.projectid,
            accountid=account1.accountid,
            rfc='XAXX010101001',
            businessname='Supplier 1',
        )
        dto2 = CreateSupplierDto(
            projectid=project.projectid,
            accountid=account2.accountid,
            rfc='XAXX010101002',
            businessname='Supplier 2',
        )

        s1 = SupplierService.add_supplier(dto1, salesperson)
        s2 = SupplierService.add_supplier(dto2, salesperson)

        assert s1.suppliernumber == 1
        assert s2.suppliernumber == 2

    def test_add_supplier_duplicate_rfc(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        account = AccountFactory(ownerid=salesperson)
        ProjectSupplierFactory(projectid=project, rfc='XAXX010101000')

        dto = CreateSupplierDto(
            projectid=project.projectid,
            accountid=account.accountid,
            rfc='XAXX010101000',
            businessname='Duplicate',
        )
        with pytest.raises(ValidationError, match='already exists'):
            SupplierService.add_supplier(dto, salesperson)

    def test_add_supplier_invalid_account(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)

        dto = CreateSupplierDto(
            projectid=project.projectid,
            accountid=uuid4(),
            rfc='XAXX010101000',
            businessname='Test',
        )
        with pytest.raises(ValidationError, match='Account.*not found'):
            SupplierService.add_supplier(dto, salesperson)

    def test_remove_supplier_soft(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        supplier = ProjectSupplierFactory(projectid=project)

        removed = SupplierService.remove_supplier(supplier.projectsupplierid, salesperson)
        assert removed.statecode == SupplierStateCode.INACTIVE


# ============================================================================
# TeamMemberService Tests
# ============================================================================

@pytest.mark.unit
class TestTeamMemberService:
    """Tests for TeamMemberService CRUD operations."""

    def test_list_team_members(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        ProjectTeamMemberFactory(projectid=project)
        ProjectTeamMemberFactory(projectid=project)

        members = TeamMemberService.list_team_members(project.projectid, salesperson)
        assert members.count() == 2

    def test_add_team_member(self, db, salesperson):
        from apps.users.tests.factories import SalespersonFactory
        project = ConstructionProjectFactory(ownerid=salesperson)
        target_user = SalespersonFactory()

        dto = CreateTeamMemberDto(
            projectid=project.projectid,
            systemuserid=target_user.systemuserid,
            role=ProjectRoleCode.PROJECT_MANAGER,
        )
        member = TeamMemberService.add_team_member(dto, salesperson)

        assert member.teammemberid is not None
        assert member.systemuserid == target_user
        assert member.role == ProjectRoleCode.PROJECT_MANAGER

    def test_add_team_member_duplicate(self, db, salesperson):
        from apps.users.tests.factories import SalespersonFactory
        project = ConstructionProjectFactory(ownerid=salesperson)
        target_user = SalespersonFactory()

        dto = CreateTeamMemberDto(
            projectid=project.projectid,
            systemuserid=target_user.systemuserid,
            role=ProjectRoleCode.PROJECT_MANAGER,
        )
        TeamMemberService.add_team_member(dto, salesperson)

        with pytest.raises(ValidationError, match='already a member'):
            TeamMemberService.add_team_member(dto, salesperson)

    def test_add_team_member_invalid_role(self, db, salesperson):
        from apps.users.tests.factories import SalespersonFactory
        project = ConstructionProjectFactory(ownerid=salesperson)
        target_user = SalespersonFactory()

        dto = CreateTeamMemberDto(
            projectid=project.projectid,
            systemuserid=target_user.systemuserid,
            role='InvalidRole',
        )
        with pytest.raises(ValidationError, match='Invalid role'):
            TeamMemberService.add_team_member(dto, salesperson)

    def test_update_team_member(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        member = ProjectTeamMemberFactory(projectid=project)

        dto = UpdateTeamMemberDto(role=ProjectRoleCode.SAFETY_OFFICER)
        updated = TeamMemberService.update_team_member(member.teammemberid, dto, salesperson)

        assert updated.role == ProjectRoleCode.SAFETY_OFFICER

    def test_update_team_member_invalid_role(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        member = ProjectTeamMemberFactory(projectid=project)

        dto = UpdateTeamMemberDto(role='InvalidRole')
        with pytest.raises(ValidationError, match='Invalid role'):
            TeamMemberService.update_team_member(member.teammemberid, dto, salesperson)

    def test_remove_team_member_hard_delete(self, db, salesperson):
        project = ConstructionProjectFactory(ownerid=salesperson)
        member = ProjectTeamMemberFactory(projectid=project)
        member_id = member.teammemberid

        TeamMemberService.remove_team_member(member_id, salesperson)

        assert not ProjectTeamMember.objects.filter(teammemberid=member_id).exists()

    def test_remove_team_member_not_found(self, db, salesperson):
        with pytest.raises(NotFound, match='not found'):
            TeamMemberService.remove_team_member(uuid4(), salesperson)

    def test_team_member_ownership_check(self, db, salesperson, salesperson2):
        project = ConstructionProjectFactory(ownerid=salesperson2)
        member = ProjectTeamMemberFactory(projectid=project)

        with pytest.raises(PermissionDenied, match="don't have access"):
            TeamMemberService.get_team_member_by_id(member.teammemberid, salesperson)
