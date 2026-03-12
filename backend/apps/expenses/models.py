"""
Expense management models for construction project ERP.

Implements ProjectExpense, ExpenseLine, ExpenseAttachment,
ClassificationLog, and ClientEstimate entities.
"""

import uuid
from decimal import Decimal
from django.db import models
from core.models import AuditMixin


# =============================================================================
# Enum Definitions
# =============================================================================

class DocumentTypeCode(models.IntegerChoices):
    INVOICE = 0, 'Invoice'
    CREDIT_NOTE = 1, 'Credit Note'
    NO_INVOICE_EXPENSE = 2, 'No Invoice Expense'
    PAYROLL = 3, 'Payroll'
    PROVISION = 4, 'Provision'


class ClassificationStatusCode(models.IntegerChoices):
    PENDING = 1, 'Unclassified'
    CLASSIFIED = 2, 'Classified'
    PARTIAL = 3, 'Partial'


class PaymentStatusCode(models.IntegerChoices):
    PENDING = 0, 'Pending'
    PAID = 1, 'Paid'
    PARTIALLY_PAID = 2, 'Partially Paid'
    OVERDUE = 3, 'Overdue'


class CurrencyCode(models.IntegerChoices):
    MXN = 0, 'MXN'
    USD = 1, 'USD'


class ExpensePaymentMethodCode(models.IntegerChoices):
    CREDIT_CARD = 0, 'Credit Card'
    BANK_TRANSFER = 1, 'Bank Transfer'
    CASH = 2, 'Cash'
    CHECK = 3, 'Check'
    DEBIT_CARD = 4, 'Debit Card'
    OTHER = 99, 'Other'


class PayrollTypeCode(models.IntegerChoices):
    WEEKLY = 0, 'Weekly'
    BIWEEKLY = 1, 'Biweekly'


class ProvisionStatusCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    CONVERTED = 1, 'Converted'
    CANCELED = 2, 'Canceled'


class VerificationStatusCode(models.IntegerChoices):
    PENDING = 0, 'Pending'
    VERIFIED = 1, 'Verified'
    DISCREPANCY = 2, 'Discrepancy'


class ExpenseStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    CANCELED = 1, 'Canceled'


class ClassificationActionCode(models.IntegerChoices):
    ASSIGNED = 0, 'Assigned'
    CHANGED = 1, 'Changed'
    REMOVED = 2, 'Removed'


class AttachmentTypeCode(models.IntegerChoices):
    PDF = 0, 'PDF'
    XML = 1, 'XML'
    IMAGE = 2, 'Image'
    OTHER = 99, 'Other'


class EstimateTypeCode(models.IntegerChoices):
    ESTIMATE = 0, 'Estimate'
    OTHER = 1, 'Other'


class EstimateStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    PAID = 1, 'Paid'
    CANCELED = 2, 'Canceled'


# =============================================================================
# Models
# =============================================================================

class ProjectExpense(AuditMixin):
    """Construction project expense record."""

    expenseid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='expenseid'
    )

    # Project and period
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='expenses'
    )
    periodid = models.ForeignKey(
        'budgets.ImputationPeriod',
        on_delete=models.PROTECT,
        db_column='periodid',
        related_name='expenses'
    )

    # Classification
    imputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='imputationcodeid',
        related_name='expenses'
    )
    classificationstatus = models.IntegerField(
        choices=ClassificationStatusCode.choices,
        default=ClassificationStatusCode.PENDING,
        db_column='classificationstatus'
    )

    # Document information
    documenttype = models.IntegerField(
        choices=DocumentTypeCode.choices,
        db_column='documenttype'
    )
    supplierrfc = models.CharField(
        max_length=13,
        db_column='supplierrfc',
        blank=True,
        null=True
    )
    suppliername = models.CharField(
        max_length=300,
        db_column='suppliername',
        blank=True,
        null=True
    )
    invoiceuuid = models.CharField(
        max_length=36,
        db_column='invoiceuuid',
        blank=True,
        null=True
    )
    invoicefolio = models.CharField(
        max_length=50,
        db_column='invoicefolio',
        blank=True,
        null=True
    )
    invoicedate = models.DateField(
        db_column='invoicedate',
        blank=True,
        null=True
    )
    expensesource = models.CharField(
        max_length=300,
        db_column='expensesource',
        blank=True,
        null=True
    )

    # Payroll-specific
    payrolltype = models.IntegerField(
        choices=PayrollTypeCode.choices,
        db_column='payrolltype',
        blank=True,
        null=True
    )
    workername = models.CharField(
        max_length=200,
        db_column='workername',
        blank=True,
        null=True
    )

    # Provision-specific
    provisionstatus = models.IntegerField(
        choices=ProvisionStatusCode.choices,
        db_column='provisionstatus',
        blank=True,
        null=True
    )
    provisionconvertedfromid = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='provisionconvertedfromid',
        related_name='converted_expenses'
    )

    # Payment
    paymentmethod = models.IntegerField(
        choices=ExpensePaymentMethodCode.choices,
        db_column='paymentmethod',
        blank=True,
        null=True
    )
    paymentstatus = models.IntegerField(
        choices=PaymentStatusCode.choices,
        default=PaymentStatusCode.PENDING,
        db_column='paymentstatus'
    )

    # Currency and amounts
    currency = models.IntegerField(
        choices=CurrencyCode.choices,
        default=CurrencyCode.MXN,
        db_column='currency'
    )
    exchangerate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal('1.0000'),
        db_column='exchangerate'
    )
    subtotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='subtotal'
    )
    taxamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='taxamount'
    )
    retentionamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='retentionamount'
    )
    discountamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='discountamount'
    )
    netamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='netamount'
    )

    # Verification
    verificationstatus = models.IntegerField(
        choices=VerificationStatusCode.choices,
        default=VerificationStatusCode.PENDING,
        db_column='verificationstatus'
    )
    verificationnotes = models.TextField(
        db_column='verificationnotes',
        blank=True,
        null=True
    )
    verifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='verifiedby',
        related_name='verified_expenses'
    )
    verifiedon = models.DateTimeField(
        db_column='verifiedon',
        blank=True,
        null=True
    )

    # State
    statecode = models.IntegerField(
        choices=ExpenseStateCode.choices,
        default=ExpenseStateCode.ACTIVE,
        db_column='statecode'
    )
    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_expenses'
    )

    class Meta:
        db_table = 'projectexpense'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['projectid', 'statecode']),
            models.Index(fields=['projectid', 'classificationstatus']),
            models.Index(fields=['projectid', 'periodid']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'invoiceuuid'],
                name='unique_invoice_per_project',
                condition=models.Q(invoiceuuid__isnull=False),
            ),
        ]

    def __str__(self):
        return f"Expense {self.expenseid} - {self.get_documenttype_display()}"


class ExpenseLine(models.Model):
    """Line item within a project expense."""

    expenselineid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='expenselineid'
    )
    expenseid = models.ForeignKey(
        ProjectExpense,
        on_delete=models.CASCADE,
        db_column='expenseid',
        related_name='lines'
    )
    linenumber = models.IntegerField(
        db_column='linenumber'
    )
    description = models.CharField(
        max_length=500,
        db_column='description'
    )
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        db_column='quantity'
    )
    unitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        db_column='unitprice'
    )
    subtotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='subtotal'
    )
    taxamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='taxamount'
    )
    retentionamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='retentionamount'
    )
    discountamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='discountamount'
    )
    netamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='netamount'
    )
    imputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='imputationcodeid',
        related_name='expense_lines'
    )
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )

    class Meta:
        db_table = 'expenseline'
        ordering = ['linenumber']

    def __str__(self):
        return f"Line {self.linenumber} - {self.description}"


class ExpenseAttachment(models.Model):
    """File attachment for a project expense."""

    attachmentid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='attachmentid'
    )
    expenseid = models.ForeignKey(
        ProjectExpense,
        on_delete=models.CASCADE,
        db_column='expenseid',
        related_name='attachments'
    )
    filename = models.CharField(
        max_length=255,
        db_column='filename'
    )
    suggestedfilename = models.CharField(
        max_length=255,
        db_column='suggestedfilename'
    )
    filetype = models.IntegerField(
        choices=AttachmentTypeCode.choices,
        db_column='filetype'
    )
    filesize = models.IntegerField(
        db_column='filesize'
    )
    mimetype = models.CharField(
        max_length=100,
        db_column='mimetype'
    )
    storageurl = models.CharField(
        max_length=500,
        db_column='storageurl',
        blank=True,
        default=''
    )
    file = models.FileField(
        upload_to='expenses/attachments/%Y/%m/',
        blank=True,
        null=True,
        db_column='file'
    )
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )

    class Meta:
        db_table = 'expenseattachment'

    def __str__(self):
        return self.filename


class ClassificationLog(models.Model):
    """Audit log for expense classification changes."""

    classificationlogid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='classificationlogid'
    )
    expenseid = models.ForeignKey(
        ProjectExpense,
        on_delete=models.CASCADE,
        db_column='expenseid',
        related_name='classification_logs'
    )
    previousimputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='previousimputationcodeid',
        related_name='+'
    )
    previousimputationcode = models.CharField(
        max_length=20,
        db_column='previousimputationcode',
        blank=True,
        null=True
    )
    newimputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='newimputationcodeid',
        related_name='+'
    )
    newimputationcode = models.CharField(
        max_length=20,
        db_column='newimputationcode',
        blank=True,
        null=True
    )
    action = models.IntegerField(
        choices=ClassificationActionCode.choices,
        db_column='action'
    )
    classifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='classifiedby',
        related_name='+'
    )
    classifiedbyname = models.CharField(
        max_length=200,
        db_column='classifiedbyname'
    )
    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )

    class Meta:
        db_table = 'classificationlog'
        ordering = ['-createdon']

    def __str__(self):
        return f"Classification {self.get_action_display()} on {self.createdon}"


class ClientEstimate(AuditMixin):
    """Client estimate for a construction project."""

    estimateid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='estimateid'
    )
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='estimates'
    )
    periodid = models.ForeignKey(
        'budgets.ImputationPeriod',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='periodid',
        related_name='estimates'
    )
    estimatenumber = models.IntegerField(
        db_column='estimatenumber'
    )
    invoicenumber = models.CharField(
        max_length=50,
        db_column='invoicenumber',
        blank=True,
        null=True
    )
    invoicedate = models.DateField(
        db_column='invoicedate',
        blank=True,
        null=True
    )
    estimationperiod = models.CharField(
        max_length=50,
        db_column='estimationperiod',
        blank=True,
        null=True
    )
    estimatetype = models.IntegerField(
        choices=EstimateTypeCode.choices,
        default=EstimateTypeCode.ESTIMATE,
        db_column='estimatetype'
    )

    # Financial fields
    estimatedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='estimatedamount'
    )
    advanceamortization = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='advanceamortization'
    )
    otherdeductions = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='otherdeductions'
    )
    materialdeductions = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='materialdeductions'
    )
    guaranteefund = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='guaranteefund'
    )
    totaldeductions = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totaldeductions'
    )
    amountnotax = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='amountnotax'
    )
    taxamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='taxamount'
    )
    taxretained = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='taxretained'
    )
    totalinvoiced = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='totalinvoiced'
    )
    collectableamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='collectableamount'
    )

    # Payment
    paymentstatus = models.IntegerField(
        choices=PaymentStatusCode.choices,
        default=PaymentStatusCode.PENDING,
        db_column='paymentstatus'
    )
    paymentdate = models.DateField(
        db_column='paymentdate',
        blank=True,
        null=True
    )
    amountpaid = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=Decimal('0.00'),
        db_column='amountpaid'
    )

    # State
    statecode = models.IntegerField(
        choices=EstimateStateCode.choices,
        default=EstimateStateCode.ACTIVE,
        db_column='statecode'
    )

    class Meta:
        db_table = 'clientestimate'
        ordering = ['-createdon']

    def __str__(self):
        return f"Estimate #{self.estimatenumber} - {self.projectid}"
