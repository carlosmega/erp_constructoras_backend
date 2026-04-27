"""Budget estimation (proyección) models for construction projects."""

import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Q, CheckConstraint, UniqueConstraint
from core.models import AuditMixin


# =============================================================================
# Enum Definitions
# =============================================================================

class BreakdownCategoryCode(models.IntegerChoices):
    MATERIALS = 1, 'Materials'
    HAULING = 2, 'Hauling'
    MACHINERY = 3, 'Machinery'
    LABOR = 4, 'Labor'
    SUBCONTRACTS = 5, 'Subcontracts'
    MINOR_TOOLS = 6, 'Minor Tools'
    PPE = 7, 'PPE'


class BreakdownMethodCode(models.IntegerChoices):
    DETAILED = 0, 'Detailed'
    DIRECT_QUOTE = 1, 'Direct Quote'


class SupplyTypeCode(models.IntegerChoices):
    MATERIAL = 0, 'Material'
    LABOR = 1, 'Labor'
    MACHINERY = 2, 'Machinery'
    SUBCONTRACT = 3, 'Subcontract'
    HAULING = 4, 'Hauling'


class CatalogSourceCode(models.IntegerChoices):
    SICT = 0, 'SICT'
    HISTORICO = 1, 'Histórico'
    MANUAL = 2, 'Manual'


class ChecklistStatusCode(models.IntegerChoices):
    NA = 0, 'N/A'
    YES = 1, 'Yes'
    NO = 2, 'No'


class ProjectSizeCode(models.IntegerChoices):
    SMALL = 0, 'Small'
    MEDIUM = 1, 'Medium'
    LARGE = 2, 'Large'


class ProyeccionStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class EstimationStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    IN_REVIEW = 1, 'In Review'
    ACCEPTED = 2, 'Accepted'
    CONVERTED = 3, 'Converted'
    CANCELED = 4, 'Canceled'


# =============================================================================
# Models
# =============================================================================


class EstimationProject(AuditMixin):
    """Root entity for a budget estimation/projection before project creation."""

    estimationprojectid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='estimationprojectid'
    )

    # Basic project information (will seed the ConstructionProject when converted)
    name = models.CharField(max_length=300, db_column='name')
    description = models.TextField(db_column='description', blank=True, null=True)
    estimationnumber = models.CharField(max_length=20, db_column='estimationnumber', unique=True)

    # Client reference
    accountid = models.ForeignKey(
        'accounts.Account',
        on_delete=models.PROTECT,
        db_column='accountid',
        related_name='estimation_projects',
        null=True,
        blank=True,
    )

    # Opportunity reference (optional)
    opportunityid = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        db_column='opportunityid',
        blank=True,
        null=True,
        related_name='estimation_projects'
    )

    # Key dates
    presentationdate = models.DateField(db_column='presentationdate', blank=True, null=True)
    estimatedstartdate = models.DateField(db_column='estimatedstartdate', blank=True, null=True)
    estimatedenddate = models.DateField(db_column='estimatedenddate', blank=True, null=True)
    durationmonths = models.IntegerField(db_column='durationmonths', default=0)
    periodcount = models.IntegerField(db_column='periodcount', default=0)

    # Project classification (will carry over to ConstructionProject)
    projecttype = models.IntegerField(db_column='projecttype', default=0)  # 0=Public, 1=Private
    biddingtype = models.IntegerField(db_column='biddingtype', default=0)  # 0=Open, 1=Invited, 2=Direct
    periodtype = models.IntegerField(db_column='periodtype', default=0)  # 0=Weekly, 1=Fortnightly

    # Contract amounts (estimated at this stage)
    estimatedcontractamount = models.DecimalField(
        max_digits=19, decimal_places=2, default=0, db_column='estimatedcontractamount'
    )
    exchangerate_mxn_usd = models.DecimalField(
        max_digits=12, decimal_places=4, db_column='exchangerate_mxn_usd', blank=True, null=True
    )

    # State
    statecode = models.IntegerField(
        choices=EstimationStateCode.choices,
        default=EstimationStateCode.DRAFT,
        db_column='statecode'
    )

    # Link to generated project (populated after conversion)
    generatedprojectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.SET_NULL,
        db_column='generatedprojectid',
        null=True,
        blank=True,
        related_name='source_estimation'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_estimation_projects'
    )

    class Meta:
        db_table = 'estimationproject'
        verbose_name = 'Estimation Project'
        verbose_name_plural = 'Estimation Projects'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['estimationnumber']),
            models.Index(fields=['statecode', 'ownerid']),
        ]

    def __str__(self):
        return f"{self.estimationnumber} - {self.name}"

    @property
    def is_draft(self):
        return self.statecode == EstimationStateCode.DRAFT

    @property
    def is_converted(self):
        return self.statecode == EstimationStateCode.CONVERTED

    @property
    def state_name(self):
        return EstimationStateCode(self.statecode).label

class ConceptFamily(AuditMixin):
    """Top-level grouping of budget concepts."""

    familyid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='familyid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='concept_families'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    code = models.CharField(
        max_length=50,
        db_column='code'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'conceptfamily'
        ordering = ['sortorder', 'code']
        unique_together = [('projectid', 'code')]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ConceptSubfamily(AuditMixin):
    """Second-level grouping of budget concepts within a family."""

    subfamilyid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='subfamilyid'
    )

    familyid = models.ForeignKey(
        ConceptFamily,
        on_delete=models.CASCADE,
        db_column='familyid',
        related_name='subfamilies'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='concept_subfamilies'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    code = models.CharField(
        max_length=50,
        db_column='code'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'conceptsubfamily'
        ordering = ['sortorder', 'code']
        unique_together = [('familyid', 'code')]

    def __str__(self):
        return f"{self.code} - {self.name}"


class BudgetConcept(AuditMixin):
    """Individual budget concept (line item) within a subfamily."""

    conceptid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='conceptid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='budget_concepts'
    )

    subfamilyid = models.ForeignKey(
        ConceptSubfamily,
        on_delete=models.CASCADE,
        db_column='subfamilyid',
        related_name='concepts'
    )

    code = models.CharField(
        max_length=20,
        db_column='code'
    )

    sequencenumber = models.IntegerField(
        db_column='sequencenumber'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    unit = models.CharField(
        max_length=20,
        db_column='unit'
    )

    quantity = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        db_column='quantity'
    )

    directunitcost = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='directunitcost'
    )

    indirectunitcost = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='indirectunitcost'
    )

    utilityunitcost = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='utilityunitcost'
    )

    unitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='unitprice'
    )

    totalamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='totalamount'
    )

    clientunitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='clientunitprice'
    )

    breakdownmethod = models.IntegerField(
        choices=BreakdownMethodCode.choices,
        default=0,
        db_column='breakdownmethod'
    )

    isprintable = models.BooleanField(
        default=True,
        db_column='isprintable'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'budgetconcept'
        ordering = ['subfamilyid', 'sequencenumber']
        unique_together = [('projectid', 'code')]
        indexes = [
            models.Index(fields=['projectid', 'subfamilyid']),
            models.Index(fields=['projectid', 'statecode']),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class UnitCostBreakdown(models.Model):
    """Detailed cost breakdown line for a budget concept."""

    breakdownid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='breakdownid'
    )

    conceptid = models.ForeignKey(
        BudgetConcept,
        on_delete=models.CASCADE,
        db_column='conceptid',
        related_name='breakdowns'
    )

    categorycode = models.IntegerField(
        choices=BreakdownCategoryCode.choices,
        db_column='categorycode'
    )

    linenumber = models.IntegerField(
        db_column='linenumber'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    unit = models.CharField(
        max_length=20,
        db_column='unit'
    )

    quantity = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='quantity'
    )

    unitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='unitprice'
    )

    yieldvalue = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1.0,
        db_column='yieldvalue'
    )

    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='amount'
    )

    supplyid = models.ForeignKey(
        'proyeccion.SupplyCatalogItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='supplyid',
        related_name='breakdown_usages'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    paymentlagperiods = models.IntegerField(
        null=True,
        blank=True,
        db_column='paymentlagperiods',
        help_text='Lag de pago en periodos del proyecto. NULL = usa el default global (directpaymentlag).',
    )

    lineversion = models.IntegerField(
        default=0,
        db_column='lineversion',
        help_text='Optimistic lock para edits a nivel de línea (lag).',
    )

    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )

    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )

    class Meta:
        db_table = 'unitcostbreakdown'
        ordering = ['categorycode', 'linenumber']
        indexes = [
            models.Index(fields=['conceptid', 'categorycode']),
            models.Index(fields=['conceptid', 'statecode']),
        ]

    def __str__(self):
        return f"Breakdown {self.linenumber} - {self.description}"


class IndirectCostDetail(AuditMixin):
    """Indirect cost detail line for a construction project."""

    indirectcostid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='indirectcostid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='indirect_cost_details'
    )

    categorycode = models.CharField(
        max_length=5,
        db_column='categorycode'
    )

    linenumber = models.IntegerField(
        db_column='linenumber'
    )

    imputationcode = models.CharField(
        max_length=10,
        blank=True,
        default='',
        db_column='imputationcode'
    )

    area = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='area'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    monthlycost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='monthlycost'
    )

    units = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1,
        db_column='units'
    )

    months = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        db_column='months'
    )

    startmonth = models.IntegerField(
        null=True, blank=True, db_column='startmonth',
        help_text='First period (1-based) where this cost applies. null = from P1.',
    )
    endmonth = models.IntegerField(
        null=True, blank=True, db_column='endmonth',
        help_text='Last period (1-based) where this cost applies. null = until last.',
    )

    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='amount'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    paymentlagperiods = models.IntegerField(
        null=True,
        blank=True,
        db_column='paymentlagperiods',
        help_text='Lag de pago en periodos del proyecto. NULL = usa el default global (indirectpaymentlag).',
    )

    lineversion = models.IntegerField(
        default=0,
        db_column='lineversion',
        help_text='Optimistic lock para edits a nivel de línea (lag).',
    )

    class Meta:
        db_table = 'indirectcostdetail'
        ordering = ['categorycode', 'linenumber']
        indexes = [
            models.Index(fields=['projectid', 'categorycode']),
            models.Index(fields=['projectid', 'statecode']),
        ]

    def __str__(self):
        return f"{self.categorycode}-{self.linenumber} - {self.description}"

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.startmonth is not None and self.endmonth is not None:
            if self.startmonth > self.endmonth:
                raise ValidationError({
                    'startmonth': 'startmonth must be <= endmonth'
                })
        if self.projectid_id and self.projectid.periodcount:
            pc = self.projectid.periodcount
            if self.startmonth is not None and not (1 <= self.startmonth <= pc):
                raise ValidationError({'startmonth': f'startmonth out of range [1, {pc}]'})
            if self.endmonth is not None and not (1 <= self.endmonth <= pc):
                raise ValidationError({'endmonth': f'endmonth out of range [1, {pc}]'})


class OfferAlternative(AuditMixin):
    """Offer alternative for a construction project budget."""

    alternativeid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='alternativeid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='offer_alternatives'
    )

    alternativenumber = models.IntegerField(
        db_column='alternativenumber'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    description = models.TextField(
        blank=True,
        null=True,
        db_column='description'
    )

    transversalpercent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        db_column='transversalpercent'
    )

    profitpercent = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        db_column='profitpercent'
    )

    coefficient = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=1,
        db_column='coefficient'
    )

    directcosttotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='directcosttotal'
    )

    indirectcosttotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='indirectcosttotal'
    )

    constructioncost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='constructioncost'
    )

    salepricenet = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='salepricenet'
    )

    taxamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='taxamount'
    )

    salepricetotal = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='salepricetotal'
    )

    saleusd = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='saleusd'
    )

    ischosen = models.BooleanField(
        default=False,
        db_column='ischosen'
    )

    authorizationname = models.CharField(
        max_length=200,
        blank=True,
        default='',
        db_column='authorizationname'
    )

    authorizationposition = models.CharField(
        max_length=200,
        blank=True,
        default='',
        db_column='authorizationposition'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'offeralternative'
        ordering = ['alternativenumber']
        unique_together = [('projectid', 'alternativenumber')]
        indexes = [
            models.Index(fields=['projectid', 'statecode']),
        ]

    def __str__(self):
        return f"Alternative {self.alternativenumber} - {self.name}"


class ExternalCostItem(models.Model):
    """External cost checklist item for a project offer."""

    externalcostid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='externalcostid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='external_costs'
    )

    itemname = models.CharField(
        max_length=200,
        db_column='itemname'
    )

    applies = models.IntegerField(
        choices=ChecklistStatusCode.choices,
        default=0,
        db_column='applies'
    )

    percentofsale = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='percentofsale'
    )

    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='amount'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )

    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )

    class Meta:
        db_table = 'externalcostitem'
        ordering = ['sortorder']
        indexes = [
            models.Index(fields=['projectid']),
        ]

    def __str__(self):
        return self.itemname


class SupplyCatalogItem(AuditMixin):
    """Global supply catalog item for unit cost breakdowns."""

    supplyid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='supplyid'
    )

    code = models.CharField(
        max_length=20,
        unique=True,
        db_column='code'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    unit = models.CharField(
        max_length=20,
        db_column='unit'
    )

    supplytype = models.IntegerField(
        choices=SupplyTypeCode.choices,
        db_column='supplytype'
    )

    referenceprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='referenceprice'
    )

    referencedate = models.DateField(
        null=True,
        blank=True,
        db_column='referencedate'
    )

    geographiczone = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='geographiczone'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'supplycatalogitem'
        ordering = ['code']
        indexes = [
            models.Index(fields=['supplytype']),
            models.Index(fields=['code']),
        ]

    def __str__(self):
        return f"{self.code} - {self.description}"


class IndirectCostTemplate(AuditMixin):
    """Global template for indirect cost seeding."""

    templateid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='templateid'
    )

    name = models.CharField(
        max_length=200,
        db_column='name'
    )

    projectsize = models.IntegerField(
        choices=ProjectSizeCode.choices,
        db_column='projectsize'
    )

    categorycode = models.CharField(
        max_length=5,
        db_column='categorycode'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    monthlycost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='monthlycost'
    )

    units = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1,
        db_column='units'
    )

    months = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        db_column='months'
    )

    sortorder = models.IntegerField(
        default=0,
        db_column='sortorder'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'indirectcosttemplate'
        ordering = ['projectsize', 'categorycode', 'sortorder']

    def __str__(self):
        return f"{self.name} ({self.get_projectsize_display()}) - {self.categorycode}"


class EquipmentYield(AuditMixin):
    """Global equipment yield reference data."""

    equipmentyieldid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='equipmentyieldid'
    )

    category = models.CharField(
        max_length=100,
        db_column='category'
    )

    description = models.CharField(
        max_length=500,
        db_column='description'
    )

    suppliername = models.CharField(
        max_length=200,
        blank=True,
        default='',
        db_column='suppliername'
    )

    monthlycost = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='monthlycost'
    )

    numberofequipment = models.IntegerField(
        default=1,
        db_column='numberofequipment'
    )

    theoreticalyield = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='theoreticalyield'
    )

    effectivehours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        db_column='effectivehours'
    )

    realyield = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='realyield'
    )

    fuelconsumption = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='fuelconsumption'
    )

    dailyfuelconsumption = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='dailyfuelconsumption'
    )

    effectivedays = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        db_column='effectivedays'
    )

    trafficfactor = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0.8,
        db_column='trafficfactor'
    )

    monthlycubicmeters = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='monthlycubicmeters'
    )

    monthlydiesel = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=0,
        db_column='monthlydiesel'
    )

    costpercubicmeter = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='costpercubicmeter'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'equipmentyield'
        ordering = ['category', 'description']

    def __str__(self):
        return f"{self.category} - {self.description}"


class WorkPlanEntryType(models.IntegerChoices):
    PLANNED = 0, 'Planned'
    ACTUAL = 1, 'Actual'


class WorkPlanEntry(AuditMixin):
    """Work plan distribution entry for a budget concept across periods.

    Mirrors the Excel "Plan de obra" cell grid: each row is a (concept, period, entrytype)
    — entrytype distinguishes PROGRAMADO (planned) from PRODUCCION REAL (actual).
    """

    workplanentryid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='workplanentryid'
    )

    conceptid = models.ForeignKey(
        BudgetConcept,
        on_delete=models.CASCADE,
        db_column='conceptid',
        related_name='workplan_entries'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='workplan_entries'
    )

    periodnumber = models.IntegerField(
        db_column='periodnumber'
    )

    periodlabel = models.CharField(
        max_length=20,
        db_column='periodlabel'
    )

    entrytype = models.IntegerField(
        choices=WorkPlanEntryType.choices,
        default=WorkPlanEntryType.PLANNED,
        db_column='entrytype',
    )

    distributedquantity = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='distributedquantity'
    )

    distributedamount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0,
        db_column='distributedamount'
    )

    class Meta:
        db_table = 'workplanentry'
        ordering = ['entrytype', 'periodnumber']
        unique_together = [('conceptid', 'periodnumber', 'entrytype')]
        indexes = [
            models.Index(fields=['projectid']),
            models.Index(fields=['projectid', 'entrytype']),
        ]

    def __str__(self):
        tname = WorkPlanEntryType(self.entrytype).label
        return f"[{tname}] P{self.periodnumber} ({self.periodlabel}) - {self.conceptid}"


# =============================================================================
# Concept Price Catalog (Historical P.U. Database)
# =============================================================================

class ConceptPriceCatalogItem(AuditMixin):
    """Master catalog of work concepts from multiple sources (SICT, historical, manual).

    Each item represents a unique concept description + unit combination.
    Price references per project are stored in ConceptPriceReference.
    """

    catalogitemid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='catalogitemid'
    )

    code = models.CharField(
        max_length=30,
        unique=True,
        db_column='code',
        help_text='Auto-generated or manual concept code'
    )

    description = models.TextField(
        db_column='description',
        help_text='Full concept description'
    )

    unit = models.CharField(
        max_length=20,
        db_column='unit'
    )

    source = models.IntegerField(
        choices=CatalogSourceCode.choices,
        default=CatalogSourceCode.HISTORICO,
        db_column='source',
        help_text='Origin: SICT(0), Histórico(1), Manual(2)'
    )

    category = models.CharField(
        max_length=200,
        blank=True,
        default='',
        db_column='category',
        help_text='Optional grouping (Preliminares, Instalaciones, etc.)'
    )

    averageprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='averageprice',
        help_text='Computed average P.U. across all references'
    )

    minprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='minprice',
        help_text='Minimum P.U. across all references'
    )

    maxprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='maxprice',
        help_text='Maximum P.U. across all references'
    )

    referencecount = models.IntegerField(
        default=0,
        db_column='referencecount',
        help_text='Number of project references for this concept'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    # ── Classification hierarchy ──────────────────────────────────────
    # SICT:     L1=Libro, L2=Título, L3=Capítulo
    # Dimovere: L1=(vacío), L2=Familia, L3=Subfamilia
    classificationl1 = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='classificationl1',
        help_text='Level 1: Libro (SICT) — empty for Dimovere'
    )

    classificationl2 = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='classificationl2',
        help_text='Level 2: Título (SICT) / Familia (Dimovere)'
    )

    classificationl3 = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_column='classificationl3',
        help_text='Level 3: Capítulo (SICT) / Subfamilia (Dimovere)'
    )

    class Meta:
        db_table = 'conceptpricecatalogitem'
        ordering = ['code']
        indexes = [
            models.Index(fields=['source']),
            models.Index(fields=['code']),
            models.Index(fields=['unit']),
            models.Index(fields=['classificationl2']),
        ]

    def __str__(self):
        return f"{self.code} - {self.description[:80]}"

    def update_price_stats(self):
        """Recompute average/min/max from related references."""
        refs = self.price_references.filter(statecode=0)
        prices = [r.unitprice for r in refs if r.unitprice > 0]
        if prices:
            self.averageprice = sum(prices) / len(prices)
            self.minprice = min(prices)
            self.maxprice = max(prices)
            self.referencecount = len(prices)
        else:
            self.averageprice = 0
            self.minprice = 0
            self.maxprice = 0
            self.referencecount = 0


class ConceptPriceReference(AuditMixin):
    """Historical price reference for a catalog concept from a specific project."""

    referenceid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='referenceid'
    )

    catalogitemid = models.ForeignKey(
        ConceptPriceCatalogItem,
        on_delete=models.CASCADE,
        db_column='catalogitemid',
        related_name='price_references'
    )

    projectname = models.CharField(
        max_length=200,
        db_column='projectname',
        help_text='Historical project name (e.g., Cumbres Elite, Swiss Lab Mty)'
    )

    projectlocation = models.CharField(
        max_length=300,
        blank=True,
        default='',
        db_column='projectlocation'
    )

    unitprice = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        default=0,
        db_column='unitprice',
        help_text='Precio Unitario in this project'
    )

    quantity = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='quantity',
        help_text='Quantity used in this project'
    )

    totalamount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='totalamount',
        help_text='Total amount (P.U. x quantity)'
    )

    referencedate = models.DateField(
        null=True,
        blank=True,
        db_column='referencedate'
    )

    notes = models.CharField(
        max_length=500,
        blank=True,
        default='',
        db_column='notes'
    )

    statecode = models.IntegerField(
        default=0,
        choices=ProyeccionStateCode.choices,
        db_column='statecode'
    )

    class Meta:
        db_table = 'conceptpricereference'
        ordering = ['projectname']
        indexes = [
            models.Index(fields=['catalogitemid']),
            models.Index(fields=['projectname']),
        ]

    def __str__(self):
        return f"{self.projectname} - ${self.unitprice}"


# =============================================================================
# Family Template Models
# =============================================================================


class FamilyTemplateSet(AuditMixin):
    """Reusable template containing a set of families and subfamilies."""

    templatesetid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='templatesetid'
    )
    name = models.CharField(max_length=200, db_column='name')
    description = models.TextField(blank=True, default='', db_column='description')
    category = models.CharField(max_length=30, default='custom', db_column='category')
    issystem = models.BooleanField(default=False, db_column='issystem')
    statecode = models.IntegerField(
        default=0, choices=ProyeccionStateCode.choices, db_column='statecode'
    )

    class Meta:
        db_table = 'familytemplateset'
        ordering = ['category', 'name']
        verbose_name = 'Family Template Set'
        indexes = [
            models.Index(fields=['statecode']),
        ]

    def __str__(self):
        return self.name


class FamilyTemplateItem(models.Model):
    """Single family+subfamily entry within a template set (flat structure)."""

    templateitemid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='templateitemid'
    )
    templatesetid = models.ForeignKey(
        FamilyTemplateSet, on_delete=models.CASCADE,
        db_column='templatesetid', related_name='items'
    )
    familycode = models.CharField(max_length=10, db_column='familycode')
    familyname = models.CharField(max_length=200, db_column='familyname')
    subfamilycode = models.CharField(max_length=10, blank=True, default='', db_column='subfamilycode')
    subfamilyname = models.CharField(max_length=200, blank=True, default='', db_column='subfamilyname')
    familysortorder = models.IntegerField(default=0, db_column='familysortorder')
    subfamilysortorder = models.IntegerField(default=0, db_column='subfamilysortorder')
    statecode = models.IntegerField(default=0, db_column='statecode')
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')

    class Meta:
        db_table = 'familytemplateitem'
        ordering = ['familysortorder', 'familycode', 'subfamilysortorder']
        unique_together = [('templatesetid', 'familycode', 'subfamilycode')]

    def __str__(self):
        return f"{self.familycode}/{self.subfamilycode} - {self.familyname}/{self.subfamilyname}"


# =============================================================================
# Temporal Distribution (see spec 2026-04-22)
# =============================================================================

class ProjectionPeriod(AuditMixin):
    """Auto-generated time periods for EstimationProject (weekly or fortnightly).

    Mirrors the 90-column grid of the Excel 'Dist. Temporal' sheet but with real
    dates derived from the project's start/end + periodtype.
    """

    periodid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='periodid'
    )

    projectid = models.ForeignKey(
        EstimationProject,
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='projection_periods',
    )

    periodnumber = models.IntegerField(db_column='periodnumber')
    periodlabel = models.CharField(max_length=20, db_column='periodlabel')
    startdate = models.DateField(db_column='startdate')
    enddate = models.DateField(db_column='enddate')
    periodtype = models.IntegerField(db_column='periodtype')  # 0=weekly, 1=fortnightly

    class Meta:
        db_table = 'projectionperiod'
        ordering = ['periodnumber']
        unique_together = [('projectid', 'periodnumber')]
        indexes = [models.Index(fields=['projectid', 'periodnumber'])]

    def __str__(self):
        return f"P{self.periodnumber} {self.periodlabel}"


class CostLineType(models.IntegerChoices):
    BREAKDOWN = 0, 'Direct Cost (UnitCostBreakdown)'
    INDIRECT  = 1, 'Indirect Cost (IndirectCostDetail)'


class CostDistribution(models.Model):
    """Fraction (0..1) of a cost line applied to a specific period.

    One row per (line, period). The same table covers direct costs (breakdownid)
    and indirect costs (indirectcostid) via a polymorphic FK discriminated by linetype.
    """

    distributionid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='distributionid'
    )
    projectid = models.ForeignKey(
        EstimationProject, on_delete=models.CASCADE,
        db_column='projectid', related_name='cost_distributions',
    )
    linetype = models.IntegerField(choices=CostLineType.choices, db_column='linetype')
    breakdownid = models.ForeignKey(
        'proyeccion.UnitCostBreakdown', on_delete=models.CASCADE,
        null=True, blank=True,
        db_column='breakdownid', related_name='period_distributions',
    )
    indirectcostid = models.ForeignKey(
        'proyeccion.IndirectCostDetail', on_delete=models.CASCADE,
        null=True, blank=True,
        db_column='indirectcostid', related_name='period_distributions',
    )

    periodnumber = models.IntegerField(db_column='periodnumber')
    fraction = models.DecimalField(
        max_digits=10, decimal_places=8, default=Decimal('0'), db_column='fraction'
    )
    isderived = models.BooleanField(default=True, db_column='isderived')

    # Concurrency + audit
    version = models.IntegerField(default=0, db_column='version')
    modifiedby = models.ForeignKey(
        'users.SystemUser', on_delete=models.PROTECT,
        null=True, blank=True,
        db_column='modifiedby', related_name='+',
    )
    modifiedon = models.DateTimeField(auto_now=True, db_column='modifiedon')
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')

    class Meta:
        db_table = 'costdistribution'
        indexes = [
            models.Index(fields=['projectid', 'periodnumber']),
            models.Index(fields=['projectid', 'linetype']),
            models.Index(fields=['breakdownid']),
            models.Index(fields=['indirectcostid']),
        ]
        constraints = [
            CheckConstraint(
                condition=(
                    (Q(breakdownid__isnull=False) & Q(indirectcostid__isnull=True) & Q(linetype=0)) |
                    (Q(breakdownid__isnull=True) & Q(indirectcostid__isnull=False) & Q(linetype=1))
                ),
                name='cost_distribution_exactly_one_fk',
            ),
            UniqueConstraint(
                fields=['breakdownid', 'periodnumber'],
                name='uq_distribution_breakdown_period',
                condition=Q(breakdownid__isnull=False),
            ),
            UniqueConstraint(
                fields=['indirectcostid', 'periodnumber'],
                name='uq_distribution_indirect_period',
                condition=Q(indirectcostid__isnull=False),
            ),
            CheckConstraint(
                condition=Q(fraction__gte=0) & Q(fraction__lte=1),
                name='cost_distribution_fraction_range',
            ),
        ]

    def __str__(self):
        return f"Dist P{self.periodnumber} line={self.linetype} frac={self.fraction}"


class DistributionPresence(models.Model):
    """Tracks users viewing/editing the distribution tab for a project.

    Heartbeat refreshes `last_seen` every 30s from the frontend. Entries stale
    beyond 2 minutes are ignored by the read endpoint; the cleanup_presence
    management command removes entries older than 7 days.
    """

    MODE_CHOICES = [('viewing', 'Viewing'), ('editing', 'Editing')]

    presenceid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='presenceid'
    )
    projectid = models.ForeignKey(
        EstimationProject, on_delete=models.CASCADE,
        db_column='projectid', related_name='distribution_presence',
    )
    userid = models.ForeignKey(
        'users.SystemUser', on_delete=models.CASCADE,
        db_column='userid',
    )
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, db_column='mode')
    last_seen = models.DateTimeField(auto_now=True, db_column='last_seen')

    class Meta:
        db_table = 'distributionpresence'
        unique_together = [('projectid', 'userid')]
        indexes = [models.Index(fields=['projectid', 'last_seen'])]

    def __str__(self):
        return f"{self.userid} {self.mode} on {self.projectid}"


class EstimationFinancialSettings(AuditMixin):
    """Financial parameters for an estimation project (1:1)."""

    settingsid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='settingsid',
    )
    projectid = models.OneToOneField(
        'EstimationProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='financial_settings',
    )

    # Anticipo
    advanceamountnotax = models.DecimalField(
        max_digits=19, decimal_places=2,
        default=Decimal('0'),
        db_column='advanceamountnotax',
    )
    advanceentryperiod = models.IntegerField(
        default=1,
        db_column='advanceentryperiod',
    )
    advanceamortizationrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0'),
        db_column='advanceamortizationrate',
    )

    # Retenciones del cliente
    imssretentionrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0.0500'),
        db_column='imssretentionrate',
    )
    otherretentionrate = models.DecimalField(
        max_digits=5, decimal_places=4,
        default=Decimal('0'),
        db_column='otherretentionrate',
    )
    retentionreturnperiod = models.IntegerField(
        null=True, blank=True,
        db_column='retentionreturnperiod',
    )

    # Lag default global de pagos a proveedores
    directpaymentlag = models.IntegerField(
        default=0,
        db_column='directpaymentlag',
    )
    indirectpaymentlag = models.IntegerField(
        default=0,
        db_column='indirectpaymentlag',
    )

    # Overrides de lag por categoría. Cualquier categoría que no aparezca usa el lag global.
    # Formato:
    #   {"direct": {"1": 0, "4": 2}, "indirect": {"C1": 3, "C5": 1}}
    # Las llaves son categorycode (int como string para directos 1-7, str para indirectos C1-C8).
    # Los valores son enteros 0..120 (mismas reglas que los lags globales).
    category_lags = models.JSONField(
        default=dict,
        blank=True,
        db_column='category_lags',
    )

    # Costo financiero
    financecostrate = models.DecimalField(
        max_digits=7, decimal_places=6,
        default=Decimal('0.001000'),
        db_column='financecostrate',
    )

    class Meta:
        db_table = 'estimationfinancialsettings'
        verbose_name = 'Estimation Financial Settings'
        verbose_name_plural = 'Estimation Financial Settings'

    def __str__(self):
        return f"Financial settings for {self.projectid}"


class EstimationBillingRule(AuditMixin):
    """N billing tranches per estimation project (e.g. 50%/30%/20% at lags 0/1/2)."""

    ruleid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='ruleid',
    )
    projectid = models.ForeignKey(
        'EstimationProject',
        on_delete=models.CASCADE,
        db_column='projectid',
        related_name='billing_rules',
    )
    sequence = models.IntegerField(db_column='sequence')
    percent = models.DecimalField(
        max_digits=5, decimal_places=4,
        db_column='percent',
    )
    lagperiods = models.IntegerField(db_column='lagperiods')

    class Meta:
        db_table = 'estimationbillingrule'
        verbose_name = 'Estimation Billing Rule'
        verbose_name_plural = 'Estimation Billing Rules'
        ordering = ['projectid', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['projectid', 'sequence'],
                name='uniq_estimation_billing_seq',
            ),
            models.CheckConstraint(
                condition=models.Q(sequence__gte=1) & models.Q(sequence__lte=10),
                name='estimation_billing_seq_range',
            ),
            models.CheckConstraint(
                condition=models.Q(percent__gte=0) & models.Q(percent__lte=1),
                name='estimation_billing_pct_range',
            ),
            models.CheckConstraint(
                condition=models.Q(lagperiods__gte=0) & models.Q(lagperiods__lte=120),
                name='estimation_billing_lag_range',
            ),
        ]

    def __str__(self):
        return f"{self.projectid} #{self.sequence}: {self.percent} @ +{self.lagperiods}"
