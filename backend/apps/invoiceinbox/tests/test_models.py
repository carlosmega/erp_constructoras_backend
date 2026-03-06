"""Unit tests for Invoice Inbox models."""

import pytest
from decimal import Decimal

from django.db import IntegrityError

from apps.invoiceinbox.models import (
    IncomingInvoice,
    IncomingInvoiceStateCode,
    InboxSyncLog,
    SyncStatusCode,
    SyncTriggerCode,
)
from apps.invoiceinbox.tests.factories import (
    IncomingInvoiceFactory,
    ClassifiedInvoiceFactory,
    RejectedInvoiceFactory,
    InboxSyncLogFactory,
)


# =============================================================================
# Enum Tests
# =============================================================================

@pytest.mark.unit
class TestInvoiceInboxEnums:
    """Tests for invoice inbox enum definitions."""

    def test_incoming_invoice_state_code_values(self):
        assert IncomingInvoiceStateCode.DRAFT.value == 0
        assert IncomingInvoiceStateCode.CLASSIFIED.value == 1
        assert IncomingInvoiceStateCode.LINKED.value == 2
        assert IncomingInvoiceStateCode.REJECTED.value == 3

    def test_sync_status_code_values(self):
        assert SyncStatusCode.SUCCESS.value == 0
        assert SyncStatusCode.PARTIAL.value == 1
        assert SyncStatusCode.FAILED.value == 2

    def test_sync_trigger_code_values(self):
        assert SyncTriggerCode.MANUAL.value == 0
        assert SyncTriggerCode.MANAGEMENT_COMMAND.value == 1


# =============================================================================
# IncomingInvoice Model Tests
# =============================================================================

@pytest.mark.unit
class TestIncomingInvoiceModel:
    """Tests for IncomingInvoice model creation."""

    def test_create_incoming_invoice(self, db):
        """Test factory creates valid incoming invoice with auto-assigned project."""
        invoice = IncomingInvoiceFactory()
        assert invoice.incominginvoiceid is not None
        assert invoice.statecode == IncomingInvoiceStateCode.DRAFT
        assert invoice.cfdiversion == '4.0'
        assert invoice.uuid is not None
        assert invoice.emisorrfc is not None
        assert invoice.emisornombre is not None
        assert invoice.subtotal == Decimal('10000.00')
        assert invoice.total == Decimal('11600.00')
        assert invoice.moneda == 'MXN'
        assert invoice.projectid is not None  # Auto-assigned from shared mailbox

    def test_unique_uuid_constraint(self, db):
        """Verify duplicate UUID raises IntegrityError."""
        fixed_uuid = '12345678-1234-1234-1234-123456789ABC'
        IncomingInvoiceFactory(uuid=fixed_uuid)
        with pytest.raises(IntegrityError):
            IncomingInvoiceFactory(uuid=fixed_uuid)

    def test_state_choices(self, db):
        """Verify all state codes can be assigned."""
        draft = IncomingInvoiceFactory(statecode=IncomingInvoiceStateCode.DRAFT)
        assert draft.statecode == IncomingInvoiceStateCode.DRAFT

        classified = ClassifiedInvoiceFactory()
        assert classified.statecode == IncomingInvoiceStateCode.CLASSIFIED

        rejected = RejectedInvoiceFactory()
        assert rejected.statecode == IncomingInvoiceStateCode.REJECTED

        linked = IncomingInvoiceFactory(statecode=IncomingInvoiceStateCode.LINKED)
        assert linked.statecode == IncomingInvoiceStateCode.LINKED

    def test_incoming_invoice_str_with_uuid(self, db):
        """Test __str__ method with UUID."""
        invoice = IncomingInvoiceFactory(
            uuid='AAAA-BBBB-CCCC',
            emisornombre='Acme Corp'
        )
        str_repr = str(invoice)
        assert 'AAAA-BBBB-CCCC' in str_repr
        assert 'Acme Corp' in str_repr

    def test_incoming_invoice_str_without_uuid(self, db):
        """Test __str__ method without UUID."""
        invoice = IncomingInvoiceFactory(uuid=None, emisornombre=None)
        str_repr = str(invoice)
        assert 'no-uuid' in str_repr
        assert 'unknown' in str_repr

    def test_incoming_invoice_default_amounts(self, db):
        """Test default amount values."""
        invoice = IncomingInvoiceFactory()
        assert invoice.tipocambio == Decimal('1.0000')
        assert invoice.descuento == Decimal('0.00')
        assert invoice.totalimpuestosretenidos == Decimal('0.00')
        assert invoice.matchconfidence == 0

    def test_classified_invoice_has_project(self, db):
        """Test that ClassifiedInvoiceFactory creates invoice with project."""
        invoice = ClassifiedInvoiceFactory()
        assert invoice.projectid is not None
        assert invoice.statecode == IncomingInvoiceStateCode.CLASSIFIED

    def test_null_uuid_allows_duplicates(self, db):
        """Null UUIDs should not violate unique constraint (conditional)."""
        inv1 = IncomingInvoiceFactory(uuid=None)
        inv2 = IncomingInvoiceFactory(uuid=None)
        assert inv1.incominginvoiceid != inv2.incominginvoiceid

    def test_invoice_belongs_to_project(self, db):
        """Verify invoice is always associated with a project."""
        invoice = IncomingInvoiceFactory()
        assert invoice.projectid is not None
        assert invoice.projectid.projectid is not None


# =============================================================================
# InboxSyncLog Model Tests
# =============================================================================

@pytest.mark.unit
class TestInboxSyncLogModel:
    """Tests for InboxSyncLog model."""

    def test_create_sync_log(self, db):
        """Test creating a sync log entry."""
        log = InboxSyncLogFactory()
        assert log.synclogid is not None
        assert log.syncstatus == SyncStatusCode.SUCCESS
        assert log.triggeredby == SyncTriggerCode.MANUAL
        assert log.triggeredbyuserid is not None
        assert log.projectid is not None
        assert log.totalemailsfetched >= 0
        assert log.errorscount == 0

    def test_sync_log_str(self, db):
        """Test __str__ method."""
        log = InboxSyncLogFactory()
        str_repr = str(log)
        assert 'Sync' in str_repr
        assert 'Success' in str_repr

    def test_sync_log_failed_status(self, db):
        """Test creating a failed sync log."""
        log = InboxSyncLogFactory(
            syncstatus=SyncStatusCode.FAILED,
            errorscount=3,
            errorsdetail=[
                {'message': 'Connection timeout'},
                {'message': 'Parse error in file.xml'},
                {'message': 'Unknown attachment type'},
            ],
        )
        assert log.syncstatus == SyncStatusCode.FAILED
        assert log.errorscount == 3
        assert len(log.errorsdetail) == 3

    def test_sync_log_ordering(self, db):
        """Test default ordering by -startedon."""
        log1 = InboxSyncLogFactory()
        log2 = InboxSyncLogFactory()
        logs = list(InboxSyncLog.objects.all())
        # Most recent first
        assert logs[0].synclogid == log2.synclogid
        assert logs[1].synclogid == log1.synclogid

    def test_sync_log_belongs_to_project(self, db):
        """Verify sync log is associated with a project."""
        log = InboxSyncLogFactory()
        assert log.projectid is not None
