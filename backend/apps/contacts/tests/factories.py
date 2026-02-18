"""
Factory Boy factories for Contact model.

Provides test data generation for B2C individual contacts.
"""

import factory
from factory.django import DjangoModelFactory
from apps.contacts.models import Contact, ContactStateCode, ContactStatusCode
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory


class ContactFactory(DjangoModelFactory):
    """Factory for creating Contact instances (B2C individuals)."""

    class Meta:
        model = Contact

    firstname = factory.Faker('first_name')
    lastname = factory.Faker('last_name')
    fullname = factory.LazyAttribute(
        lambda obj: f"{obj.firstname or ''} {obj.lastname}".strip()
    )

    # Contact Information
    emailaddress1 = factory.Faker('email')
    telephone1 = factory.Faker('phone_number')
    mobilephone = factory.Faker('phone_number')

    # Business Information
    jobtitle = factory.Faker('job')
    parentcustomerid = None  # Optional company

    # Address
    address1_line1 = factory.Faker('street_address')
    address1_city = factory.Faker('city')
    address1_stateorprovince = factory.Faker('state')
    address1_postalcode = factory.Faker('postcode')
    address1_country = factory.Faker('country')

    # State/Status
    statecode = ContactStateCode.ACTIVE
    statuscode = ContactStatusCode.ACTIVE

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class ContactWithAccountFactory(ContactFactory):
    """Factory for creating Contact with parent Account (employee of company)."""

    parentcustomerid = factory.SubFactory(AccountFactory)
    jobtitle = factory.Faker('job')


class InactiveContactFactory(ContactFactory):
    """Factory for creating inactive Contact instances."""

    statecode = ContactStateCode.INACTIVE
    statuscode = ContactStatusCode.INACTIVE
