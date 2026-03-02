"""Tests for polymorphic customer resolution utilities."""

import uuid
import pytest
from core.customers import resolve_customer, get_customerid, get_customeridtype
from core.exceptions import ValidationError, NotFound


@pytest.mark.django_db
class TestResolveCustomer:
    def test_none_customerid_returns_none_tuple(self):
        account, contact = resolve_customer(None, 'account')
        assert account is None
        assert contact is None

    def test_resolves_account(self, salesperson):
        from apps.accounts.tests.factories import AccountFactory
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result_account, result_contact = resolve_customer(account.accountid, 'account')
        assert result_account == account
        assert result_contact is None

    def test_resolves_contact(self, salesperson):
        from apps.contacts.tests.factories import ContactFactory
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result_account, result_contact = resolve_customer(contact.contactid, 'contact')
        assert result_account is None
        assert result_contact == contact

    def test_invalid_type_raises_validation_error(self):
        with pytest.raises(ValidationError):
            resolve_customer(uuid.uuid4(), 'invalid')

    def test_nonexistent_account_raises_not_found(self):
        with pytest.raises(NotFound):
            resolve_customer(uuid.uuid4(), 'account')

    def test_nonexistent_contact_raises_not_found(self):
        with pytest.raises(NotFound):
            resolve_customer(uuid.uuid4(), 'contact')
