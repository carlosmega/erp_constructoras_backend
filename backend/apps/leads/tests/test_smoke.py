"""Smoke tests for Leads module."""

import pytest
from apps.leads.tests.factories import LeadFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeLeads:
    """Quick sanity checks for leads module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.leads.services import LeadService
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = LeadService.list_leads(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/leads/')
        assert response.status_code == 200
