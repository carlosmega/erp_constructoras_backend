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
from core.pagination import paginate_queryset, create_paginated_response
from core.permissions import require_permission, Permission

orders_router = Router(tags=['Orders'])

PaginatedSalesOrderList = create_paginated_response(SalesOrderListItemSchema)


def _build_orders_queryset(
    request: HttpRequest,
    state,
    statecode,
    owner,
    quoteid,
    opportunityid,
    customerid,
):
    """Shared queryset builder for legacy and paginated list endpoints."""
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
    return queryset.select_related('accountid', 'contactid', 'ownerid')


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
    """List all orders with optional filtering (non-paginated)."""
    return list(_build_orders_queryset(
        request, state, statecode, owner, quoteid, opportunityid, customerid,
    ))


@orders_router.get('/paginated/', response=PaginatedSalesOrderList)
@require_permission(Permission.ORDER_READ)
def list_orders_paginated(
    request: HttpRequest,
    page: int = 1,
    page_size: int = 50,
    state: int = None,
    statecode: int = None,
    owner: UUID = None,
    quoteid: Optional[str] = None,
    opportunityid: Optional[str] = None,
    customerid: Optional[str] = None,
):
    """List orders with offset-based pagination (opt-in alternative to `/`)."""
    queryset = _build_orders_queryset(
        request, state, statecode, owner, quoteid, opportunityid, customerid,
    )
    return paginate_queryset(queryset, page=page, page_size=page_size, request_url=request.path)


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
    """Delete an order (only active orders, ownership-checked)."""
    OrderService.delete_order(order_id, request.user)
    return 204, None


# ============ Order Detail Endpoints ============

@orders_router.post('/{order_id}/details', response={201: SalesOrderDetailSchema})
@require_permission(Permission.ORDER_UPDATE)
def add_order_detail(request: HttpRequest, order_id: UUID, payload: CreateOrderDetailDto):
    """Add a line item to an order (ownership-checked)."""
    return 201, OrderService.add_order_detail(order_id, payload, request.user)


@orders_router.get('/details/{detail_id}', response=SalesOrderDetailSchema)
@require_permission(Permission.ORDER_READ)
def get_order_detail(request: HttpRequest, detail_id: UUID):
    """Get a single order detail by ID (ownership-checked)."""
    return OrderService.get_order_detail(detail_id, request.user)


@orders_router.patch('/details/{detail_id}', response=SalesOrderDetailSchema)
@require_permission(Permission.ORDER_UPDATE)
def update_order_detail(request: HttpRequest, detail_id: UUID, payload: UpdateOrderDetailDto):
    """Update an order detail line item (ownership-checked)."""
    return OrderService.update_order_detail(detail_id, payload, request.user)


@orders_router.delete('/details/{detail_id}', response={204: None})
@require_permission(Permission.ORDER_UPDATE)
def remove_order_detail(request: HttpRequest, detail_id: UUID):
    """Remove a line item from an order (ownership-checked)."""
    OrderService.remove_order_detail(detail_id, request.user)
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


