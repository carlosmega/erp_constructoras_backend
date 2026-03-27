"""Smoke tests for Orders module."""

import pytest
from apps.orders.tests.factories import SalesOrderFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeOrders:
    """Quick sanity checks for orders module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.orders.models import SalesOrder
        from core.permissions import filter_by_ownership
        SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = filter_by_ownership(SalesOrder.objects.all(), salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/orders/')
        assert response.status_code == 200
