"""
Unit tests for Account model.

Tests Account entity including state management, validation,
computed properties, and business rules.
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import (
    Account,
    AccountStateCode,
    AccountStatusCode,
    CustomerTypeCode,
)
from apps.accounts.tests.factories import (
    AccountFactory,
    InactiveAccountFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestAccountEnums:
    """Tests for Account enum definitions."""

    def test_account_state_code_values(self):
        """Test AccountStateCode enum values."""
        assert AccountStateCode.ACTIVE.value == 0
        assert AccountStateCode.INACTIVE.value == 1

        assert AccountStateCode.ACTIVE.label == 'Active'
        assert AccountStateCode.INACTIVE.label == 'Inactive'

    def test_account_status_code_values(self):
        """Test AccountStatusCode enum values."""
        assert AccountStatusCode.ACTIVE.value == 1
        assert AccountStatusCode.INACTIVE.value == 2

        assert AccountStatusCode.ACTIVE.label == 'Active'
        assert AccountStatusCode.INACTIVE.label == 'Inactive'

    def test_customer_type_code_values(self):
        """Test CustomerTypeCode enum values."""
        assert CustomerTypeCode.CUSTOMER.value == 1
        assert CustomerTypeCode.SUPPLIER.value == 2
        assert CustomerTypeCode.BOTH.value == 3

        assert CustomerTypeCode.CUSTOMER.label == 'Customer'
        assert CustomerTypeCode.SUPPLIER.label == 'Supplier'
        assert CustomerTypeCode.BOTH.label == 'Both'


@pytest.mark.unit
class TestAccountModel:
    """Tests for Account model creation and basic operations."""

    def test_create_account_minimal(self, db):
        """Test creating an account with minimal required fields."""
        owner = SalespersonFactory()
        account = Account.objects.create(
            name='Acme Corp',
            ownerid=owner,
        )

        assert account.accountid is not None
        assert account.name == 'Acme Corp'
        assert account.statecode == AccountStateCode.ACTIVE
        assert account.statuscode == AccountStatusCode.ACTIVE
        assert account.customertypecode == CustomerTypeCode.CUSTOMER
        assert account.ownerid == owner

    def test_create_account_full(self, db):
        """Test creating an account with all fields."""
        owner = SalespersonFactory()
        account = Account.objects.create(
            name='Acme Corp',
            accountnumber='ACC000001',
            emailaddress1='info@acme.com',
            telephone1='555-1234',
            websiteurl='https://acme.com',
            address1_line1='123 Main St',
            address1_city='Springfield',
            address1_stateorprovince='IL',
            address1_postalcode='62704',
            address1_country='US',
            description='A large corporation',
            revenue=Decimal('1000000.00'),
            numberofemployees=500,
            customertypecode=CustomerTypeCode.BOTH,
            ownerid=owner,
        )

        assert account.accountid is not None
        assert account.name == 'Acme Corp'
        assert account.emailaddress1 == 'info@acme.com'
        assert account.revenue == Decimal('1000000.00')
        assert account.numberofemployees == 500
        assert account.customertypecode == CustomerTypeCode.BOTH

    def test_account_factory(self, db):
        """Test AccountFactory creates valid accounts."""
        account = AccountFactory()

        assert account.accountid is not None
        assert account.name is not None
        assert account.ownerid is not None
        assert account.statecode == AccountStateCode.ACTIVE
        assert account.statuscode == AccountStatusCode.ACTIVE

    def test_account_str_representation(self, db):
        """Test __str__ method."""
        account = AccountFactory(name='Test Company')
        assert str(account) == 'Test Company'

    def test_account_unique_account_number(self, db):
        """Test accountnumber uniqueness constraint."""
        owner = SalespersonFactory()
        Account.objects.create(
            name='Company A',
            accountnumber='UNIQUE001',
            ownerid=owner,
        )

        with pytest.raises(IntegrityError):
            Account.objects.create(
                name='Company B',
                accountnumber='UNIQUE001',
                ownerid=owner,
            )


@pytest.mark.unit
class TestAccountProperties:
    """Tests for Account computed properties."""

    def test_is_active_property(self, db):
        """Test is_active property."""
        active_account = AccountFactory(statecode=AccountStateCode.ACTIVE)
        inactive_account = InactiveAccountFactory()

        assert active_account.is_active is True
        assert inactive_account.is_active is False

    def test_state_name_property(self, db):
        """Test state_name property returns human-readable name."""
        active_account = AccountFactory(statecode=AccountStateCode.ACTIVE)
        inactive_account = InactiveAccountFactory()

        assert active_account.state_name == 'Active'
        assert inactive_account.state_name == 'Inactive'

    def test_status_name_property(self, db):
        """Test status_name property returns human-readable name."""
        active_account = AccountFactory(statuscode=AccountStatusCode.ACTIVE)
        inactive_account = InactiveAccountFactory()

        assert active_account.status_name == 'Active'
        assert inactive_account.status_name == 'Inactive'


@pytest.mark.unit
class TestAccountValidation:
    """Tests for Account model validation."""

    def test_name_required(self, db):
        """Test name is required."""
        owner = SalespersonFactory()
        account = Account(
            name='',
            ownerid=owner,
        )

        with pytest.raises(ValidationError):
            account.full_clean()

    def test_ownerid_required(self, db):
        """Test ownerid is required."""
        account = Account(name='Test Corp')

        with pytest.raises(IntegrityError):
            account.save()

    def test_email_format_validation(self, db):
        """Test email format validation."""
        owner = SalespersonFactory()

        # Valid email
        account_valid = Account(
            name='Test Corp',
            emailaddress1='valid@email.com',
            ownerid=owner,
        )
        account_valid.full_clean()  # Should not raise

        # Invalid email
        account_invalid = Account(
            name='Test Corp',
            emailaddress1='invalid-email',
            ownerid=owner,
        )

        with pytest.raises(ValidationError):
            account_invalid.full_clean()

    def test_state_code_valid_choices(self, db):
        """Test statecode must be valid choice."""
        account = AccountFactory()

        account.statecode = AccountStateCode.ACTIVE
        account.full_clean()  # Should not raise

        account.statecode = 999  # Invalid value
        with pytest.raises(ValidationError):
            account.full_clean()


@pytest.mark.unit
class TestAccountOrdering:
    """Tests for Account model ordering."""

    def test_accounts_ordered_by_createdon_desc(self, db):
        """Test that accounts are ordered by createdon descending."""
        account1 = AccountFactory()
        account2 = AccountFactory()
        account3 = AccountFactory()

        accounts = list(Account.objects.all())

        assert accounts[0].accountid == account3.accountid
        assert accounts[1].accountid == account2.accountid
        assert accounts[2].accountid == account1.accountid


@pytest.mark.unit
class TestAccountFactories:
    """Tests for Account factories."""

    def test_inactive_account_factory(self, db):
        """Test InactiveAccountFactory creates inactive accounts."""
        account = InactiveAccountFactory()

        assert account.statecode == AccountStateCode.INACTIVE
        assert account.statuscode == AccountStatusCode.INACTIVE


@pytest.mark.unit
class TestAccountAuditFields:
    """Tests for Account audit trail fields (from AuditMixin)."""

    def test_account_has_audit_fields(self, db):
        """Test that account has createdby, modifiedby, createdon, modifiedon."""
        owner = SalespersonFactory()
        account = AccountFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert hasattr(account, 'createdon')
        assert hasattr(account, 'modifiedon')
        assert hasattr(account, 'createdby')
        assert hasattr(account, 'modifiedby')

        assert account.createdon is not None
        assert account.modifiedon is not None
        assert account.createdby == owner
        assert account.modifiedby == owner

    def test_modifiedon_updates_on_save(self, db):
        """Test that modifiedon updates when account is saved."""
        account = AccountFactory()
        original_modifiedon = account.modifiedon

        import time
        time.sleep(0.01)

        account.description = 'Updated description'
        account.save()

        assert account.modifiedon > original_modifiedon
