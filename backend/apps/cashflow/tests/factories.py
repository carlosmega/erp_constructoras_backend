"""Factory Boy factories for cashflow models."""
import factory
from decimal import Decimal
from datetime import date
from factory.django import DjangoModelFactory

from apps.projects.tests.factories import ConstructionProjectFactory
from apps.projects.models import ProjectZone
from apps.budgets.models import (
    CostCategory, CostTypeCode, ImputationCode,
    ImputationPeriod, ImputationCodeBudget, PeriodTypeCode,
)


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


def build_simple_project_fixture(
    periods=3,
    produccion_per_period=1000,
    direct_cost_per_period=700,
    indirect_cost_per_period=100,
):
    """
    Build a project with:
      - N monthly periods
      - 1 direct imputation code (contractunitprice=10, plannedvolume/period=produccion_per_period/10)
      - 1 indirect imputation code
      - ImputationCodeBudget rows for every (code x period)
    Returns dict with project, periods, direct_code, indirect_code.
    """
    project = ConstructionProjectFactory()
    zone = ProjectZone.objects.create(
        projectid=project, name='Zone A', prefix='ZA',
        createdby=project.createdby, modifiedby=project.modifiedby,
    )
    direct_cat = CostCategory.objects.create(
        projectid=project, costtype=CostTypeCode.DIRECT, code='P4',
        name='Materiales', sortorder=4, defaultpaymentlag=0,
        createdby=project.createdby, modifiedby=project.modifiedby,
    )
    indirect_cat = CostCategory.objects.create(
        projectid=project, costtype=CostTypeCode.INDIRECT, code='C1',
        name='Personal', sortorder=11, defaultpaymentlag=0,
        createdby=project.createdby, modifiedby=project.modifiedby,
    )
    direct_code = ImputationCode.objects.create(
        projectid=project, categoryid=direct_cat, zoneid=zone,
        costtype=CostTypeCode.DIRECT, code='ZA-P4-1', sequencenumber=1,
        name='Direct line', contractunitprice=Decimal('10'), unitcost=Decimal('7'),
        createdby=project.createdby, modifiedby=project.modifiedby,
    )
    indirect_code = ImputationCode.objects.create(
        projectid=project, categoryid=indirect_cat, zoneid=None,
        costtype=CostTypeCode.INDIRECT, code='C1-1', sequencenumber=1,
        name='Indirect line', unitcost=Decimal('100'),
        createdby=project.createdby, modifiedby=project.modifiedby,
    )

    period_objs = []
    for i in range(periods):
        p = ImputationPeriod.objects.create(
            projectid=project, periodtype=PeriodTypeCode.WEEKLY,
            year=2026, month=(i % 12) + 1, periodnumber=i + 1,
            label=f'P{i+1}',
            startdate=date(2026, (i % 12) + 1, 1),
            enddate=date(2026, (i % 12) + 1, 28),
            sortorder=i,
            createdby=project.createdby, modifiedby=project.modifiedby,
        )
        period_objs.append(p)
        ImputationCodeBudget.objects.create(
            imputationcodeid=direct_code, periodid=p, periodlabel=p.label,
            plannedamount=Decimal(direct_cost_per_period),
            plannedvolume=Decimal(produccion_per_period) / Decimal('10'),
        )
        ImputationCodeBudget.objects.create(
            imputationcodeid=indirect_code, periodid=p, periodlabel=p.label,
            plannedamount=Decimal(indirect_cost_per_period),
            plannedvolume=Decimal('0'),
        )
    return {
        'project': project, 'periods': period_objs,
        'direct_code': direct_code, 'indirect_code': indirect_code,
    }
