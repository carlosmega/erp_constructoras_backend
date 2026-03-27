"""Smoke tests for Quotes module."""

import pytest
from apps.quotes.tests.factories import QuoteFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeQuotes:
    """Quick sanity checks for quotes module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.quotes.models import Quote
        from core.permissions import filter_by_ownership
        QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = filter_by_ownership(Quote.objects.all(), salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/quotes/')
        assert response.status_code == 200
