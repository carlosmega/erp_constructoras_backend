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
