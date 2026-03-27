"""Smoke tests for Notifications module."""

import pytest
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeNotifications:
    """Quick sanity checks for notifications module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = NotificationFactory(ownerid=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_list(self, salesperson):
        """Test that the service list method works."""
        from apps.notifications.services import NotificationService
        NotificationFactory(ownerid=salesperson)
        result = NotificationService.list_notifications(salesperson)
        assert result.count() >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        NotificationFactory(ownerid=salesperson)
        response = auth_client.get('/api/notifications/')
        assert response.status_code == 200
