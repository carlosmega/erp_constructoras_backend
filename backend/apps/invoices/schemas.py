"""
Django Ninja schemas (DTOs) for Invoice management.

Phase 10 Implementation: Invoice Management
"""

from ninja import ModelSchema, Schema
from apps.invoices.models import Invoice, InvoiceDetail
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal


# ============================================================================
# InvoiceDetail Schemas
# ============================================================================

class InvoiceDetailSchema(ModelSchema):
    """Full InvoiceDetail response schema."""
    class Meta:
        model = InvoiceDetail
        fields = [
            'invoicedetailid', 'invoiceid', 'productname', 'productdescription',
            'quantity', 'priceperunit', 'manualdiscountamount', 'tax',
            'baseamount', 'extendedamount', 'sequencenumber',
            'createdon', 'modifiedon'
        ]


class CreateInvoiceDetailDto(Schema):
    """DTO for creating invoice line items."""
    productname: str
    productdescription: Optional[str] = None
    quantity: Decimal
    priceperunit: Decimal
    manualdiscountamount: Decimal = Decimal('0.00')
    tax: Decimal = Decimal('0.00')
    sequencenumber: int = 1


# ============================================================================
# Invoice Schemas
# ============================================================================

class InvoiceSchema(ModelSchema):
    """Full Invoice response schema with nested details."""
    invoice_details: List[InvoiceDetailSchema] = []
    customer_name: Optional[str] = None
    is_overdue: bool = False

    class Meta:
        model = Invoice
        fields = [
            'invoiceid', 'name', 'invoicenumber', 'salesorderid', 'opportunityid',
            'accountid', 'contactid', 'totalamount', 'totaldiscountamount',
            'totaltax', 'totallineitemamount', 'totalamountless',
            'totalpaid', 'totalamountdue', 'datedelivered', 'duedate', 'paidon',
            'statecode', 'statuscode', 'description', 'ownerid',
            'createdon', 'modifiedon', 'createdby', 'modifiedby'
        ]


class InvoiceListItemSchema(ModelSchema):
    """Simplified Invoice schema for list views."""
    customer_name: Optional[str] = None
    is_overdue: bool = False

    class Meta:
        model = Invoice
        fields = [
            'invoiceid', 'name', 'invoicenumber', 'totalamount',
            'totalpaid', 'totalamountdue', 'duedate', 'statecode',
            'statuscode', 'ownerid', 'createdon'
        ]


class CreateInvoiceDto(Schema):
    """DTO for creating a new invoice manually."""
    name: str
    salesorderid: Optional[UUID] = None
    accountid: Optional[UUID] = None
    contactid: Optional[UUID] = None
    datedelivered: Optional[date] = None
    duedate: Optional[date] = None
    description: Optional[str] = None


class UpdateInvoiceDto(Schema):
    """DTO for updating an invoice (all fields optional)."""
    name: Optional[str] = None
    datedelivered: Optional[date] = None
    duedate: Optional[date] = None
    description: Optional[str] = None
    totaldiscountamount: Optional[Decimal] = None


class RecordPaymentDto(Schema):
    """DTO for recording a payment on an invoice."""
    payment_amount: Decimal
    payment_date: Optional[date] = None


class CancelInvoiceDto(Schema):
    """DTO for canceling an invoice."""
    reason: Optional[str] = None


class InvoiceStatsSchema(Schema):
    """DTO for invoice statistics."""
    total_invoices: int
    total_amount: Decimal
    total_paid: Decimal
    total_due: Decimal
    active_count: int
    paid_count: int
    overdue_count: int
    canceled_count: int
