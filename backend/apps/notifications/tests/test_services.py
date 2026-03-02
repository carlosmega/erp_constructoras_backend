"""Tests for Notification service layer."""

import pytest
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification, NotificationTypeCode, NotificationPriorityCode
from apps.notifications.tests.factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationQueries:
    def test_list_notifications(self, salesperson):
        NotificationFactory(ownerid=salesperson)
        result = NotificationService.list_notifications(salesperson)
        assert result.count() >= 1

    def test_list_notifications_filters_by_is_read(self, salesperson):
        NotificationFactory(ownerid=salesperson, isread=True)
        NotificationFactory(ownerid=salesperson, isread=False)
        unread = NotificationService.list_notifications(salesperson, is_read=False)
        assert all(not n.isread for n in unread)

    def test_list_notifications_filters_by_typecode(self, salesperson):
        NotificationFactory(ownerid=salesperson, typecode=NotificationTypeCode.LEAD)
        NotificationFactory(ownerid=salesperson, typecode=NotificationTypeCode.QUOTE)
        result = NotificationService.list_notifications(salesperson, typecode='lead')
        assert all(n.typecode == 'lead' for n in result)

    def test_list_notifications_search(self, salesperson):
        NotificationFactory(ownerid=salesperson, title='Unique search term xyz')
        result = NotificationService.list_notifications(salesperson, search='xyz')
        assert result.count() >= 1

    def test_get_unread_count(self, salesperson):
        NotificationFactory(ownerid=salesperson, isread=False)
        NotificationFactory(ownerid=salesperson, isread=True)
        count = NotificationService.get_unread_count(salesperson)
        assert count >= 1


@pytest.mark.django_db
class TestNotificationMutations:
    def test_mark_as_read(self, salesperson):
        notif = NotificationFactory(ownerid=salesperson, isread=False)
        result = NotificationService.mark_as_read(notif.notificationid, salesperson)
        assert result.isread is True
        assert result.readon is not None

    def test_mark_all_as_read(self, salesperson):
        NotificationFactory(ownerid=salesperson, isread=False)
        NotificationFactory(ownerid=salesperson, isread=False)
        count = NotificationService.mark_all_as_read(salesperson)
        assert count >= 2

    def test_archive_notifications(self, salesperson):
        n1 = NotificationFactory(ownerid=salesperson)
        n2 = NotificationFactory(ownerid=salesperson)
        count = NotificationService.archive_notifications(
            [n1.notificationid, n2.notificationid], salesperson
        )
        assert count == 2

    def test_delete_notifications(self, salesperson):
        n1 = NotificationFactory(ownerid=salesperson)
        n2 = NotificationFactory(ownerid=salesperson)
        count = NotificationService.delete_notifications(
            [n1.notificationid, n2.notificationid], salesperson
        )
        assert count == 2


@pytest.mark.django_db
class TestNotificationGenerators:
    def test_create_notification(self, salesperson, system_admin):
        notif = NotificationService._create_notification(
            owner=salesperson,
            typecode=NotificationTypeCode.SYSTEM,
            title='Test notification',
            actor=system_admin,
        )
        assert notif is not None
        assert notif.title == 'Test notification'

    def test_skips_self_notification(self, salesperson):
        notif = NotificationService._create_notification(
            owner=salesperson,
            typecode=NotificationTypeCode.SYSTEM,
            title='Self test',
            actor=salesperson,
        )
        assert notif is None

    def test_notify_record_assigned(self, salesperson, system_admin):
        import uuid
        notif = NotificationService.notify_record_assigned(
            entity_type='lead',
            entity_id=str(uuid.uuid4()),
            entity_name='Test Lead',
            new_owner=salesperson,
            actor=system_admin,
        )
        assert notif is not None
        assert 'assigned' in notif.title

    def test_notify_state_changed(self, salesperson, system_admin):
        import uuid
        notif = NotificationService.notify_state_changed(
            entity_type='opportunity',
            entity_id=str(uuid.uuid4()),
            entity_name='Test Opp',
            new_state='Won',
            owner=salesperson,
            actor=system_admin,
        )
        assert notif is not None
