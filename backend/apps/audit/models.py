"""
Audit Log model.

Tracks all CRUD operations and state transitions across CRM entities.
Follows Microsoft Dynamics 365 audit entity patterns.
"""

import uuid

from django.db import models


class AuditActionCode(models.TextChoices):
    """Audit action types matching frontend AuditAction enum."""
    CREATE = 'create', 'Create'
    UPDATE = 'update', 'Update'
    DELETE = 'delete', 'Delete'
    ACTIVATE = 'activate', 'Activate'
    DEACTIVATE = 'deactivate', 'Deactivate'
    ASSIGN = 'assign', 'Assign'
    QUALIFY = 'qualify', 'Qualify'
    CLOSE = 'close', 'Close'
    WIN = 'win', 'Win'
    LOSE = 'lose', 'Lose'
    CANCEL = 'cancel', 'Cancel'
    APPROVE = 'approve', 'Approve'
    REJECT = 'reject', 'Reject'
    CONVERT = 'convert', 'Convert'
    CLASSIFY = 'classify', 'Classify'
    VERIFY = 'verify', 'Verify'


class AuditLog(models.Model):
    """
    General-purpose audit log entry.

    Records who did what, when, to which record, and what changed.
    Designed for high-volume writes and efficient querying by entity+record.
    """

    auditid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # What happened
    action = models.CharField(
        max_length=20,
        choices=AuditActionCode.choices,
        db_index=True,
    )
    entity = models.CharField(
        max_length=50,
        db_index=True,
        help_text='Entity type (e.g. lead, opportunity, quote)',
    )
    recordid = models.UUIDField(
        db_index=True,
        help_text='ID of the affected record',
    )
    recordname = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Display name of the record at time of action',
    )

    # Who did it
    userid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        db_column='userid',
    )
    username = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text='Denormalized user fullname for fast display',
    )

    # What changed (JSON)
    changes = models.JSONField(
        null=True,
        blank=True,
        help_text='List of {field, old, new} dicts for update actions',
    )
    old_values = models.JSONField(
        null=True,
        blank=True,
        help_text='Full snapshot before (for delete or critical changes)',
    )
    new_values = models.JSONField(
        null=True,
        blank=True,
        help_text='Full snapshot after (for create or critical changes)',
    )

    # Context
    message = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text='Human-readable description of the action',
    )
    ipaddress = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    # When
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity', 'recordid', '-timestamp'], name='idx_audit_entity_record'),
            models.Index(fields=['userid', '-timestamp'], name='idx_audit_user'),
            models.Index(fields=['action', '-timestamp'], name='idx_audit_action'),
        ]
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        return f"[{self.action}] {self.entity}:{self.recordid} by {self.username}"
