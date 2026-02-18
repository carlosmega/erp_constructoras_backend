"""
Unit tests for Order services.

Tests OrderService business logic including order creation from quotes,
fulfillment, and state management.
"""

import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError

from apps.orders.models import SalesOrder, SalesOrderDetail, OrderStateCode, OrderStatusCode
from apps.orders.services import OrderService
from apps.orders.tests.factories import SalesOrderFactory, FulfilledOrderFactory
from apps.quotes.tests.factories import WonQuoteFactory, QuoteFactory, QuoteDetailFactory
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestGenerateOrderNumber:
    """Tests for OrderService.generate_order_number method."""

    def test_generate_order_number_first(self, db):
        """Test generating first order number of the year."""
        number = OrderService.generate_order_number()

        assert number.startswith('SO-2024-') or number.startswith('SO-2025-')
        assert len(number) == 12  # SO-YYYY-NNNN

    def test_generate_order_number_increments(self, db, salesperson):
        """Test order numbers increment."""
        SalesOrderFactory(ordernumber='SO-2024-0001', ownerid=salesperson)

        number = OrderService.generate_order_number()

        assert 'SO-2024-0002' in number or 'SO-2025-' in number


@pytest.mark.unit
@pytest.mark.workflow
class TestCreateOrderFromQuote:
    """Tests for OrderService.create_order_from_quote method."""

    def test_create_order_from_won_quote(self, db, salesperson):
        """Test creating order from won quote."""
        quote = WonQuoteFactory(ownerid=salesperson)
        QuoteDetailFactory(quoteid=quote, quantity=Decimal('10'), priceperunit=Decimal('100'))
        quote.calculate_totals()
        quote.save()

        order = OrderService.create_order_from_quote(quote.quoteid, salesperson)

        assert order.salesorderid is not None
        assert order.quoteid == quote
        assert order.totalamount == quote.totalamount
        assert order.statecode == OrderStateCode.ACTIVE

        # Verify line items were copied
        assert order.order_details.count() == 1

    def test_create_order_from_non_won_quote_fails(self, db, salesperson):
        """Test cannot create order from non-won quote."""
        quote = QuoteFactory(ownerid=salesperson)  # Draft quote

        with pytest.raises(ValidationError, match='Can only create order from won quotes'):
            OrderService.create_order_from_quote(quote.quoteid, salesperson)

    def test_create_order_from_quote_not_found(self, db, salesperson):
        """Test creating order from non-existent quote."""
        with pytest.raises(ValidationError, match='Quote not found'):
            OrderService.create_order_from_quote(uuid4(), salesperson)

    def test_create_order_duplicate_from_same_quote_fails(self, db, salesperson):
        """Test cannot create multiple orders from same quote."""
        quote = WonQuoteFactory(ownerid=salesperson)

        # Create first order
        OrderService.create_order_from_quote(quote.quoteid, salesperson)

        # Try to create second order
        with pytest.raises(ValidationError, match='Order already exists for this quote'):
            OrderService.create_order_from_quote(quote.quoteid, salesperson)


@pytest.mark.unit
class TestGetOrderById:
    """Tests for OrderService.get_order_by_id method."""

    def test_get_order_by_id_success(self, db, salesperson):
        """Test getting order by ID."""
        order = SalesOrderFactory(ownerid=salesperson)

        retrieved = OrderService.get_order_by_id(order.salesorderid, salesperson)

        assert retrieved.salesorderid == order.salesorderid

    def test_get_order_by_id_not_found(self, db, salesperson):
        """Test getting non-existent order."""
        with pytest.raises(ValidationError, match='Order not found'):
            OrderService.get_order_by_id(uuid4(), salesperson)


@pytest.mark.unit
class TestSubmitOrder:
    """Tests for OrderService.submit_order method."""

    def test_submit_order_success(self, db, salesperson):
        """Test submitting an order."""
        order = SalesOrderFactory(ownerid=salesperson, statecode=OrderStateCode.ACTIVE)

        submitted = OrderService.submit_order(order.salesorderid, salesperson)

        assert submitted.statecode == OrderStateCode.SUBMITTED
        assert submitted.statuscode == OrderStatusCode.PENDING

    def test_submit_order_already_submitted_fails(self, db, salesperson):
        """Test cannot submit already submitted order."""
        from apps.orders.tests.factories import SubmittedOrderFactory
        order = SubmittedOrderFactory(ownerid=salesperson)

        with pytest.raises(ValidationError, match='Can only submit active orders'):
            OrderService.submit_order(order.salesorderid, salesperson)


@pytest.mark.unit
@pytest.mark.workflow
class TestFulfillOrder:
    """Tests for OrderService.fulfill_order method."""

    def test_fulfill_order_success(self, db, salesperson):
        """Test fulfilling an order."""
        from apps.orders.tests.factories import SubmittedOrderFactory
        from apps.orders.schemas import FulfillOrderDto

        order = SubmittedOrderFactory(ownerid=salesperson)

        dto = FulfillOrderDto(notes='Order shipped to customer')
        fulfilled = OrderService.fulfill_order(order.salesorderid, dto, salesperson)

        assert fulfilled.statecode == OrderStateCode.FULFILLED
        assert fulfilled.statuscode == OrderStatusCode.COMPLETE
        assert fulfilled.datefulfilled is not None

    def test_fulfill_order_not_submitted_fails(self, db, salesperson):
        """Test cannot fulfill non-submitted order."""
        from apps.orders.schemas import FulfillOrderDto

        order = SalesOrderFactory(ownerid=salesperson, statecode=OrderStateCode.CANCELED)

        dto = FulfillOrderDto()

        with pytest.raises(ValidationError, match='Can only fulfill active or submitted orders'):
            OrderService.fulfill_order(order.salesorderid, dto, salesperson)


@pytest.mark.unit
class TestCancelOrder:
    """Tests for OrderService.cancel_order method."""

    def test_cancel_order_success(self, db, salesperson):
        """Test canceling an order."""
        order = SalesOrderFactory(ownerid=salesperson)

        canceled = OrderService.cancel_order(order.salesorderid, salesperson)

        assert canceled.statecode == OrderStateCode.CANCELED
        assert canceled.statuscode == OrderStatusCode.CANCELED

    def test_cancel_fulfilled_order_fails(self, db, salesperson):
        """Test cannot cancel fulfilled order."""
        order = FulfilledOrderFactory(ownerid=salesperson)

        with pytest.raises(ValidationError, match='Cannot cancel fulfilled orders'):
            OrderService.cancel_order(order.salesorderid, salesperson)
