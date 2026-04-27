"""Factory Boy factories for Proyeccion models."""

import factory
import uuid
from factory.django import DjangoModelFactory
from decimal import Decimal
from datetime import date, timedelta

from apps.proyeccion.models import (
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    CatalogSourceCode,
    EstimationProject,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
    UnitCostBreakdown,
    IndirectCostDetail,
    IndirectCostTemplate,
    OfferAlternative,
    ExternalCostItem,
    SupplyCatalogItem,
    EquipmentYield,
    WorkPlanEntry,
    WorkPlanEntryType,
    FamilyTemplateSet,
    FamilyTemplateItem,
    BreakdownCategoryCode,
    SupplyTypeCode,
    ProjectSizeCode,
    ProjectionPeriod,
    CostDistribution,
    CostLineType,
)
from apps.users.tests.factories import SalespersonFactory, SystemUserFactory


class ConceptPriceCatalogItemFactory(DjangoModelFactory):
    """Factory for creating ConceptPriceCatalogItem instances."""

    class Meta:
        model = ConceptPriceCatalogItem

    code = factory.Sequence(lambda n: f'HIST-{n + 1:05d}')
    description = factory.Faker('sentence', nb_words=12)
    unit = factory.Iterator(['m2', 'ml', 'pza', 'm3', 'kg', 'evento', 'salida'])
    source = CatalogSourceCode.HISTORICO
    category = ''
    averageprice = Decimal('0')
    minprice = Decimal('0')
    maxprice = Decimal('0')
    referencecount = 0
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class SICTCatalogItemFactory(ConceptPriceCatalogItemFactory):
    """Factory for SICT-sourced catalog items."""

    code = factory.Sequence(lambda n: f'SICT-{n + 1:05d}')
    source = CatalogSourceCode.SICT


class ManualCatalogItemFactory(ConceptPriceCatalogItemFactory):
    """Factory for manually-entered catalog items."""

    code = factory.Sequence(lambda n: f'MAN-{n + 1:05d}')
    source = CatalogSourceCode.MANUAL


class ConceptPriceReferenceFactory(DjangoModelFactory):
    """Factory for creating ConceptPriceReference instances."""

    class Meta:
        model = ConceptPriceReference

    catalogitemid = factory.SubFactory(ConceptPriceCatalogItemFactory)
    projectname = factory.Iterator([
        'Cumbres Elite', 'Swiss Lab Mty', 'Valle',
        'Polab Morelos', 'Jenner Texcoco', 'La Selva Tripp',
    ])
    projectlocation = ''
    unitprice = factory.Faker(
        'pydecimal', left_digits=5, right_digits=2, positive=True,
        min_value=50, max_value=50000,
    )
    quantity = factory.Faker(
        'pydecimal', left_digits=3, right_digits=2, positive=True,
        min_value=1, max_value=500,
    )
    totalamount = factory.LazyAttribute(
        lambda o: o.unitprice * o.quantity if o.quantity else None
    )
    notes = ''
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class EstimationProjectFactory(DjangoModelFactory):
    """Factory for creating EstimationProject instances."""

    class Meta:
        model = EstimationProject

    name = factory.Sequence(lambda n: f'Test Project {n + 1}')
    description = factory.Faker('sentence', nb_words=8)
    estimationnumber = factory.Sequence(lambda n: f'EST-2026-{n + 1:03d}')
    ownerid = factory.SubFactory(SystemUserFactory)
    createdby = factory.LazyAttribute(lambda o: o.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.ownerid)
    statecode = 0


class ConceptFamilyFactory(DjangoModelFactory):
    """Factory for creating ConceptFamily instances."""

    class Meta:
        model = ConceptFamily

    projectid = factory.SubFactory(EstimationProjectFactory)
    name = factory.Sequence(lambda n: f'Family {n + 1}')
    code = factory.Sequence(lambda n: f'F{n + 1:02d}')
    sortorder = factory.Sequence(lambda n: n)
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class ConceptSubfamilyFactory(DjangoModelFactory):
    """Factory for creating ConceptSubfamily instances."""

    class Meta:
        model = ConceptSubfamily

    familyid = factory.SubFactory(ConceptFamilyFactory)
    projectid = factory.LazyAttribute(lambda o: o.familyid.projectid)
    name = factory.Sequence(lambda n: f'Subfamily {n + 1}')
    code = factory.Sequence(lambda n: f'SF{n + 1:02d}')
    sortorder = factory.Sequence(lambda n: n)
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class BudgetConceptFactory(DjangoModelFactory):
    """Factory for creating BudgetConcept instances."""

    class Meta:
        model = BudgetConcept

    projectid = factory.LazyAttribute(lambda o: o.subfamilyid.projectid)
    subfamilyid = factory.SubFactory(ConceptSubfamilyFactory)
    code = factory.Sequence(lambda n: f'F01-SF01-{n + 1}')
    sequencenumber = factory.Sequence(lambda n: n + 1)
    description = factory.Sequence(lambda n: f'Test Concept {n + 1}')
    unit = 'm2'
    quantity = Decimal('100')
    directunitcost = Decimal('0')
    indirectunitcost = Decimal('0')
    utilityunitcost = Decimal('0')
    unitprice = Decimal('0')
    totalamount = Decimal('0')
    breakdownmethod = 0
    isprintable = True
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class UnitCostBreakdownFactory(DjangoModelFactory):
    """Factory for creating UnitCostBreakdown instances."""

    class Meta:
        model = UnitCostBreakdown

    conceptid = factory.SubFactory(BudgetConceptFactory)
    categorycode = BreakdownCategoryCode.MATERIALS
    linenumber = factory.Sequence(lambda n: n + 1)
    description = factory.Sequence(lambda n: f'Breakdown item {n + 1}')
    unit = 'kg'
    quantity = Decimal('10')
    unitprice = Decimal('50')
    yieldvalue = Decimal('1')
    amount = factory.LazyAttribute(lambda o: o.quantity * o.unitprice * o.yieldvalue)
    statecode = 0


class IndirectCostDetailFactory(DjangoModelFactory):
    """Factory for creating IndirectCostDetail instances."""

    class Meta:
        model = IndirectCostDetail

    projectid = factory.SubFactory(EstimationProjectFactory)
    categorycode = 'C1'
    linenumber = factory.Sequence(lambda n: n + 1)
    description = factory.Sequence(lambda n: f'Indirect cost {n + 1}')
    monthlycost = Decimal('5000')
    units = Decimal('1')
    months = Decimal('6')
    amount = factory.LazyAttribute(lambda o: o.monthlycost * o.units * o.months)
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class IndirectCostTemplateFactory(DjangoModelFactory):
    """Factory for creating IndirectCostTemplate instances."""

    class Meta:
        model = IndirectCostTemplate

    name = factory.Sequence(lambda n: f'Template {n + 1}')
    projectsize = ProjectSizeCode.MEDIUM
    categorycode = 'C1'
    description = factory.Sequence(lambda n: f'Template indirect cost {n + 1}')
    monthlycost = Decimal('3000')
    units = Decimal('1')
    months = Decimal('6')
    sortorder = factory.Sequence(lambda n: n)
    statecode = 0
    createdby = factory.SubFactory(SystemUserFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class OfferAlternativeFactory(DjangoModelFactory):
    """Factory for creating OfferAlternative instances."""

    class Meta:
        model = OfferAlternative

    projectid = factory.SubFactory(EstimationProjectFactory)
    alternativenumber = factory.Sequence(lambda n: n + 1)
    name = factory.Sequence(lambda n: f'Alternative {n + 1}')
    description = ''
    transversalpercent = Decimal('5')
    profitpercent = Decimal('10')
    coefficient = Decimal('1.15')
    directcosttotal = Decimal('100000')
    indirectcosttotal = Decimal('30000')
    constructioncost = Decimal('130000')
    salepricenet = Decimal('149500')
    taxamount = Decimal('23920')
    salepricetotal = Decimal('173420')
    ischosen = False
    statecode = 0
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class ExternalCostItemFactory(DjangoModelFactory):
    """Factory for creating ExternalCostItem instances."""

    class Meta:
        model = ExternalCostItem

    projectid = factory.SubFactory(EstimationProjectFactory)
    itemname = factory.Sequence(lambda n: f'External cost {n + 1}')
    applies = 0
    amount = Decimal('0')
    sortorder = factory.Sequence(lambda n: n + 1)
    statecode = 0


class SupplyCatalogItemFactory(DjangoModelFactory):
    """Factory for creating SupplyCatalogItem instances."""

    class Meta:
        model = SupplyCatalogItem

    code = factory.Sequence(lambda n: f'SUP-{n + 1:05d}')
    description = factory.Sequence(lambda n: f'Supply item {n + 1}')
    unit = 'kg'
    supplytype = SupplyTypeCode.MATERIAL
    referenceprice = Decimal('100')
    statecode = 0
    createdby = factory.SubFactory(SystemUserFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class EquipmentYieldFactory(DjangoModelFactory):
    """Factory for creating EquipmentYield instances."""

    class Meta:
        model = EquipmentYield

    category = 'Excavation'
    description = factory.Sequence(lambda n: f'Equipment {n + 1}')
    monthlycost = Decimal('50000')
    numberofequipment = 1
    theoreticalyield = Decimal('100')
    effectivehours = Decimal('8')
    realyield = Decimal('80')
    fuelconsumption = Decimal('15')
    dailyfuelconsumption = Decimal('120')
    effectivedays = Decimal('22')
    trafficfactor = Decimal('0.8')
    monthlycubicmeters = Decimal('14080')
    monthlydiesel = Decimal('2640')
    costpercubicmeter = Decimal('3.5511')
    statecode = 0
    createdby = factory.SubFactory(SystemUserFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class WorkPlanEntryFactory(DjangoModelFactory):
    """Factory for creating WorkPlanEntry instances."""

    class Meta:
        model = WorkPlanEntry

    conceptid = factory.SubFactory(BudgetConceptFactory)
    projectid = factory.LazyAttribute(lambda o: o.conceptid.projectid)
    periodnumber = factory.Sequence(lambda n: n + 1)
    periodlabel = factory.Sequence(lambda n: f'S{n + 1}')
    entrytype = WorkPlanEntryType.PLANNED
    distributedquantity = Decimal('10')
    distributedamount = Decimal('0')
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class FamilyTemplateSetFactory(DjangoModelFactory):
    """Factory for creating FamilyTemplateSet instances."""

    class Meta:
        model = FamilyTemplateSet

    name = factory.Sequence(lambda n: f'Template Set {n + 1}')
    description = factory.Faker('sentence', nb_words=6)
    category = 'custom'
    issystem = False
    statecode = 0
    createdby = factory.SubFactory(SystemUserFactory)
    modifiedby = factory.LazyAttribute(lambda o: o.createdby)


class FamilyTemplateItemFactory(DjangoModelFactory):
    """Factory for creating FamilyTemplateItem instances."""

    class Meta:
        model = FamilyTemplateItem

    templatesetid = factory.SubFactory(FamilyTemplateSetFactory)
    familycode = factory.Sequence(lambda n: f'F{n + 1:02d}')
    familyname = factory.Sequence(lambda n: f'Family {n + 1}')
    subfamilycode = factory.Sequence(lambda n: f'SF{n + 1:02d}')
    subfamilyname = factory.Sequence(lambda n: f'Subfamily {n + 1}')
    familysortorder = factory.Sequence(lambda n: n)
    subfamilysortorder = factory.Sequence(lambda n: n)
    statecode = 0


class ProjectionPeriodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectionPeriod

    projectid = factory.SubFactory(EstimationProjectFactory)
    periodnumber = factory.Sequence(lambda n: n + 1)
    periodlabel = factory.LazyAttribute(lambda o: f"P{o.periodnumber}")
    startdate = factory.LazyAttribute(lambda o: date(2026, 1, 1) + timedelta(days=15 * (o.periodnumber - 1)))
    enddate = factory.LazyAttribute(lambda o: o.startdate + timedelta(days=14))
    periodtype = 1
    createdby = factory.LazyAttribute(lambda o: o.projectid.ownerid)
    modifiedby = factory.LazyAttribute(lambda o: o.projectid.ownerid)


class CostDistributionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CostDistribution

    projectid = factory.SubFactory(EstimationProjectFactory)
    linetype = CostLineType.BREAKDOWN
    breakdownid = factory.SubFactory(UnitCostBreakdownFactory)
    indirectcostid = None
    periodnumber = 1
    fraction = Decimal("0.1")
    isderived = True

    @factory.post_generation
    def align_project(obj, create, extracted, **kwargs):
        """Ensure projectid matches the FK's project when specified."""
        if obj.breakdownid and obj.breakdownid.conceptid:
            obj.projectid = obj.breakdownid.conceptid.projectid
            obj.save()


class EstimationFinancialSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'proyeccion.EstimationFinancialSettings'

    settingsid = factory.LazyFunction(uuid.uuid4)
    projectid = factory.SubFactory(EstimationProjectFactory)
    advanceamountnotax = Decimal('0')
    advanceentryperiod = 1
    advanceamortizationrate = Decimal('0')
    imssretentionrate = Decimal('0.0500')
    otherretentionrate = Decimal('0')
    retentionreturnperiod = None
    directpaymentlag = 0
    indirectpaymentlag = 0
    financecostrate = Decimal('0.001000')


class EstimationBillingRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'proyeccion.EstimationBillingRule'

    ruleid = factory.LazyFunction(uuid.uuid4)
    projectid = factory.SubFactory(EstimationProjectFactory)
    sequence = factory.Sequence(lambda n: (n % 10) + 1)
    percent = Decimal('1.0000')
    lagperiods = 0


def build_pnt_ready_project(*, periods=4, periodtype=0):
    """Helper that wires an EstimationProject + N periods + 1 chosen alternative.

    Returns: (project, list[ProjectionPeriod])
    """
    from apps.proyeccion.models import (
        ProjectionPeriod, OfferAlternative, BudgetConcept,
        UnitCostBreakdown, IndirectCostDetail, CostDistribution, WorkPlanEntry,
    )
    from datetime import date, timedelta
    project = EstimationProjectFactory(periodtype=periodtype, periodcount=periods)
    period_list = []
    base = date(2026, 1, 1)
    for i in range(periods):
        offset = i * (7 if periodtype == 0 else 14)
        p = ProjectionPeriod.objects.create(
            projectid=project,
            periodnumber=i + 1,
            periodlabel=f'P{i + 1:02d}',
            startdate=base + timedelta(days=offset),
            enddate=base + timedelta(days=offset + (6 if periodtype == 0 else 13)),
            periodtype=periodtype,
        )
        period_list.append(p)
    OfferAlternative.objects.create(
        projectid=project, alternativenumber=1, name='Base',
        transversalpercent=Decimal('0.05'), profitpercent=Decimal('0.10'),
        coefficient=Decimal('1.15'),
        directcosttotal=Decimal('100000'), indirectcosttotal=Decimal('20000'),
        constructioncost=Decimal('120000'), salepricenet=Decimal('138000'),
        taxamount=Decimal('22080'), salepricetotal=Decimal('160080'),
        ischosen=True,
    )
    return project, period_list


def make_concept_for_project(project, code='C-001', description='Test', unit='m2'):
    """Helper: create a BudgetConcept attached to project with required relations."""
    family = ConceptFamilyFactory(projectid=project)
    subfamily = ConceptSubfamilyFactory(familyid=family, projectid=project)
    return BudgetConcept.objects.create(
        projectid=project,
        subfamilyid=subfamily,
        code=code,
        sequencenumber=1,
        description=description,
        unit=unit,
        quantity=Decimal('1'),
    )
