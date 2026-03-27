"""Smoke tests for Expenses module."""

import pytest
from apps.expenses.tests.factories import ProjectExpenseFactory
from apps.projects.tests.factories import ConstructionProjectFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeExpenses:
    """Quick sanity checks for expenses module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        obj = ProjectExpenseFactory(
            projectid=project, ownerid=salesperson,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert obj.pk is not None

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.expenses.services import ExpenseService
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ProjectExpenseFactory(
            projectid=project, ownerid=salesperson,
            createdby=salesperson, modifiedby=salesperson,
        )
        result = ExpenseService.list_expenses(project_id=project.pk, user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        project = ConstructionProjectFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        ProjectExpenseFactory(
            projectid=project, ownerid=salesperson,
            createdby=salesperson, modifiedby=salesperson,
        )
        response = auth_client.get(f'/api/expenses/projects/{project.pk}/expenses/')
        assert response.status_code == 200
