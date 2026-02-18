"""
Invoice management models for CRM Backend.

Implements Invoice and InvoiceDetail entities following Dynamics CDS patterns.

Phase 10 Implementation: Invoice Management
"""

from django.db import models
from django.core.validators import MinValueValidator
from core.models import AuditMixin
from decimal import Decimal
import uuid


class InvoiceStateCode(models.IntegerChoices):
    """Invoice state codes (high-level status)."""
    ACTIVE = 0, 'Active'
    PAID = 1, 'Paid'
    CANCELED = 2, 'Canceled'


class InvoiceStatusCode(models.IntegerChoices):
    """Invoice status codes (detailed status within each state)."""
    # Active state
    NEW = 1, 'New'
    PARTIAL = 2, 'Partial'
    # Paid state
    COMPLETE = 3, 'Complete'
    # Canceled state
    CANCELED = 4, 'Canceled'


class Invoice(AuditMixin):
    """
    Billing document for delivered products/services.

    CDS Entity: invoice
    Primary Key: invoiceid (UUID)
    """
    invoiceid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='invoiceid'
    )

    # Invoice identification
    name = models.CharField(
        max_length=300,
        db_column='name',
        help_text='Invoice name/title'
    )
    invoicenumber = models.CharField(
        max_length=100,
        unique=True,
        db_column='invoicenumber',
        help_text='Auto-generated invoice number (e.g., INV-2024-001)'
    )

    # Related entities
    salesorderid = models.ForeignKey(
        'orders.SalesOrder',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='salesorderid',
        related_name='invoices',
        help_text='Order this invoice is for'
    )
    opportunityid = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='opportunityid',
        related_name='invoices'
    )
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='accountid',
        related_name='invoices'
    )
    contactid = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='contactid',
        related_name='invoices'
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
    totalamountless = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totalamountless',
        help_text='Total amount excluding freight and tax'
    )

    # Payment tracking
    totalpaid = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totalpaid',
        help_text='Amount paid so far'
    )
    totalamountdue = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totalamountdue',
        help_text='Amount still owed (totalamount - totalpaid)'
    )

    # Dates
    datedelivered = models.DateField(
        null=True,
        blank=True,
        db_column='datedelivered',
        help_text='Date products/services were delivered'
    )
    duedate = models.DateField(
        null=True,
        blank=True,
        db_column='duedate',
        help_text='Payment due date'
    )
    paidon = models.DateField(
        null=True,
        blank=True,
        db_column='paidon',
        help_text='Date invoice was fully paid'
    )

    # Status
    statecode = models.IntegerField(
        choices=InvoiceStateCode.choices,
        default=InvoiceStateCode.ACTIVE,
        db_column='statecode'
    )
    statuscode = models.IntegerField(
        choices=InvoiceStatusCode.choices,
        default=InvoiceStatusCode.NEW,
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
        related_name='owned_invoices'
    )

    class Meta:
        db_table = 'invoice'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['salesorderid']),
            models.Index(fields=['accountid']),
            models.Index(fields=['invoicenumber']),
            models.Index(fields=['duedate']),
        ]
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f"{self.invoicenumber} - {self.name}"

    @property
    def customer_name(self):
        """Get customer name from account or contact."""
        if self.accountid:
            return self.accountid.name
        elif self.contactid:
            return self.contactid.fullname
        return None

    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        from datetime import date
        if self.duedate and self.statecode == InvoiceStateCode.ACTIVE:
            return date.today() > self.duedate
        return False

    def calculate_totals(self):
        """Calculate all totals from line items."""
        details = self.invoice_details.all()

        # Calculate line item total
        self.totallineitemamount = sum(
            detail.extendedamount for detail in details
        ) or Decimal('0.00')

        # Calculate total before tax
        self.totalamountless = self.totallineitemamount - self.totaldiscountamount

        # Tax is included in line items for now
        self.totaltax = sum(
            detail.tax for detail in details
        ) or Decimal('0.00')

        # Calculate final total
        self.totalamount = self.totalamountless + self.totaltax

        # Calculate amount due
        self.totalamountdue = self.totalamount - self.totalpaid

        return self.totalamount


class InvoiceDetail(models.Model):
    """
    Line items for an invoice (products/services).

    CDS Entity: invoicedetail
    Primary Key: invoicedetailid (UUID)
    """
    invoicedetailid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='invoicedetailid'
    )

    # Parent invoice
    invoiceid = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        db_column='invoiceid',
        related_name='invoice_details'
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
        db_table = 'invoicedetail'
        ordering = ['invoiceid', 'sequencenumber']
        verbose_name = 'Invoice Detail'
        verbose_name_plural = 'Invoice Details'

    def __str__(self):
        return f"{self.productname} (Qty: {self.quantity})"

    def save(self, *args, **kwargs):
        """Auto-calculate amounts before saving."""
        # Calculate base amount
        self.baseamount = self.quantity * self.priceperunit

        # Calculate extended amount
        self.extendedamount = self.baseamount - self.manualdiscountamount + self.tax

        super().save(*args, **kwargs)
