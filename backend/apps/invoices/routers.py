"""
Django Ninja API routers for Invoice management.

Phase 10 Implementation: Invoice Management
"""

from typing import List
from uuid import UUID
from django.http import HttpRequest
from ninja import Router

from apps.invoices.models import Invoice, InvoiceStateCode
from apps.invoices.schemas import (
    InvoiceSchema, InvoiceListItemSchema, CreateInvoiceDto, UpdateInvoiceDto,
    CreateInvoiceDetailDto, InvoiceDetailSchema, RecordPaymentDto,
    CancelInvoiceDto, InvoiceStatsSchema
)
from apps.invoices.services import InvoiceService
from core.permissions import Permission, require_permission, filter_by_ownership

# Initialize router
invoices_router = Router(tags=["Invoices"])


# ============================================================================
# Invoice CRUD Operations
# ============================================================================

@invoices_router.get('/', response=List[InvoiceListItemSchema])
@require_permission(Permission.INVOICE_READ)
def list_invoices(
    request: HttpRequest,
    statecode: int = None,
    overdue: bool = None,
    limit: int = 100,
    offset: int = 0
):
    """
    List invoices with filtering.

    Query Parameters:
    - statecode: Filter by state (0=Active, 1=Paid, 2=Canceled)
    - overdue: Filter overdue invoices (true/false)
    - limit: Max results (default 100)
    - offset: Pagination offset (default 0)
    """
    queryset = filter_by_ownership(Invoice.objects.all(), request.user)

    # Apply filters
    if statecode is not None:
        queryset = queryset.filter(statecode=statecode)

    if overdue is not None:
        from datetime import date
        if overdue:
            queryset = queryset.filter(
                statecode=InvoiceStateCode.ACTIVE,
                duedate__lt=date.today()
            )

    # Order by creation date (newest first)
    queryset = queryset.order_by('-createdon')[offset:offset + limit]

    return list(queryset)


@invoices_router.get('/{invoice_id}', response=InvoiceSchema)
@require_permission(Permission.INVOICE_READ)
def get_invoice(request: HttpRequest, invoice_id: UUID):
    """Get a specific invoice by ID."""
    invoice = InvoiceService.get_invoice_by_id(invoice_id, request.user)
    return invoice


@invoices_router.post('/', response={201: InvoiceSchema})
@require_permission(Permission.INVOICE_CREATE)
def create_invoice(request: HttpRequest, payload: CreateInvoiceDto):
    """
    Create a new invoice manually.

    Note: For creating from orders, use POST /invoices/from-order/{order_id}
    """
    invoice = InvoiceService.create_invoice(payload, request.user)
    return 201, invoice


@invoices_router.patch('/{invoice_id}', response=InvoiceSchema)
@require_permission(Permission.INVOICE_UPDATE)
def update_invoice(request: HttpRequest, invoice_id: UUID, payload: UpdateInvoiceDto):
    """
    Update invoice details.

    Cannot update paid or canceled invoices.
    """
    invoice = InvoiceService.update_invoice(invoice_id, payload, request.user)
    return invoice


@invoices_router.delete('/{invoice_id}', response={204: None})
@require_permission(Permission.INVOICE_DELETE)
def delete_invoice(request: HttpRequest, invoice_id: UUID):
    """
    Delete an invoice.

    Can only delete draft invoices that haven't been paid.
    """
    invoice = InvoiceService.get_invoice_by_id(invoice_id, request.user)

    # Can only delete unpaid invoices with no payments
    if invoice.totalpaid > 0:
        from core.exceptions import ValidationError
        raise ValidationError('Cannot delete invoices that have payments')

    invoice.delete()
    return 204, None


# ============================================================================
# Invoice Line Items
# ============================================================================

@invoices_router.post('/{invoice_id}/details', response={201: InvoiceDetailSchema})
@require_permission(Permission.INVOICE_UPDATE)
def add_invoice_detail(request: HttpRequest, invoice_id: UUID, payload: CreateInvoiceDetailDto):
    """
    Add a line item to an invoice.

    Automatically recalculates invoice totals.
    """
    detail = InvoiceService.add_invoice_detail(invoice_id, payload, request.user)
    return 201, detail


@invoices_router.delete('/{invoice_id}/details/{detail_id}', response={204: None})
@require_permission(Permission.INVOICE_UPDATE)
def remove_invoice_detail(request: HttpRequest, invoice_id: UUID, detail_id: UUID):
    """
    Remove a line item from an invoice.

    Automatically recalculates invoice totals.
    """
    InvoiceService.remove_invoice_detail(invoice_id, detail_id, request.user)
    return 204, None


# ============================================================================
# Special Invoice Operations
# ============================================================================

@invoices_router.post('/from-order/{order_id}', response={201: InvoiceSchema})
@require_permission(Permission.INVOICE_CREATE)
def create_invoice_from_order(request: HttpRequest, order_id: UUID):
    """
    Create an invoice from a fulfilled sales order.

    Automatically:
    - Validates order is fulfilled
    - Copies all order details to invoice
    - Links invoice to order, opportunity, and customer
    - Sets due date to 30 days from now
    - Updates order state to INVOICED
    """
    invoice = InvoiceService.create_invoice_from_order(order_id, request.user)
    return 201, invoice


@invoices_router.post('/{invoice_id}/record-payment', response=InvoiceSchema)
@require_permission(Permission.INVOICE_UPDATE)
def record_payment(request: HttpRequest, invoice_id: UUID, payload: RecordPaymentDto):
    """
    Record a payment on an invoice.

    Automatically updates:
    - totalpaid (adds payment amount)
    - totalamountdue (recalculates)
    - statecode/statuscode (if fully paid)
    - paidon date (if fully paid)
    """
    invoice = InvoiceService.record_payment(invoice_id, payload, request.user)
    return invoice


@invoices_router.post('/{invoice_id}/cancel', response=InvoiceSchema)
@require_permission(Permission.INVOICE_UPDATE)
def cancel_invoice(request: HttpRequest, invoice_id: UUID, payload: CancelInvoiceDto):
    """
    Cancel an invoice.

    Cannot cancel paid invoices.
    Sets statecode to CANCELED and statuscode to CANCELED.
    """
    invoice = InvoiceService.cancel_invoice(invoice_id, payload, request.user)
    return invoice


@invoices_router.get('/stats/summary', response=InvoiceStatsSchema)
@require_permission(Permission.INVOICE_READ)
def get_invoice_stats(request: HttpRequest):
    """
    Get invoice statistics for the current user.

    Returns:
    - total_invoices: Total count
    - total_amount: Sum of all invoice amounts
    - total_paid: Sum of all payments received
    - total_due: Sum of all amounts still owed
    - active_count: Count of active invoices
    - paid_count: Count of fully paid invoices
    - overdue_count: Count of overdue invoices
    - canceled_count: Count of canceled invoices
    """
    stats = InvoiceService.get_invoice_stats(request.user)
    return stats
