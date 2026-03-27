"""
Factory Boy factories for Graph (Microsoft integration) models.

Provides test data generation for MicrosoftToken and SSOToken.
"""

import secrets

import factory
from factory.django import DjangoModelFactory

from apps.graph.models import MicrosoftToken, SSOToken
from apps.users.tests.factories import SalespersonFactory


class MicrosoftTokenFactory(DjangoModelFactory):
    """Factory for creating MicrosoftToken instances."""

    class Meta:
        model = MicrosoftToken

    userid = factory.SubFactory(SalespersonFactory)
    microsoft_user_id = factory.Sequence(lambda n: f'azure-oid-{n:08d}')
    microsoft_email = factory.LazyAttribute(
        lambda obj: obj.userid.emailaddress1.replace('@crm.test', '@contoso.com')
    )
    token_cache = factory.LazyFunction(
        lambda: '{"AccessToken": {}, "RefreshToken": {}, "IdToken": {}}'
    )
    last_sync_on = None
    last_sync_count = 0


class SSOTokenFactory(DjangoModelFactory):
    """Factory for creating SSOToken instances."""

    class Meta:
        model = SSOToken

    userid = factory.SubFactory(SalespersonFactory)
    token = factory.LazyFunction(lambda: secrets.token_urlsafe(48))
