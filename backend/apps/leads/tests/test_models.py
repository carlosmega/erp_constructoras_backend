"""
Unit tests for Lead model.

Tests Lead entity including state management, validation,
computed fields, and business rules.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.leads.models import (
    Lead,
    LeadStateCode,
    LeadStatusCode,
    LeadQualityCode,
    LeadSourceCode,
)
from apps.leads.tests.factories import (
    LeadFactory,
    HotLeadFactory,
    ColdLeadFactory,
    QualifiedLeadFactory,
    DisqualifiedLeadFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestLeadEnums:
    """Tests for Lead enum definitions."""

    def test_lead_state_code_values(self):
        """Test LeadStateCode enum values."""
        assert LeadStateCode.OPEN.value == 0
        assert LeadStateCode.QUALIFIED.value == 1
        assert LeadStateCode.DISQUALIFIED.value == 2

        assert LeadStateCode.OPEN.label == 'Open'
        assert LeadStateCode.QUALIFIED.label == 'Qualified'
        assert LeadStateCode.DISQUALIFIED.label == 'Disqualified'

    def test_lead_status_code_values(self):
        """Test LeadStatusCode enum values."""
        assert LeadStatusCode.NEW.value == 1
        assert LeadStatusCode.CONTACTED.value == 2
        assert LeadStatusCode.QUALIFIED.value == 3
        assert LeadStatusCode.LOST.value == 4
        assert LeadStatusCode.CANNOT_CONTACT.value == 5
        assert LeadStatusCode.NO_LONGER_INTERESTED.value == 6

    def test_lead_quality_code_values(self):
        """Test LeadQualityCode enum values."""
        assert LeadQualityCode.COLD.value == 1
        assert LeadQualityCode.WARM.value == 2
        assert LeadQualityCode.HOT.value == 3

    def test_lead_source_code_values(self):
        """Test LeadSourceCode enum values."""
        assert LeadSourceCode.WEB.value == 8
        assert LeadSourceCode.ADVERTISEMENT.value == 1
        assert LeadSourceCode.TRADE_SHOW.value == 7


@pytest.mark.unit
class TestLeadModel:
    """Tests for Lead model creation and basic operations."""

    def test_create_lead_minimal(self, db):
        """Test creating a lead with minimal required fields."""
        owner = SalespersonFactory()
        lead = Lead.objects.create(
            lastname='Doe',
            ownerid=owner,
        )

        assert lead.leadid is not None
        assert lead.lastname == 'Doe'
        assert lead.fullname == 'Doe'
        assert lead.statecode == LeadStateCode.OPEN
        assert lead.statuscode == LeadStatusCode.NEW
        assert lead.ownerid == owner

    def test_create_lead_full(self, db):
        """Test creating a lead with all fields."""
        owner = SalespersonFactory()
        today = date.today()

        lead = Lead.objects.create(
            firstname='John',
            lastname='Doe',
            emailaddress1='john@example.com',
            telephone1='555-1234',
            mobilephone='555-5678',
            companyname='Acme Corp',
            jobtitle='CEO',
            subject='Interested in Product X',
            description='Lead came from trade show',
            leadqualitycode=LeadQualityCode.HOT,
            leadsourcecode=LeadSourceCode.TRADE_SHOW,
            estimatedvalue=Decimal('50000.00'),
            estimatedclosedate=today + timedelta(days=30),
            ownerid=owner,
        )

        assert lead.leadid is not None
        assert lead.firstname == 'John'
        assert lead.lastname == 'Doe'
        assert lead.fullname == 'John Doe'
        assert lead.emailaddress1 == 'john@example.com'
        assert lead.companyname == 'Acme Corp'
        assert lead.leadqualitycode == LeadQualityCode.HOT
        assert lead.leadsourcecode == LeadSourceCode.TRADE_SHOW
        assert lead.estimatedvalue == Decimal('50000.00')

    def test_lead_factory(self, db):
        """Test LeadFactory creates valid leads."""
        lead = LeadFactory()

        assert lead.leadid is not None
        assert lead.firstname is not None
        assert lead.lastname is not None
        assert lead.fullname is not None
        assert lead.ownerid is not None
        assert lead.statecode == LeadStateCode.OPEN
        assert lead.statuscode == LeadStatusCode.NEW

    def test_lead_str_representation(self, db):
        """Test __str__ method."""
        lead = LeadFactory(firstname='John', lastname='Doe')
        assert str(lead) == 'John Doe'

        # Lead without firstname
        lead2 = LeadFactory(firstname='', lastname='Smith')
        assert str(lead2) == 'Smith'


@pytest.mark.unit
class TestLeadFullnameComputation:
    """Tests for automatic fullname computation."""

    def test_fullname_computed_on_save(self, db):
        """Test fullname is auto-computed when saving."""
        owner = SalespersonFactory()
        lead = Lead(
            firstname='John',
            lastname='Doe',
            ownerid=owner,
        )
        lead.save()

        assert lead.fullname == 'John Doe'

    def test_fullname_lastname_only(self, db):
        """Test fullname with only lastname."""
        owner = SalespersonFactory()
        lead = Lead(
            lastname='Doe',
            ownerid=owner,
        )
        lead.save()

        assert lead.fullname == 'Doe'

    def test_fullname_updated_on_change(self, db):
        """Test fullname updates when name changes."""
        lead = LeadFactory(firstname='John', lastname='Doe')
        assert lead.fullname == 'John Doe'

        lead.firstname = 'Jane'
        lead.save()

        assert lead.fullname == 'Jane Doe'

    def test_fullname_empty_when_no_names(self, db):
        """Test fullname is empty when no names provided."""
        owner = SalespersonFactory()
        lead = Lead(
            lastname='',
            ownerid=owner,
        )
        # This would fail validation, but for testing the save logic
        # we can create without full_clean
        lead.save()

        assert lead.fullname == ''


@pytest.mark.unit
class TestLeadProperties:
    """Tests for Lead computed properties."""

    def test_is_open_property(self, db):
        """Test is_open property."""
        open_lead = LeadFactory(statecode=LeadStateCode.OPEN)
        qualified_lead = QualifiedLeadFactory()

        assert open_lead.is_open is True
        assert qualified_lead.is_open is False

    def test_is_qualified_property(self, db):
        """Test is_qualified property."""
        open_lead = LeadFactory(statecode=LeadStateCode.OPEN)
        qualified_lead = QualifiedLeadFactory()

        assert open_lead.is_qualified is False
        assert qualified_lead.is_qualified is True

    def test_is_disqualified_property(self, db):
        """Test is_disqualified property."""
        open_lead = LeadFactory(statecode=LeadStateCode.OPEN)
        disqualified_lead = DisqualifiedLeadFactory()

        assert open_lead.is_disqualified is False
        assert disqualified_lead.is_disqualified is True

    def test_state_name_property(self, db):
        """Test state_name property returns human-readable name."""
        open_lead = LeadFactory(statecode=LeadStateCode.OPEN)
        qualified_lead = QualifiedLeadFactory()
        disqualified_lead = DisqualifiedLeadFactory()

        assert open_lead.state_name == 'Open'
        assert qualified_lead.state_name == 'Qualified'
        assert disqualified_lead.state_name == 'Disqualified'

    def test_status_name_property(self, db):
        """Test status_name property returns human-readable name."""
        new_lead = LeadFactory(statuscode=LeadStatusCode.NEW)
        contacted_lead = LeadFactory(statuscode=LeadStatusCode.CONTACTED)
        qualified_lead = QualifiedLeadFactory()

        assert new_lead.status_name == 'New'
        assert contacted_lead.status_name == 'Contacted'
        assert qualified_lead.status_name == 'Qualified'

    def test_quality_name_property(self, db):
        """Test quality_name property."""
        cold_lead = ColdLeadFactory()
        hot_lead = HotLeadFactory()
        lead_no_quality = LeadFactory(leadqualitycode=None)

        assert cold_lead.quality_name == 'Cold'
        assert hot_lead.quality_name == 'Hot'
        assert lead_no_quality.quality_name is None

    def test_source_name_property(self, db):
        """Test source_name property."""
        web_lead = LeadFactory(leadsourcecode=LeadSourceCode.WEB)
        trade_show_lead = LeadFactory(leadsourcecode=LeadSourceCode.TRADE_SHOW)
        lead_no_source = LeadFactory(leadsourcecode=None)

        assert web_lead.source_name == 'Web'
        assert trade_show_lead.source_name == 'Trade Show'
        assert lead_no_source.source_name is None


@pytest.mark.unit
class TestLeadValidation:
    """Tests for Lead model validation."""

    def test_lastname_required(self, db):
        """Test lastname is required."""
        owner = SalespersonFactory()

        # Create lead without lastname - should use ValidationError
        with pytest.raises((ValidationError, IntegrityError)):
            lead = Lead(
                firstname='John',
                lastname='',  # Empty lastname
                ownerid=owner,
            )
            lead.full_clean()  # This will raise ValidationError

    def test_ownerid_required(self, db):
        """Test ownerid is required."""
        lead = Lead(lastname='Doe')

        with pytest.raises(IntegrityError):
            lead.save()

    def test_email_format_validation(self, db):
        """Test email format validation."""
        owner = SalespersonFactory()

        # Valid email
        lead_valid = Lead(
            lastname='Doe',
            emailaddress1='valid@email.com',
            ownerid=owner,
        )
        lead_valid.full_clean()  # Should not raise

        # Invalid email
        lead_invalid = Lead(
            lastname='Doe',
            emailaddress1='invalid-email',
            ownerid=owner,
        )

        with pytest.raises(ValidationError):
            lead_invalid.full_clean()

    def test_estimated_value_positive(self, db):
        """Test estimatedvalue must be positive."""
        owner = SalespersonFactory()

        # Positive value is OK
        lead_valid = Lead(
            lastname='Doe',
            estimatedvalue=Decimal('1000.00'),
            ownerid=owner,
        )
        lead_valid.full_clean()  # Should not raise

        # Negative value fails
        lead_invalid = Lead(
            lastname='Doe',
            estimatedvalue=Decimal('-1000.00'),
            ownerid=owner,
        )

        with pytest.raises(ValidationError):
            lead_invalid.full_clean()

    def test_state_code_valid_choices(self, db):
        """Test statecode must be valid choice."""
        lead = LeadFactory()

        lead.statecode = LeadStateCode.OPEN
        lead.full_clean()  # Should not raise

        lead.statecode = 999  # Invalid value
        with pytest.raises(ValidationError):
            lead.full_clean()


@pytest.mark.unit
class TestLeadOrdering:
    """Tests for Lead model ordering."""

    def test_leads_ordered_by_createdon_desc(self, db):
        """Test that leads are ordered by createdon descending."""
        # Factories will create with different timestamps
        lead1 = LeadFactory()
        lead2 = LeadFactory()
        lead3 = LeadFactory()

        leads = list(Lead.objects.all())

        # Most recent first
        assert leads[0].leadid == lead3.leadid
        assert leads[1].leadid == lead2.leadid
        assert leads[2].leadid == lead1.leadid


@pytest.mark.unit
class TestLeadFactories:
    """Tests for Lead factories."""

    def test_hot_lead_factory(self, db):
        """Test HotLeadFactory creates hot leads."""
        lead = HotLeadFactory()

        assert lead.leadqualitycode == LeadQualityCode.HOT
        assert lead.statuscode == LeadStatusCode.CONTACTED
        assert lead.estimatedvalue >= Decimal('50000.00')

    def test_cold_lead_factory(self, db):
        """Test ColdLeadFactory creates cold leads."""
        lead = ColdLeadFactory()

        assert lead.leadqualitycode == LeadQualityCode.COLD
        assert lead.estimatedvalue <= Decimal('5000.00')

    def test_qualified_lead_factory(self, db):
        """Test QualifiedLeadFactory creates qualified leads."""
        lead = QualifiedLeadFactory()

        assert lead.statecode == LeadStateCode.QUALIFIED
        assert lead.statuscode == LeadStatusCode.QUALIFIED
        assert lead.leadqualitycode == LeadQualityCode.HOT

    def test_disqualified_lead_factory(self, db):
        """Test DisqualifiedLeadFactory creates disqualified leads."""
        lead = DisqualifiedLeadFactory()

        assert lead.statecode == LeadStateCode.DISQUALIFIED
        assert lead.statuscode in [
            LeadStatusCode.LOST,
            LeadStatusCode.CANNOT_CONTACT,
            LeadStatusCode.NO_LONGER_INTERESTED,
        ]


@pytest.mark.unit
class TestLeadAuditFields:
    """Tests for Lead audit trail fields (from AuditMixin)."""

    def test_lead_has_audit_fields(self, db):
        """Test that lead has createdby, modifiedby, createdon, modifiedon."""
        owner = SalespersonFactory()
        lead = LeadFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert hasattr(lead, 'createdon')
        assert hasattr(lead, 'modifiedon')
        assert hasattr(lead, 'createdby')
        assert hasattr(lead, 'modifiedby')

        assert lead.createdon is not None
        assert lead.modifiedon is not None
        assert lead.createdby == owner
        assert lead.modifiedby == owner

    def test_modifiedon_updates_on_save(self, db):
        """Test that modifiedon updates when lead is saved."""
        lead = LeadFactory()
        original_modifiedon = lead.modifiedon

        # Small delay to ensure timestamp difference
        import time
        time.sleep(0.01)

        lead.subject = 'Updated subject'
        lead.save()

        assert lead.modifiedon > original_modifiedon
