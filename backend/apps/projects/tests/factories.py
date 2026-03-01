"""
Factory Boy factories for Construction Project models.

Provides test data generation for ConstructionProject, ProjectZone,
ProjectSupplier, and ProjectTeamMember entities.
"""

import factory
from datetime import date, timedelta
from decimal import Decimal
from factory.django import DjangoModelFactory
from apps.projects.models import (
    ConstructionProject, ProjectStateCode, ProjectTypeCode, BiddingTypeCode,
    PeriodTypeCode, ProjectRoleCode,
    ProjectTeamMember,
    ProjectZone, ZoneStateCode,
    ProjectSupplier, SupplierStateCode,
)
from apps.users.tests.factories import SalespersonFactory
from apps.accounts.tests.factories import AccountFactory


class ConstructionProjectFactory(DjangoModelFactory):
    """Factory for creating ConstructionProject instances."""

    class Meta:
        model = ConstructionProject

    projectnumber = factory.Sequence(lambda n: f'PRY-2026-{n + 1:03d}')
    name = factory.Faker('catch_phrase')
    description = factory.Faker('paragraph')
    statecode = ProjectStateCode.DRAFT
    accountid = factory.SubFactory(AccountFactory)
    opportunityid = None

    presentationdate = factory.LazyFunction(lambda: date.today() - timedelta(days=60))
    awarddate = factory.LazyFunction(lambda: date.today() - timedelta(days=30))
    startdate = factory.LazyFunction(date.today)
    contractenddate = factory.LazyFunction(lambda: date.today() + timedelta(days=365))
    expectedenddate = None
    durationmonths = 12

    projecttype = ProjectTypeCode.PRIVATE
    biddingtype = BiddingTypeCode.DIRECT_AWARD

    contractamount_notax = Decimal('1000000.00')
    contractamount_withtax = Decimal('1160000.00')
    advancepayment_notax = None
    advancepayment_withtax = None
    exchangerate_mxn_usd = None

    projectemail = None
    emailconfigured = False
    emailprotocol = None
    periodtype = PeriodTypeCode.WEEKLY

    alertthreshold_warning = None
    alertthreshold_critical = None
    alertthreshold_exceeded = None

    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class ActiveProjectFactory(ConstructionProjectFactory):
    """Factory for creating active projects."""
    statecode = ProjectStateCode.ACTIVE


class CompletedProjectFactory(ConstructionProjectFactory):
    """Factory for creating completed projects."""
    statecode = ProjectStateCode.COMPLETED


class ProjectTeamMemberFactory(DjangoModelFactory):
    """Factory for creating ProjectTeamMember instances."""

    class Meta:
        model = ProjectTeamMember

    projectid = factory.SubFactory(ConstructionProjectFactory)
    name = factory.Faker('name')
    role = ProjectRoleCode.SITE_ENGINEER
    phone = factory.Faker('phone_number')
    email = factory.Faker('email')
    createdby = factory.SelfAttribute('projectid.ownerid')
    modifiedby = factory.SelfAttribute('projectid.ownerid')


class ProjectZoneFactory(DjangoModelFactory):
    """Factory for creating ProjectZone instances."""

    class Meta:
        model = ProjectZone

    projectid = factory.SubFactory(ConstructionProjectFactory)
    name = factory.Faker('word')
    prefix = factory.Sequence(lambda n: f'Z{n:02d}'[:3])
    description = factory.Faker('sentence')
    statecode = ZoneStateCode.ACTIVE
    sortorder = factory.Sequence(lambda n: n + 1)
    createdby = factory.SelfAttribute('projectid.ownerid')
    modifiedby = factory.SelfAttribute('projectid.ownerid')


class ProjectSupplierFactory(DjangoModelFactory):
    """Factory for creating ProjectSupplier instances."""

    class Meta:
        model = ProjectSupplier

    projectid = factory.SubFactory(ConstructionProjectFactory)
    accountid = factory.SubFactory(AccountFactory)
    suppliernumber = factory.Sequence(lambda n: n + 1)
    rfc = factory.Sequence(lambda n: f'RFC{n:010d}')
    businessname = factory.Faker('company')
    statecode = SupplierStateCode.ACTIVE
    notes = None
    createdby = factory.SelfAttribute('projectid.ownerid')
    modifiedby = factory.SelfAttribute('projectid.ownerid')
