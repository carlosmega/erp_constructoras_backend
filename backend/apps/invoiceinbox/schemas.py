"""
Invoice Inbox Django Ninja schemas (DTOs).

Response schemas, create/update DTOs, and operation-specific payloads.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from ninja import ModelSchema, Schema

from apps.invoiceinbox.models import IncomingInvoice, InboxSyncLog


# =============================================================================
# Response Schemas
# =============================================================================

class IncomingInvoiceSchema(ModelSchema):
    """Full response schema for IncomingInvoice."""
    projectname: Optional[str] = None
    imputationcode: Optional[str] = None
    imputationcodename: Optional[str] = None
    linkedexpensefolio: Optional[str] = None

    class Meta:
        model = IncomingInvoice
        fields = '__all__'

    @staticmethod
    def resolve_projectname(obj):
        return obj.projectid.name if obj.projectid else None

    @staticmethod
    def resolve_imputationcode(obj):
        return obj.imputationcodeid.code if obj.imputationcodeid else None

    @staticmethod
    def resolve_imputationcodename(obj):
        return obj.imputationcodeid.name if obj.imputationcodeid else None

    @staticmethod
    def resolve_linkedexpensefolio(obj):
        return obj.linkedexpenseid.invoicefolio if obj.linkedexpenseid else None


class IncomingInvoiceListSchema(Schema):
    """Lightweight list schema (without conceptosjson)."""
    incominginvoiceid: UUID
    statecode: int
    projectid: UUID
    projectname: Optional[str] = None
    imputationcodeid: Optional[UUID] = None
    imputationcode: Optional[str] = None

    # CFDI key fields
    uuid: Optional[str] = None
    folio: Optional[str] = None
    serie: Optional[str] = None
    emisorrfc: Optional[str] = None
    emisornombre: Optional[str] = None
    receptorrfc: Optional[str] = None
    moneda: str = 'MXN'
    subtotal: Decimal = Decimal('0.00')
    totalimpuestostrasladados: Decimal = Decimal('0.00')
    total: Decimal = Decimal('0.00')
    fecha: Optional[datetime] = None

    # Email info
    emailsubject: Optional[str] = None
    emailfrom: Optional[str] = None
    emailreceivedon: Optional[datetime] = None

    # Linking
    linkedexpenseid: Optional[UUID] = None
    suggestedexpenseid: Optional[UUID] = None
    matchtype: Optional[str] = None
    matchconfidence: int = 0

    # Files
    xmlfilename: Optional[str] = None
    pdffilename: Optional[str] = None
    parseerrors: Optional[str] = None

    # Audit
    createdon: Optional[datetime] = None

    @staticmethod
    def resolve_projectid(obj):
        return obj.projectid.projectid if obj.projectid else None

    @staticmethod
    def resolve_projectname(obj):
        return obj.projectid.name if obj.projectid else None

    @staticmethod
    def resolve_imputationcodeid(obj):
        return obj.imputationcodeid.imputationcodeid if obj.imputationcodeid else None

    @staticmethod
    def resolve_imputationcode(obj):
        return obj.imputationcodeid.code if obj.imputationcodeid else None

    @staticmethod
    def resolve_linkedexpenseid(obj):
        return obj.linkedexpenseid.expenseid if obj.linkedexpenseid else None

    @staticmethod
    def resolve_suggestedexpenseid(obj):
        return obj.suggestedexpenseid.expenseid if obj.suggestedexpenseid else None


class InboxSyncLogSchema(ModelSchema):
    """Response schema for InboxSyncLog."""

    class Meta:
        model = InboxSyncLog
        fields = '__all__'


# =============================================================================
# Operation DTOs
# =============================================================================

class ClassifyInvoiceDto(Schema):
    """DTO for classifying an incoming invoice (assign imputation code)."""
    imputationcodeid: UUID
    notes: Optional[str] = None


class RejectInvoiceDto(Schema):
    """DTO for rejecting an incoming invoice."""
    notes: str


class LinkToExpenseDto(Schema):
    """DTO for linking an incoming invoice to an expense."""
    expenseid: Optional[UUID] = None  # None = create new expense
    periodid: UUID


class BulkClassifyDto(Schema):
    """DTO for bulk classifying multiple incoming invoices."""
    invoiceids: list[UUID]
    imputationcodeid: UUID
    notes: Optional[str] = None


# =============================================================================
# Summary / Result Schemas
# =============================================================================

class InboxSummarySchema(Schema):
    """Summary counts for inbox dashboard."""
    draftcount: int = 0
    classifiedcount: int = 0
    linkedcount: int = 0
    rejectedcount: int = 0
    totalcount: int = 0
    lastsyncdate: Optional[datetime] = None


class SyncResultSchema(Schema):
    """Response from a sync operation."""
    success: bool
    totalemailsfetched: int = 0
    newxmlattachments: int = 0
    newpdfattachments: int = 0
    duplicatesskipped: int = 0
    errorscount: int = 0
    errors: list[str] = []


class MatchSuggestionSchema(Schema):
    """A match suggestion for an incoming invoice."""
    expenseid: UUID
    matchtype: str
    confidence: int
    suppliername: Optional[str] = None
    supplierrfc: Optional[str] = None
    invoicefolio: Optional[str] = None
    netamount: Decimal = Decimal('0.00')
    projectname: Optional[str] = None


class CapturedEmailsResponse(Schema):
    """Map of Graph message IDs → IncomingInvoice IDs for Bandeja cross-referencing."""
    captured: dict[str, str]
