"""Corporate headquarters budget, expense tracking, and project allocation models."""

import uuid
from django.db import models
from core.models import AuditMixin


# ============================================================================
# Enums
# ============================================================================

class BudgetPeriodCode(models.IntegerChoices):
    ANNUAL = 0, 'Anual'
    Q1 = 1, 'Q1 (Ene-Mar)'
    Q2 = 2, 'Q2 (Abr-Jun)'
    Q3 = 3, 'Q3 (Jul-Sep)'
    Q4 = 4, 'Q4 (Oct-Dic)'


class BudgetStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    APPROVED = 1, 'Approved'
    CLOSED = 2, 'Closed'


class BudgetVersionStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    SUPERSEDED = 1, 'Superseded'


class ProrationMethodCode(models.IntegerChoices):
    DIRECT_COST = 0, 'By Direct Cost %'
    CONTRACT_AMOUNT = 1, 'By Contract Amount %'
    DURATION = 2, 'By Duration %'
    MANUAL = 3, 'Manual %'
    HYBRID = 4, 'Hybrid'


class CorporateExpenseCategoryCode(models.TextChoices):
    PERSONNEL = '4.1', 'Personal Directivo y Administrativo'
    INFRASTRUCTURE = '4.2', 'Infraestructura de Oficina'
    TECHNOLOGY = '4.3', 'Equipamiento y Tecnología'
    VEHICLES = '4.4', 'Vehículos y Transporte'
    INSURANCE = '4.5', 'Seguros y Obligaciones'
    COMMERCIAL = '4.6', 'Desarrollo Comercial y Licitaciones'
    TRAINING = '4.7', 'Capacitación y Desarrollo'
    FINANCIAL = '4.8', 'Gastos Financieros'
    MISCELLANEOUS = '4.9', 'Varios / No Clasificados'


class AllocationStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    APPLIED = 1, 'Applied'
    REVERSED = 2, 'Reversed'


class SimulationStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    ARCHIVED = 1, 'Archived'


# ============================================================================
# Models
# ============================================================================

class CorporateBudget(AuditMixin):
    """Annual corporate headquarters budget."""

    corporatebudgetid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='corporatebudgetid'
    )

    fiscalyear = models.IntegerField(
        db_column='fiscalyear'
    )

    periodtype = models.IntegerField(
        choices=BudgetPeriodCode.choices,
        default=BudgetPeriodCode.ANNUAL,
        db_column='periodtype'
    )

    quarter = models.IntegerField(
        db_column='quarter',
        null=True,
        blank=True,
        help_text='Quarter number (1-4) when periodtype is quarterly'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    currency = models.CharField(
        max_length=3,
        default='MXN',
        db_column='currency'
    )

    totalbudget = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='totalbudget'
    )

    monthlypromedio = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='monthlypromedio'
    )

    statecode = models.IntegerField(
        choices=BudgetStateCode.choices,
        default=BudgetStateCode.DRAFT,
        db_column='statecode'
    )

    approvedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_corporate_budgets',
        db_column='approvedby'
    )

    approveddate = models.DateField(
        db_column='approveddate',
        null=True,
        blank=True
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_corporate_budgets',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'corporatebudget'
        ordering = ['-fiscalyear']
        unique_together = [('fiscalyear', 'periodtype', 'quarter')]
        indexes = [
            models.Index(fields=['fiscalyear']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"{self.name} ({self.fiscalyear})"


class CorporateBudgetVersion(AuditMixin):
    """Versioned snapshot of a corporate budget."""

    versionid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='versionid'
    )

    corporatebudgetid = models.ForeignKey(
        CorporateBudget,
        on_delete=models.CASCADE,
        db_column='corporatebudgetid',
        related_name='versions'
    )

    versionnumber = models.IntegerField(
        db_column='versionnumber'
    )

    label = models.CharField(
        max_length=100,
        db_column='label'
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    approveddate = models.DateField(
        db_column='approveddate',
        null=True,
        blank=True
    )

    statecode = models.IntegerField(
        choices=BudgetVersionStateCode.choices,
        default=BudgetVersionStateCode.ACTIVE,
        db_column='statecode'
    )

    class Meta:
        db_table = 'corporatebudgetversion'
        ordering = ['-versionnumber']
        unique_together = [('corporatebudgetid', 'versionnumber')]
        indexes = [
            models.Index(fields=['corporatebudgetid', 'statecode']),
        ]

    def __str__(self):
        return f"V{self.versionnumber} - {self.label}"


class CorporateBudgetLine(AuditMixin):
    """Budget amount per expense category per version (12 monthly columns)."""

    budgetlineid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='budgetlineid'
    )

    versionid = models.ForeignKey(
        CorporateBudgetVersion,
        on_delete=models.CASCADE,
        db_column='versionid',
        related_name='lines'
    )

    categorycode = models.CharField(
        max_length=5,
        choices=CorporateExpenseCategoryCode.choices,
        db_column='categorycode'
    )

    categoryname = models.CharField(
        max_length=200,
        db_column='categoryname'
    )

    # 12 monthly budget columns
    jan = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='jan')
    feb = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='feb')
    mar = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='mar')
    apr = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='apr')
    may = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='may')
    jun = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='jun')
    jul = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='jul')
    aug = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='aug')
    sep = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='sep')
    oct = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='oct')
    nov = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='nov')
    dec = models.DecimalField(max_digits=19, decimal_places=2, default=0, db_column='dec')

    annualamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='annualamount'
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'corporatebudgetline'
        ordering = ['categorycode']
        unique_together = [('versionid', 'categorycode')]
        indexes = [
            models.Index(fields=['versionid']),
        ]

    def __str__(self):
        return f"{self.categorycode} - {self.categoryname}"

    @property
    def monthlypromedio(self):
        total = sum([
            self.jan, self.feb, self.mar, self.apr, self.may, self.jun,
            self.jul, self.aug, self.sep, self.oct, self.nov, self.dec
        ])
        return total / 12


class CorporateExpense(AuditMixin):
    """DEPRECATED: Corporate expenses are now stored as ProjectExpense records
    with expensescope=CORPORATE. This model is kept for migration compatibility
    and will be removed in a future release. Do not write new code against it.
    """

    corporateexpenseid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='corporateexpenseid'
    )

    corporatebudgetid = models.ForeignKey(
        CorporateBudget,
        on_delete=models.PROTECT,
        db_column='corporatebudgetid',
        related_name='expenses'
    )

    categorycode = models.CharField(
        max_length=5,
        choices=CorporateExpenseCategoryCode.choices,
        db_column='categorycode'
    )

    year = models.IntegerField(
        db_column='year'
    )

    month = models.IntegerField(
        db_column='month'
    )

    budgetedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='budgetedamount'
    )

    actualamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='actualamount'
    )

    variance = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='variance'
    )

    variancepercent = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        db_column='variancepercent'
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    statecode = models.IntegerField(
        default=0,
        db_column='statecode'
    )

    class Meta:
        db_table = 'corporateexpense'
        ordering = ['year', 'month', 'categorycode']
        unique_together = [('corporatebudgetid', 'categorycode', 'year', 'month')]
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['corporatebudgetid', 'year']),
        ]

    def __str__(self):
        return f"{self.categorycode} - {self.year}/{self.month}"


class CorporateAllocation(AuditMixin):
    """A proration run distributing corporate costs to projects."""

    allocationid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='allocationid'
    )

    corporatebudgetid = models.ForeignKey(
        CorporateBudget,
        on_delete=models.PROTECT,
        db_column='corporatebudgetid',
        related_name='allocations'
    )

    year = models.IntegerField(
        db_column='year'
    )

    month = models.IntegerField(
        db_column='month'
    )

    prorationmethod = models.IntegerField(
        choices=ProrationMethodCode.choices,
        db_column='prorationmethod'
    )

    totalamountallocated = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='totalamountallocated'
    )

    unallocatedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='unallocatedamount'
    )

    statecode = models.IntegerField(
        choices=AllocationStateCode.choices,
        default=AllocationStateCode.DRAFT,
        db_column='statecode'
    )

    appliedon = models.DateTimeField(
        db_column='appliedon',
        null=True,
        blank=True
    )

    notes = models.TextField(
        db_column='notes',
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'corporateallocation'
        ordering = ['-year', '-month']
        unique_together = [('corporatebudgetid', 'year', 'month')]
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"Allocation {self.year}/{self.month} - {self.get_prorationmethod_display()}"


class CorporateAllocationLine(AuditMixin):
    """Per-project share of a corporate allocation."""

    allocationlineid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='allocationlineid'
    )

    allocationid = models.ForeignKey(
        CorporateAllocation,
        on_delete=models.CASCADE,
        db_column='allocationid',
        related_name='lines'
    )

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.PROTECT,
        db_column='projectid',
        related_name='corporate_allocations'
    )

    prorationmethod = models.IntegerField(
        choices=ProrationMethodCode.choices,
        db_column='prorationmethod'
    )

    weightvalue = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='weightvalue'
    )

    weightpercent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        db_column='weightpercent'
    )

    allocatedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='allocatedamount'
    )

    imputationcodeid = models.ForeignKey(
        'budgets.ImputationCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='imputationcodeid',
        related_name='corporate_allocation_lines'
    )

    class Meta:
        db_table = 'corporateallocationline'
        ordering = ['-allocatedamount']
        unique_together = [('allocationid', 'projectid')]
        indexes = [
            models.Index(fields=['projectid']),
        ]

    def __str__(self):
        return f"Project {self.projectid_id} - {self.weightpercent}%"


class WhatIfSimulation(AuditMixin):
    """Saved what-if scenario for corporate allocation impact analysis."""

    simulationid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='simulationid'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    fiscalyear = models.IntegerField(
        db_column='fiscalyear'
    )

    corporatebudgetid = models.ForeignKey(
        CorporateBudget,
        on_delete=models.PROTECT,
        db_column='corporatebudgetid',
        related_name='simulations',
        null=True,
        blank=True
    )

    parameters = models.JSONField(
        db_column='parameters',
        default=dict
    )

    results = models.JSONField(
        db_column='results',
        default=dict
    )

    statecode = models.IntegerField(
        choices=SimulationStateCode.choices,
        default=SimulationStateCode.ACTIVE,
        db_column='statecode'
    )

    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='owned_simulations',
        db_column='ownerid'
    )

    class Meta:
        db_table = 'whatifsimulation'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['fiscalyear']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return self.name
