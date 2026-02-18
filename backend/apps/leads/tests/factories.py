"""
Factory Boy factories for Lead model.

Provides test data generation for lead entities.
"""

import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from apps.leads.models import (
    Lead,
    LeadStateCode,
    LeadStatusCode,
    LeadQualityCode,
    LeadSourceCode,
)
from apps.users.tests.factories import SalespersonFactory


class LeadFactory(DjangoModelFactory):
    """Factory for creating Lead instances."""

    class Meta:
        model = Lead

    # Personal Information
    firstname = factory.Faker('first_name')
    lastname = factory.Faker('last_name')
    fullname = factory.LazyAttribute(
        lambda obj: f"{obj.firstname or ''} {obj.lastname}".strip()
    )

    # Contact Information
    emailaddress1 = factory.Faker('email')
    telephone1 = factory.Faker('phone_number')
    mobilephone = factory.Faker('phone_number')

    # Company Information
    companyname = factory.Faker('company')
    jobtitle = factory.Faker('job')

    # Lead Details
    subject = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=500)

    # Lead Classification
    leadqualitycode = LeadQualityCode.WARM
    leadsourcecode = LeadSourceCode.WEB

    # Estimated Value
    estimatedvalue = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('1000.00'),
        max_value=Decimal('100000.00')
    )

    # State/Status
    statecode = LeadStateCode.OPEN
    statuscode = LeadStatusCode.NEW

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class HotLeadFactory(LeadFactory):
    """Factory for creating hot quality leads."""

    leadqualitycode = LeadQualityCode.HOT
    estimatedvalue = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('50000.00'),
        max_value=Decimal('500000.00')
    )
    statuscode = LeadStatusCode.CONTACTED


class ColdLeadFactory(LeadFactory):
    """Factory for creating cold quality leads."""

    leadqualitycode = LeadQualityCode.COLD
    estimatedvalue = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('500.00'),
        max_value=Decimal('5000.00')
    )


class QualifiedLeadFactory(LeadFactory):
    """Factory for creating qualified leads."""

    statecode = LeadStateCode.QUALIFIED
    statuscode = LeadStatusCode.QUALIFIED
    leadqualitycode = LeadQualityCode.HOT


class DisqualifiedLeadFactory(LeadFactory):
    """Factory for creating disqualified leads."""

    statecode = LeadStateCode.DISQUALIFIED
    statuscode = factory.Iterator([
        LeadStatusCode.LOST,
        LeadStatusCode.CANNOT_CONTACT,
        LeadStatusCode.NO_LONGER_INTERESTED,
    ])
