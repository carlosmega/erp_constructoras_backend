"""
Unit tests for Account services.

Tests account CRUD operations, ownership filtering, deactivation,
and supplier lookup functionality.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from apps.accounts.models import Account, AccountStateCode, AccountStatusCode, CustomerTypeCode
from apps.accounts.services import AccountService
from apps.accounts.schemas import CreateAccountDto, UpdateAccountDto
from apps.accounts.tests.factories import AccountFactory, InactiveAccountFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


@pytest.mark.unit
class TestCreateAccount:
    """Tests for AccountService.create_account method."""

    def test_create_account_minimal(self, db, salesperson):
        """Test creating an account with minimal required fields."""
        dto = CreateAccountDto(name='Test Corp')

        account = AccountService.create_account(dto, salesperson)

        assert account.accountid is not None
        assert account.name == 'Test Corp'
        assert account.statecode == AccountStateCode.ACTIVE
        assert account.statuscode == AccountStatusCode.ACTIVE
        assert account.customertypecode == CustomerTypeCode.CUSTOMER
        assert account.ownerid == salesperson
        assert account.createdby == salesperson
        assert account.modifiedby == salesperson

    def test_create_account_full(self, db, salesperson):
        """Test creating an account with all fields populated."""
        dto = CreateAccountDto(
            name='Acme Corp',
            accountnumber='ACC999',
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
            customertypecode=CustomerTypeCode.SUPPLIER,
        )

        account = AccountService.create_account(dto, salesperson)

        assert account.name == 'Acme Corp'
        assert account.accountnumber == 'ACC999'
        assert account.emailaddress1 == 'info@acme.com'
        assert account.revenue == Decimal('1000000.00')
        assert account.customertypecode == CustomerTypeCode.SUPPLIER

    def test_create_account_with_different_owner(self, db, salesperson, salesperson2):
        """Test creating an account assigned to a different owner."""
        dto = CreateAccountDto(
            name='Test Corp',
            ownerid=salesperson2.systemuserid,
        )

        account = AccountService.create_account(dto, salesperson)

        assert account.ownerid == salesperson2
        assert account.createdby == salesperson

    def test_create_account_invalid_owner(self, db, salesperson):
        """Test creating an account with non-existent owner."""
        invalid_id = uuid4()
        dto = CreateAccountDto(
            name='Test Corp',
            ownerid=invalid_id,
        )

        with pytest.raises(ValidationError, match='not found'):
            AccountService.create_account(dto, salesperson)


@pytest.mark.unit
class TestListAccounts:
    """Tests for AccountService.list_accounts method."""

    def test_salesperson_sees_own_only(self, db, salesperson, salesperson2):
        """Test that salesperson only sees their own accounts."""
        AccountFactory(ownerid=salesperson)
        AccountFactory(ownerid=salesperson)
        AccountFactory(ownerid=salesperson2)

        accounts = AccountService.list_accounts(salesperson)

        assert accounts.count() == 2

    def test_admin_sees_all(self, db, system_admin, salesperson):
        """Test that System Administrator sees all accounts."""
        AccountFactory(ownerid=salesperson)
        AccountFactory(ownerid=system_admin)

        accounts = AccountService.list_accounts(system_admin)

        assert accounts.count() == 2

    def test_filter_by_state(self, db, salesperson):
        """Test filtering accounts by state code."""
        AccountFactory(ownerid=salesperson, statecode=AccountStateCode.ACTIVE)
        AccountFactory(ownerid=salesperson, statecode=AccountStateCode.ACTIVE)
        InactiveAccountFactory(ownerid=salesperson)

        active = AccountService.list_accounts(salesperson, statecode=AccountStateCode.ACTIVE)
        inactive = AccountService.list_accounts(salesperson, statecode=AccountStateCode.INACTIVE)

        assert active.count() == 2
        assert inactive.count() == 1

    def test_filter_by_customer_type(self, db, salesperson):
        """Test filtering accounts by customer type code."""
        AccountFactory(ownerid=salesperson, customertypecode=CustomerTypeCode.CUSTOMER)
        AccountFactory(ownerid=salesperson, customertypecode=CustomerTypeCode.SUPPLIER)
        AccountFactory(ownerid=salesperson, customertypecode=CustomerTypeCode.BOTH)

        # Filtering for customer should include CUSTOMER and BOTH
        customers = AccountService.list_accounts(salesperson, customertypecode=1)
        assert customers.count() == 2

        # Filtering for supplier should include SUPPLIER and BOTH
        suppliers = AccountService.list_accounts(salesperson, customertypecode=2)
        assert suppliers.count() == 2

    def test_search(self, db, salesperson):
        """Test searching accounts by name, account number, email."""
        AccountFactory(ownerid=salesperson, name='Acme Corp', emailaddress1='info@acme.com')
        AccountFactory(ownerid=salesperson, name='Beta Inc', accountnumber='BETA001')

        results = AccountService.list_accounts(salesperson, search='Acme')
        assert results.count() == 1

        results = AccountService.list_accounts(salesperson, search='BETA001')
        assert results.count() == 1

    def test_filter_by_owner_admin(self, db, system_admin, salesperson):
        """Test that admin can filter by specific owner."""
        AccountFactory(ownerid=salesperson)
        AccountFactory(ownerid=salesperson)
        AccountFactory(ownerid=system_admin)

        accounts = AccountService.list_accounts(system_admin, ownerid=salesperson.systemuserid)

        assert accounts.count() == 2

    def test_filter_by_owner_forbidden(self, db, salesperson, salesperson2):
        """Test that non-admin cannot filter by other owners."""
        AccountFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="cannot view other users"):
            AccountService.list_accounts(salesperson, ownerid=salesperson2.systemuserid)


@pytest.mark.unit
class TestGetAccountById:
    """Tests for AccountService.get_account_by_id method."""

    def test_get_account_by_id_owner(self, db, salesperson):
        """Test getting account by ID as owner."""
        account = AccountFactory(ownerid=salesperson)

        retrieved = AccountService.get_account_by_id(account.accountid, salesperson)

        assert retrieved.accountid == account.accountid

    def test_get_account_by_id_admin(self, db, system_admin, salesperson):
        """Test that admin can get any account."""
        account = AccountFactory(ownerid=salesperson)

        retrieved = AccountService.get_account_by_id(account.accountid, system_admin)

        assert retrieved.accountid == account.accountid

    def test_get_account_by_id_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot get account."""
        account = AccountFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied, match="don't have access"):
            AccountService.get_account_by_id(account.accountid, salesperson)

    def test_get_account_by_id_not_found(self, db, salesperson):
        """Test getting non-existent account."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            AccountService.get_account_by_id(invalid_id, salesperson)


@pytest.mark.unit
class TestUpdateAccount:
    """Tests for AccountService.update_account method."""

    def test_update_account_basic_fields(self, db, salesperson):
        """Test updating basic account fields."""
        account = AccountFactory(ownerid=salesperson, name='Old Name')

        dto = UpdateAccountDto(
            name='New Name',
            emailaddress1='new@example.com',
            telephone1='555-9999',
        )

        updated = AccountService.update_account(account.accountid, dto, salesperson)

        assert updated.name == 'New Name'
        assert updated.emailaddress1 == 'new@example.com'
        assert updated.telephone1 == '555-9999'
        assert updated.modifiedby == salesperson

    def test_update_account_customer_type(self, db, salesperson):
        """Test updating account customer type."""
        account = AccountFactory(ownerid=salesperson, customertypecode=CustomerTypeCode.CUSTOMER)

        dto = UpdateAccountDto(customertypecode=CustomerTypeCode.BOTH)
        updated = AccountService.update_account(account.accountid, dto, salesperson)

        assert updated.customertypecode == CustomerTypeCode.BOTH


@pytest.mark.unit
class TestDeactivateAccount:
    """Tests for AccountService.deactivate_account method."""

    def test_deactivate_account(self, db, salesperson):
        """Test deactivating an account."""
        account = AccountFactory(ownerid=salesperson, statecode=AccountStateCode.ACTIVE)

        deactivated = AccountService.deactivate_account(account.accountid, salesperson)

        assert deactivated.statecode == AccountStateCode.INACTIVE
        assert deactivated.modifiedby == salesperson

    def test_deactivate_account_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot deactivate account."""
        account = AccountFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied):
            AccountService.deactivate_account(account.accountid, salesperson)


@pytest.mark.unit
class TestListAccountsForSupplierLookup:
    """Tests for AccountService.list_accounts_for_supplier_lookup method."""

    def test_returns_active_accounts_only(self, db):
        """Test supplier lookup only returns active accounts."""
        AccountFactory(statecode=AccountStateCode.ACTIVE)
        AccountFactory(statecode=AccountStateCode.ACTIVE)
        InactiveAccountFactory()

        results = AccountService.list_accounts_for_supplier_lookup()

        assert results.count() == 2

    def test_search_by_name(self, db):
        """Test supplier lookup search by name."""
        AccountFactory(name='Acme Corp', statecode=AccountStateCode.ACTIVE)
        AccountFactory(name='Beta Inc', statecode=AccountStateCode.ACTIVE)

        results = AccountService.list_accounts_for_supplier_lookup(search='Acme')

        assert results.count() == 1
        assert results.first().name == 'Acme Corp'
