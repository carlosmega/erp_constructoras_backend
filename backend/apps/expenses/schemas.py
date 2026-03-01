"""Expense management API schemas."""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime

from apps.expenses.models import (
    ProjectExpense,
    ExpenseLine,
    ExpenseAttachment,
    ClassificationLog,
    ClientEstimate,
)


# =============================================================================
# ProjectExpense Schemas
# =============================================================================

class ExpenseLineSchema(ModelSchema):
    """Full ExpenseLine response schema."""

    class Meta:
        model = ExpenseLine
        fields = '__all__'


class ExpenseAttachmentSchema(ModelSchema):
    """Full ExpenseAttachment response schema."""

    class Meta:
        model = ExpenseAttachment
        fields = '__all__'


class ClassificationLogSchema(ModelSchema):
    """Full ClassificationLog response schema."""
    previousimputationcode: Optional[str] = None
    newimputationcode: Optional[str] = None

    class Meta:
        model = ClassificationLog
        fields = '__all__'


class ProjectExpenseSchema(ModelSchema):
    """Full ProjectExpense response schema."""
    periodlabel: Optional[str] = None
    imputationcodename: Optional[str] = None
    imputationcode: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = ProjectExpense
        fields = '__all__'

    @staticmethod
    def resolve_periodlabel(obj):
        return obj.periodid.label if obj.periodid else None

    @staticmethod
    def resolve_imputationcodename(obj):
        return obj.imputationcodeid.name if obj.imputationcodeid else None

    @staticmethod
    def resolve_imputationcode(obj):
        return obj.imputationcodeid.code if obj.imputationcodeid else None

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


# =============================================================================
# Create / Update DTOs
# =============================================================================

class CreateExpenseLineDto(Schema):
    """DTO for creating an expense line."""
    description: str
    quantity: Decimal
    unitprice: Decimal
    taxamount: Decimal = Decimal('0.00')
    retentionamount: Decimal = Decimal('0.00')
    discountamount: Decimal = Decimal('0.00')


class UpdateExpenseLineDto(Schema):
    """DTO for updating an expense line."""
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unitprice: Optional[Decimal] = None
    taxamount: Optional[Decimal] = None
    retentionamount: Optional[Decimal] = None
    discountamount: Optional[Decimal] = None


class CreateProjectExpenseDto(Schema):
    """DTO for creating a project expense."""
    projectid: UUID
    periodid: UUID
    documenttype: int
    imputationcodeid: Optional[UUID] = None
    supplierrfc: Optional[str] = None
    suppliername: Optional[str] = None
    invoiceuuid: Optional[str] = None
    invoicefolio: Optional[str] = None
    invoicedate: Optional[date] = None
    expensesource: Optional[str] = None
    payrolltype: Optional[int] = None
    workername: Optional[str] = None
    provisionstatus: Optional[int] = None
    paymentmethod: Optional[int] = None
    paymentstatus: int = 0
    currency: int = 0
    exchangerate: Decimal = Decimal('1.0000')
    subtotal: Decimal = Decimal('0.00')
    taxamount: Decimal = Decimal('0.00')
    retentionamount: Decimal = Decimal('0.00')
    discountamount: Decimal = Decimal('0.00')
    netamount: Decimal = Decimal('0.00')
    notes: Optional[str] = None
    lines: Optional[list[CreateExpenseLineDto]] = None


class UpdateProjectExpenseDto(Schema):
    """DTO for updating a project expense."""
    periodid: Optional[UUID] = None
    documenttype: Optional[int] = None
    supplierrfc: Optional[str] = None
    suppliername: Optional[str] = None
    invoiceuuid: Optional[str] = None
    invoicefolio: Optional[str] = None
    invoicedate: Optional[date] = None
    expensesource: Optional[str] = None
    payrolltype: Optional[int] = None
    workername: Optional[str] = None
    paymentmethod: Optional[int] = None
    paymentstatus: Optional[int] = None
    currency: Optional[int] = None
    exchangerate: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    taxamount: Optional[Decimal] = None
    retentionamount: Optional[Decimal] = None
    discountamount: Optional[Decimal] = None
    netamount: Optional[Decimal] = None
    notes: Optional[str] = None
    lines: Optional[list[CreateExpenseLineDto]] = None


# =============================================================================
# Attachment DTOs
# =============================================================================

class CreateExpenseAttachmentDto(Schema):
    """DTO for creating an expense attachment."""
    expenseid: UUID
    filename: str
    suggestedfilename: str
    filetype: int
    filesize: int
    mimetype: str
    storageurl: str


# =============================================================================
# Classification DTOs
# =============================================================================

class ClassifyExpenseDto(Schema):
    """DTO for classifying a single expense."""
    imputationcodeid: UUID
    notes: Optional[str] = None


class BulkClassifyDto(Schema):
    """DTO for bulk classifying expenses."""
    expenseids: list[UUID]
    imputationcodeid: UUID
    notes: Optional[str] = None


# =============================================================================
# Verification DTOs
# =============================================================================

class VerifyExpenseDto(Schema):
    """DTO for updating verification status."""
    verificationstatus: int
    verificationnotes: Optional[str] = None


# =============================================================================
# Summary Schema
# =============================================================================

class ExpenseSummarySchema(Schema):
    """Aggregate expense summary for a project."""
    total_count: int = 0
    total_amount: Decimal = Decimal('0.00')
    classified_count: int = 0
    unclassified_count: int = 0
    by_document_type: list[dict] = []


# =============================================================================
# ClientEstimate Schemas
# =============================================================================

class ClientEstimateSchema(ModelSchema):
    """Full ClientEstimate response schema."""
    periodlabel: Optional[str] = None
    daysoverdue: int = 0

    class Meta:
        model = ClientEstimate
        fields = '__all__'

    @staticmethod
    def resolve_periodlabel(obj):
        return obj.periodid.label if obj.periodid else None

    @staticmethod
    def resolve_daysoverdue(obj):
        if obj.paymentstatus == 0 and obj.paymentdate:
            from django.utils import timezone
            delta = timezone.now().date() - obj.paymentdate
            return max(delta.days, 0)
        return 0


class CreateClientEstimateDto(Schema):
    """DTO for creating a client estimate."""
    projectid: UUID
    periodid: Optional[UUID] = None
    invoicenumber: Optional[str] = None
    invoicedate: Optional[date] = None
    estimationperiod: Optional[str] = None
    estimatetype: int = 0
    estimatedamount: Decimal = Decimal('0.00')
    advanceamortization: Decimal = Decimal('0.00')
    otherdeductions: Decimal = Decimal('0.00')
    materialdeductions: Decimal = Decimal('0.00')
    guaranteefund: Decimal = Decimal('0.00')
    taxretained: Decimal = Decimal('0.00')
    paymentstatus: int = 0
    paymentdate: Optional[date] = None
    amountpaid: Decimal = Decimal('0.00')


class UpdateClientEstimateDto(Schema):
    """DTO for updating a client estimate."""
    periodid: Optional[UUID] = None
    invoicenumber: Optional[str] = None
    invoicedate: Optional[date] = None
    estimationperiod: Optional[str] = None
    estimatetype: Optional[int] = None
    estimatedamount: Optional[Decimal] = None
    advanceamortization: Optional[Decimal] = None
    otherdeductions: Optional[Decimal] = None
    materialdeductions: Optional[Decimal] = None
    guaranteefund: Optional[Decimal] = None
    taxretained: Optional[Decimal] = None
    paymentstatus: Optional[int] = None
    paymentdate: Optional[date] = None
    amountpaid: Optional[Decimal] = None
