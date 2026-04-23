"""
Unit tests for Lead services.

Tests lead CRUD operations, state transitions, and the critical qualification workflow.
This is the most important test suite for the CRM system.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch

from apps.leads.models import Lead, LeadStateCode, LeadStatusCode, LeadQualityCode, LeadSourceCode
from apps.leads.services import LeadService
from apps.leads.schemas import CreateLeadDto, UpdateLeadDto, QualifyLeadDto, DisqualifyLeadDto
from apps.leads.tests.factories import LeadFactory, HotLeadFactory, QualifiedLeadFactory, DisqualifiedLeadFactory
from apps.users.tests.factories import SalespersonFactory, SystemAdminFactory, SalesManagerFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


@pytest.mark.unit
@pytest.mark.workflow
class TestCreateLead:
    """Tests for LeadService.create_lead method."""

    def test_create_lead_minimal(self, db, salesperson):
        """Test creating a lead with minimal required fields."""
        dto = CreateLeadDto(
            lastname='Doe',
        )

        lead = LeadService.create_lead(dto, salesperson)

        assert lead.leadid is not None
        assert lead.lastname == 'Doe'
        assert lead.fullname == 'Doe'
        assert lead.statecode == LeadStateCode.OPEN
        assert lead.statuscode == LeadStatusCode.NEW
        assert lead.ownerid == salesperson
        assert lead.createdby == salesperson
        assert lead.modifiedby == salesperson

    def test_create_lead_full(self, db, salesperson):
        """Test creating a lead with all fields populated."""
        today = date.today()
        dto = CreateLeadDto(
            firstname='John',
            lastname='Doe',
            emailaddress1='john@example.com',
            telephone1='555-1234',
            mobilephone='555-5678',
            companyname='Acme Corp',
            jobtitle='CEO',
            subject='Interested in Product X',
            description='Met at trade show',
            leadqualitycode=LeadQualityCode.HOT,
            leadsourcecode=LeadSourceCode.TRADE_SHOW,
            estimatedvalue=Decimal('50000.00'),
            estimatedclosedate=today + timedelta(days=30),
        )

        lead = LeadService.create_lead(dto, salesperson)

        assert lead.firstname == 'John'
        assert lead.lastname == 'Doe'
        assert lead.fullname == 'John Doe'
        assert lead.emailaddress1 == 'john@example.com'
        assert lead.companyname == 'Acme Corp'
        assert lead.leadqualitycode == LeadQualityCode.HOT
        assert lead.leadsourcecode == LeadSourceCode.TRADE_SHOW
        assert lead.estimatedvalue == Decimal('50000.00')

    def test_create_lead_with_different_owner(self, db, salesperson, salesperson2):
        """Test creating a lead assigned to a different owner."""
        dto = CreateLeadDto(
            lastname='Doe',
            ownerid=salesperson2.systemuserid,
        )

        lead = LeadService.create_lead(dto, salesperson)

        assert lead.ownerid == salesperson2
        assert lead.createdby == salesperson  # Creator is different from owner

    def test_create_lead_invalid_owner(self, db, salesperson):
        """Test creating a lead with non-existent owner."""
        invalid_id = uuid4()
        dto = CreateLeadDto(
            lastname='Doe',
            ownerid=invalid_id,
        )

        with pytest.raises(ValidationError, match='Owner.*not found'):
            LeadService.create_lead(dto, salesperson)


@pytest.mark.unit
class TestListLeads:
    """Tests for LeadService.list_leads method."""

    def test_list_leads_salesperson_sees_own_only(self, db, salesperson, salesperson2):
        """Test that salesperson only sees their own leads."""
        lead1 = LeadFactory(ownerid=salesperson)
        lead2 = LeadFactory(ownerid=salesperson)
        lead3 = LeadFactory(ownerid=salesperson2)

        leads = LeadService.list_leads(salesperson)

        assert leads.count() == 2
        assert lead1 in leads
        assert lead2 in leads
        assert lead3 not in leads

    def test_list_leads_admin_sees_all(self, db, system_admin, salesperson):
        """Test that System Administrator sees all leads."""
        lead1 = LeadFactory(ownerid=salesperson)
        lead2 = LeadFactory(ownerid=system_admin)

        leads = LeadService.list_leads(system_admin)

        assert leads.count() == 2

    def test_list_leads_filter_by_state(self, db, salesperson):
        """Test filtering leads by state code."""
        LeadFactory.create_batch(2, ownerid=salesperson, statecode=LeadStateCode.OPEN)
        QualifiedLeadFactory(ownerid=salesperson)

        open_leads = LeadService.list_leads(salesperson, statecode=LeadStateCode.OPEN)
        qualified_leads = LeadService.list_leads(salesperson, statecode=LeadStateCode.QUALIFIED)

        assert open_leads.count() == 2
        assert qualified_leads.count() == 1

    def test_list_leads_filter_by_status(self, db, salesperson):
        """Test filtering leads by status code."""
        LeadFactory(ownerid=salesperson, statuscode=LeadStatusCode.NEW)
        LeadFactory(ownerid=salesperson, statuscode=LeadStatusCode.CONTACTED)

        new_leads = LeadService.list_leads(salesperson, statuscode=LeadStatusCode.NEW)

        assert new_leads.count() == 1

    def test_list_leads_filter_by_quality(self, db, salesperson):
        """Test filtering leads by quality code."""
        HotLeadFactory(ownerid=salesperson)
        LeadFactory.create_batch(2, ownerid=salesperson, leadqualitycode=LeadQualityCode.WARM)

        hot_leads = LeadService.list_leads(salesperson, leadqualitycode=LeadQualityCode.HOT)

        assert hot_leads.count() == 1

    def test_list_leads_search(self, db, salesperson):
        """Test searching leads by name, email, company, subject."""
        # Create leads with specific names (fullname is auto-computed from firstname+lastname)
        LeadFactory(ownerid=salesperson, firstname='John', lastname='Doe', emailaddress1='john@test.com')
        LeadFactory(ownerid=salesperson, firstname='Jane', lastname='Smith', companyname='Acme Corp')
        LeadFactory(ownerid=salesperson, firstname='Bob', lastname='Johnson', subject='Important deal')

        # Search by name
        results = LeadService.list_leads(salesperson, search='John')
        assert results.count() >= 1  # At least John Doe (Bob Johnson may match if "John" is in fullname)

        # Search by company
        results = LeadService.list_leads(salesperson, search='Acme')
        assert results.count() >= 1

        # Search by subject
        results = LeadService.list_leads(salesperson, search='Important')
        assert results.count() >= 1

    def test_list_leads_filter_by_owner_admin(self, db, system_admin, salesperson):
        """Test that admin can filter by specific owner."""
        LeadFactory.create_batch(2, ownerid=salesperson)
        LeadFactory(ownerid=system_admin)

        leads = LeadService.list_leads(system_admin, ownerid=salesperson.systemuserid)

        assert leads.count() == 2

    def test_list_leads_filter_by_owner_forbidden(self, db, salesperson, salesperson2):
        """Test that non-admin cannot filter by other owners."""
        LeadFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match='cannot view other users'):
            LeadService.list_leads(salesperson, ownerid=salesperson2.systemuserid)


@pytest.mark.unit
class TestGetLeadById:
    """Tests for LeadService.get_lead_by_id method."""

    def test_get_lead_by_id_owner(self, db, salesperson):
        """Test getting lead by ID as owner."""
        lead = LeadFactory(ownerid=salesperson)

        retrieved = LeadService.get_lead_by_id(lead.leadid, salesperson)

        assert retrieved.leadid == lead.leadid

    def test_get_lead_by_id_admin(self, db, system_admin, salesperson):
        """Test that admin can get any lead."""
        lead = LeadFactory(ownerid=salesperson)

        retrieved = LeadService.get_lead_by_id(lead.leadid, system_admin)

        assert retrieved.leadid == lead.leadid

    def test_get_lead_by_id_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot get lead."""
        lead = LeadFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="don't have access"):
            LeadService.get_lead_by_id(lead.leadid, salesperson)

    def test_get_lead_by_id_not_found(self, db, salesperson):
        """Test getting non-existent lead."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            LeadService.get_lead_by_id(invalid_id, salesperson)


@pytest.mark.unit
class TestUpdateLead:
    """Tests for LeadService.update_lead method."""

    def test_update_lead_basic_fields(self, db, salesperson):
        """Test updating basic lead fields."""
        lead = LeadFactory(ownerid=salesperson, firstname='John', lastname='Doe')

        dto = UpdateLeadDto(
            firstname='Jane',
            emailaddress1='jane@example.com',
            telephone1='555-9999',
        )

        updated = LeadService.update_lead(lead.leadid, dto, salesperson)

        assert updated.firstname == 'Jane'
        assert updated.fullname == 'Jane Doe'  # Auto-computed
        assert updated.emailaddress1 == 'jane@example.com'
        assert updated.telephone1 == '555-9999'

    def test_update_lead_status_to_contacted(self, db, salesperson):
        """Test updating lead status from New to Contacted."""
        lead = LeadFactory(ownerid=salesperson, statuscode=LeadStatusCode.NEW)

        dto = UpdateLeadDto(statuscode=LeadStatusCode.CONTACTED)
        updated = LeadService.update_lead(lead.leadid, dto, salesperson)

        assert updated.statuscode == LeadStatusCode.CONTACTED

    def test_update_lead_cannot_update_qualified(self, db, salesperson):
        """Test that qualified leads cannot be updated."""
        lead = QualifiedLeadFactory(ownerid=salesperson)

        dto = UpdateLeadDto(firstname='Jane')

        with pytest.raises(ValidationError, match='Only open leads can be updated'):
            LeadService.update_lead(lead.leadid, dto, salesperson)

    def test_update_lead_cannot_update_disqualified(self, db, salesperson):
        """Test that disqualified leads cannot be updated."""
        lead = DisqualifiedLeadFactory(ownerid=salesperson)

        dto = UpdateLeadDto(firstname='Jane')

        with pytest.raises(ValidationError, match='Only open leads can be updated'):
            LeadService.update_lead(lead.leadid, dto, salesperson)

    def test_update_lead_invalid_status_for_open(self, db, salesperson):
        """Invalid statuscode for open lead is rejected at DTO construction.

        The validator in UpdateLeadDto catches this earlier than the service,
        so qualify/disqualify transitions must use their dedicated endpoints.
        """
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises(PydanticValidationError, match='New|Contacted'):
            UpdateLeadDto(statuscode=LeadStatusCode.QUALIFIED)


@pytest.mark.unit
@pytest.mark.workflow
class TestQualifyLead:
    """Tests for LeadService.qualify_lead method - CRITICAL WORKFLOW."""

    def test_qualify_lead_basic(self, db, salesperson):
        """Test basic lead qualification creates opportunity."""
        lead = LeadFactory(
            ownerid=salesperson,
            firstname='John',
            lastname='Doe',
            companyname='Acme Corp',
            estimatedvalue=Decimal('10000.00'),
        )

        dto = QualifyLeadDto(
            createAccount=False,
            createContact=False,
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        # Check lead state changed (reload from DB)
        lead.refresh_from_db()
        assert lead.statecode == LeadStateCode.QUALIFIED
        assert lead.statuscode == LeadStatusCode.QUALIFIED
        assert lead.qualifyingopportunityid is not None

        # Check opportunity was created
        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.originatingleadid == lead
        assert opportunity.ownerid == salesperson

    def test_qualify_lead_with_account(self, db, salesperson):
        """Test qualifying lead creates account when requested."""
        lead = LeadFactory(
            ownerid=salesperson,
            companyname='Acme Corp',
            emailaddress1='contact@acme.com',
            telephone1='555-1234',
        )

        dto = QualifyLeadDto(
            createAccount=True,
            createContact=False,
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        # Check account was created
        from apps.accounts.models import Account
        accounts = Account.objects.filter(name='Acme Corp')
        assert accounts.exists()
        account = accounts.first()
        assert account.emailaddress1 == 'contact@acme.com'
        assert account.telephone1 == '555-1234'
        assert account.ownerid == salesperson

        # Check opportunity linked to account
        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.accountid == account

    def test_qualify_lead_with_contact(self, db, salesperson):
        """Test qualifying lead creates contact when requested."""
        lead = LeadFactory(
            ownerid=salesperson,
            firstname='John',
            lastname='Doe',
            emailaddress1='john@example.com',
            telephone1='555-1234',
            jobtitle='CEO',
        )

        dto = QualifyLeadDto(
            createAccount=False,
            createContact=True,
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        # Check contact was created
        from apps.contacts.models import Contact
        contacts = Contact.objects.filter(firstname='John', lastname='Doe')
        assert contacts.exists()
        contact = contacts.first()
        assert contact.emailaddress1 == 'john@example.com'
        assert contact.jobtitle == 'CEO'

        # Check opportunity linked to contact
        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.contactid == contact

    def test_qualify_lead_with_both_account_and_contact(self, db, salesperson):
        """Test qualifying lead creates both account and contact, with contact linked to account."""
        lead = LeadFactory(
            ownerid=salesperson,
            firstname='John',
            lastname='Doe',
            companyname='Acme Corp',
            emailaddress1='john@acme.com',
        )

        dto = QualifyLeadDto(
            createAccount=True,
            createContact=True,
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        # Check both were created
        from apps.accounts.models import Account
        from apps.contacts.models import Contact

        account = Account.objects.get(name='Acme Corp')
        contact = Contact.objects.get(firstname='John', lastname='Doe')

        # Check contact is linked to account
        assert contact.parentcustomerid == account

        # Check opportunity linked to both
        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.accountid == account
        assert opportunity.contactid == contact

    def test_qualify_lead_custom_opportunity_name(self, db, salesperson):
        """Test qualifying lead with custom opportunity name."""
        lead = LeadFactory(ownerid=salesperson)

        dto = QualifyLeadDto(
            createAccount=False,
            createContact=False,
            opportunityName='Big Deal 2025',
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.name == 'Big Deal 2025'

    def test_qualify_lead_custom_revenue_and_date(self, db, salesperson):
        """Test qualifying lead with custom estimated revenue and close date."""
        lead = LeadFactory(ownerid=salesperson)
        close_date = date.today() + timedelta(days=60)

        dto = QualifyLeadDto(
            createAccount=False,
            createContact=False,
            estimatedValue=Decimal('100000.00'),
            estimatedCloseDate=close_date,
        )

        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        from apps.opportunities.models import Opportunity
        opportunity = Opportunity.objects.get(opportunityid=result['opportunityId'])
        assert opportunity.estimatedrevenue == Decimal('100000.00')
        assert opportunity.estimatedclosedate == close_date

    def test_qualify_lead_cannot_qualify_already_qualified(self, db, salesperson):
        """Test cannot qualify an already qualified lead."""
        lead = QualifiedLeadFactory(ownerid=salesperson)

        dto = QualifyLeadDto(createAccount=False, createContact=False)

        with pytest.raises(ValidationError, match='Only open leads can be qualified'):
            LeadService.qualify_lead(lead.leadid, dto, salesperson)

    def test_qualify_lead_cannot_qualify_disqualified(self, db, salesperson):
        """Test cannot qualify a disqualified lead."""
        lead = DisqualifiedLeadFactory(ownerid=salesperson)

        dto = QualifyLeadDto(createAccount=False, createContact=False)

        with pytest.raises(ValidationError, match='Only open leads can be qualified'):
            LeadService.qualify_lead(lead.leadid, dto, salesperson)

    def test_qualify_lead_atomic_transaction(self, db, salesperson):
        """Test that qualification creates all entities atomically."""
        lead = LeadFactory(
            ownerid=salesperson,
            companyname='Test Corp',
            firstname='John',
            lastname='Doe',
        )

        dto = QualifyLeadDto(
            createAccount=True,
            createContact=True,
        )

        # Qualify the lead
        result = LeadService.qualify_lead(lead.leadid, dto, salesperson)

        # Verify all entities were created
        from apps.opportunities.models import Opportunity
        from apps.accounts.models import Account
        from apps.contacts.models import Contact

        # All should exist
        assert Account.objects.filter(name='Test Corp').exists()
        assert Contact.objects.filter(firstname='John', lastname='Doe').exists()
        assert Opportunity.objects.filter(opportunityid=result['opportunityId']).exists()

        # Lead should be qualified (reload from DB)
        lead.refresh_from_db()
        assert lead.statecode == LeadStateCode.QUALIFIED


@pytest.mark.unit
@pytest.mark.workflow
class TestDisqualifyLead:
    """Tests for LeadService.disqualify_lead method."""

    def test_disqualify_lead_lost(self, db, salesperson):
        """Test disqualifying lead as lost with reason."""
        lead = LeadFactory(ownerid=salesperson)

        dto = DisqualifyLeadDto(reason='Price too high')

        disqualified = LeadService.disqualify_lead(lead.leadid, dto, salesperson)

        assert disqualified.statecode == LeadStateCode.DISQUALIFIED
        assert disqualified.statuscode == LeadStatusCode.LOST
        assert 'Price too high' in disqualified.description

    def test_disqualify_lead_without_reason(self, db, salesperson):
        """Test disqualifying lead without a reason."""
        lead = LeadFactory(ownerid=salesperson)

        dto = DisqualifyLeadDto()

        disqualified = LeadService.disqualify_lead(lead.leadid, dto, salesperson)

        assert disqualified.statecode == LeadStateCode.DISQUALIFIED
        assert disqualified.statuscode == LeadStatusCode.LOST

    def test_disqualify_lead_with_reason(self, db, salesperson):
        """Test disqualifying lead appends reason to description."""
        lead = LeadFactory(ownerid=salesperson, description='Original description')

        dto = DisqualifyLeadDto(reason='Found another vendor')

        disqualified = LeadService.disqualify_lead(lead.leadid, dto, salesperson)

        assert disqualified.statuscode == LeadStatusCode.LOST
        assert 'Found another vendor' in disqualified.description
        assert 'Original description' in disqualified.description

    def test_disqualify_lead_cannot_disqualify_qualified(self, db, salesperson):
        """Test cannot disqualify an already qualified lead."""
        lead = QualifiedLeadFactory(ownerid=salesperson)

        dto = DisqualifyLeadDto(statuscode=LeadStatusCode.LOST)

        with pytest.raises(ValidationError, match='Only open leads can be disqualified'):
            LeadService.disqualify_lead(lead.leadid, dto, salesperson)


@pytest.mark.unit
class TestDeleteLead:
    """Tests for LeadService.delete_lead method."""

    def test_delete_lead(self, db, salesperson):
        """Test deleting a lead (soft delete as disqualified/lost)."""
        lead = LeadFactory(ownerid=salesperson)

        deleted = LeadService.delete_lead(lead.leadid, salesperson)

        assert deleted.statecode == LeadStateCode.DISQUALIFIED
        assert deleted.statuscode == LeadStatusCode.LOST
        assert 'Deleted by user' in deleted.description


@pytest.mark.unit
class TestGetLeadStats:
    """Tests for LeadService.get_lead_stats method."""

    def test_get_lead_stats_count_by_state(self, db, salesperson):
        """Test getting lead statistics - counts by state."""
        LeadFactory.create_batch(3, ownerid=salesperson, statecode=LeadStateCode.OPEN)
        QualifiedLeadFactory.create_batch(2, ownerid=salesperson)
        DisqualifiedLeadFactory(ownerid=salesperson)

        stats = LeadService.get_lead_stats(salesperson)

        assert stats.total_leads == 6
        assert stats.open_leads == 3
        assert stats.qualified_leads == 2
        assert stats.disqualified_leads == 1

    def test_get_lead_stats_by_quality(self, db, salesperson):
        """Test lead statistics by quality."""
        HotLeadFactory.create_batch(2, ownerid=salesperson)
        LeadFactory.create_batch(3, ownerid=salesperson, leadqualitycode=LeadQualityCode.WARM)

        stats = LeadService.get_lead_stats(salesperson)

        assert stats.leads_by_quality['Hot'] == 2
        assert stats.leads_by_quality['Warm'] == 3

    def test_get_lead_stats_value_metrics(self, db, salesperson):
        """Test lead statistics value metrics."""
        LeadFactory(ownerid=salesperson, estimatedvalue=Decimal('10000.00'))
        LeadFactory(ownerid=salesperson, estimatedvalue=Decimal('20000.00'))
        LeadFactory(ownerid=salesperson, estimatedvalue=Decimal('30000.00'))

        stats = LeadService.get_lead_stats(salesperson)

        assert stats.total_estimated_value == Decimal('60000.00')
        assert stats.avg_estimated_value == Decimal('20000.00')

    def test_get_lead_stats_respects_ownership(self, db, salesperson, salesperson2):
        """Test that stats only include user's own leads."""
        LeadFactory.create_batch(3, ownerid=salesperson)
        LeadFactory.create_batch(5, ownerid=salesperson2)

        stats = LeadService.get_lead_stats(salesperson)

        assert stats.total_leads == 3  # Only own leads
