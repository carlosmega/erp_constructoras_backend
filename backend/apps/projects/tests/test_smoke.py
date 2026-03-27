"""Smoke tests for Projects module."""

import pytest
from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeProjects:
    """Quick sanity checks for projects module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.projects.services import ProjectService
        ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = ProjectService.list_projects(user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/projects/')
        assert response.status_code == 200
