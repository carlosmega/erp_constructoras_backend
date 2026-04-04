"""Budget and cost structure models for construction projects."""

import uuid
from django.db import models
from core.models import AuditMixin


class CostTypeCode(models.IntegerChoices):
    """Cost type classification."""
    DIRECT = 0, 'Direct'
    INDIRECT = 1, 'Indirect'


class PersonnelTypeCode(models.IntegerChoices):
    """Personnel type for C1 category imputation codes."""
    OFFICE_STAFF = 0, 'Office Staff'
    FIELD_STAFF = 1, 'Field Staff'


class PeriodTypeCode(models.IntegerChoices):
    """Period type for imputation periods."""
    WEEKLY = 0, 'Weekly'
    FORTNIGHTLY = 1, 'Fortnightly'


class CostCategory(AuditMixin):
    """Cost category for a construction project budget."""

    categoryid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='categoryid'
    )

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='cost_categories'
    )

    costtype = models.IntegerField(
        choices=CostTypeCode.choices,
        db_column='costtype'
    )

    code = models.CharField(
        max_length=5,
        db_column='code'
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

    statecode = models.IntegerField(
        default=0,
        db_column='statecode'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    class Meta:
        db_table = 'costcategory'
        ordering = ['sortorder', 'code']
        unique_together = [('projectid', 'code')]
        indexes = [
            models.Index(fields=['projectid', 'costtype']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ImputationCode(AuditMixin):
    """Imputation code (budget line item) for tracking costs."""

    imputationcodeid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='imputationcodeid'
    )

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='imputation_codes'
    )

    categoryid = models.ForeignKey(
        CostCategory,
        on_delete=models.PROTECT,
        db_column='categoryid',
        related_name='imputation_codes'
    )

    zoneid = models.ForeignKey(
        'projects.ProjectZone',
        on_delete=models.PROTECT,
        db_column='zoneid',
        null=True,
        blank=True,
        related_name='imputation_codes'
    )

    costtype = models.IntegerField(
        choices=CostTypeCode.choices,
        db_column='costtype'
    )

    code = models.CharField(
        max_length=20,
        db_column='code'
    )

    sequencenumber = models.IntegerField(
        db_column='sequencenumber'
    )

    name = models.CharField(
        max_length=300,
        db_column='name'
    )

    description = models.TextField(
        db_column='description',
        blank=True,
        null=True
    )

    unit = models.CharField(
        max_length=20,
        db_column='unit',
        blank=True,
        null=True,
        help_text='Unit of measurement (PZA, m3, ml, etc.)'
    )

    contractcode = models.CharField(
        max_length=20,
        db_column='contractcode',
        blank=True,
        null=True,
        help_text='Original concept code from estimation (A1, A2, B1, etc.)'
    )

    contractunitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        db_column='contractunitprice',
        blank=True,
        null=True,
        help_text='Client unit price from contract/estimation'
    )

    sourceconceptid = models.ForeignKey(
        'proyeccion.BudgetConcept',
        on_delete=models.SET_NULL,
        db_column='sourceconceptid',
        related_name='generated_codes',
        blank=True,
        null=True,
        help_text='Original BudgetConcept from estimation'
    )

    estimatedsupplier = models.CharField(
        max_length=200,
        db_column='estimatedsupplier',
        blank=True,
        null=True
    )

    unitcost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='unitcost',
        blank=True,
        null=True
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        db_column='quantity',
        blank=True,
        null=True
    )

    executionmonths = models.IntegerField(
        db_column='executionmonths',
        blank=True,
        null=True
    )

    totalbudget = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='totalbudget'
    )

    # Personnel fields (C1 category only)
    personnelname = models.CharField(
        max_length=200,
        db_column='personnelname',
        blank=True,
        null=True
    )

    personnelrole = models.CharField(
        max_length=100,
        db_column='personnelrole',
        blank=True,
        null=True
    )

    personneltype = models.IntegerField(
        choices=PersonnelTypeCode.choices,
        db_column='personneltype',
        blank=True,
        null=True
    )

    monthlycost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        db_column='monthlycost',
        blank=True,
        null=True
    )

    units = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        db_column='units',
        blank=True,
        null=True
    )

    # Computed / tracking fields
    totalspent = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='totalspent'
    )

    remainingbudget = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='remainingbudget'
    )

    percentused = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        db_column='percentused'
    )

    statecode = models.IntegerField(
        default=0,
        db_column='statecode'
    )

    class Meta:
        db_table = 'imputationcode'
        ordering = ['code']
        unique_together = [('projectid', 'code')]
        indexes = [
            models.Index(fields=['projectid', 'costtype']),
            models.Index(fields=['projectid', 'categoryid']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ImputationPeriod(AuditMixin):
    """Time period for budget tracking and imputation."""

    periodid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='periodid'
    )

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='imputation_periods'
    )

    periodtype = models.IntegerField(
        choices=PeriodTypeCode.choices,
        db_column='periodtype'
    )

    year = models.IntegerField(
        db_column='year'
    )

    month = models.IntegerField(
        db_column='month'
    )

    periodnumber = models.IntegerField(
        db_column='periodnumber'
    )

    label = models.CharField(
        max_length=30,
        db_column='label'
    )

    startdate = models.DateField(
        db_column='startdate'
    )

    enddate = models.DateField(
        db_column='enddate'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    statecode = models.IntegerField(
        default=0,
        db_column='statecode'
    )

    class Meta:
        db_table = 'imputationperiod'
        ordering = ['sortorder']
        unique_together = [('projectid', 'year', 'month', 'periodnumber')]
        indexes = [
            models.Index(fields=['projectid', 'year', 'month']),
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return self.label


class ImputationCodeBudget(models.Model):
    """Per-period planned and actual budget for an imputation code."""

    budgetlineid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='budgetlineid'
    )
    imputationcodeid = models.ForeignKey(
        ImputationCode,
        on_delete=models.CASCADE,
        db_column='imputationcodeid',
        related_name='budget_lines'
    )
    # FK to period when it falls within project range; null for out-of-range periods
    periodid = models.ForeignKey(
        ImputationPeriod,
        on_delete=models.SET_NULL,
        db_column='periodid',
        null=True,
        blank=True,
        related_name='code_budgets'
    )
    periodlabel = models.CharField(
        max_length=30,
        db_column='periodlabel'
    )
    plannedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='plannedamount'
    )
    actualamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='actualamount'
    )
    plannedvolume = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='plannedvolume',
        help_text='Planned production volume in units for this period'
    )
    actualvolume = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='actualvolume',
        help_text='Actual production volume in units for this period'
    )
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')

    class Meta:
        db_table = 'imputationcodebudget'
        ordering = ['imputationcodeid', 'periodlabel']
        unique_together = [('imputationcodeid', 'periodlabel')]
        indexes = [
            models.Index(fields=['imputationcodeid', 'periodlabel']),
            models.Index(fields=['periodid']),
        ]

    def __str__(self):
        return f"{self.imputationcodeid.code} | {self.periodlabel}"
