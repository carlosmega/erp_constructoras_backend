"""
Order API routers.

Phase 9 Implementation: Order Management
"""

from ninja import Router
from django.http import HttpRequest
from typing import List
from uuid import UUID

from apps.orders.services import OrderService
from apps.orders.schemas import (
    SalesOrderSchema, SalesOrderListItemSchema, CreateSalesOrderDto,
    UpdateSalesOrderDto, FulfillOrderDto, OrderStatsSchema
)
from core.permissions import require_permission, Permission
from core.pagination import paginate_queryset, create_paginated_response

PaginatedOrderList = create_paginated_response(SalesOrderListItemSchema)

orders_router = Router(tags=['Orders'])


@orders_router.get('/', response=PaginatedOrderList)
@require_permission(Permission.ORDER_READ)
def list_orders(request: HttpRequest, page: int = 1, page_size: int = 50, state: int = None, owner: UUID = None):
    """
    List all orders with optional filtering and pagination.

    Filters:
    - page: Page number (1-indexed, default: 1)
    - page_size: Items per page (default: 50, max: 100)
    - state: Filter by statecode (0=Active, 1=Submitted, 2=Canceled, 3=Fulfilled, 4=Invoiced)
    - owner: Filter by owner ID
    """
    from apps.orders.models import SalesOrder
    from core.permissions import filter_by_ownership

    # Base queryset filtered by ownership (System Admin/Sales Manager see all)
    queryset = filter_by_ownership(SalesOrder.objects.all(), request.user)

    # Apply filters
    if state is not None:
        queryset = queryset.filter(statecode=state)
    if owner:
        queryset = queryset.filter(ownerid=owner)

    queryset = queryset.select_related('accountid', 'contactid', 'ownerid')
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
    """
    Create an order from a won quote.

    This automatically:
    - Validates quote is won
    - Copies all quote details to order
    - Links order to quote, opportunity, and customer
    """
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


@orders_router.post('/{order_id}/submit', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def submit_order(request: HttpRequest, order_id: UUID):
    """
    Submit order for processing.
    Changes state from Active to Submitted.
    """
    order = OrderService.submit_order(order_id, request.user)
    return order


@orders_router.post('/{order_id}/fulfill', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def fulfill_order(request: HttpRequest, order_id: UUID, payload: FulfillOrderDto):
    """
    Mark order as fulfilled.
    Sets datefulfilled and changes state to Fulfilled.
    """
    order = OrderService.fulfill_order(order_id, payload, request.user)
    return order


@orders_router.post('/{order_id}/cancel', response=SalesOrderSchema)
@require_permission(Permission.ORDER_UPDATE)
def cancel_order(request: HttpRequest, order_id: UUID):
    """
    Cancel an order.
    Cannot cancel fulfilled orders.
    """
    order = OrderService.cancel_order(order_id, request.user)
    return order


@orders_router.get('/stats/summary', response=OrderStatsSchema)
@require_permission(Permission.ORDER_READ)
def get_order_stats(request: HttpRequest):
    """Get statistics about orders."""
    stats = OrderService.get_order_stats(request.user)
    return stats
