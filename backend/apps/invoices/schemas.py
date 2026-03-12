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
    imputationcode: Optional[str] = None
    imputationcodename: Optional[str] = None

    class Meta:
        model = InvoiceDetail
        fields = [
            'invoicedetailid', 'invoiceid', 'imputationcodeid',
            'productname', 'productdescription',
            'quantity', 'priceperunit', 'manualdiscountamount', 'tax',
            'baseamount', 'extendedamount', 'sequencenumber',
            'createdon', 'modifiedon'
        ]

    @staticmethod
    def resolve_imputationcode(obj):
        if obj.imputationcodeid:
            return obj.imputationcodeid.code
        return None

    @staticmethod
    def resolve_imputationcodename(obj):
        if obj.imputationcodeid:
            return obj.imputationcodeid.name
        return None


class InvoiceDetailListItemSchema(ModelSchema):
    """InvoiceDetail schema for cross-invoice list views.

    Includes parent invoice info so items can be displayed outside
    the context of a single invoice.
    """
    imputationcode: Optional[str] = None
    imputationcodename: Optional[str] = None
    invoicenumber: Optional[str] = None
    invoicename: Optional[str] = None
    invoicestatecode: Optional[int] = None

    class Meta:
        model = InvoiceDetail
        fields = [
            'invoicedetailid', 'invoiceid', 'imputationcodeid',
            'productname', 'productdescription',
            'quantity', 'priceperunit', 'manualdiscountamount', 'tax',
            'baseamount', 'extendedamount', 'sequencenumber',
            'createdon', 'modifiedon'
        ]

    @staticmethod
    def resolve_imputationcode(obj):
        if obj.imputationcodeid:
            return obj.imputationcodeid.code
        return None

    @staticmethod
    def resolve_imputationcodename(obj):
        if obj.imputationcodeid:
            return obj.imputationcodeid.name
        return None

    @staticmethod
    def resolve_invoicenumber(obj):
        return obj.invoiceid.invoicenumber if obj.invoiceid else None

    @staticmethod
    def resolve_invoicename(obj):
        return obj.invoiceid.name if obj.invoiceid else None

    @staticmethod
    def resolve_invoicestatecode(obj):
        return obj.invoiceid.statecode if obj.invoiceid else None


class CreateInvoiceDetailDto(Schema):
    """DTO for creating invoice line items."""
    productname: str
    productdescription: Optional[str] = None
    quantity: Decimal
    priceperunit: Decimal
    manualdiscountamount: Decimal = Decimal('0.00')
    tax: Decimal = Decimal('0.00')
    sequencenumber: int = 1
    imputationcodeid: Optional[UUID] = None


class UpdateInvoiceDetailDto(Schema):
    """DTO for updating invoice line items."""
    productdescription: Optional[str] = None
    quantity: Optional[Decimal] = None
    priceperunit: Optional[Decimal] = None
    manualdiscountamount: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    imputationcodeid: Optional[UUID] = None
    clear_imputationcodeid: bool = False


# ============================================================================
# Invoice Schemas
# ============================================================================

class InvoiceSchema(ModelSchema):
    """Full Invoice response schema with nested details."""
    invoice_details: List[InvoiceDetailSchema] = []
    customer_name: Optional[str] = None
    customerid: Optional[str] = None
    customeridtype: Optional[str] = None
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

    @staticmethod
    def resolve_customerid(obj):
        from core.customers import get_customerid
        return get_customerid(obj)

    @staticmethod
    def resolve_customeridtype(obj):
        from core.customers import get_customeridtype
        return get_customeridtype(obj)


class InvoiceListItemSchema(ModelSchema):
    """Simplified Invoice schema for list views."""
    customer_name: Optional[str] = None
    customerid: Optional[str] = None
    customeridtype: Optional[str] = None
    is_overdue: bool = False

    class Meta:
        model = Invoice
        fields = [
            'invoiceid', 'name', 'invoicenumber', 'totalamount',
            'totalpaid', 'totalamountdue', 'duedate', 'statecode',
            'statuscode', 'ownerid', 'createdon'
        ]

    @staticmethod
    def resolve_customerid(obj):
        from core.customers import get_customerid
        return get_customerid(obj)

    @staticmethod
    def resolve_customeridtype(obj):
        from core.customers import get_customeridtype
        return get_customeridtype(obj)


class CreateInvoiceDto(Schema):
    """DTO for creating a new invoice manually."""
    name: str
    salesorderid: Optional[UUID] = None
    opportunityid: Optional[UUID] = None
    customerid: Optional[UUID] = None
    customeridtype: Optional[str] = None  # 'account' or 'contact'
    datedelivered: Optional[date] = None
    duedate: Optional[date] = None
    description: Optional[str] = None
    ownerid: Optional[UUID] = None


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
