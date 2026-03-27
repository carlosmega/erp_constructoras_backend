"""Smoke tests for Users module."""

import pytest
from apps.users.tests.factories import SystemUserFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeUsers:
    """Quick sanity checks for users module."""

    def test_model_creation(self, salesperson_role):
        """Test that the primary model can be created via factory."""
        obj = SystemUserFactory(securityroleid=salesperson_role)
        assert obj.pk is not None
        assert obj.securityroleid == salesperson_role

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.users.services import UserService
        result = UserService.list_users()
        assert len(result) >= 1

    def test_router_list_200(self, admin_auth_client, system_admin):
        """Test that the list endpoint returns 200."""
        response = admin_auth_client.get('/api/users/')
        assert response.status_code == 200
