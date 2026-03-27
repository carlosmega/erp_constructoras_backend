"""Tests for audit services and @audit_action decorator."""

import uuid
import pytest
from unittest.mock import patch

from apps.audit.models import AuditLog, AuditActionCode
from apps.audit.services import (
    log_action,
    audit_action,
    AuditLogService,
    _get_model_snapshot,
    _compute_changes,
)
from apps.audit.tests.factories import AuditLogFactory


@pytest.mark.django_db
class TestLogAction:
    """Tests for the log_action function."""

    def test_basic_log(self):
        record_id = uuid.uuid4()
        entry = log_action(
            action='create',
            entity='lead',
            record_id=record_id,
            record_name='Test Lead',
            message='Created test lead',
        )
        assert entry is not None
        assert entry.action == 'create'
        assert entry.entity == 'lead'
        assert entry.recordid == record_id
        assert entry.recordname == 'Test Lead'
        assert entry.message == 'Created test lead'

    def test_log_with_changes(self):
        changes = [{'field': 'name', 'old': 'A', 'new': 'B'}]
        entry = log_action(
            action='update',
            entity='account',
            record_id=uuid.uuid4(),
            changes=changes,
        )
        assert entry.changes == changes

    def test_log_with_snapshots(self):
        old_vals = {'statecode': 0}
        new_vals = {'statecode': 1}
        entry = log_action(
            action='qualify',
            entity='lead',
            record_id=uuid.uuid4(),
            old_values=old_vals,
            new_values=new_vals,
        )
        assert entry.old_values == old_vals
        assert entry.new_values == new_vals

    def test_log_never_raises(self):
        """log_action should never raise, even with bad data."""
        # Pass a non-UUID record_id — should still not raise
        with patch('apps.audit.services.AuditLog.objects.create', side_effect=Exception('DB error')):
            result = log_action(
                action='create',
                entity='lead',
                record_id=uuid.uuid4(),
            )
            assert result is None  # Failed gracefully


@pytest.mark.django_db
class TestComputeChanges:
    """Tests for the diff computation helper."""

    def test_no_changes(self):
        old = {'name': 'A', 'email': 'a@b.com'}
        new = {'name': 'A', 'email': 'a@b.com'}
        assert _compute_changes(old, new) == []

    def test_single_change(self):
        old = {'name': 'A', 'email': 'a@b.com'}
        new = {'name': 'B', 'email': 'a@b.com'}
        changes = _compute_changes(old, new)
        assert len(changes) == 1
        assert changes[0] == {'field': 'name', 'old': 'A', 'new': 'B'}

    def test_multiple_changes(self):
        old = {'name': 'A', 'value': 100}
        new = {'name': 'B', 'value': 200}
        changes = _compute_changes(old, new)
        assert len(changes) == 2

    def test_ignores_modifiedon(self):
        old = {'name': 'A', 'modifiedon': '2024-01-01', 'modifiedby': 'user1'}
        new = {'name': 'A', 'modifiedon': '2024-01-02', 'modifiedby': 'user2'}
        assert _compute_changes(old, new) == []

    def test_new_field_added(self):
        old = {'name': 'A'}
        new = {'name': 'A', 'email': 'a@b.com'}
        changes = _compute_changes(old, new)
        assert len(changes) == 1
        assert changes[0]['field'] == 'email'
        assert changes[0]['old'] is None


@pytest.mark.django_db
class TestAuditLogService:
    """Tests for AuditLogService query methods."""

    def test_get_record_trail(self):
        record_id = uuid.uuid4()
        AuditLogFactory(entity='lead', recordid=record_id, action=AuditActionCode.CREATE)
        AuditLogFactory(entity='lead', recordid=record_id, action=AuditActionCode.UPDATE)
        AuditLogFactory(entity='opportunity', recordid=uuid.uuid4())  # different entity

        trail = list(AuditLogService.get_record_trail('lead', record_id))
        assert len(trail) == 2

    def test_query_by_entity(self):
        AuditLogFactory(entity='lead')
        AuditLogFactory(entity='quote')
        AuditLogFactory(entity='lead')

        results = list(AuditLogService.query_logs(entity='lead'))
        assert len(results) == 2

    def test_query_by_action(self):
        AuditLogFactory(action=AuditActionCode.CREATE)
        AuditLogFactory(action=AuditActionCode.UPDATE)
        AuditLogFactory(action=AuditActionCode.CREATE)

        results = list(AuditLogService.query_logs(action='create'))
        assert len(results) == 2

    def test_query_pagination(self):
        for _ in range(5):
            AuditLogFactory(entity='lead')

        page1 = list(AuditLogService.query_logs(entity='lead', limit=2, offset=0))
        page2 = list(AuditLogService.query_logs(entity='lead', limit=2, offset=2))
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].auditid != page2[0].auditid

    def test_count_logs(self):
        AuditLogFactory(entity='lead')
        AuditLogFactory(entity='lead')
        AuditLogFactory(entity='quote')

        assert AuditLogService.count_logs(entity='lead') == 2
        assert AuditLogService.count_logs() == 3

    def test_query_by_search(self):
        AuditLogFactory(recordname='Important Project Alpha')
        AuditLogFactory(recordname='Something Else')

        results = list(AuditLogService.query_logs(search='Alpha'))
        assert len(results) == 1


@pytest.mark.django_db
class TestAuditActionDecorator:
    """Tests for the @audit_action decorator."""

    def test_decorator_on_create(self):
        """Decorator should log a create action when method returns a model-like object."""

        class FakeModel:
            pk = uuid.uuid4()
            name = 'Test'
            _meta = type('Meta', (), {'concrete_fields': []})()

        @audit_action(action='create', entity='testentity')
        def create_thing():
            return FakeModel()

        result = create_thing()
        assert result is not None

        # Should have created an audit log
        logs = AuditLog.objects.filter(entity='testentity', action='create')
        assert logs.count() == 1

    def test_decorator_does_not_block_on_failure(self):
        """If audit logging fails, the decorated method should still return normally."""

        @audit_action(action='create', entity='testentity')
        def create_thing():
            return 'not a model'  # This will cause audit to skip gracefully

        result = create_thing()
        assert result == 'not a model'

    def test_decorator_preserves_return_value(self):
        """The decorator must return the same value as the original method."""

        class FakeModel:
            pk = uuid.uuid4()
            name = 'Preserved'
            _meta = type('Meta', (), {'concrete_fields': []})()

        @audit_action(action='create', entity='preserved')
        def create_thing():
            return FakeModel()

        result = create_thing()
        assert result.name == 'Preserved'
