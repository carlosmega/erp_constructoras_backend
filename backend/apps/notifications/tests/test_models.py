"""Unit tests for Notification models and enums."""

import pytest
from apps.notifications.models import (
    Notification,
    NotificationTypeCode,
    NotificationPriorityCode,
    PRIORITY_NAME_MAP,
)
from apps.notifications.tests.factories import NotificationFactory
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Enum Tests
# ============================================================================

@pytest.mark.unit
class TestNotificationTypeCodeEnum:
    """Tests for NotificationTypeCode enum values."""

    def test_lead_value(self):
        assert NotificationTypeCode.LEAD.value == 'lead'
        assert NotificationTypeCode.LEAD.label == 'Lead'

    def test_opportunity_value(self):
        assert NotificationTypeCode.OPPORTUNITY.value == 'opportunity'

    def test_quote_value(self):
        assert NotificationTypeCode.QUOTE.value == 'quote'

    def test_task_value(self):
        assert NotificationTypeCode.TASK.value == 'task'

    def test_mention_value(self):
        assert NotificationTypeCode.MENTION.value == 'mention'

    def test_system_value(self):
        assert NotificationTypeCode.SYSTEM.value == 'system'
        assert NotificationTypeCode.SYSTEM.label == 'System'


@pytest.mark.unit
class TestNotificationPriorityCodeEnum:
    """Tests for NotificationPriorityCode enum values."""

    def test_low_value(self):
        assert NotificationPriorityCode.LOW.value == 0
        assert NotificationPriorityCode.LOW.label == 'Low'

    def test_medium_value(self):
        assert NotificationPriorityCode.MEDIUM.value == 1
        assert NotificationPriorityCode.MEDIUM.label == 'Medium'

    def test_high_value(self):
        assert NotificationPriorityCode.HIGH.value == 2
        assert NotificationPriorityCode.HIGH.label == 'High'


@pytest.mark.unit
class TestPriorityNameMap:
    """Tests for PRIORITY_NAME_MAP constant."""

    def test_low_mapping(self):
        assert PRIORITY_NAME_MAP[0] == 'low'

    def test_medium_mapping(self):
        assert PRIORITY_NAME_MAP[1] == 'medium'

    def test_high_mapping(self):
        assert PRIORITY_NAME_MAP[2] == 'high'


# ============================================================================
# Model Tests
# ============================================================================

@pytest.mark.unit
class TestNotificationModel:
    """Tests for Notification model creation and properties."""

    def test_create_minimal(self, db):
        """Create a notification with only required fields."""
        owner = SalespersonFactory()
        notif = Notification.objects.create(
            ownerid=owner,
            typecode=NotificationTypeCode.SYSTEM,
            title='Test Notification',
        )
        assert notif.pk is not None
        assert notif.isread is False
        assert notif.isarchived is False
        assert notif.prioritycode == NotificationPriorityCode.MEDIUM

    def test_factory(self, db):
        """NotificationFactory should create a valid notification."""
        notif = NotificationFactory()
        assert notif.pk is not None
        assert notif.title is not None
        assert notif.ownerid is not None

    def test_str_representation(self, db):
        """String representation should include typecode, title, and owner."""
        owner = SalespersonFactory()
        notif = NotificationFactory(
            ownerid=owner,
            typecode=NotificationTypeCode.LEAD,
            title='New lead assigned',
        )
        result = str(notif)
        assert '[lead]' in result
        assert 'New lead assigned' in result

    def test_priority_name_low(self, db):
        """priority_name should return 'low' for LOW priority."""
        notif = NotificationFactory(prioritycode=NotificationPriorityCode.LOW)
        assert notif.priority_name == 'low'

    def test_priority_name_medium(self, db):
        """priority_name should return 'medium' for MEDIUM priority."""
        notif = NotificationFactory(prioritycode=NotificationPriorityCode.MEDIUM)
        assert notif.priority_name == 'medium'

    def test_priority_name_high(self, db):
        """priority_name should return 'high' for HIGH priority."""
        notif = NotificationFactory(prioritycode=NotificationPriorityCode.HIGH)
        assert notif.priority_name == 'high'

    def test_default_isread_false(self, db):
        """New notifications should be unread by default."""
        notif = NotificationFactory()
        assert notif.isread is False

    def test_default_isarchived_false(self, db):
        """New notifications should be unarchived by default."""
        notif = NotificationFactory()
        assert notif.isarchived is False

    def test_default_description_empty(self, db):
        """Default description should be empty string."""
        owner = SalespersonFactory()
        notif = Notification.objects.create(
            ownerid=owner,
            typecode=NotificationTypeCode.SYSTEM,
            title='Minimal',
        )
        assert notif.description == ''

    def test_related_entity_fields(self, db):
        """Related entity fields should store polymorphic reference."""
        import uuid
        entity_id = uuid.uuid4()
        notif = NotificationFactory(
            relatedentityid=entity_id,
            relatedentitytype='opportunity',
            relatedentityname='Big Deal',
            actionurl='/opportunities/123',
        )
        assert notif.relatedentityid == entity_id
        assert notif.relatedentitytype == 'opportunity'
        assert notif.relatedentityname == 'Big Deal'
        assert notif.actionurl == '/opportunities/123'

    def test_actor_can_be_null(self, db):
        """actorid should be optional (system-generated notifications)."""
        notif = NotificationFactory(actorid=None)
        assert notif.actorid is None

    def test_default_ordering(self):
        """Notifications should be ordered by -createdon by default."""
        assert Notification._meta.ordering == ['-createdon']

    def test_db_table_name(self):
        """DB table should be 'notification'."""
        assert Notification._meta.db_table == 'notification'
