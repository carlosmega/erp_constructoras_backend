"""Smoke tests for Activities module."""

import pytest
from apps.activities.tests.factories import ActivityFactory


@pytest.mark.smoke
@pytest.mark.django_db
class TestSmokeActivities:
    """Quick sanity checks for activities module."""

    def test_model_creation(self, salesperson):
        """Test that the primary model can be created via factory."""
        obj = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        assert obj.pk is not None
        assert obj.ownerid == salesperson

    def test_service_get_stats(self, salesperson):
        """Test that the service stats method works."""
        from apps.activities.services import ActivityService
        ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = ActivityService.get_activity_stats(salesperson)
        assert result['total_activities'] >= 1

    def test_router_list_200(self, auth_client, salesperson):
        """Test that the list endpoint returns 200."""
        ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/activities/')
        assert response.status_code == 200
