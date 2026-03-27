"""Tests for AuditLog model."""

import uuid
import pytest
from apps.audit.models import AuditLog, AuditActionCode
from apps.audit.tests.factories import AuditLogFactory


@pytest.mark.django_db
class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self):
        entry = AuditLogFactory()
        assert entry.auditid is not None
        assert entry.action == AuditActionCode.CREATE
        assert entry.entity == 'lead'
        assert entry.timestamp is not None

    def test_str_representation(self):
        entry = AuditLogFactory(
            action=AuditActionCode.UPDATE,
            entity='opportunity',
            username='John Doe',
        )
        result = str(entry)
        assert 'update' in result
        assert 'opportunity' in result
        assert 'John Doe' in result

    def test_ordering_by_timestamp_desc(self):
        e1 = AuditLogFactory(entity='lead')
        e2 = AuditLogFactory(entity='lead')
        logs = list(AuditLog.objects.all())
        # Most recent first
        assert logs[0].auditid == e2.auditid
        assert logs[1].auditid == e1.auditid

    def test_json_fields(self):
        changes = [{'field': 'fullname', 'old': 'Old Name', 'new': 'New Name'}]
        entry = AuditLogFactory(
            action=AuditActionCode.UPDATE,
            changes=changes,
            old_values={'fullname': 'Old Name'},
            new_values={'fullname': 'New Name'},
        )
        entry.refresh_from_db()
        assert entry.changes == changes
        assert entry.old_values['fullname'] == 'Old Name'
        assert entry.new_values['fullname'] == 'New Name'

    def test_nullable_user(self):
        entry = AuditLogFactory(userid=None)
        assert entry.userid is None

    def test_all_action_codes(self):
        for code, label in AuditActionCode.choices:
            entry = AuditLogFactory(action=code)
            assert entry.action == code
