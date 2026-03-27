"""
Order API routers.

Phase 9 Implementation: Order Management
"""

from ninja import Router
from django.http import HttpRequest
from typing import List, Optional
from uuid import UUID

from apps.orders.services import OrderService
from apps.orders.schemas import (
    SalesOrderSchema, SalesOrderListItemSchema, SalesOrderDetailSchema,
    CreateSalesOrderDto, UpdateSalesOrderDto, CreateOrderDetailDto, UpdateOrderDetailDto,
    FulfillOrderDto, OrderStatsSchema
)
from core.permissions import require_permission, Permission

orders_router = Router(tags=['Orders'])


@orders_router.get('/', response=List[SalesOrderListItemSchema])
@require_permission(Permission.ORDER_READ)
def list_orders(
    request: HttpRequest,
    state: int = None,
    statecode: int = None,
    owner: UUID = None,
    quoteid: Optional[str] = None,
    opportunityid: Optional[str] = None,
    customerid: Optional[str] = None,
):
    """
    List all orders with optional filtering.

    Filters:
    - state/statecode: Filter by statecode (0=Active, 1=Submitted, 2=Canceled, 3=Fulfilled, 4=Invoiced)
    - owner: Filter by owner ID
    - quoteid: Filter by quote ID
    - opportunityid: Filter by opportunity ID
    - customerid: Filter by customer ID (account or contact)
    """
    from apps.orders.models import SalesOrder
    from core.permissions import filter_by_ownership
    from django.db.models import Q

    queryset = filter_by_ownership(SalesOrder.objects.all(), request.user)

    effective_state = statecode if statecode is not None else state
    if effective_state is not None:
        queryset = queryset.filter(statecode=effective_state)
    if owner:
        queryset = queryset.filter(ownerid=owner)
    if quoteid:
        queryset = queryset.filter(quoteid_id=quoteid)
    if opportunityid:
        queryset = queryset.filter(opportunityid_id=opportunityid)
    if customerid:
        queryset = queryset.filter(
            Q(accountid_id=customerid) | Q(contactid_id=customerid)
        )

    queryset = queryset.select_related('accountid', 'contactid', 'ownerid')
    return list(queryset)


@orders_router.post('/', response={201: SalesOrderSchema})
@require_permission(Permission.ORDER_CREATE)
def create_order(request: HttpRequest, payload: CreateSalesOrderDto):
    """Create a new sales order manually."""
    order = OrderService.create_order(payload, request.user)
    return 201, order


@orders_router.post('/from-quote/{quote_id}', response={201: SalesOrderSchema})
@require_permission(Permission.ORDER_CREATE)
def create_order_from_quote(request: HttpRequest, quote_id: UUID):
    """Create an order from a won quote."""
    order = OrderService.create_order_from_quote(quote_id, request.user)
    return 201, order


@orders_router.get('/{order_id}', response=SalesOrderSchema)
@require_permission(Permission.ORDER_READ)
def get_order(request: HttpRequest, order_id: UUID):
    """Get a single order by ID."""
    order = OrderService.get_order_by_id(order_id, request.user)
    return order


@orders_router.patch('/{order_id}', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def update_order(request: HttpRequest, order_id: UUID, payload: UpdateSalesOrderDto):
    """Update an order."""
    order = OrderService.update_order(order_id, payload, request.user)
    return order


@orders_router.delete('/{order_id}', response={204: None})
@require_permission(Permission.ORDER_DELETE)
def delete_order(request: HttpRequest, order_id: UUID):
    """Delete an order (only active/draft orders)."""
    from apps.orders.models import SalesOrder, OrderStateCode
    from django.shortcuts import get_object_or_404
    from core.exceptions import ValidationError

    order = get_object_or_404(SalesOrder, salesorderid=order_id)
    if order.statecode not in (OrderStateCode.ACTIVE,):
        raise ValidationError('Can only delete active orders')
    order.statecode = OrderStateCode.CANCELED
    order.save()
    return 204, None


# ============ Order Detail Endpoints ============

@orders_router.post('/{order_id}/details', response={201: SalesOrderDetailSchema})
@require_permission(Permission.ORDER_UPDATE)
def add_order_detail(request: HttpRequest, order_id: UUID, payload: CreateOrderDetailDto):
    """Add a line item to an order."""
    from apps.orders.models import SalesOrder, SalesOrderDetail
    from django.shortcuts import get_object_or_404

    order = get_object_or_404(SalesOrder, salesorderid=order_id)

    detail = SalesOrderDetail(
        salesorderid=order,
        productname=payload.productdescription or payload.productname or 'Product',
        productdescription=payload.productdescription,
        quantity=payload.quantity,
        priceperunit=payload.priceperunit,
        manualdiscountamount=payload.manualdiscountamount,
        tax=payload.tax,
    )
    detail.save()

    # Recalculate order totals
    _recalculate_order_totals(order)

    return 201, detail


@orders_router.get('/details/{detail_id}', response=SalesOrderDetailSchema)
@require_permission(Permission.ORDER_READ)
def get_order_detail(request: HttpRequest, detail_id: UUID):
    """Get a single order detail by ID."""
    from apps.orders.models import SalesOrderDetail
    from django.shortcuts import get_object_or_404
    detail = get_object_or_404(SalesOrderDetail, salesorderdetailid=detail_id)
    return detail


@orders_router.patch('/details/{detail_id}', response=SalesOrderDetailSchema)
@require_permission(Permission.ORDER_UPDATE)
def update_order_detail(request: HttpRequest, detail_id: UUID, payload: UpdateOrderDetailDto):
    """Update an order detail line item."""
    from apps.orders.models import SalesOrderDetail
    from django.shortcuts import get_object_or_404

    detail = get_object_or_404(SalesOrderDetail, salesorderdetailid=detail_id)

    if payload.productdescription is not None:
        detail.productdescription = payload.productdescription
    if payload.quantity is not None:
        detail.quantity = payload.quantity
    if payload.priceperunit is not None:
        detail.priceperunit = payload.priceperunit
    if payload.manualdiscountamount is not None:
        detail.manualdiscountamount = payload.manualdiscountamount
    if payload.tax is not None:
        detail.tax = payload.tax

    detail.save()

    # Recalculate order totals
    _recalculate_order_totals(detail.salesorderid)

    return detail


@orders_router.delete('/details/{detail_id}', response={204: None})
@require_permission(Permission.ORDER_UPDATE)
def remove_order_detail(request: HttpRequest, detail_id: UUID):
    """Remove a line item from an order."""
    from apps.orders.models import SalesOrderDetail
    from django.shortcuts import get_object_or_404

    detail = get_object_or_404(SalesOrderDetail, salesorderdetailid=detail_id)
    order = detail.salesorderid
    detail.delete()

    # Recalculate order totals
    _recalculate_order_totals(order)

    return 204, None


# ============ Order Actions ============

@orders_router.post('/{order_id}/submit', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def submit_order(request: HttpRequest, order_id: UUID):
    """Submit order for processing."""
    order = OrderService.submit_order(order_id, request.user)
    return order


@orders_router.post('/{order_id}/fulfill', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def fulfill_order(request: HttpRequest, order_id: UUID, payload: FulfillOrderDto):
    """Mark order as fulfilled."""
    order = OrderService.fulfill_order(order_id, payload, request.user)
    return order


@orders_router.post('/{order_id}/cancel', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def cancel_order(request: HttpRequest, order_id: UUID):
    """Cancel an order."""
    order = OrderService.cancel_order(order_id, request.user)
    return order


@orders_router.get('/stats/summary', response=OrderStatsSchema)
@require_permission(Permission.ORDER_READ)
def get_order_stats(request: HttpRequest):
    """Get statistics about orders."""
    stats = OrderService.get_order_stats(request.user)
    return stats


def _recalculate_order_totals(order):
    """Recalculate order totals from line items."""
    from django.db.models import Sum
    from decimal import Decimal

    details = order.order_details.all()
    totals = details.aggregate(
        line_total=Sum('extendedamount'),
        tax_total=Sum('tax'),
        discount_total=Sum('manualdiscountamount'),
        base_total=Sum('baseamount'),
    )

    order.totallineitemamount = totals['base_total'] or Decimal('0.00')
    order.totaltax = totals['tax_total'] or Decimal('0.00')
    order.totaldiscountamount = totals['discount_total'] or Decimal('0.00')
    order.totalamount = totals['line_total'] or Decimal('0.00')
    order.save(update_fields=['totallineitemamount', 'totaltax', 'totaldiscountamount', 'totalamount'])
