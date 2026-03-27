"""Factories for audit test data."""

import uuid
import factory
from apps.audit.models import AuditLog, AuditActionCode


class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    auditid = factory.LazyFunction(uuid.uuid4)
    action = AuditActionCode.CREATE
    entity = 'lead'
    recordid = factory.LazyFunction(uuid.uuid4)
    recordname = factory.Faker('name')
    username = factory.Faker('name')
    message = factory.Faker('sentence')
