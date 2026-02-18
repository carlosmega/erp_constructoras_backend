"""
Core model utilities for CRM Backend Foundation.

Provides base classes and mixins for all business entities.
Following Microsoft Dynamics 365 CDS audit trail patterns.
"""

from django.db import models


class AuditMixin(models.Model):
    """
    Abstract base class providing audit trail fields for all business entities.

    Fields:
        createdon: Timestamp when record was created (auto-populated)
        modifiedon: Timestamp when record was last modified (auto-updated)
        createdby: User who created the record (populated by service layer)
        modifiedby: User who last modified the record (populated by service layer)

    Usage:
        class MyEntity(AuditMixin):
            # your fields here
            pass

    Note:
        - This is an abstract model (not a database table)
        - createdby and modifiedby allow NULL for system-generated records
        - Audit middleware captures current user for service layer population
    """

    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon',
        help_text="Timestamp when this record was created"
    )

    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon',
        help_text="Timestamp when this record was last modified"
    )

    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        db_column='createdby',
        help_text="User who created this record"
    )

    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified',
        db_column='modifiedby',
        help_text="User who last modified this record"
    )

    class Meta:
        abstract = True  # This is a mixin, not a concrete table
