"""
Unit tests for Construction Project models.

Tests model creation, enum values, auto-generated UUIDs,
and string representations.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.db import IntegrityError

from apps.projects.models import (
    ConstructionProject,
    ProjectStateCode, ProjectTypeCode, BiddingTypeCode,
    PeriodTypeCode, EmailProtocolCode, ProjectRoleCode,
    ProjectTeamMember,
    ProjectZone, ZoneStateCode,
    ProjectSupplier, SupplierStateCode,
)
from apps.projects.tests.factories import (
    ConstructionProjectFactory, ActiveProjectFactory, CompletedProjectFactory,
    ProjectTeamMemberFactory, ProjectZoneFactory, ProjectSupplierFactory,
)
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Enum Tests
# ============================================================================

@pytest.mark.unit
class TestProjectEnums:
    """Tests for project-related enum definitions."""

    def test_project_state_code_values(self):
        assert ProjectStateCode.DRAFT.value == 0
        assert ProjectStateCode.ACTIVE.value == 1
        assert ProjectStateCode.ON_HOLD.value == 2
        assert ProjectStateCode.COMPLETED.value == 3
        assert ProjectStateCode.CANCELED.value == 4

        assert ProjectStateCode.DRAFT.label == 'Draft'
        assert ProjectStateCode.ACTIVE.label == 'Active'
        assert ProjectStateCode.ON_HOLD.label == 'On Hold'
        assert ProjectStateCode.COMPLETED.label == 'Completed'
        assert ProjectStateCode.CANCELED.label == 'Canceled'

    def test_project_type_code_values(self):
        assert ProjectTypeCode.PUBLIC.value == 0
        assert ProjectTypeCode.PRIVATE.value == 1

    def test_bidding_type_code_values(self):
        assert BiddingTypeCode.OPEN_BID.value == 0
        assert BiddingTypeCode.INVITED_BID.value == 1
        assert BiddingTypeCode.DIRECT_AWARD.value == 2

    def test_period_type_code_values(self):
        assert PeriodTypeCode.WEEKLY.value == 0
        assert PeriodTypeCode.FORTNIGHTLY.value == 1

    def test_email_protocol_code_values(self):
        assert EmailProtocolCode.IMAP.value == 0
        assert EmailProtocolCode.GRAPH_API.value == 1

    def test_project_role_code_values(self):
        assert ProjectRoleCode.PROJECT_MANAGER.value == 'ProjectManager'
        assert ProjectRoleCode.ADMIN_ASSISTANT.value == 'AdminAssistant'
        assert ProjectRoleCode.PRODUCTION_MANAGER.value == 'ProductionManager'
        assert ProjectRoleCode.SITE_ENGINEER.value == 'SiteEngineer'
        assert ProjectRoleCode.SAFETY_OFFICER.value == 'SafetyOfficer'
        assert ProjectRoleCode.QUALITY_INSPECTOR.value == 'QualityInspector'
        assert ProjectRoleCode.CLIENT_CONTACT.value == 'ClientContact'
        assert ProjectRoleCode.OTHER.value == 'Other'

    def test_zone_state_code_values(self):
        assert ZoneStateCode.ACTIVE.value == 0
        assert ZoneStateCode.INACTIVE.value == 1

    def test_supplier_state_code_values(self):
        assert SupplierStateCode.ACTIVE.value == 0
        assert SupplierStateCode.INACTIVE.value == 1


# ============================================================================
# ConstructionProject Model Tests
# ============================================================================

@pytest.mark.unit
class TestConstructionProjectModel:
    """Tests for ConstructionProject model creation and basic operations."""

    def test_create_project_with_factory(self, db):
        project = ConstructionProjectFactory()
        assert project.projectid is not None
        assert project.projectnumber is not None
        assert project.name is not None
        assert project.statecode == ProjectStateCode.DRAFT
        assert project.ownerid is not None
        assert project.accountid is not None

    def test_create_project_all_fields(self, db):
        owner = SalespersonFactory()
        from apps.accounts.tests.factories import AccountFactory
        account = AccountFactory(ownerid=owner)
        today = date.today()

        project = ConstructionProject.objects.create(
            projectnumber='PRY-2026-999',
            name='Test Construction Project',
            description='Full project test',
            statecode=ProjectStateCode.ACTIVE,
            accountid=account,
            startdate=today,
            contractenddate=today + timedelta(days=365),
            durationmonths=12,
            projecttype=ProjectTypeCode.PUBLIC,
            biddingtype=BiddingTypeCode.OPEN_BID,
            contractamount_notax=Decimal('5000000.00'),
            contractamount_withtax=Decimal('5800000.00'),
            advancepayment_notax=Decimal('500000.00'),
            advancepayment_withtax=Decimal('580000.00'),
            exchangerate_mxn_usd=Decimal('17.5000'),
            advancebond_amount=Decimal('100000.00'),
            advancebond_policycost=Decimal('5000.00'),
            advancebond_validitystartdate=today,
            advancebond_validityenddate=today + timedelta(days=180),
            periodtype=PeriodTypeCode.FORTNIGHTLY,
            alertthreshold_warning=Decimal('80.00'),
            alertthreshold_critical=Decimal('90.00'),
            alertthreshold_exceeded=Decimal('100.00'),
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert project.projectid is not None
        assert project.name == 'Test Construction Project'
        assert project.contractamount_notax == Decimal('5000000.00')
        assert project.advancebond_amount == Decimal('100000.00')
        assert project.periodtype == PeriodTypeCode.FORTNIGHTLY

    def test_project_uuid_auto_generated(self, db):
        project = ConstructionProjectFactory()
        assert project.projectid is not None
        assert len(str(project.projectid)) == 36  # UUID format

    def test_project_str_representation(self, db):
        project = ConstructionProjectFactory(projectnumber='PRY-2026-001', name='Highway Bridge')
        assert str(project) == 'PRY-2026-001 - Highway Bridge'

    def test_project_state_name_property(self, db):
        draft = ConstructionProjectFactory(statecode=ProjectStateCode.DRAFT)
        active = ActiveProjectFactory()
        completed = CompletedProjectFactory()

        assert draft.state_name == 'Draft'
        assert active.state_name == 'Active'
        assert completed.state_name == 'Completed'

    def test_project_is_active_property(self, db):
        draft = ConstructionProjectFactory()
        active = ActiveProjectFactory()

        assert draft.is_active is False
        assert active.is_active is True

    def test_project_ordering(self, db):
        p1 = ConstructionProjectFactory()
        p2 = ConstructionProjectFactory()
        p3 = ConstructionProjectFactory()

        projects = list(ConstructionProject.objects.all())
        assert projects[0].projectid == p3.projectid
        assert projects[1].projectid == p2.projectid
        assert projects[2].projectid == p1.projectid

    def test_project_unique_project_number(self, db):
        ConstructionProjectFactory(projectnumber='PRY-2026-100')
        with pytest.raises(IntegrityError):
            ConstructionProjectFactory(projectnumber='PRY-2026-100')

    def test_project_audit_fields(self, db):
        owner = SalespersonFactory()
        project = ConstructionProjectFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert project.createdon is not None
        assert project.modifiedon is not None
        assert project.createdby == owner
        assert project.modifiedby == owner


# ============================================================================
# ProjectTeamMember Model Tests
# ============================================================================

@pytest.mark.unit
class TestProjectTeamMemberModel:
    """Tests for ProjectTeamMember model."""

    def test_create_team_member(self, db):
        member = ProjectTeamMemberFactory()
        assert member.teammemberid is not None
        assert member.systemuserid is not None
        assert member.role == ProjectRoleCode.SITE_ENGINEER
        assert member.projectid is not None

    def test_team_member_str_representation(self, db):
        member = ProjectTeamMemberFactory(role=ProjectRoleCode.PROJECT_MANAGER)
        expected = f'{member.systemuserid.fullname} (Project Manager)'
        assert str(member) == expected

    def test_team_member_uuid_auto_generated(self, db):
        member = ProjectTeamMemberFactory()
        assert member.teammemberid is not None
        assert len(str(member.teammemberid)) == 36

    def test_team_member_cascade_delete(self, db):
        project = ConstructionProjectFactory()
        ProjectTeamMemberFactory(projectid=project)
        ProjectTeamMemberFactory(projectid=project)
        project_pk = project.projectid

        assert ProjectTeamMember.objects.filter(projectid_id=project_pk).count() == 2
        project.delete()
        assert ProjectTeamMember.objects.filter(projectid_id=project_pk).count() == 0


# ============================================================================
# ProjectZone Model Tests
# ============================================================================

@pytest.mark.unit
class TestProjectZoneModel:
    """Tests for ProjectZone model."""

    def test_create_zone(self, db):
        zone = ProjectZoneFactory()
        assert zone.zoneid is not None
        assert zone.name is not None
        assert zone.prefix is not None
        assert zone.statecode == ZoneStateCode.ACTIVE

    def test_zone_str_representation(self, db):
        zone = ProjectZoneFactory(prefix='Z01', name='Main Building')
        assert str(zone) == '[Z01] Main Building'

    def test_zone_uuid_auto_generated(self, db):
        zone = ProjectZoneFactory()
        assert zone.zoneid is not None
        assert len(str(zone.zoneid)) == 36

    def test_zone_unique_prefix_per_project(self, db):
        project = ConstructionProjectFactory()
        ProjectZoneFactory(projectid=project, prefix='Z01')
        with pytest.raises(IntegrityError):
            ProjectZoneFactory(projectid=project, prefix='Z01')

    def test_zone_same_prefix_different_projects(self, db):
        p1 = ConstructionProjectFactory()
        p2 = ConstructionProjectFactory()
        z1 = ProjectZoneFactory(projectid=p1, prefix='Z01')
        z2 = ProjectZoneFactory(projectid=p2, prefix='Z01')
        assert z1.zoneid != z2.zoneid

    def test_zone_cascade_delete(self, db):
        project = ConstructionProjectFactory()
        ProjectZoneFactory(projectid=project)
        project_pk = project.projectid
        assert ProjectZone.objects.filter(projectid_id=project_pk).count() == 1
        project.delete()
        assert ProjectZone.objects.filter(projectid_id=project_pk).count() == 0


# ============================================================================
# ProjectSupplier Model Tests
# ============================================================================

@pytest.mark.unit
class TestProjectSupplierModel:
    """Tests for ProjectSupplier model."""

    def test_create_supplier(self, db):
        supplier = ProjectSupplierFactory()
        assert supplier.projectsupplierid is not None
        assert supplier.businessname is not None
        assert supplier.rfc is not None
        assert supplier.statecode == SupplierStateCode.ACTIVE

    def test_supplier_str_representation(self, db):
        supplier = ProjectSupplierFactory(suppliernumber=5, businessname='Acme Supplies')
        assert str(supplier) == '#5 - Acme Supplies'

    def test_supplier_uuid_auto_generated(self, db):
        supplier = ProjectSupplierFactory()
        assert supplier.projectsupplierid is not None
        assert len(str(supplier.projectsupplierid)) == 36

    def test_supplier_unique_rfc_per_project(self, db):
        project = ConstructionProjectFactory()
        ProjectSupplierFactory(projectid=project, rfc='XAXX010101000')
        with pytest.raises(IntegrityError):
            ProjectSupplierFactory(projectid=project, rfc='XAXX010101000')

    def test_supplier_same_rfc_different_projects(self, db):
        p1 = ConstructionProjectFactory()
        p2 = ConstructionProjectFactory()
        s1 = ProjectSupplierFactory(projectid=p1, rfc='XAXX010101000')
        s2 = ProjectSupplierFactory(projectid=p2, rfc='XAXX010101000')
        assert s1.projectsupplierid != s2.projectsupplierid

    def test_supplier_cascade_delete(self, db):
        project = ConstructionProjectFactory()
        ProjectSupplierFactory(projectid=project)
        project_pk = project.projectid
        assert ProjectSupplier.objects.filter(projectid_id=project_pk).count() == 1
        project.delete()
        assert ProjectSupplier.objects.filter(projectid_id=project_pk).count() == 0
