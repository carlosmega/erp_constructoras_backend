"""Smoke tests for HRPayroll module."""

import pytest
from apps.hrpayroll.tests.factories import EmployeeFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeHRPayroll:
    """Quick sanity checks for hrpayroll module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.hrpayroll.services import EmployeeService
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = EmployeeService.list_employees(user=salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, admin_auth_client, system_admin, salesperson):
        """Test that the list endpoint returns 200."""
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = admin_auth_client.get('/api/employees/')
        assert response.status_code == 200
