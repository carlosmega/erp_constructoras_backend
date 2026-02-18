"""
Factory Boy factories for Account model.

Provides test data generation for B2B company accounts.
"""

import factory
from factory.django import DjangoModelFactory
from apps.accounts.models import Account, AccountStateCode, AccountStatusCode
from apps.users.tests.factories import SalespersonFactory


class AccountFactory(DjangoModelFactory):
    """Factory for creating Account instances (B2B companies)."""

    class Meta:
        model = Account

    name = factory.Faker('company')
    accountnumber = factory.Sequence(lambda n: f'ACC{n:06d}')
    emailaddress1 = factory.Faker('company_email')
    telephone1 = factory.Faker('phone_number')
    websiteurl = factory.Faker('url')

    # Address
    address1_line1 = factory.Faker('street_address')
    address1_city = factory.Faker('city')
    address1_stateorprovince = factory.Faker('state')
    address1_postalcode = factory.Faker('postcode')
    address1_country = factory.Faker('country')

    # State/Status
    statecode = AccountStateCode.ACTIVE
    statuscode = AccountStatusCode.ACTIVE

    # Ownership
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class InactiveAccountFactory(AccountFactory):
    """Factory for creating inactive Account instances."""

    statecode = AccountStateCode.INACTIVE
    statuscode = AccountStatusCode.INACTIVE
