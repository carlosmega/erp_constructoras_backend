"""Smoke tests for Budgets module."""

import pytest
from apps.budgets.tests.factories import CostCategoryFactory
from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeBudgets:
    """Quick sanity checks for budgets module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        obj = CostCategoryFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.budgets.services import CostCategoryService
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        CostCategoryFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        result = CostCategoryService.list_categories(project_id=project.pk, user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        CostCategoryFactory(projectid=project, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/categories/projects/{project.pk}/categories/')
        assert response.status_code == 200
