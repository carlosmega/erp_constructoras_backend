"""Smoke tests for Proyeccion module."""

import pytest
from apps.proyeccion.tests.factories import EstimationProjectFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeProyeccion:
    """Quick sanity checks for proyeccion module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = EstimationProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.proyeccion.services import EstimationProjectService
        EstimationProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = EstimationProjectService.list_projects(user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        EstimationProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/estimation-projects/')
        assert response.status_code == 200
