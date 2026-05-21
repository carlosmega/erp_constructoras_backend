"""Budget estimation (proyeccion) API schemas (DTOs)."""

from ninja import ModelSchema, Schema
from typing import List, Literal, Optional
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
    profitpercent: Optional[Decimal] = Decimal('0')


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
    profitpercent: Optional[Decimal] = None
    statecode: Optional[int] = None


class ConvertEstimationResponseDto(Schema):
    """Response shape returned by POST /estimation-projects/{id}/convert/.

    All inputs come from the estimation itself; no body is needed on the request.
    """
    projectid: UUID
    projectnumber: str
    estimation_locked: bool
    summary: dict  # {periods_created, direct_codes_created, indirect_codes_created, contract_amount}


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
    entrytype: int = 0  # 0=PLANNED, 1=ACTUAL


class UpdateWorkPlanEntryDto(Schema):
    """DTO for updating a work plan entry."""
    distributedquantity: Optional[Decimal] = None


# ----- Matrix / Summary response schemas -----

class WorkPlanPeriodSchema(Schema):
    number: int
    label: str


class WorkPlanEntryValueSchema(Schema):
    total_qty: Decimal
    total_amount: Decimal
    by_period: dict  # {str(period_number): quantity}


class WorkPlanConceptRowSchema(Schema):
    conceptid: UUID
    code: str
    description: str
    unit: str
    quantity: Decimal
    unitprice: Decimal
    totalamount: Decimal
    planned: WorkPlanEntryValueSchema
    actual: WorkPlanEntryValueSchema


class WorkPlanSubfamilyGroupSchema(Schema):
    subfamilyid: UUID
    code: str
    name: str
    concepts: list[WorkPlanConceptRowSchema]


class WorkPlanFamilyTotalsSchema(Schema):
    planned_amount: Decimal
    actual_amount: Decimal
    planned_by_period_amount: dict
    actual_by_period_amount: dict


class WorkPlanFamilyGroupSchema(Schema):
    familyid: UUID
    code: str
    name: str
    contract_amount: Decimal
    subfamilies: list[WorkPlanSubfamilyGroupSchema]
    totals: WorkPlanFamilyTotalsSchema


class WorkPlanGrandTotalsSchema(Schema):
    contract_amount: Decimal
    planned_amount: Decimal
    actual_amount: Decimal
    planned_by_period_amount: dict
    actual_by_period_amount: dict


class WorkPlanMatrixSchema(Schema):
    periods: list[WorkPlanPeriodSchema]
    families: list[WorkPlanFamilyGroupSchema]
    grand_totals: WorkPlanGrandTotalsSchema


class WorkPlanFamilySummarySchema(Schema):
    familyid: UUID
    code: str
    name: str
    contract_amount: Decimal
    planned_amount: Decimal
    actual_amount: Decimal
    percent_planned: float
    percent_actual: float


class WorkPlanSummarySchema(Schema):
    families: list[WorkPlanFamilySummarySchema]
    grand_totals: WorkPlanGrandTotalsSchema


# =============================================================================
# Aggregation / Computed Schemas
# =============================================================================

class SupplyExplosionItemSchema(Schema):
    """Single line in the supply explosion (auxiliary) report."""
    conceptid: UUID
    conceptcode: str
    conceptdescription: str
    conceptquantity: Decimal
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
    supplytype: int
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


class AutoGenerateSkeletonDto(Schema):
    """DTO for auto-generating skeleton breakdown lines."""
    subfamilyname: str
    unit: str
    description: Optional[str] = ''


class ApplyTemplateDto(Schema):
    """DTO for applying an indirect cost template to a project."""
    projectid: UUID
    projectsize: int  # 0=Small, 1=Medium, 2=Large


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
            'category', 'classificationl1', 'classificationl2',
            'classificationl3', 'averageprice', 'minprice', 'maxprice',
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


# =============================================================================
# Excel Import Schemas
# =============================================================================

class AnalyzeMatchCandidateSchema(Schema):
    """Catalog item suggested as match."""
    catalogitemid: UUID
    code: str
    description: str
    unit: str
    averageprice: float
    classificationl2: str
    classificationl3: str


class AnalyzeConceptRowSchema(Schema):
    """A single concept row from the Excel analysis."""
    row: int
    partida: str
    code: str
    description: str
    unit: str
    quantity: float
    match_status: str  # 'exact' | 'partial' | 'none'
    match_score: float
    match_candidate: Optional[AnalyzeMatchCandidateSchema] = None


class AnalyzePartidaSchema(Schema):
    """A partida (subfamily group) from the Excel."""
    name: str
    subfamilyid: Optional[UUID] = None
    is_new: bool


class AnalyzeSummarySchema(Schema):
    """Summary of the analysis results."""
    total: int
    exact: int
    partial: int
    none: int


class AnalyzeExcelResponseSchema(Schema):
    """Response from the analyze-excel endpoint."""
    partidas: list[AnalyzePartidaSchema]
    concepts: list[AnalyzeConceptRowSchema]
    summary: AnalyzeSummarySchema


class ImportExcelItemDto(Schema):
    """A single concept to import."""
    row: int
    partida: str
    code: str
    description: str
    unit: str
    quantity: float
    accepted_catalog_id: Optional[UUID] = None
    use_catalog_price: bool = False


class ImportExcelRequestDto(Schema):
    """Request to import concepts from analyzed Excel."""
    create_missing_subfamilies: bool = True
    items: list[ImportExcelItemDto]


class ImportExcelResponseSchema(Schema):
    """Response from the import-excel endpoint."""
    created: int
    subfamilies_created: int
    matched: int


# =============================================================================
# Concept Excel Export / Import DTOs (8-column round-trip format)
# =============================================================================

class ConceptExcelRowSchema(Schema):
    row: int
    familia: str
    cod_fam: str
    subfamilia: str
    cod_sub: str
    codigo: str
    description: str
    unit: str
    quantity: float
    status: str  # 'new' | 'skip' | 'error'
    error_msg: Optional[str] = None


class AnalyzeConceptExcelResponseSchema(Schema):
    summary: dict
    rows: list[ConceptExcelRowSchema]


class ImportConceptExcelItemDto(Schema):
    row: int
    cod_sub: str
    codigo: str
    description: str
    unit: str
    quantity: float


class ImportConceptExcelRequestDto(Schema):
    items: list[ImportConceptExcelItemDto]


class ImportConceptExcelResponseSchema(Schema):
    created: int
    skipped: int


# =============================================================================
# Temporal Distribution DTOs (see spec 2026-04-22)
# =============================================================================

class ProjectionPeriodDto(Schema):
    periodid: UUID
    periodnumber: int
    periodlabel: str
    startdate: date
    enddate: date
    periodtype: int


class RegenerateResult(Schema):
    created: int
    deleted: int
    kept: int
    lost_manual_edits: int


class DistributionCellDto(Schema):
    periodnumber: int
    fraction: Decimal
    isderived: bool
    version: int


class DistributionLineDto(Schema):
    lineid: UUID
    linetype: Literal['BREAKDOWN', 'INDIRECT']
    description: str
    unit: str
    totalamount: float
    paymentlagperiods: Optional[int] = None
    lineversion: int = 0
    distribution: List[DistributionCellDto]
    checksum: float


class DistributionFamilyDto(Schema):
    code: str
    name: str
    categorytype: Literal['DIRECT', 'INDIRECT']
    totalamount: float
    rollups_by_period: List[float]
    lines: List[DistributionLineDto]


class DistributionRollupsDto(Schema):
    direct_by_period: List[float]
    indirect_by_period: List[float]
    retiro_by_period: List[float]
    utility_by_period: List[float]
    total_cost_by_period: List[float]
    sale_by_period: List[float]
    margin_by_period: List[float]


class DistributionTotalsDto(Schema):
    direct_total: float
    indirect_total: float
    retiro_total: float
    utility_total: float
    cost_total: float
    sale_total: float
    margin_total: float
    margin_pct: float


class ChosenAlternativeDto(Schema):
    alternativeid: Optional[UUID] = None
    name: Optional[str] = None
    transversalpercent: float = 0.0
    profitpercent: float = 0.0


class DistributionPayloadDto(Schema):
    periods: List[ProjectionPeriodDto]
    families: List[DistributionFamilyDto]
    rollups: DistributionRollupsDto
    totals: DistributionTotalsDto
    chosen_alternative: ChosenAlternativeDto


class BulkEditItem(Schema):
    lineid: UUID
    linetype: Literal['BREAKDOWN', 'INDIRECT']
    periodnumber: int
    fraction: Decimal
    expected_version: int


class BulkLagEditItem(Schema):
    """Per-line payment lag edit. None = clear (use global default)."""
    lineid: UUID
    linetype: Literal['BREAKDOWN', 'INDIRECT']
    paymentlagperiods: Optional[int] = None
    expected_lineversion: int


class BulkEditRequest(Schema):
    edits: List[BulkEditItem] = []
    lag_edits: List[BulkLagEditItem] = []


class BulkEditOkResponse(Schema):
    updated: int
    new_versions: dict
    lag_updated: int
    new_lineversions: dict
    rollups: DistributionRollupsDto
    totals: DistributionTotalsDto


class ConflictItem(Schema):
    lineid: UUID
    periodnumber: int
    your_value: float
    server_value: Optional[float]
    server_modifiedby: Optional[str]
    server_modifiedon: Optional[str]
    server_version: int
    your_version: int


class ConflictResponse(Schema):
    error: Literal['version_conflict']
    conflicts: List[dict]


class AutofillRequest(Schema):
    strategy: Literal['proportional_workplan', 'uniform']
    only_empty: bool = True
    scope: str = 'all'


class AutofillResponse(Schema):
    lines_affected: int
    warnings: List[str]
    rollups: DistributionRollupsDto
    totals: DistributionTotalsDto


class ResetLineRequest(Schema):
    lineid: UUID
    linetype: Literal['BREAKDOWN', 'INDIRECT']


class PresenceItemDto(Schema):
    userid: UUID
    username: str
    mode: Literal['viewing', 'editing']
    last_seen: datetime


class PresenceResponse(Schema):
    active_users: List[PresenceItemDto]


class HeartbeatRequest(Schema):
    mode: Literal['viewing', 'editing']


# =============================================================================
# PNT Cashflow Schemas (Task 15)
# =============================================================================

class FinancialSettingsDto(Schema):
    settingsid: UUID
    projectid: UUID
    advanceamountnotax: Decimal
    advanceentryperiod: int
    advanceamortizationrate: Decimal
    imssretentionrate: Decimal
    otherretentionrate: Decimal
    retentionreturnperiod: Optional[int] = None
    directpaymentlag: int
    indirectpaymentlag: int
    financecostrate: Decimal
    createdon: datetime
    modifiedon: datetime


class UpdateFinancialSettingsDto(Schema):
    advanceamountnotax: Optional[Decimal] = None
    advanceentryperiod: Optional[int] = None
    advanceamortizationrate: Optional[Decimal] = None
    imssretentionrate: Optional[Decimal] = None
    otherretentionrate: Optional[Decimal] = None
    retentionreturnperiod: Optional[int] = None
    directpaymentlag: Optional[int] = None
    indirectpaymentlag: Optional[int] = None
    financecostrate: Optional[Decimal] = None


class BillingRuleDto(Schema):
    sequence: int
    percent: Decimal
    lagperiods: int


class ReplaceBillingRulesDto(Schema):
    rules: list[BillingRuleDto]


class PNTPeriodDto(Schema):
    label: str
    startdate: date
    enddate: date


class PNTRowDto(Schema):
    code: str
    label: str
    section: str
    values: list[Decimal]
    emphasis: bool
    out_of_horizon: Decimal
    total: Decimal


class PNTStatsDto(Schema):
    pnt_min: Decimal
    pnt_max: Decimal
    pnt_avg: Decimal
    total_costo_financiero: Decimal
    cobros_fuera_horizonte: Decimal
    pagos_fuera_horizonte: Decimal
    chosen_alternative_id: Optional[UUID] = None
    transversalpercent_aplicado: Decimal
    profitpercent_aplicado: Decimal
    advance_fully_amortized_period: Optional[str] = None


class PNTReportDto(Schema):
    projectid: UUID
    granularity: Literal['period', 'month']
    periods: list[PNTPeriodDto]
    rows: list[PNTRowDto]
    stats: PNTStatsDto
    generated_at: datetime


# =============================================================================
# CDU Excel Import / Export Schemas
# =============================================================================

class BreakdownExcelLineSchema(Schema):
    row: int
    category: str
    supply_code: str
    supply_name: str
    unit: str
    yield_value: Decimal
    unit_price: Decimal
    amount: Decimal
    is_new_supply: bool
    warnings: List[str] = []


class BreakdownExcelConceptSchema(Schema):
    code: str
    name: str
    lines: List[BreakdownExcelLineSchema]
    hm_preview: Decimal
    epp_preview: Decimal
    total_preview: Decimal


class BreakdownExcelNewSupplySchema(Schema):
    code: str
    name: str
    unit: str
    supplytype: int
    reference_price: Decimal
    appears_in_concepts: List[str]


class BreakdownExcelErrorSchema(Schema):
    row: int
    concept_code: str = ""
    supply_code: str = ""
    message: str


class BreakdownExcelSummarySchema(Schema):
    concepts_count: int
    lines_count: int
    new_supplies_count: int
    errors_count: int


class AnalyzeBreakdownsResponseSchema(Schema):
    summary: BreakdownExcelSummarySchema
    concepts: List[BreakdownExcelConceptSchema]
    new_supplies: List[BreakdownExcelNewSupplySchema]
    errors: List[BreakdownExcelErrorSchema]
    project_uuid_match: bool
    uploaded_uuid: Optional[str] = None
    affected_distributions_count: int = 0
    affected_concepts_with_distributions: List[str] = []


class ImportBreakdownsLineDto(Schema):
    """Una línea para reimportar (post-analyze, sin warnings/match flags)."""
    category: str
    supply_code: str
    supply_name: str = ""
    unit: str = ""
    yield_value: Decimal
    unit_price: Decimal


class ImportBreakdownsConceptDto(Schema):
    code: str
    lines: List[ImportBreakdownsLineDto]


class ImportBreakdownsRequestDto(Schema):
    concepts: List[ImportBreakdownsConceptDto]
    new_supplies: List[BreakdownExcelNewSupplySchema] = []
    override_uuid_mismatch: bool = False
    uploaded_uuid: Optional[str] = None


class ImportBreakdownsResponseSchema(Schema):
    concepts_replaced: int
    lines_created: int
    supplies_created: int
    hm_epp_regenerated: int
    prorate_triggered: bool


# =============================================================================
# Indirect Costs Excel Import / Export Schemas
# =============================================================================


class IndirectExcelLineSchema(Schema):
    row: int
    category: str  # C1-C8
    code: str = ""
    area: str = ""
    description: str
    monthly_cost: Decimal
    units: Decimal
    months: Decimal
    start_month: Optional[int] = None
    end_month: Optional[int] = None
    payment_lag: Optional[int] = None
    amount: Decimal


class IndirectExcelErrorSchema(Schema):
    row: int
    category: str = ""
    description: str = ""
    message: str


class IndirectExcelSummarySchema(Schema):
    lines_count: int
    total_amount: Decimal
    errors_count: int


class AnalyzeIndirectsResponseSchema(Schema):
    summary: IndirectExcelSummarySchema
    lines: List[IndirectExcelLineSchema]
    errors: List[IndirectExcelErrorSchema]
    project_uuid_match: bool
    uploaded_uuid: Optional[str] = None


class ImportIndirectsLineDto(Schema):
    """Línea lista para persistir (post-analyze, importe ya calculado)."""
    category: str
    code: str = ""
    area: str = ""
    description: str
    monthly_cost: Decimal
    units: Decimal
    months: Decimal
    start_month: Optional[int] = None
    end_month: Optional[int] = None
    payment_lag: Optional[int] = None
    amount: Decimal


class ImportIndirectsRequestDto(Schema):
    lines: List[ImportIndirectsLineDto]
    override_uuid_mismatch: bool = False
    uploaded_uuid: Optional[str] = None


class ImportIndirectsResponseSchema(Schema):
    details_deleted: int
    details_created: int
    prorate_triggered: bool
