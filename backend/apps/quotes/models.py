"""
Quote management models for CRM Backend.

Implements Quote and QuoteDetail entities following Dynamics CDS patterns.

Phase 8 Implementation: Quote Management
"""

from django.db import models
from django.core.validators import MinValueValidator
from core.models import AuditMixin
from decimal import Decimal
import uuid


class QuoteStateCode(models.IntegerChoices):
    """Quote state codes (high-level status)."""
    DRAFT = 0, 'Draft'
    ACTIVE = 1, 'Active'
    WON = 2, 'Won'
    CLOSED = 3, 'Closed'


class QuoteStatusCode(models.IntegerChoices):
    """Quote status codes (detailed status within each state)."""
    # Draft state
    IN_PROGRESS = 1, 'In Progress'
    # Active state
    IN_REVIEW = 2, 'In Review'
    # Won state
    WON = 3, 'Won'
    # Closed state
    LOST = 4, 'Lost'
    CANCELED = 5, 'Canceled'
    REVISED = 6, 'Revised'


class Quote(AuditMixin):
    """
    Price proposal for products/services.

    CDS Entity: quote
    Primary Key: quoteid (UUID)
    """
    quoteid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='quoteid'
    )

    # Quote identification
    name = models.CharField(
        max_length=300,
        db_column='name',
        help_text='Quote name/title'
    )
    quotenumber = models.CharField(
        max_length=100,
        unique=True,
        db_column='quotenumber',
        help_text='Auto-generated quote number (e.g., Q-2024-001)'
    )

    # Related entities
    opportunityid = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='opportunityid',
        related_name='quotes',
        help_text='Opportunity this quote is for'
    )
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='accountid',
        related_name='quotes'
    )
    contactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='contactid',
        related_name='quotes'
    )

    # Financial fields
    totalamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totalamount',
        help_text='Total amount (calculated from line items)'
    )
    totaldiscountamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totaldiscountamount'
    )
    totaltax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totaltax'
    )
    totallineitemamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totallineitemamount',
        help_text='Sum of all line items before discounts/taxes'
    )

    # Discount
    discountpercentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        db_column='discountpercentage'
    )

    # Dates
    effectivefrom = models.DateField(
        null=True,
        blank=True,
        db_column='effectivefrom',
        help_text='Quote valid from date'
    )
    effectiveto = models.DateField(
        null=True,
        blank=True,
        db_column='effectiveto',
        help_text='Quote expiration date'
    )
    closedon = models.DateTimeField(
        null=True,
        blank=True,
        db_column='closedon',
        help_text='Date when quote was won/lost/canceled'
    )

    # Status
    statecode = models.IntegerField(
        choices=QuoteStateCode.choices,
        default=QuoteStateCode.DRAFT,
        db_column='statecode'
    )
    statuscode = models.IntegerField(
        choices=QuoteStatusCode.choices,
        default=QuoteStatusCode.IN_PROGRESS,
        db_column='statuscode'
    )

    # Description
    description = models.TextField(
        blank=True,
        null=True,
        db_column='description'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_quotes'
    )

    class Meta:
        db_table = 'quote'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['opportunityid']),
            models.Index(fields=['accountid']),
            models.Index(fields=['quotenumber']),
        ]
        verbose_name = 'Quote'
        verbose_name_plural = 'Quotes'

    def __str__(self):
        return f"{self.quotenumber} - {self.name}"

    @property
    def customer_name(self):
        """Get customer name from account or contact."""
        if self.accountid:
            return self.accountid.name
        elif self.contactid:
            return self.contactid.fullname
        return None

    def calculate_totals(self):
        """Calculate all totals from line items."""
        # Calculate line item total via DB aggregation (avoids N+1 / loading rows)
        agg = self.quote_details.aggregate(total=models.Sum('extendedamount'))
        self.totallineitemamount = agg['total'] or Decimal('0.00')

        # Apply discount
        if self.discountpercentage > 0:
            self.totaldiscountamount = (
                self.totallineitemamount * (self.discountpercentage / Decimal('100'))
            )
        else:
            self.totaldiscountamount = Decimal('0.00')

        # Calculate total before tax
        amount_before_tax = self.totallineitemamount - self.totaldiscountamount

        # Calculate tax (you can make this more sophisticated)
        # For now, we'll assume tax is already included in line items
        # or you can add a tax_rate field
        self.totaltax = Decimal('0.00')

        # Calculate final total
        self.totalamount = amount_before_tax + self.totaltax

        return self.totalamount


class QuoteDetail(models.Model):
    """
    Line items for a quote (products/services).

    CDS Entity: quotedetail
    Primary Key: quotedetailid (UUID)
    """
    quotedetailid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='quotedetailid'
    )

    # Parent quote
    quoteid = models.ForeignKey(
        Quote,
        on_delete=models.CASCADE,
        db_column='quoteid',
        related_name='quote_details'
    )

    # Product information (simplified - no FK to Product for now)
    productname = models.CharField(
        max_length=100,
        db_column='productname',
        help_text='Product or service name'
    )
    productdescription = models.TextField(
        blank=True,
        null=True,
        db_column='productdescription'
    )

    # Quantity and pricing
    quantity = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        db_column='quantity'
    )
    priceperunit = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        db_column='priceperunit',
        help_text='Unit price'
    )
    manualdiscountamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='manualdiscountamount',
        help_text='Discount amount for this line'
    )
    tax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='tax'
    )

    # Calculated fields
    baseamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='baseamount',
        help_text='quantity * priceperunit (auto-calculated)'
    )
    extendedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='extendedamount',
        help_text='baseamount - manualdiscountamount + tax (auto-calculated)'
    )

    # Line number for ordering
    sequencenumber = models.IntegerField(
        default=1,
        db_column='sequencenumber'
    )

    # Audit fields
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')

    class Meta:
        db_table = 'quotedetail'
        ordering = ['quoteid', 'sequencenumber']
        verbose_name = 'Quote Detail'
        verbose_name_plural = 'Quote Details'

    def __str__(self):
        return f"{self.productname} (Qty: {self.quantity})"

    def save(self, *args, **kwargs):
        """Auto-calculate amounts before saving."""
        # Calculate base amount
        self.baseamount = self.quantity * self.priceperunit

        # Calculate extended amount
        self.extendedamount = self.baseamount - self.manualdiscountamount + self.tax

        super().save(*args, **kwargs)


class QuoteTemplateCategory(models.TextChoices):
    STANDARD = 'standard', 'Standard'
    CUSTOM = 'custom', 'Custom'
    INDUSTRY = 'industry', 'Industry'
    SERVICE = 'service', 'Service'
    PRODUCT = 'product', 'Product'
    BUNDLE = 'bundle', 'Bundle'


class QuoteTemplate(AuditMixin):
    """
    Reusable quote templates with pre-defined line items.
    CDS Entity: quotetemplate
    """
    quotetemplateid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='quotetemplateid'
    )
    name = models.CharField(max_length=300, db_column='name')
    description = models.TextField(blank=True, null=True, db_column='description')
    category = models.CharField(
        max_length=20,
        choices=QuoteTemplateCategory.choices,
        null=True,
        blank=True,
        db_column='category'
    )
    templatedata = models.JSONField(
        default=dict,
        db_column='templatedata',
        help_text='JSON with quote fields and line items'
    )
    isshared = models.BooleanField(default=False, db_column='isshared')
    usagecount = models.IntegerField(default=0, db_column='usagecount')
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_quote_templates'
    )

    class Meta:
        db_table = 'quotetemplate'
        ordering = ['-createdon']
        verbose_name = 'Quote Template'
        verbose_name_plural = 'Quote Templates'

    def __str__(self):
        return self.name
