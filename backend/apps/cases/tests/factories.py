"""Factory Boy factories for Case model."""

import factory
from factory.django import DjangoModelFactory
from apps.cases.models import Case, CaseStateCode, CaseStatusCode
from apps.users.tests.factories import SalespersonFactory


class CaseFactory(DjangoModelFactory):
    class Meta:
        model = Case

    title = factory.Sequence(lambda n: f'Case {n}')
    ticketnumber = factory.Sequence(lambda n: f'CS-{n:06d}')
    statecode = CaseStateCode.ACTIVE
    statuscode = CaseStatusCode.IN_PROGRESS
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')
