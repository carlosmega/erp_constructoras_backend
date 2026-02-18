"""
Factory Boy factories for Quote models.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
from decimal import Decimal

from apps.quotes.models import Quote, QuoteDetail, QuoteStateCode, QuoteStatusCode
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory
from apps.opportunities.tests.factories import OpportunityFactory

fake = Faker()


class QuoteFactory(DjangoModelFactory):
    """Base factory for creating Quote instances."""

    class Meta:
        model = Quote

    name = factory.Faker('catch_phrase')
    quotenumber = factory.Sequence(lambda n: f'Q-2024-{n:05d}')

    # Related entities
    opportunityid = factory.SubFactory(OpportunityFactory)
    accountid = factory.LazyAttribute(lambda obj: obj.opportunityid.accountid if obj.opportunityid else None)
    contactid = None

    # Financial fields (will be calculated from line items)
    totalamount = Decimal('0.00')
    totaldiscountamount = Decimal('0.00')
    totaltax = Decimal('0.00')
    totallineitemamount = Decimal('0.00')

    discountpercentage = Decimal('0.00')

    # Dates
    effectivefrom = factory.LazyFunction(lambda: date.today())
    effectiveto = factory.LazyFunction(
        lambda: date.today() + timedelta(days=30)
    )
    closedon = None

    # Status
    statecode = QuoteStateCode.DRAFT
    statuscode = QuoteStatusCode.IN_PROGRESS

    description = factory.Faker('paragraph')

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)

    # Audit fields
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class QuoteDetailFactory(DjangoModelFactory):
    """Factory for creating QuoteDetail (line item) instances."""

    class Meta:
        model = QuoteDetail

    quoteid = factory.SubFactory(QuoteFactory)

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


class ActiveQuoteFactory(QuoteFactory):
    """Factory for active quotes."""

    statecode = QuoteStateCode.ACTIVE
    statuscode = QuoteStatusCode.IN_REVIEW


class WonQuoteFactory(QuoteFactory):
    """Factory for won quotes."""

    statecode = QuoteStateCode.WON
    statuscode = QuoteStatusCode.WON
    closedon = factory.LazyFunction(lambda: date.today())


class ClosedQuoteFactory(QuoteFactory):
    """Factory for closed (lost/canceled) quotes."""

    statecode = QuoteStateCode.CLOSED
    statuscode = factory.Iterator([
        QuoteStatusCode.LOST,
        QuoteStatusCode.CANCELED,
        QuoteStatusCode.REVISED
    ])
    closedon = factory.LazyFunction(lambda: date.today())


class QuoteWithDiscountFactory(QuoteFactory):
    """Factory for quotes with discount."""

    discountpercentage = factory.Faker(
        'pydecimal',
        left_digits=2,
        right_digits=2,
        positive=True,
        min_value=Decimal('5.00'),
        max_value=Decimal('20.00')
    )


class ExpiredQuoteFactory(QuoteFactory):
    """Factory for expired quotes."""

    statecode = QuoteStateCode.ACTIVE
    statuscode = QuoteStatusCode.IN_REVIEW
    effectivefrom = factory.LazyFunction(
        lambda: date.today() - timedelta(days=60)
    )
    effectiveto = factory.LazyFunction(
        lambda: date.today() - timedelta(days=1)
    )
