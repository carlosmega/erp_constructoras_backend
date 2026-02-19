"""
Order business logic services.

Phase 9 Implementation: Order Management
"""

from django.db import transaction
from core.exceptions import ValidationError, NotFound, PermissionDenied
from django.utils import timezone
from django.db.models import Sum, Count
from decimal import Decimal
from uuid import UUID

from apps.orders.models import SalesOrder, SalesOrderDetail, OrderStateCode, OrderStatusCode
from apps.orders.schemas import CreateSalesOrderDto, FulfillOrderDto
from apps.users.models import SystemUser
from core.permissions import can_modify_record


class OrderService:
    """Service class for SalesOrder operations."""

    @staticmethod
    def generate_order_number():
        """Generate unique order number (SO-YYYY-NNN)."""
        from datetime import date
        year = date.today().year

        last_order = SalesOrder.objects.filter(
            ordernumber__startswith=f'SO-{year}-'
        ).order_by('-ordernumber').first()

        if last_order:
            last_num = int(last_order.ordernumber.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1

        return f'SO-{year}-{next_num:04d}'

    @staticmethod
    @transaction.atomic
    def create_order_from_quote(quote_id: UUID, user: SystemUser) -> SalesOrder:
        """Create an order from a won quote."""
        from apps.quotes.models import Quote, QuoteStateCode

        try:
            quote = Quote.objects.prefetch_related('quote_details').get(quoteid=quote_id)
        except Quote.DoesNotExist:
            raise NotFound('Quote not found')

        # Verify quote is won
        if quote.statecode != QuoteStateCode.WON:
            raise ValidationError('Can only create order from won quotes')

        # Check if order already exists for this quote
        if SalesOrder.objects.filter(quoteid=quote).exists():
            raise ValidationError('Order already exists for this quote')

        # Generate order number
        ordernumber = OrderService.generate_order_number()

        # Create order from quote data
        order = SalesOrder.objects.create(
            name=quote.name,
            ordernumber=ordernumber,
            quoteid=quote,
            opportunityid=quote.opportunityid,
            accountid=quote.accountid,
            contactid=quote.contactid,
            totalamount=quote.totalamount,
            totaldiscountamount=quote.totaldiscountamount,
            totaltax=quote.totaltax,
            totallineitemamount=quote.totallineitemamount,
            description=f"Order created from quote {quote.quotenumber}",
            statecode=OrderStateCode.ACTIVE,
            statuscode=OrderStatusCode.NEW,
            ownerid=user,
            createdby=user,
            modifiedby=user
        )

        # Copy quote details to order details
        for quote_detail in quote.quote_details.all():
            SalesOrderDetail.objects.create(
                salesorderid=order,
                productname=quote_detail.productname,
                productdescription=quote_detail.productdescription,
                quantity=quote_detail.quantity,
                priceperunit=quote_detail.priceperunit,
                manualdiscountamount=quote_detail.manualdiscountamount,
                tax=quote_detail.tax,
                sequencenumber=quote_detail.sequencenumber
            )

        return order

    @staticmethod
    @transaction.atomic
    def create_order(dto: CreateSalesOrderDto, user: SystemUser) -> SalesOrder:
        """Create a new order manually."""
        ordernumber = OrderService.generate_order_number()

        # Get related entities if provided
        quote = None
        opportunity = None
        account = None
        contact = None

        if dto.quoteid:
            from apps.quotes.models import Quote
            try:
                quote = Quote.objects.get(quoteid=dto.quoteid)
                opportunity = quote.opportunityid
                account = quote.accountid
                contact = quote.contactid
            except Quote.DoesNotExist:
                raise NotFound('Quote not found')

        # Override with polymorphic customer if provided
        if dto.customerid and dto.customeridtype:
            from core.customers import resolve_customer
            account, contact = resolve_customer(dto.customerid, dto.customeridtype)

        # Create order
        order = SalesOrder.objects.create(
            name=dto.name,
            ordernumber=ordernumber,
            quoteid=quote,
            opportunityid=opportunity,
            accountid=account,
            contactid=contact,
            requestdeliveryby=dto.requestdeliveryby,
            description=dto.description,
            statecode=OrderStateCode.ACTIVE,
            statuscode=OrderStatusCode.NEW,
            ownerid=user,
            createdby=user,
            modifiedby=user
        )

        return order

    @staticmethod
    def get_order_by_id(order_id: UUID, user: SystemUser) -> SalesOrder:
        """Get order by ID with permission check."""
        try:
            order = SalesOrder.objects.select_related(
                'quoteid', 'opportunityid', 'accountid', 'contactid', 'ownerid'
            ).prefetch_related('order_details').get(salesorderid=order_id)
        except SalesOrder.DoesNotExist:
            raise NotFound('Order not found')

        # Permission check
        if not can_modify_record(user, order.ownerid):
            raise PermissionDenied('You do not have permission to view this order')

        return order

    @staticmethod
    @transaction.atomic
    def update_order(order_id: UUID, dto, user: SystemUser) -> SalesOrder:
        """Update order."""
        order = OrderService.get_order_by_id(order_id, user)

        # Cannot update fulfilled or canceled orders
        if order.statecode in [OrderStateCode.FULFILLED, OrderStateCode.CANCELED]:
            raise ValidationError('Cannot update fulfilled or canceled orders')

        # Update fields if provided
        if hasattr(dto, 'name') and dto.name is not None:
            order.name = dto.name
        if hasattr(dto, 'requestdeliveryby') and dto.requestdeliveryby is not None:
            order.requestdeliveryby = dto.requestdeliveryby
        if hasattr(dto, 'description') and dto.description is not None:
            order.description = dto.description

        order.modifiedby = user
        order.save()

        return order

    @staticmethod
    @transaction.atomic
    def fulfill_order(order_id: UUID, dto: FulfillOrderDto, user: SystemUser) -> SalesOrder:
        """Mark order as fulfilled."""
        order = OrderService.get_order_by_id(order_id, user)

        # Must be in active or submitted state
        if order.statecode not in [OrderStateCode.ACTIVE, OrderStateCode.SUBMITTED]:
            raise ValidationError('Can only fulfill active or submitted orders')

        # Set to fulfilled state
        order.statecode = OrderStateCode.FULFILLED
        order.statuscode = OrderStatusCode.COMPLETE
        order.datefulfilled = dto.datefulfilled or timezone.now()
        order.modifiedby = user
        order.save()

        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order_id: UUID, user: SystemUser) -> SalesOrder:
        """Cancel an order."""
        order = OrderService.get_order_by_id(order_id, user)

        # Cannot cancel fulfilled orders
        if order.statecode == OrderStateCode.FULFILLED:
            raise ValidationError('Cannot cancel fulfilled orders')

        order.statecode = OrderStateCode.CANCELED
        order.statuscode = OrderStatusCode.CANCELED
        order.modifiedby = user
        order.save()

        return order

    @staticmethod
    @transaction.atomic
    def submit_order(order_id: UUID, user: SystemUser) -> SalesOrder:
        """Submit order for processing."""
        order = OrderService.get_order_by_id(order_id, user)

        # Must be in active state
        if order.statecode != OrderStateCode.ACTIVE:
            raise ValidationError('Can only submit active orders')

        order.statecode = OrderStateCode.SUBMITTED
        order.statuscode = OrderStatusCode.PENDING
        order.modifiedby = user
        order.save()

        return order

    @staticmethod
    def get_order_stats(user: SystemUser):
        """Get statistics about orders."""
        from core.permissions import filter_by_ownership

        # Base queryset filtered by ownership (System Admin/Sales Manager see all)
        queryset = filter_by_ownership(SalesOrder.objects.all(), user)

        # Calculate stats
        total = queryset.count()
        active = queryset.filter(statecode=OrderStateCode.ACTIVE).count()
        submitted = queryset.filter(statecode=OrderStateCode.SUBMITTED).count()
        fulfilled = queryset.filter(statecode=OrderStateCode.FULFILLED).count()
        canceled = queryset.filter(statecode=OrderStateCode.CANCELED).count()

        total_value = queryset.aggregate(total=Sum('totalamount'))['total'] or Decimal('0')
        fulfilled_value = queryset.filter(statecode=OrderStateCode.FULFILLED).aggregate(
            total=Sum('totalamount')
        )['total'] or Decimal('0')

        return {
            'total_orders': total,
            'active_orders': active,
            'submitted_orders': submitted,
            'fulfilled_orders': fulfilled,
            'canceled_orders': canceled,
            'total_value': total_value,
            'fulfilled_value': fulfilled_value
        }
