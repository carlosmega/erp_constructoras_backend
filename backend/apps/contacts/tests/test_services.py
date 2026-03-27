"""
Unit tests for Contact services.

Tests contact CRUD operations, ownership filtering, parent account
relationships, deactivation, and search functionality.
"""

import pytest
from uuid import uuid4

from apps.contacts.models import Contact, ContactStateCode, ContactStatusCode
from apps.contacts.services import ContactService
from apps.contacts.schemas import CreateContactDto, UpdateContactDto
from apps.contacts.tests.factories import ContactFactory, ContactWithAccountFactory, InactiveContactFactory
from apps.accounts.tests.factories import AccountFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


@pytest.mark.unit
class TestCreateContact:
    """Tests for ContactService.create_contact method."""

    def test_create_contact_minimal(self, db, salesperson):
        """Test creating a contact with minimal required fields."""
        dto = CreateContactDto(lastname='Doe')

        contact = ContactService.create_contact(dto, salesperson)

        assert contact.contactid is not None
        assert contact.lastname == 'Doe'
        assert contact.fullname == 'Doe'
        assert contact.statecode == ContactStateCode.ACTIVE
        assert contact.statuscode == ContactStatusCode.ACTIVE
        assert contact.ownerid == salesperson
        assert contact.createdby == salesperson
        assert contact.modifiedby == salesperson

    def test_create_contact_full(self, db, salesperson):
        """Test creating a contact with all fields populated."""
        account = AccountFactory(ownerid=salesperson)
        dto = CreateContactDto(
            firstname='John',
            lastname='Doe',
            emailaddress1='john@example.com',
            telephone1='555-1234',
            mobilephone='555-5678',
            jobtitle='CEO',
            parentcustomerid=account.accountid,
            address1_line1='123 Main St',
            address1_city='Springfield',
            description='Key contact',
        )

        contact = ContactService.create_contact(dto, salesperson)

        assert contact.firstname == 'John'
        assert contact.lastname == 'Doe'
        assert contact.fullname == 'John Doe'
        assert contact.emailaddress1 == 'john@example.com'
        assert contact.jobtitle == 'CEO'
        assert contact.parentcustomerid_id == account.accountid

    def test_create_contact_with_different_owner(self, db, salesperson, salesperson2):
        """Test creating a contact assigned to a different owner."""
        dto = CreateContactDto(
            lastname='Doe',
            ownerid=salesperson2.systemuserid,
        )

        contact = ContactService.create_contact(dto, salesperson)

        assert contact.ownerid == salesperson2
        assert contact.createdby == salesperson

    def test_create_contact_invalid_owner(self, db, salesperson):
        """Test creating a contact with non-existent owner."""
        invalid_id = uuid4()
        dto = CreateContactDto(
            lastname='Doe',
            ownerid=invalid_id,
        )

        with pytest.raises(ValidationError, match='not found'):
            ContactService.create_contact(dto, salesperson)

    def test_create_contact_with_parent_account(self, db, salesperson):
        """Test creating a contact linked to a parent account."""
        account = AccountFactory(ownerid=salesperson, name='Acme Corp')
        dto = CreateContactDto(
            firstname='John',
            lastname='Doe',
            parentcustomerid=account.accountid,
        )

        contact = ContactService.create_contact(dto, salesperson)

        assert contact.parentcustomerid_id == account.accountid


@pytest.mark.unit
class TestListContacts:
    """Tests for ContactService.list_contacts method."""

    def test_salesperson_sees_own_only(self, db, salesperson, salesperson2):
        """Test that salesperson only sees their own contacts."""
        ContactFactory(ownerid=salesperson)
        ContactFactory(ownerid=salesperson)
        ContactFactory(ownerid=salesperson2)

        contacts = ContactService.list_contacts(salesperson)

        assert contacts.count() == 2

    def test_admin_sees_all(self, db, system_admin, salesperson):
        """Test that System Administrator sees all contacts."""
        ContactFactory(ownerid=salesperson)
        ContactFactory(ownerid=system_admin)

        contacts = ContactService.list_contacts(system_admin)

        assert contacts.count() == 2

    def test_filter_by_state(self, db, salesperson):
        """Test filtering contacts by state code."""
        ContactFactory(ownerid=salesperson, statecode=ContactStateCode.ACTIVE)
        ContactFactory(ownerid=salesperson, statecode=ContactStateCode.ACTIVE)
        InactiveContactFactory(ownerid=salesperson)

        active = ContactService.list_contacts(salesperson, statecode=ContactStateCode.ACTIVE)
        inactive = ContactService.list_contacts(salesperson, statecode=ContactStateCode.INACTIVE)

        assert active.count() == 2
        assert inactive.count() == 1

    def test_filter_by_parent_account(self, db, salesperson):
        """Test filtering contacts by parent account."""
        account = AccountFactory(ownerid=salesperson)
        ContactFactory(ownerid=salesperson, parentcustomerid=account)
        ContactFactory(ownerid=salesperson, parentcustomerid=account)
        ContactFactory(ownerid=salesperson, parentcustomerid=None)

        results = ContactService.list_contacts(salesperson, parentcustomerid=account.accountid)

        assert results.count() == 2

    def test_search(self, db, salesperson):
        """Test searching contacts by name, email, job title."""
        ContactFactory(ownerid=salesperson, firstname='John', lastname='Doe', emailaddress1='john@test.com')
        ContactFactory(ownerid=salesperson, firstname='Jane', lastname='Smith', jobtitle='CEO')

        # Search by name (fullname)
        results = ContactService.list_contacts(salesperson, search='John')
        assert results.count() >= 1

        # Search by job title
        results = ContactService.list_contacts(salesperson, search='CEO')
        assert results.count() >= 1

    def test_filter_by_owner_admin(self, db, system_admin, salesperson):
        """Test that admin can filter by specific owner."""
        ContactFactory(ownerid=salesperson)
        ContactFactory(ownerid=salesperson)
        ContactFactory(ownerid=system_admin)

        contacts = ContactService.list_contacts(system_admin, ownerid=salesperson.systemuserid)

        assert contacts.count() == 2

    def test_filter_by_owner_forbidden(self, db, salesperson, salesperson2):
        """Test that non-admin cannot filter by other owners."""
        ContactFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="cannot view other users"):
            ContactService.list_contacts(salesperson, ownerid=salesperson2.systemuserid)


@pytest.mark.unit
class TestGetContactById:
    """Tests for ContactService.get_contact_by_id method."""

    def test_get_contact_by_id_owner(self, db, salesperson):
        """Test getting contact by ID as owner."""
        contact = ContactFactory(ownerid=salesperson)

        retrieved = ContactService.get_contact_by_id(contact.contactid, salesperson)

        assert retrieved.contactid == contact.contactid

    def test_get_contact_by_id_admin(self, db, system_admin, salesperson):
        """Test that admin can get any contact."""
        contact = ContactFactory(ownerid=salesperson)

        retrieved = ContactService.get_contact_by_id(contact.contactid, system_admin)

        assert retrieved.contactid == contact.contactid

    def test_get_contact_by_id_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot get contact."""
        contact = ContactFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="don't have access"):
            ContactService.get_contact_by_id(contact.contactid, salesperson)

    def test_get_contact_by_id_not_found(self, db, salesperson):
        """Test getting non-existent contact."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            ContactService.get_contact_by_id(invalid_id, salesperson)


@pytest.mark.unit
class TestUpdateContact:
    """Tests for ContactService.update_contact method."""

    def test_update_contact_basic_fields(self, db, salesperson):
        """Test updating basic contact fields."""
        contact = ContactFactory(ownerid=salesperson, firstname='John', lastname='Doe')

        dto = UpdateContactDto(
            firstname='Jane',
            emailaddress1='jane@example.com',
            telephone1='555-9999',
        )

        updated = ContactService.update_contact(contact.contactid, dto, salesperson)

        assert updated.firstname == 'Jane'
        assert updated.fullname == 'Jane Doe'  # Auto-computed
        assert updated.emailaddress1 == 'jane@example.com'
        assert updated.telephone1 == '555-9999'
        assert updated.modifiedby == salesperson

    def test_update_contact_parent_account(self, db, salesperson):
        """Test updating contact's parent account."""
        contact = ContactFactory(ownerid=salesperson, parentcustomerid=None)
        account = AccountFactory(ownerid=salesperson, name='New Company')

        dto = UpdateContactDto(parentcustomerid=account.accountid)
        updated = ContactService.update_contact(contact.contactid, dto, salesperson)

        assert updated.parentcustomerid_id == account.accountid

    def test_update_contact_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot update contact."""
        contact = ContactFactory(ownerid=salesperson2)

        dto = UpdateContactDto(firstname='New Name')

        with pytest.raises(PermissionDenied):
            ContactService.update_contact(contact.contactid, dto, salesperson)


@pytest.mark.unit
class TestDeactivateContact:
    """Tests for ContactService.deactivate_contact method."""

    def test_deactivate_contact(self, db, salesperson):
        """Test deactivating a contact."""
        contact = ContactFactory(ownerid=salesperson, statecode=ContactStateCode.ACTIVE)

        deactivated = ContactService.deactivate_contact(contact.contactid, salesperson)

        assert deactivated.statecode == ContactStateCode.INACTIVE
        assert deactivated.modifiedby == salesperson

    def test_deactivate_contact_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot deactivate contact."""
        contact = ContactFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied):
            ContactService.deactivate_contact(contact.contactid, salesperson)
