"""
Lead entity model.

Implements Microsoft Dynamics 365 CDS Lead entity following the data model specification.
Leads represent potential customers that need to be qualified.

Phase 5 Implementation (User Story 3)
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator
from core.models import AuditMixin


# ============================================================================
# State and Status Code Enums
# ============================================================================

class LeadStateCode(models.IntegerChoices):
    """
    Lead state code (high-level state).
    """
    OPEN = 0, 'Open'
    QUALIFIED = 1, 'Qualified'
    DISQUALIFIED = 2, 'Disqualified'


class LeadStatusCode(models.IntegerChoices):
    """
    Lead status code (detailed status within state).
    """
    # Open state statuses
    NEW = 1, 'New'
    CONTACTED = 2, 'Contacted'

    # Qualified state status
    QUALIFIED = 3, 'Qualified'

    # Disqualified state statuses
    LOST = 4, 'Lost'
    CANNOT_CONTACT = 5, 'Cannot Contact'
    NO_LONGER_INTERESTED = 6, 'No Longer Interested'


class LeadQualityCode(models.IntegerChoices):
    """
    Lead quality rating.
    """
    COLD = 1, 'Cold'
    WARM = 2, 'Warm'
    HOT = 3, 'Hot'


class LeadSourceCode(models.IntegerChoices):
    """
    Lead source (how the lead was acquired).
    """
    ADVERTISEMENT = 1, 'Advertisement'
    EMPLOYEE_REFERRAL = 2, 'Employee Referral'
    EXTERNAL_REFERRAL = 3, 'External Referral'
    PARTNER = 4, 'Partner'
    PUBLIC_RELATIONS = 5, 'Public Relations'
    SEMINAR = 6, 'Seminar'
    TRADE_SHOW = 7, 'Trade Show'
    WEB = 8, 'Web'
    WORD_OF_MOUTH = 9, 'Word of Mouth'
    OTHER = 10, 'Other'


# ============================================================================
# Lead Model
# ============================================================================

class Lead(AuditMixin):
    """
    Lead entity (potential customer).

    Follows Microsoft Dynamics 365 CDS Lead entity structure.
    """

    # Primary Key
    leadid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='leadid'
    )

    # Personal Information
    firstname = models.CharField(
        max_length=50,
        db_column='firstname',
        blank=True,
        null=True
    )

    lastname = models.CharField(
        max_length=50,
        db_column='lastname'
    )

    fullname = models.CharField(
        max_length=160,
        db_column='fullname',
        blank=True
    )

    # Contact Information
    emailaddress1 = models.EmailField(
        max_length=100,
        db_column='emailaddress1',
        blank=True,
        null=True
    )

    telephone1 = models.CharField(
        max_length=50,
        db_column='telephone1',
        blank=True,
        null=True,
        verbose_name='Business Phone'
    )

    mobilephone = models.CharField(
        max_length=50,
        db_column='mobilephone',
        blank=True,
        null=True
    )

    # Company Information
    companyname = models.CharField(
        max_length=100,
        db_column='companyname',
        blank=True,
        null=True
    )

    jobtitle = models.CharField(
        max_length=100,
        db_column='jobtitle',
        blank=True,
        null=True
    )

    # Lead Details
    subject = models.CharField(
        max_length=300,
        db_column='subject',
        blank=True,
        null=True,
        verbose_name='Topic'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    # Lead Classification
    leadqualitycode = models.IntegerField(
        choices=LeadQualityCode.choices,
        db_column='leadqualitycode',
        blank=True,
        null=True,
        verbose_name='Rating'
    )

    leadsourcecode = models.IntegerField(
        choices=LeadSourceCode.choices,
        db_column='leadsourcecode',
        blank=True,
        null=True,
        verbose_name='Lead Source'
    )

    # State Management
    statecode = models.IntegerField(
        choices=LeadStateCode.choices,
        default=LeadStateCode.OPEN,
        db_column='statecode'
    )

    statuscode = models.IntegerField(
        choices=LeadStatusCode.choices,
        default=LeadStatusCode.NEW,
        db_column='statuscode'
    )

    # Sales Information
    estimatedvalue = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='estimatedvalue',
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Est. Value'
    )

    estimatedclosedate = models.DateField(
        db_column='estimatedclosedate',
        blank=True,
        null=True,
        verbose_name='Est. Close Date'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_leads'
    )

    # Qualification Result (populated when lead is qualified)
    qualifyingopportunityid = models.UUIDField(
        db_column='qualifyingopportunityid',
        blank=True,
        null=True,
        help_text='Opportunity created when this lead was qualified'
    )

    class Meta:
        db_table = 'lead'
        verbose_name = 'Lead'
        verbose_name_plural = 'Leads'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['statuscode']),
            models.Index(fields=['emailaddress1']),
            models.Index(fields=['ownerid', 'statecode']),
            models.Index(fields=['createdon']),
        ]

    def __str__(self):
        return self.fullname or f"{self.firstname or ''} {self.lastname}".strip()

    def save(self, *args, **kwargs):
        """Override save to auto-compute fullname."""
        # Always recompute fullname based on firstname and lastname
        parts = []
        if self.firstname:
            parts.append(self.firstname)
        if self.lastname:
            parts.append(self.lastname)
        self.fullname = ' '.join(parts) if parts else ''

        super().save(*args, **kwargs)

    @property
    def is_open(self):
        """Check if lead is still open."""
        return self.statecode == LeadStateCode.OPEN

    @property
    def is_qualified(self):
        """Check if lead is qualified."""
        return self.statecode == LeadStateCode.QUALIFIED

    @property
    def is_disqualified(self):
        """Check if lead is disqualified."""
        return self.statecode == LeadStateCode.DISQUALIFIED

    @property
    def state_name(self):
        """Get human-readable state name."""
        return LeadStateCode(self.statecode).label

    @property
    def status_name(self):
        """Get human-readable status name."""
        return LeadStatusCode(self.statuscode).label

    @property
    def quality_name(self):
        """Get human-readable quality name."""
        if self.leadqualitycode:
            return LeadQualityCode(self.leadqualitycode).label
        return None

    @property
    def source_name(self):
        """Get human-readable source name."""
        if self.leadsourcecode:
            return LeadSourceCode(self.leadsourcecode).label
        return None
