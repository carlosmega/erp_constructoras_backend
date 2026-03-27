"""Budget estimation (proyeccion) API schemas (DTOs)."""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime

from apps.proyeccion.models import (
    EstimationProject,
    EstimationStateCode,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
    UnitCostBreakdown,
    IndirectCostDetail,
    OfferAlternative,
    ExternalCostItem,
    SupplyCatalogItem,
    IndirectCostTemplate,
    EquipmentYield,
    WorkPlanEntry,
    ConceptPriceCatalogItem,
    ConceptPriceReference,
    FamilyTemplateSet,
    FamilyTemplateItem,
)


# =============================================================================
# EstimationProject Schemas
# =============================================================================

class EstimationProjectSchema(ModelSchema):
    """Full EstimationProject response schema."""
    accountname: Optional[str] = None
    ownername: Optional[str] = None
    state_name: Optional[str] = None

    class Meta:
        model = EstimationProject
        fields = '__all__'

    @staticmethod
    def resolve_accountname(obj):
        return obj.accountid.name if obj.accountid else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name


class CreateEstimationProjectDto(Schema):
    name: str
    description: Optional[str] = None
    accountid: Optional[UUID] = None
    opportunityid: Optional[UUID] = None
    presentationdate: Optional[date] = None
    estimatedstartdate: Optional[date] = None
    estimatedenddate: Optional[date] = None
    durationmonths: Optional[int] = 0
    projecttype: Optional[int] = 0
    biddingtype: Optional[int] = 0
    periodtype: Optional[int] = 0
    estimatedcontractamount: Optional[Decimal] = Decimal('0')
    exchangerate_mxn_usd: Optional[Decimal] = None


class UpdateEstimationProjectDto(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    accountid: Optional[UUID] = None
    opportunityid: Optional[UUID] = None
    presentationdate: Optional[date] = None
    estimatedstartdate: Optional[date] = None
    estimatedenddate: Optional[date] = None
    durationmonths: Optional[int] = None
    projecttype: Optional[int] = None
    biddingtype: Optional[int] = None
    periodtype: Optional[int] = None
    estimatedcontractamount: Optional[Decimal] = None
    exchangerate_mxn_usd: Optional[Decimal] = None
    statecode: Optional[int] = None


class ConvertToProjectDto(Schema):
    """DTO for converting an estimation to a construction project."""
    contractamount_notax: Decimal
    contractamount_withtax: Decimal
    advancepayment_notax: Optional[Decimal] = None
    advancepayment_withtax: Optional[Decimal] = None
    startdate: date
    contractenddate: date
    expectedenddate: Optional[date] = None


# =============================================================================
# ConceptFamily Schemas
# =============================================================================

class ConceptFamilySchema(ModelSchema):
    """Full ConceptFamily response schema."""

    class Meta:
        model = ConceptFamily
        fields = '__all__'


class CreateConceptFamilyDto(Schema):
    """DTO for creating a concept family."""
    projectid: UUID
    name: str
    code: str
    sortorder: Optional[int] = 0


class UpdateConceptFamilyDto(Schema):
    """DTO for updating a concept family."""
    name: Optional[str] = None
    code: Optional[str] = None
    sortorder: Optional[int] = None
    statecode: Optional[int] = None


# =============================================================================
# ConceptSubfamily Schemas
# =============================================================================

class ConceptSubfamilySchema(ModelSchema):
    """Full ConceptSubfamily response schema."""

    class Meta:
        model = ConceptSubfamily
        fields = '__all__'


class CreateConceptSubfamilyDto(Schema):
    """DTO for creating a concept subfamily."""
    familyid: UUID
    projectid: UUID
    name: str
    code: str
    sortorder: Optional[int] = 0


class UpdateConceptSubfamilyDto(Schema):
    """DTO for updating a concept subfamily."""
    name: Optional[str] = None
    code: Optional[str] = None
    sortorder: Optional[int] = None
    statecode: Optional[int] = None


# =============================================================================
# BudgetConcept Schemas
# =============================================================================

class BudgetConceptSchema(ModelSchema):
    """Full BudgetConcept response schema."""
    subfamilyname: Optional[str] = None
    familyname: Optional[str] = None

    class Meta:
        model = BudgetConcept
        fields = '__all__'

    @staticmethod
    def resolve_subfamilyname(obj):
        return obj.subfamilyid.name if obj.subfamilyid else None

    @staticmethod
    def resolve_familyname(obj):
        if obj.subfamilyid and obj.subfamilyid.familyid:
            return obj.subfamilyid.familyid.name
        return None


class CreateBudgetConceptDto(Schema):
    """DTO for creating a budget concept."""
    projectid: UUID
    subfamilyid: UUID
    description: str
    unit: str
    quantity: Decimal
    breakdownmethod: Optional[int] = 0
    clientunitprice: Optional[Decimal] = None
    isprintable: Optional[bool] = True


class UpdateBudgetConceptDto(Schema):
    """DTO for updating a budget concept."""
    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[Decimal] = None
    directunitcost: Optional[Decimal] = None
    indirectunitcost: Optional[Decimal] = None
    utilityunitcost: Optional[Decimal] = None
    unitprice: Optional[Decimal] = None
    totalamount: Optional[Decimal] = None
    clientunitprice: Optional[Decimal] = None
    breakdownmethod: Optional[int] = None
    isprintable: Optional[bool] = None
    statecode: Optional[int] = None


# =============================================================================
# UnitCostBreakdown Schemas
# =============================================================================

class UnitCostBreakdownSchema(ModelSchema):
    """Full UnitCostBreakdown response schema."""
    supplyname: Optional[str] = None

    class Meta:
        model = UnitCostBreakdown
        fields = '__all__'

    @staticmethod
    def resolve_supplyname(obj):
        return obj.supplyid.description if obj.supplyid else None


class CreateUnitCostBreakdownDto(Schema):
    """DTO for creating a unit cost breakdown line."""
    conceptid: UUID
    categorycode: int
    description: str
    unit: str
    quantity: Optional[Decimal] = Decimal('0')
    unitprice: Optional[Decimal] = Decimal('0')
    yieldvalue: Optional[Decimal] = Decimal('1')
    supplyid: Optional[UUID] = None


class UpdateUnitCostBreakdownDto(Schema):
    """DTO for updating a unit cost breakdown line."""
    categorycode: Optional[int] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[Decimal] = None
    unitprice: Optional[Decimal] = None
    yieldvalue: Optional[Decimal] = None
    supplyid: Optional[UUID] = None
    statecode: Optional[int] = None


# =============================================================================
# IndirectCostDetail Schemas
# =============================================================================

class IndirectCostDetailSchema(ModelSchema):
    """Full IndirectCostDetail response schema."""

    class Meta:
        model = IndirectCostDetail
        fields = '__all__'


class CreateIndirectCostDetailDto(Schema):
    """DTO for creating an indirect cost detail line."""
    projectid: UUID
    categorycode: str
    imputationcode: Optional[str] = ''
    area: Optional[str] = ''
    description: str
    monthlycost: Optional[Decimal] = Decimal('0')
    units: Optional[Decimal] = Decimal('1')
    months: Optional[Decimal] = Decimal('0')


class UpdateIndirectCostDetailDto(Schema):
    """DTO for updating an indirect cost detail line."""
    categorycode: Optional[str] = None
    imputationcode: Optional[str] = None
    area: Optional[str] = None
    description: Optional[str] = None
    monthlycost: Optional[Decimal] = None
    units: Optional[Decimal] = None
    months: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# OfferAlternative Schemas
# =============================================================================

class OfferAlternativeSchema(ModelSchema):
    """Full OfferAlternative response schema."""

    class Meta:
        model = OfferAlternative
        fields = '__all__'


class CreateOfferAlternativeDto(Schema):
    """DTO for creating an offer alternative."""
    projectid: UUID
    name: str
    description: Optional[str] = None
    transversalpercent: Optional[Decimal] = Decimal('0')
    profitpercent: Optional[Decimal] = Decimal('0')
    authorizationname: Optional[str] = ''
    authorizationposition: Optional[str] = ''


class UpdateOfferAlternativeDto(Schema):
    """DTO for updating an offer alternative."""
    name: Optional[str] = None
    description: Optional[str] = None
    transversalpercent: Optional[Decimal] = None
    profitpercent: Optional[Decimal] = None
    authorizationname: Optional[str] = None
    authorizationposition: Optional[str] = None
    statecode: Optional[int] = None


# =============================================================================
# ExternalCostItem Schemas
# =============================================================================

class ExternalCostItemSchema(ModelSchema):
    """Full ExternalCostItem response schema."""

    class Meta:
        model = ExternalCostItem
        fields = '__all__'


class UpdateExternalCostItemDto(Schema):
    """DTO for updating an external cost item."""
    applies: Optional[int] = None
    percentofsale: Optional[Decimal] = None
    amount: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# SupplyCatalogItem Schemas
# =============================================================================

class SupplyCatalogItemSchema(ModelSchema):
    """Full SupplyCatalogItem response schema."""

    class Meta:
        model = SupplyCatalogItem
        fields = '__all__'


class CreateSupplyCatalogItemDto(Schema):
    """DTO for creating a supply catalog item."""
    code: str
    description: str
    unit: str
    supplytype: int
    referenceprice: Optional[Decimal] = Decimal('0')
    referencedate: Optional[date] = None
    geographiczone: Optional[str] = ''


class UpdateSupplyCatalogItemDto(Schema):
    """DTO for updating a supply catalog item."""
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    supplytype: Optional[int] = None
    referenceprice: Optional[Decimal] = None
    referencedate: Optional[date] = None
    geographiczone: Optional[str] = None
    statecode: Optional[int] = None


# =============================================================================
# IndirectCostTemplate Schemas
# =============================================================================

class IndirectCostTemplateSchema(ModelSchema):
    """Full IndirectCostTemplate response schema."""

    class Meta:
        model = IndirectCostTemplate
        fields = '__all__'


# =============================================================================
# EquipmentYield Schemas
# =============================================================================

class EquipmentYieldSchema(ModelSchema):
    """Full EquipmentYield response schema."""

    class Meta:
        model = EquipmentYield
        fields = '__all__'


class CreateEquipmentYieldDto(Schema):
    """DTO for creating an equipment yield record."""
    category: str
    description: str
    suppliername: Optional[str] = ''
    monthlycost: Optional[Decimal] = Decimal('0')
    numberofequipment: Optional[int] = 1
    theoreticalyield: Optional[Decimal] = Decimal('0')
    effectivehours: Optional[Decimal] = Decimal('0')
    fuelconsumption: Optional[Decimal] = Decimal('0')
    effectivedays: Optional[Decimal] = Decimal('0')
    trafficfactor: Optional[Decimal] = Decimal('0.8')


class UpdateEquipmentYieldDto(Schema):
    """DTO for updating an equipment yield record."""
    category: Optional[str] = None
    description: Optional[str] = None
    suppliername: Optional[str] = None
    monthlycost: Optional[Decimal] = None
    numberofequipment: Optional[int] = None
    theoreticalyield: Optional[Decimal] = None
    effectivehours: Optional[Decimal] = None
    fuelconsumption: Optional[Decimal] = None
    effectivedays: Optional[Decimal] = None
    trafficfactor: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# WorkPlanEntry Schemas
# =============================================================================

class WorkPlanEntrySchema(ModelSchema):
    """Full WorkPlanEntry response schema."""

    class Meta:
        model = WorkPlanEntry
        fields = '__all__'


class CreateWorkPlanEntryDto(Schema):
    """DTO for creating a work plan entry."""
    conceptid: UUID
    projectid: UUID
    periodnumber: int
    periodlabel: str
    distributedquantity: Decimal


class UpdateWorkPlanEntryDto(Schema):
    """DTO for updating a work plan entry."""
    distributedquantity: Optional[Decimal] = None


# =============================================================================
# Aggregation / Computed Schemas
# =============================================================================

class SupplyExplosionItemSchema(Schema):
    """Single line in the supply explosion (auxiliary) report."""
    conceptid: UUID
    conceptcode: str
    conceptdescription: str
    categorycode: int
    supplyid: Optional[UUID] = None
    supplycode: Optional[str] = None
    description: str
    unit: str
    quantity: Decimal
    unitprice: Decimal
    amount: Decimal


class SupplyExplosionConsolidatedSchema(Schema):
    """Consolidated supply explosion grouped by supply code."""
    supplycode: str
    description: str
    unit: str
    totalquantity: Decimal
    averageprice: Decimal
    totalamount: Decimal
    conceptcount: int


class TemporalDistributionSchema(Schema):
    """Temporal distribution of invoiced, cost, and result per period."""
    periodnumber: int
    periodlabel: str
    invoicedamount: Decimal
    costamount: Decimal
    resultamount: Decimal
    cumulativeinvoiced: Decimal
    cumulativecost: Decimal
    cumulativeresult: Decimal


class CashFlowEntrySchema(Schema):
    """Cash flow entry per period."""
    periodnumber: int
    periodlabel: str
    income: Decimal
    expense: Decimal
    netflow: Decimal
    cumulativeposition: Decimal
    isriskzone: bool


class ProjectBudgetSummarySchema(Schema):
    """High-level budget summary for a project."""
    projectid: UUID
    totalconcepts: int
    totaldirectcost: Decimal
    totalindirectcost: Decimal
    totalconstructioncost: Decimal
    chosensaleprice: Optional[Decimal] = None
    profitpercent: Optional[Decimal] = None


class BulkWorkPlanDto(Schema):
    """DTO for bulk creating/updating work plan entries."""
    projectid: UUID
    entries: list  # list of {conceptid, periodnumber, periodlabel, distributedquantity}


class ApplyTemplateDto(Schema):
    """DTO for applying an indirect cost template to a project."""
    projectid: UUID
    projectsize: int  # 0=Small, 1=Medium, 2=Large


class CashFlowParamsSchema(Schema):
    """Parameters for cash flow calculation."""
    advancepercent: Decimal = Decimal('0')
    paymentdelay: int = 0
    paymentfrequency: int = 1


# =============================================================================
# ConceptPriceCatalog Schemas
# =============================================================================

class ConceptPriceReferenceSchema(ModelSchema):
    """Full ConceptPriceReference response schema."""

    class Meta:
        model = ConceptPriceReference
        fields = '__all__'


class ConceptPriceCatalogItemSchema(ModelSchema):
    """Full ConceptPriceCatalogItem response schema."""
    references: list[ConceptPriceReferenceSchema] = []

    class Meta:
        model = ConceptPriceCatalogItem
        fields = '__all__'

    @staticmethod
    def resolve_references(obj):
        return list(obj.price_references.filter(statecode=0))


class ConceptPriceCatalogItemListSchema(ModelSchema):
    """Lightweight catalog item for list views (no nested references)."""

    class Meta:
        model = ConceptPriceCatalogItem
        fields = [
            'catalogitemid', 'code', 'description', 'unit', 'source',
            'category', 'averageprice', 'minprice', 'maxprice',
            'referencecount', 'statecode',
        ]


class CreateConceptPriceCatalogItemDto(Schema):
    """DTO for creating a concept price catalog item."""
    code: Optional[str] = None  # Auto-generated if not provided
    description: str
    unit: str
    source: int = 1  # Default: Histórico
    category: Optional[str] = ''


class UpdateConceptPriceCatalogItemDto(Schema):
    """DTO for updating a concept price catalog item."""
    code: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    source: Optional[int] = None
    category: Optional[str] = None
    statecode: Optional[int] = None


class CreateConceptPriceReferenceDto(Schema):
    """DTO for creating a price reference."""
    catalogitemid: UUID
    projectname: str
    projectlocation: Optional[str] = ''
    unitprice: Decimal
    quantity: Optional[Decimal] = None
    totalamount: Optional[Decimal] = None
    referencedate: Optional[date] = None
    notes: Optional[str] = ''


# =============================================================================
# Family Template Schemas
# =============================================================================

class FamilyTemplateItemSchema(Schema):
    """Schema for a single template item."""
    templateitemid: UUID
    familycode: str
    familyname: str
    subfamilycode: str
    subfamilyname: str
    familysortorder: int
    subfamilysortorder: int


class FamilyTemplateSetSchema(ModelSchema):
    """Full template set with items."""
    items: list[FamilyTemplateItemSchema] = []
    family_count: int = 0
    subfamily_count: int = 0

    class Meta:
        model = FamilyTemplateSet
        fields = '__all__'

    @staticmethod
    def resolve_items(obj):
        return list(obj.items.filter(statecode=0).order_by('familysortorder', 'subfamilysortorder'))

    @staticmethod
    def resolve_family_count(obj):
        if hasattr(obj, '_family_count'):
            return obj._family_count
        return obj.items.filter(statecode=0).values('familycode').distinct().count()

    @staticmethod
    def resolve_subfamily_count(obj):
        if hasattr(obj, '_subfamily_count'):
            return obj._subfamily_count
        return obj.items.filter(statecode=0).count()


class FamilyTemplateSetListSchema(Schema):
    """Lightweight list schema without items."""
    templatesetid: UUID
    name: str
    description: str
    category: str
    issystem: bool
    statecode: int
    createdon: datetime
    family_count: int = 0
    subfamily_count: int = 0

    @staticmethod
    def resolve_family_count(obj):
        if hasattr(obj, '_family_count'):
            return obj._family_count
        return obj.items.filter(statecode=0).values('familycode').distinct().count()

    @staticmethod
    def resolve_subfamily_count(obj):
        if hasattr(obj, '_subfamily_count'):
            return obj._subfamily_count
        return obj.items.filter(statecode=0).count()


class CreateFamilyTemplateSetDto(Schema):
    """DTO for creating a template set."""
    name: str
    description: Optional[str] = ''
    category: str = 'custom'


class SaveProjectAsTemplateDto(Schema):
    """DTO for saving a project's family structure as a new template."""
    projectid: UUID
    name: str
    description: Optional[str] = ''
    category: str = 'custom'


class ApplyFamilyTemplateDto(Schema):
    """DTO for applying a family template to a project."""
    templatesetid: UUID
    projectid: UUID
    familycodes: Optional[list[str]] = None
