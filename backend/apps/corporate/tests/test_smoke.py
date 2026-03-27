"""Smoke tests for Corporate module."""

import pytest
from apps.corporate.tests.factories import CorporateBudgetFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeCorporate:
    """Quick sanity checks for corporate module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = CorporateBudgetFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.corporate.services import CorporateBudgetService
        CorporateBudgetFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = CorporateBudgetService.list_budgets(user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, admin_auth_client, system_admin, salesperson):
        """Test that the list endpoint returns 200."""
        CorporateBudgetFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = admin_auth_client.get('/api/corporate/budgets/')
        assert response.status_code == 200
