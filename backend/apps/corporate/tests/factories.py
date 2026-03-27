"""Factory Boy factories for Corporate module models."""

import factory
from datetime import date
from decimal import Decimal
from factory.django import DjangoModelFactory
from apps.corporate.models import (
    CorporateBudget, CorporateBudgetVersion, CorporateBudgetLine,
    CorporateExpense, CorporateAllocation, CorporateAllocationLine,
    WhatIfSimulation,
    BudgetStateCode, BudgetVersionStateCode, ProrationMethodCode,
    AllocationStateCode, SimulationStateCode, CorporateExpenseCategoryCode,
)
from apps.users.tests.factories import SalespersonFactory, SystemAdminFactory


class CorporateBudgetFactory(DjangoModelFactory):
    class Meta:
        model = CorporateBudget

    fiscalyear = factory.Sequence(lambda n: 2026 + n)
    name = factory.LazyAttribute(lambda o: f'Presupuesto Corporativo {o.fiscalyear}')
    description = 'Test corporate budget'
    currency = 'MXN'
    totalbudget = Decimal('2400000.00')
    monthlypromedio = Decimal('200000.00')
    statecode = BudgetStateCode.DRAFT
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class ApprovedBudgetFactory(CorporateBudgetFactory):
    statecode = BudgetStateCode.APPROVED
    approvedby = factory.SelfAttribute('ownerid')
    approveddate = factory.LazyFunction(date.today)


class CorporateBudgetVersionFactory(DjangoModelFactory):
    class Meta:
        model = CorporateBudgetVersion

    corporatebudgetid = factory.SubFactory(CorporateBudgetFactory)
    versionnumber = factory.Sequence(lambda n: n + 1)
    label = factory.LazyAttribute(lambda o: f'V{o.versionnumber} - Test')
    statecode = BudgetVersionStateCode.ACTIVE
    createdby = factory.SelfAttribute('corporatebudgetid.ownerid')
    modifiedby = factory.SelfAttribute('corporatebudgetid.ownerid')


class CorporateBudgetLineFactory(DjangoModelFactory):
    class Meta:
        model = CorporateBudgetLine

    versionid = factory.SubFactory(CorporateBudgetVersionFactory)
    categorycode = CorporateExpenseCategoryCode.PERSONNEL
    categoryname = 'Personal Directivo y Administrativo'
    jan = Decimal('80000.00')
    feb = Decimal('80000.00')
    mar = Decimal('80000.00')
    apr = Decimal('80000.00')
    may = Decimal('80000.00')
    jun = Decimal('80000.00')
    jul = Decimal('80000.00')
    aug = Decimal('80000.00')
    sep = Decimal('80000.00')
    oct = Decimal('80000.00')
    nov = Decimal('80000.00')
    dec = Decimal('80000.00')
    annualamount = Decimal('960000.00')
    createdby = factory.SelfAttribute('versionid.corporatebudgetid.ownerid')
    modifiedby = factory.SelfAttribute('versionid.corporatebudgetid.ownerid')


class CorporateExpenseFactory(DjangoModelFactory):
    class Meta:
        model = CorporateExpense

    corporatebudgetid = factory.SubFactory(ApprovedBudgetFactory)
    categorycode = CorporateExpenseCategoryCode.PERSONNEL
    year = 2026
    month = 1
    budgetedamount = Decimal('80000.00')
    actualamount = Decimal('82000.00')
    variance = Decimal('2000.00')
    variancepercent = Decimal('2.50')
    statecode = 0
    createdby = factory.SelfAttribute('corporatebudgetid.ownerid')
    modifiedby = factory.SelfAttribute('corporatebudgetid.ownerid')


class CorporateAllocationFactory(DjangoModelFactory):
    class Meta:
        model = CorporateAllocation

    corporatebudgetid = factory.SubFactory(ApprovedBudgetFactory)
    year = 2026
    month = 1
    prorationmethod = ProrationMethodCode.DIRECT_COST
    totalamountallocated = Decimal('200000.00')
    unallocatedamount = Decimal('0.00')
    statecode = AllocationStateCode.DRAFT
    createdby = factory.SelfAttribute('corporatebudgetid.ownerid')
    modifiedby = factory.SelfAttribute('corporatebudgetid.ownerid')


class AppliedAllocationFactory(CorporateAllocationFactory):
    statecode = AllocationStateCode.APPLIED


class CorporateAllocationLineFactory(DjangoModelFactory):
    class Meta:
        model = CorporateAllocationLine

    allocationid = factory.SubFactory(CorporateAllocationFactory)
    projectid = factory.SubFactory('apps.projects.tests.factories.ActiveProjectFactory')
    prorationmethod = ProrationMethodCode.DIRECT_COST
    weightvalue = Decimal('1000000.0000')
    weightpercent = Decimal('50.0000')
    allocatedamount = Decimal('100000.00')
    createdby = factory.SelfAttribute('allocationid.corporatebudgetid.ownerid')
    modifiedby = factory.SelfAttribute('allocationid.corporatebudgetid.ownerid')


class WhatIfSimulationFactory(DjangoModelFactory):
    class Meta:
        model = WhatIfSimulation

    name = factory.Sequence(lambda n: f'Simulation {n + 1}')
    description = 'Test what-if simulation'
    fiscalyear = 2026
    corporatebudgetid = factory.SubFactory(ApprovedBudgetFactory)
    parameters = factory.LazyFunction(lambda: {
        'baseprojects': [],
        'hypotheticalprojects': [{'name': 'Test Project', 'directcost': 5000000, 'contractamount': 8000000, 'durationmonths': 12, 'startdate': '2026-01-01', 'enddate': '2026-12-31'}],
        'prorationmethod': 0,
    })
    results = factory.LazyFunction(dict)
    statecode = SimulationStateCode.ACTIVE
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')
