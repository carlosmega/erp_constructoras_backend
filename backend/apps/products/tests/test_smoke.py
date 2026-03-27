"""Smoke tests for Products module."""

import pytest
from apps.products.tests.factories import ProductFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeProducts:
    """Quick sanity checks for products module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = ProductFactory(createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None

    def test_service_get_stats(self, salesperson):
        """Test that the service stats method works."""
        from apps.products.services import ProductService
        ProductFactory(createdby=salesperson, modifiedby=salesperson)
        result = ProductService.get_product_stats(salesperson)
        assert result['total_products'] >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        ProductFactory(createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/products/')
        assert response.status_code == 200
