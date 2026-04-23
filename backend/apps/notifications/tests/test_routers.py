"""Router tests for Notification API endpoints."""

import pytest
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.contract
class TestListNotifications:
    def test_returns_200(self, auth_client, salesperson):
        NotificationFactory(ownerid=salesperson)
        response = auth_client.get('/api/notifications/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_is_read(self, auth_client, salesperson):
        NotificationFactory(ownerid=salesperson, isread=False)
        response = auth_client.get('/api/notifications/?is_read=false')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/notifications/')
        assert response.status_code == 403


@pytest.mark.contract
class TestListNotificationsPaginated:
    """Cursor-based paginated listing (opt-in; legacy list endpoint remains)."""

    def test_returns_paginated_shape(self, auth_client, salesperson):
        for _ in range(3):
            NotificationFactory(ownerid=salesperson)

        response = auth_client.get('/api/notifications/paginated/?limit=2')
        assert response.status_code == 200
        body = response.json()
        assert 'results' in body
        assert 'next_cursor' in body
        assert 'has_more' in body
        assert len(body['results']) == 2
        assert body['has_more'] is True

    def test_cursor_navigates_to_next_page(self, auth_client, salesperson):
        for _ in range(3):
            NotificationFactory(ownerid=salesperson)

        page1 = auth_client.get('/api/notifications/paginated/?limit=2').json()
        page2 = auth_client.get(
            f'/api/notifications/paginated/?limit=2&cursor={page1["next_cursor"]}'
        ).json()

        page1_ids = {n['notificationid'] for n in page1['results']}
        page2_ids = {n['notificationid'] for n in page2['results']}
        assert page1_ids.isdisjoint(page2_ids)
        assert page2['has_more'] is False

    def test_only_returns_own_notifications(self, auth_client, salesperson, readonly_user):
        """Ownership must apply to paginated endpoint too (no cross-user leakage)."""
        NotificationFactory(ownerid=salesperson)
        NotificationFactory(ownerid=readonly_user)

        response = auth_client.get('/api/notifications/paginated/?limit=50')
        assert response.status_code == 200
        body = response.json()
        owner_ids = {n.get('ownerid') for n in body['results']}
        # Only salesperson's notifications should appear
        assert all(oid == str(salesperson.systemuserid) for oid in owner_ids if oid)

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/notifications/paginated/')
        assert response.status_code == 403


@pytest.mark.contract
class TestUnreadCount:
    def test_returns_count(self, auth_client, salesperson):
        NotificationFactory(ownerid=salesperson, isread=False)
        response = auth_client.get('/api/notifications/unread-count')
        assert response.status_code == 200
        assert response.json()['count'] >= 1


@pytest.mark.contract
class TestMarkAsRead:
    def test_marks_notification_as_read(self, auth_client, salesperson):
        notif = NotificationFactory(ownerid=salesperson, isread=False)
        response = auth_client.post(f'/api/notifications/{notif.notificationid}/read')
        assert response.status_code == 200
        assert response.json()['isread'] is True


@pytest.mark.contract
class TestMarkAllAsRead:
    def test_marks_all_as_read(self, auth_client, salesperson):
        NotificationFactory(ownerid=salesperson, isread=False)
        NotificationFactory(ownerid=salesperson, isread=False)
        response = auth_client.post('/api/notifications/read-all')
        assert response.status_code == 200
        assert response.json()['count'] >= 2


@pytest.mark.contract
class TestBulkArchive:
    def test_archives_notifications(self, auth_client, salesperson):
        n1 = NotificationFactory(ownerid=salesperson)
        n2 = NotificationFactory(ownerid=salesperson)
        response = auth_client.post(
            '/api/notifications/bulk-archive',
            {'ids': [str(n1.notificationid), str(n2.notificationid)]},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['count'] == 2
