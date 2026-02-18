"""
Opportunity entity model.

Implements Microsoft Dynamics 365 CDS Opportunity entity following the data model specification.
Opportunities represent qualified sales opportunities with revenue potential.

Phase 6 Implementation
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import AuditMixin


# ============================================================================
# State and Status Code Enums
# ============================================================================

class OpportunityStateCode(models.IntegerChoices):
    """
    Opportunity state code (high-level state).
    """
    OPEN = 0, 'Open'
    WON = 1, 'Won'
    LOST = 2, 'Lost'


class OpportunityStatusCode(models.IntegerChoices):
    """
    Opportunity status code (detailed status within state).
    """
    # Open state statuses
    IN_PROGRESS = 1, 'In Progress'
    ON_HOLD = 2, 'On Hold'

    # Won state status
    WON = 3, 'Won'

    # Lost state statuses
    CANCELED = 4, 'Canceled'
    OUT_SOLD = 5, 'Out-Sold'


class SalesStage(models.IntegerChoices):
    """
    Sales pipeline stage.
    """
    QUALIFY = 0, 'Qualify'
    DEVELOP = 1, 'Develop'
    PROPOSE = 2, 'Propose'
    CLOSE = 3, 'Close'


# ============================================================================
# Opportunity Model
# ============================================================================

class Opportunity(AuditMixin):
    """
    Opportunity entity (qualified sales opportunity).

    Follows Microsoft Dynamics 365 CDS Opportunity entity structure.
    """

    # Primary Key
    opportunityid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='opportunityid'
    )

    # Opportunity Information
    name = models.CharField(
        max_length=300,
        db_column='name'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    # Customer Reference - Link to Account (B2B) or Contact (B2C)
    # At least one must be set
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        db_column='accountid',
        blank=True,
        null=True,
        related_name='opportunities',
        verbose_name='Account'
    )

    contactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.PROTECT,
        db_column='contactid',
        blank=True,
        null=True,
        related_name='opportunities',
        verbose_name='Contact'
    )

    # Legacy field for backward compatibility
    customername = models.CharField(
        max_length=160,
        db_column='customername',
        blank=True,
        null=True,
        help_text='Legacy customer name field'
    )

    # Revenue Information
    estimatedrevenue = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='estimatedrevenue',
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Est. Revenue'
    )

    actualrevenue = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='actualrevenue',
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        verbose_name='Actual Revenue'
    )

    # Dates
    estimatedclosedate = models.DateField(
        db_column='estimatedclosedate',
        blank=True,
        null=True,
        verbose_name='Est. Close Date'
    )

    actualclosedate = models.DateField(
        db_column='actualclosedate',
        blank=True,
        null=True,
        verbose_name='Actual Close Date'
    )

    # State Management
    statecode = models.IntegerField(
        choices=OpportunityStateCode.choices,
        default=OpportunityStateCode.OPEN,
        db_column='statecode'
    )

    statuscode = models.IntegerField(
        choices=OpportunityStatusCode.choices,
        default=OpportunityStatusCode.IN_PROGRESS,
        db_column='statuscode'
    )

    # Sales Process
    salesstage = models.IntegerField(
        choices=SalesStage.choices,
        default=SalesStage.QUALIFY,
        db_column='salesstage',
        verbose_name='Sales Stage'
    )

    probability = models.IntegerField(
        db_column='closeprobability',
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Probability (%)',
        help_text='Probability of closing (0-100%)'
    )

    # Lead Origin
    originatingleadid = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        db_column='originatingleadid',
        blank=True,
        null=True,
        related_name='created_opportunities',
        verbose_name='Originating Lead'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_opportunities'
    )

    class Meta:
        db_table = 'opportunity'
        verbose_name = 'Opportunity'
        verbose_name_plural = 'Opportunities'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['statuscode']),
            models.Index(fields=['salesstage']),
            models.Index(fields=['ownerid', 'statecode']),
            models.Index(fields=['estimatedclosedate']),
            models.Index(fields=['createdon']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_open(self):
        """Check if opportunity is still open."""
        return self.statecode == OpportunityStateCode.OPEN

    @property
    def is_won(self):
        """Check if opportunity is won."""
        return self.statecode == OpportunityStateCode.WON

    @property
    def is_lost(self):
        """Check if opportunity is lost."""
        return self.statecode == OpportunityStateCode.LOST

    @property
    def state_name(self):
        """Get human-readable state name."""
        return OpportunityStateCode(self.statecode).label

    @property
    def status_name(self):
        """Get human-readable status name."""
        return OpportunityStatusCode(self.statuscode).label

    @property
    def stage_name(self):
        """Get human-readable sales stage name."""
        return SalesStage(self.salesstage).label

    @property
    def weighted_revenue(self):
        """Calculate weighted revenue (estimated revenue × probability)."""
        if self.estimatedrevenue and self.probability is not None:
            from decimal import Decimal
            return self.estimatedrevenue * (Decimal(str(self.probability)) / Decimal('100'))
        return None

    @property
    def customer_name(self):
        """Get customer name from Account or Contact."""
        if self.accountid:
            return self.accountid.name
        elif self.contactid:
            return self.contactid.fullname
        return self.customername
