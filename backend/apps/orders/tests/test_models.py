"""
Unit tests for Order models.

Tests SalesOrder and SalesOrderDetail entities including state management,
validation, computed properties, and business rules.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.orders.models import (
    SalesOrder,
    SalesOrderDetail,
    OrderStateCode,
    OrderStatusCode,
)
from apps.orders.tests.factories import (
    SalesOrderFactory,
    SalesOrderDetailFactory,
    SubmittedOrderFactory,
    FulfilledOrderFactory,
    CanceledOrderFactory,
    InvoicedOrderFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestOrderEnums:
    """Tests for Order enum definitions."""

    def test_order_state_code_values(self):
        """Test OrderStateCode enum values."""
        assert OrderStateCode.ACTIVE.value == 0
        assert OrderStateCode.SUBMITTED.value == 1
        assert OrderStateCode.CANCELED.value == 2
        assert OrderStateCode.FULFILLED.value == 3
        assert OrderStateCode.INVOICED.value == 4

    def test_order_status_code_values(self):
        """Test OrderStatusCode enum values."""
        assert OrderStatusCode.NEW.value == 1
        assert OrderStatusCode.PENDING.value == 2
        assert OrderStatusCode.IN_PROGRESS.value == 3
        assert OrderStatusCode.COMPLETE.value == 5


@pytest.mark.unit
class TestSalesOrderModel:
    """Tests for SalesOrder model creation and basic operations."""

    def test_create_order_minimal(self, db):
        """Test creating order with minimal required fields."""
        owner = SalespersonFactory()

        order = SalesOrder.objects.create(
            name='Test Order',
            ordernumber='SO-2024-001',
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert order.salesorderid is not None
        assert order.name == 'Test Order'
        assert order.statecode == OrderStateCode.ACTIVE
        assert order.totalamount == Decimal('0.00')

    def test_order_factory(self, db):
        """Test SalesOrderFactory creates valid orders."""
        order = SalesOrderFactory()

        assert order.salesorderid is not None
        assert order.ordernumber is not None
        assert order.ownerid is not None

    def test_order_str_representation(self, db):
        """Test __str__ method."""
        order = SalesOrderFactory(ordernumber='SO-2024-001', name='Test Order')

        assert 'SO-2024-001' in str(order)
        assert 'Test Order' in str(order)


@pytest.mark.unit
class TestOrderProperties:
    """Tests for Order computed properties."""

    def test_customer_name_property_from_account(self, db, salesperson):
        """Test customer_name property from account."""
        from apps.accounts.models import Account
        account = Account.objects.create(name='Acme Corp', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        order = SalesOrderFactory(accountid=account, contactid=None, ownerid=salesperson)

        assert order.customer_name == 'Acme Corp'

    def test_customer_name_property_none(self, db):
        """Test customer_name property returns None."""
        order = SalesOrderFactory(accountid=None, contactid=None)

        assert order.customer_name is None


@pytest.mark.unit
class TestSalesOrderDetail:
    """Tests for SalesOrderDetail model."""

    def test_create_order_detail(self, db):
        """Test creating order detail."""
        order = SalesOrderFactory()

        detail = SalesOrderDetail.objects.create(
            salesorderid=order,
            productname='Test Product',
            quantity=Decimal('5.00'),
            priceperunit=Decimal('100.00'),
        )

        # Auto-calculated on save
        assert detail.baseamount == Decimal('500.00')
        assert detail.extendedamount == Decimal('500.00')

    def test_order_detail_with_discount(self, db):
        """Test order detail with manual discount."""
        order = SalesOrderFactory()

        detail = SalesOrderDetail.objects.create(
            salesorderid=order,
            productname='Test Product',
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00'),
            manualdiscountamount=Decimal('50.00'),
        )

        # 10*100 = 1000, minus 50 = 950
        assert detail.baseamount == Decimal('1000.00')
        assert detail.extendedamount == Decimal('950.00')


@pytest.mark.unit
class TestOrderFactories:
    """Tests for Order factories."""

    def test_submitted_order_factory(self, db):
        """Test SubmittedOrderFactory creates submitted orders."""
        order = SubmittedOrderFactory()

        assert order.statecode == OrderStateCode.SUBMITTED
        assert order.statuscode == OrderStatusCode.IN_PROGRESS

    def test_fulfilled_order_factory(self, db):
        """Test FulfilledOrderFactory creates fulfilled orders."""
        order = FulfilledOrderFactory()

        assert order.statecode == OrderStateCode.FULFILLED
        assert order.statuscode == OrderStatusCode.COMPLETE
        assert order.datefulfilled is not None

    def test_canceled_order_factory(self, db):
        """Test CanceledOrderFactory creates canceled orders."""
        order = CanceledOrderFactory()

        assert order.statecode == OrderStateCode.CANCELED
        assert order.statuscode == OrderStatusCode.CANCELED

    def test_invoiced_order_factory(self, db):
        """Test InvoicedOrderFactory creates invoiced orders."""
        order = InvoicedOrderFactory()

        assert order.statecode == OrderStateCode.INVOICED
        assert order.statuscode == OrderStatusCode.COMPLETE
