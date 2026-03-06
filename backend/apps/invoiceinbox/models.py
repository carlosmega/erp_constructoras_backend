"""
Invoice Inbox models for automatic invoice capture from email.

Implements IncomingInvoice (staged CFDI invoices from email) and
InboxSyncLog (sync execution audit trail).
"""

import uuid
from decimal import Decimal
from django.db import models
from core.models import AuditMixin


# =============================================================================
# Enum Definitions
# =============================================================================

class IncomingInvoiceStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    CLASSIFIED = 1, 'Classified'
    LINKED = 2, 'Linked'
    REJECTED = 3, 'Rejected'


class SyncStatusCode(models.IntegerChoices):
    SUCCESS = 0, 'Success'
    PARTIAL = 1, 'Partial'
    FAILED = 2, 'Failed'


class SyncTriggerCode(models.IntegerChoices):
    MANUAL = 0, 'Manual'
    MANAGEMENT_COMMAND = 1, 'Management Command'


# =============================================================================
# Models
# =============================================================================

class IncomingInvoice(AuditMixin):
    """
    Staged invoice captured from a project's shared mailbox.

    Flow: Email arrives at project's O365 shared mailbox → Graph API fetches →
    XML parsed → Draft created (project auto-assigned) →
    User assigns imputation code (Classified) → Linked to ProjectExpense.
    """

    incominginvoiceid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='incominginvoiceid'
    )

    # Project (auto-assigned from the shared mailbox that received the email)
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='incoming_invoices'
    )

    # Classification (assigned during classification)
    imputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        db_column='imputationcodeid',
        related_name='incoming_invoices',
        null=True,
        blank=True
    )

    # State
    statecode = models.IntegerField(
        choices=IncomingInvoiceStateCode.choices,
        default=IncomingInvoiceStateCode.DRAFT,
        db_column='statecode'
    )

    # Email source metadata
    emailmessageid = models.CharField(
        max_length=500,
        db_column='emailmessageid',
        blank=True,
        null=True,
        help_text='Internet Message-ID header for dedup'
    )
    emailsubject = models.CharField(
        max_length=500,
        db_column='emailsubject',
        blank=True,
        null=True
    )
    emailfrom = models.CharField(
        max_length=300,
        db_column='emailfrom',
        blank=True,
        null=True
    )
    emailreceivedon = models.DateTimeField(
        db_column='emailreceivedon',
        blank=True,
        null=True
    )
    graphmessageid = models.CharField(
        max_length=500,
        db_column='graphmessageid',
        blank=True,
        null=True,
        help_text='Graph API message ID for attachment retrieval'
    )

    # CFDI parsed data
    cfdiversion = models.CharField(
        max_length=10,
        db_column='cfdiversion',
        blank=True,
        null=True
    )
    uuid = models.CharField(
        max_length=36,
        db_column='uuid',
        blank=True,
        null=True,
        help_text='TimbreFiscalDigital UUID — unique fiscal identifier'
    )
    serie = models.CharField(
        max_length=50,
        db_column='serie',
        blank=True,
        null=True
    )
    folio = models.CharField(
        max_length=50,
        db_column='folio',
        blank=True,
        null=True
    )
    fecha = models.DateTimeField(
        db_column='fecha',
        blank=True,
        null=True
    )
    fechatimbrado = models.DateTimeField(
        db_column='fechatimbrado',
        blank=True,
        null=True
    )

    # Emisor (supplier)
    emisorrfc = models.CharField(
        max_length=13,
        db_column='emisorrfc',
        blank=True,
        null=True
    )
    emisornombre = models.CharField(
        max_length=300,
        db_column='emisornombre',
        blank=True,
        null=True
    )
    emisorregimenfiscal = models.CharField(
        max_length=10,
        db_column='emisorregimenfiscal',
        blank=True,
        null=True
    )

    # Receptor (company)
    receptorrfc = models.CharField(
        max_length=13,
        db_column='receptorrfc',
        blank=True,
        null=True
    )
    receptornombre = models.CharField(
        max_length=300,
        db_column='receptornombre',
        blank=True,
        null=True
    )
    receptorusocfdi = models.CharField(
        max_length=10,
        db_column='receptorusocfdi',
        blank=True,
        null=True
    )

    # Amounts
    moneda = models.CharField(
        max_length=5,
        db_column='moneda',
        default='MXN'
    )
    tipocambio = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        db_column='tipocambio',
        default=Decimal('1.0000')
    )
    subtotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='subtotal',
        default=Decimal('0.00')
    )
    descuento = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='descuento',
        default=Decimal('0.00')
    )
    totalimpuestostrasladados = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='totalimpuestostrasladados',
        default=Decimal('0.00')
    )
    totalimpuestosretenidos = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='totalimpuestosretenidos',
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='total',
        default=Decimal('0.00')
    )

    # Payment info from CFDI
    formapago = models.CharField(
        max_length=5,
        db_column='formapago',
        blank=True,
        null=True
    )
    metodopago = models.CharField(
        max_length=5,
        db_column='metodopago',
        blank=True,
        null=True
    )

    # Conceptos stored as JSON for review display
    conceptosjson = models.JSONField(
        db_column='conceptosjson',
        default=list,
        help_text='Parsed CFDI line items as JSON array'
    )

    # File references
    xmlfile = models.FileField(
        upload_to='invoiceinbox/xml/%Y/%m/',
        db_column='xmlfile',
        blank=True,
        null=True
    )
    xmlfilename = models.CharField(
        max_length=255,
        db_column='xmlfilename',
        blank=True,
        null=True
    )
    xmlfilesize = models.IntegerField(
        db_column='xmlfilesize',
        default=0
    )
    pdffile = models.FileField(
        upload_to='invoiceinbox/pdf/%Y/%m/',
        db_column='pdffile',
        blank=True,
        null=True
    )
    pdffilename = models.CharField(
        max_length=255,
        db_column='pdffilename',
        blank=True,
        null=True
    )
    pdffilesize = models.IntegerField(
        db_column='pdffilesize',
        default=0
    )

    # Link to ProjectExpense (populated when state transitions to LINKED)
    linkedexpenseid = models.ForeignKey(
        'expenses.ProjectExpense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='linkedexpenseid',
        related_name='incoming_invoices'
    )

    # Matching metadata
    suggestedexpenseid = models.ForeignKey(
        'expenses.ProjectExpense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='suggestedexpenseid',
        related_name='+',
        help_text='Auto-suggested expense match'
    )
    matchtype = models.CharField(
        max_length=50,
        db_column='matchtype',
        blank=True,
        null=True,
        help_text='auto_uuid_match, auto_rfc_match, manual'
    )
    matchconfidence = models.IntegerField(
        db_column='matchconfidence',
        default=0,
        help_text='0-100 confidence score'
    )

    # Processing metadata
    parseerrors = models.TextField(
        db_column='parseerrors',
        blank=True,
        null=True
    )
    rejectionnotes = models.TextField(
        db_column='rejectionnotes',
        blank=True,
        null=True
    )
    classificationnotes = models.TextField(
        db_column='classificationnotes',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'incominginvoice'
        ordering = ['-emailreceivedon']
        indexes = [
            models.Index(fields=['statecode']),
            models.Index(fields=['projectid', 'statecode']),
            models.Index(fields=['uuid']),
            models.Index(fields=['emisorrfc']),
            models.Index(fields=['graphmessageid']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['uuid'],
                name='unique_incoming_invoice_uuid',
                condition=models.Q(uuid__isnull=False),
            ),
        ]

    def __str__(self):
        return f"Incoming {self.uuid or 'no-uuid'} from {self.emisornombre or 'unknown'}"


class InboxSyncLog(models.Model):
    """Audit log for each inbox sync execution."""

    synclogid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='synclogid'
    )

    # Project this sync was executed for
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='sync_logs'
    )

    syncstatus = models.IntegerField(
        choices=SyncStatusCode.choices,
        db_column='syncstatus'
    )
    triggeredby = models.IntegerField(
        choices=SyncTriggerCode.choices,
        db_column='triggeredby'
    )
    triggeredbyuserid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='triggeredbyuserid',
        related_name='+'
    )

    # Counters
    totalemailsfetched = models.IntegerField(
        db_column='totalemailsfetched',
        default=0
    )
    newxmlattachments = models.IntegerField(
        db_column='newxmlattachments',
        default=0
    )
    newpdfattachments = models.IntegerField(
        db_column='newpdfattachments',
        default=0
    )
    duplicatesskipped = models.IntegerField(
        db_column='duplicatesskipped',
        default=0
    )
    errorscount = models.IntegerField(
        db_column='errorscount',
        default=0
    )
    errorsdetail = models.JSONField(
        db_column='errorsdetail',
        default=list
    )

    startedon = models.DateTimeField(
        db_column='startedon',
        auto_now_add=True
    )
    completedon = models.DateTimeField(
        db_column='completedon',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'inboxsynclog'
        ordering = ['-startedon']

    def __str__(self):
        return f"Sync {self.synclogid} - {self.get_syncstatus_display()}"
