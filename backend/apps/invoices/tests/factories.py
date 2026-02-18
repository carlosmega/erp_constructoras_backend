"""
Factory Boy factories for Invoice models.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
from decimal import Decimal

from apps.invoices.models import Invoice, InvoiceDetail, InvoiceStateCode, InvoiceStatusCode
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory
from apps.orders.tests.factories import SalesOrderFactory, FulfilledOrderFactory
from apps.opportunities.tests.factories import OpportunityFactory

fake = Faker()


class InvoiceFactory(DjangoModelFactory):
    """Base factory for creating Invoice instances."""

    class Meta:
        model = Invoice

    name = factory.Faker('catch_phrase')
    invoicenumber = factory.Sequence(lambda n: f'INV-2024-{n:05d}')

    # Related entities
    salesorderid = factory.SubFactory(FulfilledOrderFactory)
    opportunityid = factory.LazyAttribute(lambda obj: obj.salesorderid.opportunityid if obj.salesorderid else None)
    accountid = factory.LazyAttribute(lambda obj: obj.salesorderid.accountid if obj.salesorderid else None)
    contactid = None

    # Financial fields (will be calculated from line items)
    totalamount = Decimal('0.00')
    totaldiscountamount = Decimal('0.00')
    totaltax = Decimal('0.00')
    totallineitemamount = Decimal('0.00')
    totalamountless = Decimal('0.00')

    # Payment tracking
    totalpaid = Decimal('0.00')
    totalamountdue = Decimal('0.00')

    # Dates
    datedelivered = factory.LazyFunction(lambda: date.today())
    duedate = factory.LazyFunction(
        lambda: date.today() + timedelta(days=30)
    )
    paidon = None

    # Status
    statecode = InvoiceStateCode.ACTIVE
    statuscode = InvoiceStatusCode.NEW

    description = factory.Faker('paragraph')

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)

    # Audit fields
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class InvoiceDetailFactory(DjangoModelFactory):
    """Factory for creating InvoiceDetail (line item) instances."""

    class Meta:
        model = InvoiceDetail

    invoiceid = factory.SubFactory(InvoiceFactory)

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


class PaidInvoiceFactory(InvoiceFactory):
    """Factory for paid invoices."""

    statecode = InvoiceStateCode.PAID
    statuscode = InvoiceStatusCode.COMPLETE
    totalpaid = factory.SelfAttribute('totalamount')
    totalamountdue = Decimal('0.00')
    paidon = factory.LazyFunction(lambda: date.today())


class PartiallyPaidInvoiceFactory(InvoiceFactory):
    """Factory for partially paid invoices."""

    statecode = InvoiceStateCode.ACTIVE
    statuscode = InvoiceStatusCode.PARTIAL

    # Set initial amounts that will be updated after line items are added
    totalamount = Decimal('1000.00')
    totallineitemamount = Decimal('1000.00')
    totalpaid = Decimal('500.00')
    totalamountdue = Decimal('500.00')

    @factory.post_generation
    def add_line_item(obj, create, extracted, **kwargs):
        """Add a line item to make the invoice have a real total."""
        if not create:
            return

        # Create a line item
        InvoiceDetailFactory(
            invoiceid=obj,
            quantity=Decimal('10.00'),
            priceperunit=Decimal('100.00')
        )

        # Recalculate totals
        obj.calculate_totals()

        # Set to 50% paid
        obj.totalpaid = obj.totalamount * Decimal('0.50')
        obj.totalamountdue = obj.totalamount - obj.totalpaid
        obj.save()


class CanceledInvoiceFactory(InvoiceFactory):
    """Factory for canceled invoices."""

    statecode = InvoiceStateCode.CANCELED
    statuscode = InvoiceStatusCode.CANCELED


class OverdueInvoiceFactory(InvoiceFactory):
    """Factory for overdue invoices."""

    statecode = InvoiceStateCode.ACTIVE
    statuscode = InvoiceStatusCode.NEW

    duedate = factory.LazyFunction(
        lambda: date.today() - timedelta(days=fake.random_int(min=1, max=60))
    )
    totalpaid = Decimal('0.00')
