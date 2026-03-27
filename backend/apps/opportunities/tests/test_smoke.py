"""Smoke tests for Opportunities module."""

import pytest
from apps.opportunities.tests.factories import OpportunityFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeOpportunities:
    """Quick sanity checks for opportunities module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.opportunities.services import OpportunityService
        OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = OpportunityService.list_opportunities(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/opportunities/')
        assert response.status_code == 200
