"""
Unit tests for Contact model.

Tests Contact entity including state management, validation,
computed fields, parent account relationship, and business rules.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.contacts.models import (
    Contact,
    ContactStateCode,
    ContactStatusCode,
)
from apps.contacts.tests.factories import (
    ContactFactory,
    ContactWithAccountFactory,
    InactiveContactFactory,
)
from apps.accounts.tests.factories import AccountFactory
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestContactEnums:
    """Tests for Contact enum definitions."""

    def test_contact_state_code_values(self):
        """Test ContactStateCode enum values."""
        assert ContactStateCode.ACTIVE.value == 0
        assert ContactStateCode.INACTIVE.value == 1

        assert ContactStateCode.ACTIVE.label == 'Active'
        assert ContactStateCode.INACTIVE.label == 'Inactive'

    def test_contact_status_code_values(self):
        """Test ContactStatusCode enum values."""
        assert ContactStatusCode.ACTIVE.value == 1
        assert ContactStatusCode.INACTIVE.value == 2

        assert ContactStatusCode.ACTIVE.label == 'Active'
        assert ContactStatusCode.INACTIVE.label == 'Inactive'


@pytest.mark.unit
class TestContactModel:
    """Tests for Contact model creation and basic operations."""

    def test_create_contact_minimal(self, db):
        """Test creating a contact with minimal required fields."""
        owner = SalespersonFactory()
        contact = Contact.objects.create(
            lastname='Doe',
            ownerid=owner,
        )

        assert contact.contactid is not None
        assert contact.lastname == 'Doe'
        assert contact.fullname == 'Doe'
        assert contact.statecode == ContactStateCode.ACTIVE
        assert contact.statuscode == ContactStatusCode.ACTIVE
        assert contact.ownerid == owner

    def test_create_contact_full(self, db):
        """Test creating a contact with all fields."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner)

        contact = Contact.objects.create(
            firstname='John',
            lastname='Doe',
            emailaddress1='john@example.com',
            telephone1='555-1234',
            mobilephone='555-5678',
            jobtitle='CEO',
            parentcustomerid=account,
            address1_line1='123 Main St',
            address1_city='Springfield',
            description='Key decision maker',
            ownerid=owner,
        )

        assert contact.contactid is not None
        assert contact.firstname == 'John'
        assert contact.lastname == 'Doe'
        assert contact.fullname == 'John Doe'
        assert contact.emailaddress1 == 'john@example.com'
        assert contact.jobtitle == 'CEO'
        assert contact.parentcustomerid == account

    def test_contact_factory(self, db):
        """Test ContactFactory creates valid contacts."""
        contact = ContactFactory()

        assert contact.contactid is not None
        assert contact.firstname is not None
        assert contact.lastname is not None
        assert contact.fullname is not None
        assert contact.ownerid is not None
        assert contact.statecode == ContactStateCode.ACTIVE
        assert contact.statuscode == ContactStatusCode.ACTIVE

    def test_contact_str_representation(self, db):
        """Test __str__ method."""
        contact = ContactFactory(firstname='John', lastname='Doe')
        assert str(contact) == 'John Doe'

        # Contact without firstname
        contact2 = ContactFactory(firstname='', lastname='Smith')
        assert str(contact2) == 'Smith'


@pytest.mark.unit
class TestContactFullnameComputation:
    """Tests for automatic fullname computation."""

    def test_fullname_computed_on_save(self, db):
        """Test fullname is auto-computed when saving."""
        owner = SalespersonFactory()
        contact = Contact(
            firstname='John',
            lastname='Doe',
            ownerid=owner,
        )
        contact.save()

        assert contact.fullname == 'John Doe'

    def test_fullname_lastname_only(self, db):
        """Test fullname with only lastname."""
        owner = SalespersonFactory()
        contact = Contact(
            lastname='Doe',
            ownerid=owner,
        )
        contact.save()

        assert contact.fullname == 'Doe'

    def test_fullname_updated_on_change(self, db):
        """Test fullname updates when name changes."""
        contact = ContactFactory(firstname='John', lastname='Doe')
        assert contact.fullname == 'John Doe'

        contact.firstname = 'Jane'
        contact.save()

        assert contact.fullname == 'Jane Doe'

    def test_fullname_empty_when_no_names(self, db):
        """Test fullname is empty when no names provided."""
        owner = SalespersonFactory()
        contact = Contact(
            lastname='',
            ownerid=owner,
        )
        contact.save()

        assert contact.fullname == ''


@pytest.mark.unit
class TestContactProperties:
    """Tests for Contact computed properties."""

    def test_is_active_property(self, db):
        """Test is_active property."""
        active_contact = ContactFactory(statecode=ContactStateCode.ACTIVE)
        inactive_contact = InactiveContactFactory()

        assert active_contact.is_active is True
        assert inactive_contact.is_active is False

    def test_state_name_property(self, db):
        """Test state_name property returns human-readable name."""
        active_contact = ContactFactory(statecode=ContactStateCode.ACTIVE)
        inactive_contact = InactiveContactFactory()

        assert active_contact.state_name == 'Active'
        assert inactive_contact.state_name == 'Inactive'

    def test_status_name_property(self, db):
        """Test status_name property returns human-readable name."""
        active_contact = ContactFactory(statuscode=ContactStatusCode.ACTIVE)
        inactive_contact = InactiveContactFactory()

        assert active_contact.status_name == 'Active'
        assert inactive_contact.status_name == 'Inactive'

    def test_company_name_property(self, db):
        """Test company_name property returns parent account name."""
        contact_with_account = ContactWithAccountFactory()
        contact_without_account = ContactFactory(parentcustomerid=None)

        assert contact_with_account.company_name is not None
        assert contact_with_account.company_name == contact_with_account.parentcustomerid.name
        assert contact_without_account.company_name is None


@pytest.mark.unit
class TestContactParentAccountRelationship:
    """Tests for Contact-Account (parentcustomerid) relationship."""

    def test_contact_with_parent_account(self, db):
        """Test creating contact linked to parent account."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner, name='Acme Corp')
        contact = ContactFactory(ownerid=owner, parentcustomerid=account)

        assert contact.parentcustomerid == account
        assert contact.company_name == 'Acme Corp'

    def test_contact_without_parent_account(self, db):
        """Test creating contact without parent account (B2C)."""
        contact = ContactFactory(parentcustomerid=None)

        assert contact.parentcustomerid is None
        assert contact.company_name is None

    def test_account_contacts_reverse_relation(self, db):
        """Test that Account has reverse relation to its contacts."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner)
        contact1 = ContactFactory(ownerid=owner, parentcustomerid=account)
        contact2 = ContactFactory(ownerid=owner, parentcustomerid=account)

        assert account.contacts.count() == 2
        assert contact1 in account.contacts.all()
        assert contact2 in account.contacts.all()


@pytest.mark.unit
class TestContactValidation:
    """Tests for Contact model validation."""

    def test_lastname_required(self, db):
        """Test lastname is required."""
        owner = SalespersonFactory()

        with pytest.raises((ValidationError, IntegrityError)):
            contact = Contact(
                firstname='John',
                lastname='',
                ownerid=owner,
            )
            contact.full_clean()

    def test_ownerid_required(self, db):
        """Test ownerid is required."""
        contact = Contact(lastname='Doe')

        with pytest.raises(IntegrityError):
            contact.save()

    def test_email_format_validation(self, db):
        """Test email format validation."""
        owner = SalespersonFactory()

        # Valid email
        contact_valid = Contact(
            lastname='Doe',
            emailaddress1='valid@email.com',
            ownerid=owner,
        )
        contact_valid.full_clean()  # Should not raise

        # Invalid email
        contact_invalid = Contact(
            lastname='Doe',
            emailaddress1='invalid-email',
            ownerid=owner,
        )

        with pytest.raises(ValidationError):
            contact_invalid.full_clean()

    def test_state_code_valid_choices(self, db):
        """Test statecode must be valid choice."""
        contact = ContactFactory()

        contact.statecode = ContactStateCode.ACTIVE
        contact.full_clean()  # Should not raise

        contact.statecode = 999  # Invalid value
        with pytest.raises(ValidationError):
            contact.full_clean()


@pytest.mark.unit
class TestContactOrdering:
    """Tests for Contact model ordering."""

    def test_contacts_ordered_by_createdon_desc(self, db):
        """Test that contacts are ordered by createdon descending."""
        contact1 = ContactFactory()
        contact2 = ContactFactory()
        contact3 = ContactFactory()

        contacts = list(Contact.objects.all())

        assert contacts[0].contactid == contact3.contactid
        assert contacts[1].contactid == contact2.contactid
        assert contacts[2].contactid == contact1.contactid


@pytest.mark.unit
class TestContactFactories:
    """Tests for Contact factories."""

    def test_contact_with_account_factory(self, db):
        """Test ContactWithAccountFactory creates contact with account."""
        contact = ContactWithAccountFactory()

        assert contact.parentcustomerid is not None
        assert contact.jobtitle is not None

    def test_inactive_contact_factory(self, db):
        """Test InactiveContactFactory creates inactive contacts."""
        contact = InactiveContactFactory()

        assert contact.statecode == ContactStateCode.INACTIVE
        assert contact.statuscode == ContactStatusCode.INACTIVE


@pytest.mark.unit
class TestContactAuditFields:
    """Tests for Contact audit trail fields (from AuditMixin)."""

    def test_contact_has_audit_fields(self, db):
        """Test that contact has createdby, modifiedby, createdon, modifiedon."""
        owner = SalespersonFactory()
        contact = ContactFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert hasattr(contact, 'createdon')
        assert hasattr(contact, 'modifiedon')
        assert hasattr(contact, 'createdby')
        assert hasattr(contact, 'modifiedby')

        assert contact.createdon is not None
        assert contact.modifiedon is not None
        assert contact.createdby == owner
        assert contact.modifiedby == owner

    def test_modifiedon_updates_on_save(self, db):
        """Test that modifiedon updates when contact is saved."""
        contact = ContactFactory()
        original_modifiedon = contact.modifiedon

        import time
        time.sleep(0.01)

        contact.description = 'Updated description'
        contact.save()

        assert contact.modifiedon > original_modifiedon
