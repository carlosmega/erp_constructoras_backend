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
class TestListActivitiesPaginated:
    """Cursor-based paginated listing. Backwards-compatible alternative to /api/activities/."""

    def test_returns_paginated_shape(self, auth_client, salesperson):
        for _ in range(3):
            ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        response = auth_client.get('/api/activities/paginated/?limit=2')
        assert response.status_code == 200
        body = response.json()
        assert 'results' in body
        assert 'next_cursor' in body
        assert 'has_more' in body
        assert len(body['results']) == 2
        assert body['has_more'] is True

    def test_cursor_navigates_to_next_page(self, auth_client, salesperson):
        for _ in range(3):
            ActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        page1 = auth_client.get('/api/activities/paginated/?limit=2').json()
        cursor = page1['next_cursor']
        page2 = auth_client.get(f'/api/activities/paginated/?limit=2&cursor={cursor}').json()

        page1_ids = {a['activityid'] for a in page1['results']}
        page2_ids = {a['activityid'] for a in page2['results']}
        assert page1_ids.isdisjoint(page2_ids)
        assert page2['has_more'] is False

    def test_respects_filters(self, auth_client, salesperson):
        task = TaskActivityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/activities/paginated/?activitytypecode=task&limit=50')
        assert response.status_code == 200
        body = response.json()
        # ActivityListItemSchema serializes activitytypecode as int (3 = Task)
        assert len(body['results']) >= 1
        assert all(a['activitytypecode'] == 3 for a in body['results'])
        assert str(task.activityid) in [a['activityid'] for a in body['results']]

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/activities/paginated/')
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
