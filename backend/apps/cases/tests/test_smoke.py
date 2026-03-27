"""Smoke tests for Cases module."""

import pytest
from apps.cases.tests.factories import CaseFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeCases:
    """Quick sanity checks for cases module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.cases.services import CaseService
        CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = CaseService.list_cases(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        CaseFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/cases/')
        assert response.status_code == 200
