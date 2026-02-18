"""
Factory Boy factories for Opportunity models.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
from decimal import Decimal

from apps.opportunities.models import (
    Opportunity,
    OpportunityStateCode,
    OpportunityStatusCode,
    SalesStage,
)
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory
from apps.leads.tests.factories import LeadFactory

fake = Faker()


class OpportunityFactory(DjangoModelFactory):
    """Base factory for creating Opportunity instances."""

    class Meta:
        model = Opportunity

    name = factory.Faker('catch_phrase')
    description = factory.Faker('paragraph')
    customername = factory.Faker('company')

    # Default to Account customer (B2B)
    accountid = factory.SubFactory(AccountFactory)
    contactid = None

    estimatedrevenue = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('1000.00'),
        max_value=Decimal('500000.00')
    )

    actualrevenue = None

    estimatedclosedate = factory.LazyFunction(
        lambda: date.today() + timedelta(days=fake.random_int(min=30, max=90))
    )
    actualclosedate = None

    statecode = OpportunityStateCode.OPEN
    statuscode = OpportunityStatusCode.IN_PROGRESS
    salesstage = SalesStage.QUALIFY
    probability = factory.Faker('random_int', min=10, max=50)

    # Link to originating lead (optional)
    originatingleadid = factory.SubFactory(LeadFactory)

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)

    # Audit fields
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class HighValueOpportunityFactory(OpportunityFactory):
    """Factory for high-value opportunities (>$100k)."""

    estimatedrevenue = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('100000.00'),
        max_value=Decimal('1000000.00')
    )
    salesstage = SalesStage.PROPOSE
    probability = factory.Faker('random_int', min=60, max=90)


class LowValueOpportunityFactory(OpportunityFactory):
    """Factory for low-value opportunities (<$10k)."""

    estimatedrevenue = factory.Faker(
        'pydecimal',
        left_digits=4,
        right_digits=2,
        positive=True,
        min_value=Decimal('500.00'),
        max_value=Decimal('10000.00')
    )
    salesstage = SalesStage.DEVELOP
    probability = factory.Faker('random_int', min=20, max=40)


class WonOpportunityFactory(OpportunityFactory):
    """Factory for won opportunities."""

    statecode = OpportunityStateCode.WON
    statuscode = OpportunityStatusCode.WON
    salesstage = SalesStage.CLOSE
    probability = 100

    actualrevenue = factory.SelfAttribute('estimatedrevenue')
    actualclosedate = factory.LazyFunction(lambda: date.today())


class LostOpportunityFactory(OpportunityFactory):
    """Factory for lost opportunities."""

    statecode = OpportunityStateCode.LOST
    statuscode = factory.Iterator([
        OpportunityStatusCode.CANCELED,
        OpportunityStatusCode.OUT_SOLD
    ])
    salesstage = SalesStage.CLOSE
    probability = 0

    actualrevenue = Decimal('0.00')
    actualclosedate = factory.LazyFunction(lambda: date.today())


class DevelopStageOpportunityFactory(OpportunityFactory):
    """Factory for opportunities in Develop stage."""

    salesstage = SalesStage.DEVELOP
    probability = factory.Faker('random_int', min=30, max=60)


class ProposeStageOpportunityFactory(OpportunityFactory):
    """Factory for opportunities in Propose stage."""

    salesstage = SalesStage.PROPOSE
    probability = factory.Faker('random_int', min=50, max=75)


class CloseStageOpportunityFactory(OpportunityFactory):
    """Factory for opportunities in Close stage (still open)."""

    salesstage = SalesStage.CLOSE
    probability = factory.Faker('random_int', min=70, max=95)
    statuscode = OpportunityStatusCode.IN_PROGRESS
