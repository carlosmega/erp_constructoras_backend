"""Factory Boy factories for Budget models."""

import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from datetime import date

from apps.budgets.models import (
    CostCategory,
    CostTypeCode,
    ImputationCode,
    PersonnelTypeCode,
    ImputationPeriod,
    PeriodTypeCode,
)
from apps.users.tests.factories import SalespersonFactory


class CostCategoryFactory(DjangoModelFactory):
    """Factory for creating CostCategory instances (direct by default)."""

    class Meta:
        model = CostCategory

    projectid = factory.LazyFunction(lambda: _get_or_create_project())
    costtype = CostTypeCode.DIRECT
    code = factory.Sequence(lambda n: f'P{n + 1}')
    name = factory.Faker('catch_phrase')
    sortorder = factory.Sequence(lambda n: n + 1)
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class IndirectCostCategoryFactory(CostCategoryFactory):
    """Factory for creating indirect cost categories."""

    costtype = CostTypeCode.INDIRECT
    code = factory.Sequence(lambda n: f'C{n + 1}')


class ImputationCodeFactory(DjangoModelFactory):
    """Factory for creating ImputationCode instances (direct by default)."""

    class Meta:
        model = ImputationCode

    projectid = factory.LazyAttribute(lambda obj: obj.categoryid.projectid)
    categoryid = factory.SubFactory(CostCategoryFactory)
    zoneid = factory.LazyFunction(lambda: _get_or_create_zone())
    costtype = CostTypeCode.DIRECT
    code = factory.Sequence(lambda n: f'TAM-P1-{n + 1}')
    sequencenumber = factory.Sequence(lambda n: n + 1)
    name = factory.Faker('catch_phrase')
    totalbudget = factory.Faker(
        'pydecimal',
        left_digits=6,
        right_digits=2,
        positive=True,
        min_value=Decimal('1000.00'),
        max_value=Decimal('100000.00'),
    )
    totalspent = Decimal('0')
    remainingbudget = factory.LazyAttribute(lambda obj: obj.totalbudget)
    percentused = Decimal('0')
    statecode = 0
    createdby = factory.LazyAttribute(lambda obj: obj.categoryid.createdby)
    modifiedby = factory.SelfAttribute('createdby')


class IndirectImputationCodeFactory(ImputationCodeFactory):
    """Factory for creating indirect imputation codes."""

    categoryid = factory.SubFactory(IndirectCostCategoryFactory)
    zoneid = None
    costtype = CostTypeCode.INDIRECT
    code = factory.Sequence(lambda n: f'C1-{n + 1}')


class ImputationPeriodFactory(DjangoModelFactory):
    """Factory for creating ImputationPeriod instances."""

    class Meta:
        model = ImputationPeriod

    projectid = factory.LazyFunction(lambda: _get_or_create_project())
    periodtype = PeriodTypeCode.FORTNIGHTLY
    year = 2026
    month = 1
    periodnumber = factory.Sequence(lambda n: (n % 2) + 1)
    label = factory.LazyAttribute(
        lambda obj: f"ENE {obj.year} Q{obj.periodnumber}"
    )
    startdate = factory.LazyAttribute(
        lambda obj: date(obj.year, obj.month, 1) if obj.periodnumber == 1
        else date(obj.year, obj.month, 16)
    )
    enddate = factory.LazyAttribute(
        lambda obj: date(obj.year, obj.month, 15) if obj.periodnumber == 1
        else date(obj.year, obj.month, 31)
    )
    sortorder = factory.Sequence(lambda n: n + 1)
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


def _get_or_create_project():
    """Helper to get or create a ConstructionProject for factory use."""
    from apps.projects.tests.factories import ConstructionProjectFactory

    from apps.projects.models import ConstructionProject
    project = ConstructionProject.objects.first()
    if project:
        return project

    return ConstructionProjectFactory()


def _get_or_create_zone():
    """Helper to get or create a ProjectZone for factory use."""
    from apps.projects.models import ProjectZone

    zone = ProjectZone.objects.first()
    if zone:
        return zone

    project = _get_or_create_project()
    zone = ProjectZone(
        projectid=project,
        name='Tampico',
        prefix='TAM',
        createdby=project.createdby,
        modifiedby=project.createdby,
    )
    zone.save()
    return zone
