"""
Case entity model (CDS: incident).

Implements Microsoft Dynamics 365 CDS Incident entity following the data model specification.
Cases represent customer service requests that need to be tracked and resolved.
"""

import uuid
from datetime import datetime
from django.db import models
from django.utils import timezone
from core.models import AuditMixin


# ============================================================================
# State, Status, and Code Enums
# ============================================================================

class CaseStateCode(models.IntegerChoices):
    """Case state code (high-level state)."""
    ACTIVE = 0, 'Active'
    RESOLVED = 1, 'Resolved'
    CANCELLED = 2, 'Cancelled'


class CaseStatusCode(models.IntegerChoices):
    """Case status code (detailed status within state)."""
    # Active state statuses
    IN_PROGRESS = 1, 'In Progress'
    ON_HOLD = 2, 'On Hold'
    WAITING_FOR_DETAILS = 3, 'Waiting for Details'
    RESEARCHING = 4, 'Researching'

    # Resolved state statuses
    PROBLEM_SOLVED = 5, 'Problem Solved'
    INFORMATION_PROVIDED = 1000, 'Information Provided'

    # Cancelled state statuses
    CANCELLED = 6, 'Cancelled'
    MERGED = 2000, 'Merged'


class CasePriorityCode(models.IntegerChoices):
    """Case priority code."""
    HIGH = 1, 'High'
    NORMAL = 2, 'Normal'
    LOW = 3, 'Low'


class CaseOriginCode(models.IntegerChoices):
    """Case origin code (how the case was created)."""
    PHONE = 1, 'Phone'
    EMAIL = 2, 'Email'
    WEB = 3, 'Web'
    FACEBOOK = 2483, 'Facebook'
    TWITTER = 3986, 'Twitter'
    IOT = 700610000, 'IoT'


class CaseTypeCode(models.IntegerChoices):
    """Case type code."""
    QUESTION = 1, 'Question'
    PROBLEM = 2, 'Problem'
    REQUEST = 3, 'Request'


# ============================================================================
# Case Model
# ============================================================================

class Case(AuditMixin):
    """
    Case entity (customer service incident).

    Follows Microsoft Dynamics 365 CDS Incident entity structure.
    """

    # Primary Key
    incidentid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='incidentid'
    )

    # Case Information
    title = models.CharField(
        max_length=200,
        db_column='title'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    ticketnumber = models.CharField(
        max_length=100,
        unique=True,
        db_column='ticketnumber',
        verbose_name='Ticket Number'
    )

    # Case Classification
    casetypecode = models.IntegerField(
        choices=CaseTypeCode.choices,
        db_column='casetypecode',
        blank=True,
        null=True,
        verbose_name='Case Type'
    )

    prioritycode = models.IntegerField(
        choices=CasePriorityCode.choices,
        default=CasePriorityCode.NORMAL,
        db_column='prioritycode',
        verbose_name='Priority'
    )

    caseorigincode = models.IntegerField(
        choices=CaseOriginCode.choices,
        db_column='caseorigincode',
        blank=True,
        null=True,
        verbose_name='Origin'
    )

    # State Management
    statecode = models.IntegerField(
        choices=CaseStateCode.choices,
        default=CaseStateCode.ACTIVE,
        db_column='statecode'
    )

    statuscode = models.IntegerField(
        choices=CaseStatusCode.choices,
        default=CaseStatusCode.IN_PROGRESS,
        db_column='statuscode'
    )

    # Customer Reference - Polymorphic (Account B2B or Contact B2C)
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        db_column='accountid',
        blank=True,
        null=True,
        related_name='cases',
        verbose_name='Account'
    )

    contactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.PROTECT,
        db_column='contactid',
        blank=True,
        null=True,
        related_name='cases',
        verbose_name='Contact'
    )

    # Primary Contact
    primarycontactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        db_column='primarycontactid',
        blank=True,
        null=True,
        related_name='primary_cases',
        verbose_name='Primary Contact'
    )

    # Product Reference
    productid = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        db_column='productid',
        blank=True,
        null=True,
        related_name='cases',
        verbose_name='Product'
    )

    # Response Tracking
    firstresponsesent = models.BooleanField(
        default=False,
        db_column='firstresponsesent',
        verbose_name='First Response Sent'
    )

    # Resolution
    resolutiontype = models.CharField(
        max_length=100,
        db_column='resolutiontype',
        blank=True,
        null=True,
        verbose_name='Resolution Type'
    )

    resolutionsummary = models.TextField(
        db_column='resolutionsummary',
        blank=True,
        null=True,
        verbose_name='Resolution Summary'
    )

    resolvedon = models.DateTimeField(
        db_column='resolvedon',
        blank=True,
        null=True,
        verbose_name='Resolved On'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_cases'
    )

    class Meta:
        db_table = 'incident'
        verbose_name = 'Case'
        verbose_name_plural = 'Cases'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode']),
            models.Index(fields=['ownerid']),
            models.Index(fields=['accountid']),
            models.Index(fields=['contactid']),
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['createdon']),
        ]

    def __str__(self):
        return f"{self.ticketnumber} - {self.title}"

    @property
    def is_active(self):
        """Check if case is still active."""
        return self.statecode == CaseStateCode.ACTIVE

    @property
    def is_resolved(self):
        """Check if case is resolved."""
        return self.statecode == CaseStateCode.RESOLVED

    @property
    def is_cancelled(self):
        """Check if case is cancelled."""
        return self.statecode == CaseStateCode.CANCELLED

    @property
    def state_name(self):
        """Get human-readable state name."""
        return CaseStateCode(self.statecode).label

    @property
    def status_name(self):
        """Get human-readable status name."""
        return CaseStatusCode(self.statuscode).label

    @property
    def priority_name(self):
        """Get human-readable priority name."""
        return CasePriorityCode(self.prioritycode).label

    @property
    def origin_name(self):
        """Get human-readable origin name."""
        if self.caseorigincode is not None:
            return CaseOriginCode(self.caseorigincode).label
        return None

    @property
    def type_name(self):
        """Get human-readable case type name."""
        if self.casetypecode is not None:
            return CaseTypeCode(self.casetypecode).label
        return None

    @property
    def customer_name(self):
        """Get customer name from Account or Contact."""
        if self.accountid:
            return self.accountid.name
        elif self.contactid:
            return self.contactid.fullname
        return None
