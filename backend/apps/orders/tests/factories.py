"""
Factory Boy factories for Order models.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
from decimal import Decimal

from apps.orders.models import SalesOrder, SalesOrderDetail, OrderStateCode, OrderStatusCode
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory
from apps.quotes.tests.factories import QuoteFactory, WonQuoteFactory
from apps.opportunities.tests.factories import OpportunityFactory

fake = Faker()


class SalesOrderFactory(DjangoModelFactory):
    """Base factory for creating SalesOrder instances."""

    class Meta:
        model = SalesOrder

    name = factory.Faker('catch_phrase')
    ordernumber = factory.Sequence(lambda n: f'SO-2024-{n:05d}')

    # Related entities
    quoteid = factory.SubFactory(WonQuoteFactory)
    opportunityid = factory.LazyAttribute(lambda obj: obj.quoteid.opportunityid if obj.quoteid else None)
    accountid = factory.LazyAttribute(lambda obj: obj.quoteid.accountid if obj.quoteid else None)
    contactid = None

    # Financial fields (will be calculated from line items)
    totalamount = Decimal('0.00')
    totaldiscountamount = Decimal('0.00')
    totaltax = Decimal('0.00')
    totallineitemamount = Decimal('0.00')

    # Dates
    requestdeliveryby = factory.LazyFunction(
        lambda: date.today() + timedelta(days=fake.random_int(min=7, max=30))
    )
    datefulfilled = None

    # Status
    statecode = OrderStateCode.ACTIVE
    statuscode = OrderStatusCode.NEW

    description = factory.Faker('paragraph')

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)

    # Audit fields
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class SalesOrderDetailFactory(DjangoModelFactory):
    """Factory for creating SalesOrderDetail (line item) instances."""

    class Meta:
        model = SalesOrderDetail

    salesorderid = factory.SubFactory(SalesOrderFactory)

    productname = factory.Faker('word')
    productdescription = factory.Faker('sentence')

    quantity = factory.Faker(
        'pydecimal',
        left_digits=3,
        right_digits=2,
        positive=True,
        min_value=Decimal('1.00'),
        max_value=Decimal('100.00')
    )
    priceperunit = factory.Faker(
        'pydecimal',
        left_digits=4,
        right_digits=2,
        positive=True,
        min_value=Decimal('10.00'),
        max_value=Decimal('5000.00')
    )
    manualdiscountamount = Decimal('0.00')
    tax = Decimal('0.00')

    # These will be auto-calculated on save
    baseamount = Decimal('0.00')
    extendedamount = Decimal('0.00')

    sequencenumber = factory.Sequence(lambda n: n + 1)


class SubmittedOrderFactory(SalesOrderFactory):
    """Factory for submitted orders."""

    statecode = OrderStateCode.SUBMITTED
    statuscode = OrderStatusCode.IN_PROGRESS


class FulfilledOrderFactory(SalesOrderFactory):
    """Factory for fulfilled orders."""

    statecode = OrderStateCode.FULFILLED
    statuscode = OrderStatusCode.COMPLETE
    datefulfilled = factory.LazyFunction(lambda: date.today())


class CanceledOrderFactory(SalesOrderFactory):
    """Factory for canceled orders."""

    statecode = OrderStateCode.CANCELED
    statuscode = OrderStatusCode.CANCELED


class InvoicedOrderFactory(SalesOrderFactory):
    """Factory for invoiced orders."""

    statecode = OrderStateCode.INVOICED
    statuscode = OrderStatusCode.COMPLETE
    datefulfilled = factory.LazyFunction(lambda: date.today())


class PendingOrderFactory(SalesOrderFactory):
    """Factory for pending orders."""

    statecode = OrderStateCode.ACTIVE
    statuscode = OrderStatusCode.PENDING
