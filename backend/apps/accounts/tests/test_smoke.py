"""Smoke tests for Accounts module."""

import pytest
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeAccounts:
    """Quick sanity checks for accounts module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.accounts.services import AccountService
        AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = AccountService.list_accounts(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/accounts/')
        assert response.status_code == 200
