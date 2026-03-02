"""Router tests for Activity Management API endpoints."""

import uuid
import pytest
from apps.activities.tests.factories import ActivityFactory, TaskActivityFactory


@pytest.mark.contract
class TestListActivities:
    def test_returns_200(self, auth_client, salesperson):
        ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/activities/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/activities/?statecode=0')
        assert response.status_code == 200

    def test_filter_by_type(self, auth_client, salesperson):
        TaskActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/activities/?activitytypecode=task')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/activities/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateActivity:
    def test_creates_task(self, auth_client, salesperson):
        payload = {
            'activitytypecode': 3,
            'subject': 'Follow up call',
            'ownerid': str(salesperson.systemuserid),
        }
        response = auth_client.post('/api/activities/', payload, content_type='application/json')
        assert response.status_code == 201

    def test_creates_email(self, auth_client, salesperson):
        payload = {
            'activitytypecode': 1,
            'subject': 'Test Email',
            'ownerid': str(salesperson.systemuserid),
        }
        response = auth_client.post('/api/activities/', payload, content_type='application/json')
        assert response.status_code == 201


@pytest.mark.contract
class TestGetActivity:
    def test_returns_activity(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/activities/{activity.activityid}')
        assert response.status_code == 200


@pytest.mark.contract
class TestUpdateActivity:
    def test_updates_activity(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/activities/{activity.activityid}',
            {'subject': 'Updated Subject'},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestDeleteActivity:
    def test_deletes_activity(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.delete(f'/api/activities/{activity.activityid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestActivityActions:
    def test_complete_activity(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/activities/{activity.activityid}/complete',
            {},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_cancel_activity(self, auth_client, salesperson):
        activity = ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(f'/api/activities/{activity.activityid}/cancel')
        assert response.status_code == 200


@pytest.mark.contract
class TestActivityStats:
    def test_returns_stats(self, auth_client, salesperson):
        ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/activities/stats/summary')
        assert response.status_code == 200


@pytest.mark.contract
class TestEmailMatching:
    def test_unlinked_emails(self, auth_client, salesperson):
        response = auth_client.get('/api/activities/emails/unlinked')
        assert response.status_code == 200

    def test_unlinked_count(self, auth_client, salesperson):
        response = auth_client.get('/api/activities/emails/unlinked/count')
        assert response.status_code == 200
        assert 'count' in response.json()
