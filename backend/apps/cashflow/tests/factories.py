"""Factory Boy factories for cashflow models."""
import factory
from decimal import Decimal
from factory.django import DjangoModelFactory

from apps.projects.tests.factories import ConstructionProjectFactory


class ProjectFinancialSettingsFactory(DjangoModelFactory):
    class Meta:
        model = 'cashflow.ProjectFinancialSettings'

    projectid = factory.SubFactory(ConstructionProjectFactory)
    imssretentionrate = Decimal('0.0500')
    otherretentionrate = Decimal('0.0000')
    retentionreturnperiod = None
    advanceamortizationrate = Decimal('0.0000')
    anticipoentryperiod = 1
    transversalcost = Decimal('0.00')
    transversalwithdrawalperiod = 1
    utilitycost = Decimal('0.00')
    utilitywithdrawalperiod = 1
    financecostrate = Decimal('0.001000')


class ProjectBillingRuleFactory(DjangoModelFactory):
    class Meta:
        model = 'cashflow.ProjectBillingRule'

    projectid = factory.SubFactory(ConstructionProjectFactory)
    sequence = factory.Sequence(lambda n: (n % 10) + 1)
    percent = Decimal('1.0000')
    lagperiods = 0
