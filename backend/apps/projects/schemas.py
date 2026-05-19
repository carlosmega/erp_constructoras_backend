"""Construction Project API schemas."""

from ninja import ModelSchema, Schema
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date
from apps.projects.models import (
    ConstructionProject, ProjectTeamMember, ProjectZone, ProjectSupplier,
    ProjectRisk, RiskStatusCode,
    ProjectAssetUsage, AssetCategoryCode,
)


# ============================================================================
# Nested / Shared Schemas
# ============================================================================

class ProjectBondSchema(Schema):
    """Nested bond information for project response."""
    amount: Optional[Decimal] = None
    policycost: Optional[Decimal] = None
    validitystartdate: Optional[date] = None
    validityenddate: Optional[date] = None


class ProjectBondDto(Schema):
    """DTO for bond input."""
    amount: Optional[Decimal] = None
    policycost: Optional[Decimal] = None
    validitystartdate: Optional[date] = None
    validityenddate: Optional[date] = None


# ============================================================================
# ProjectTeamMember Schemas
# ============================================================================

class ProjectTeamMemberSchema(ModelSchema):
    """Full team member response schema."""
    id: Optional[UUID] = None
    name: Optional[str] = None
    email: Optional[str] = None
    systemuserid: Optional[UUID] = None

    class Meta:
        model = ProjectTeamMember
        fields = ['teammemberid', 'role']

    @staticmethod
    def resolve_id(obj):
        return obj.teammemberid

    @staticmethod
    def resolve_name(obj):
        return obj.systemuserid.fullname if obj.systemuserid else None

    @staticmethod
    def resolve_email(obj):
        return obj.systemuserid.emailaddress1 if obj.systemuserid else None

    @staticmethod
    def resolve_systemuserid(obj):
        return obj.systemuserid_id


class CreateTeamMemberDto(Schema):
    """DTO for adding a team member."""
    projectid: UUID
    systemuserid: UUID
    role: str


class UpdateTeamMemberDto(Schema):
    """DTO for updating a team member."""
    role: Optional[str] = None


# ============================================================================
# ProjectZone Schemas
# ============================================================================

class ProjectZoneSchema(ModelSchema):
    """Full zone response schema."""

    class Meta:
        model = ProjectZone
        fields = ['zoneid', 'projectid', 'name', 'prefix', 'description',
                  'statecode', 'sortorder', 'createdon', 'modifiedon']


class CreateZoneDto(Schema):
    """DTO for creating a zone."""
    projectid: UUID
    name: str
    prefix: str
    description: Optional[str] = None
    sortorder: Optional[int] = None


class UpdateZoneDto(Schema):
    """DTO for updating a zone."""
    name: Optional[str] = None
    prefix: Optional[str] = None
    description: Optional[str] = None
    statecode: Optional[int] = None
    sortorder: Optional[int] = None


# ============================================================================
# ProjectSupplier Schemas
# ============================================================================

class ProjectSupplierSchema(ModelSchema):
    """Full supplier response schema."""

    class Meta:
        model = ProjectSupplier
        fields = ['projectsupplierid', 'projectid', 'accountid', 'suppliernumber',
                  'rfc', 'businessname', 'statecode', 'notes', 'createdon', 'modifiedon']


class CreateSupplierDto(Schema):
    """DTO for adding a supplier to a project."""
    projectid: UUID
    accountid: Optional[UUID] = None
    rfc: str
    businessname: str
    notes: Optional[str] = None
    create_account: bool = False


# ============================================================================
# ConstructionProject Schemas
# ============================================================================

class ConstructionProjectSchema(ModelSchema):
    """Full project response schema with computed fields."""
    state_name: Optional[str] = None
    ownername: Optional[str] = None
    accountname: Optional[str] = None
    opportunityname: Optional[str] = None
    teammembers: List[ProjectTeamMemberSchema] = []
    advancebond: Optional[ProjectBondSchema] = None
    completionbond: Optional[ProjectBondSchema] = None
    defectsbond: Optional[ProjectBondSchema] = None
    carinsurance: Optional[ProjectBondSchema] = None
    liabilityinsurance: Optional[ProjectBondSchema] = None

    class Meta:
        model = ConstructionProject
        fields = [
            'projectid', 'projectnumber', 'name', 'description', 'statecode',
            'accountid', 'opportunityid',
            'presentationdate', 'awarddate', 'startdate', 'contractenddate',
            'expectedenddate', 'durationmonths',
            'projecttype', 'biddingtype',
            'contractamount_notax', 'contractamount_withtax',
            'advancepayment_notax', 'advancepayment_withtax',
            'exchangerate_mxn_usd',
            'projectemail', 'emailconfigured', 'emailprotocol',
            'periodtype',
            'alertthreshold_warning', 'alertthreshold_critical', 'alertthreshold_exceeded',
            'ownerid', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_state_name(obj):
        try:
            return obj.state_name
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def resolve_ownername(obj):
        try:
            return obj.ownerid.fullname if obj.ownerid else None
        except AttributeError:
            return None

    @staticmethod
    def resolve_accountname(obj):
        try:
            return obj.accountid.name if obj.accountid else None
        except AttributeError:
            return None

    @staticmethod
    def resolve_opportunityname(obj):
        try:
            return obj.opportunityid.name if obj.opportunityid else None
        except AttributeError:
            return None

    @staticmethod
    def resolve_teammembers(obj):
        try:
            return list(obj.teammembers.all())
        except (AttributeError, Exception):
            return []

    @staticmethod
    def resolve_advancebond(obj):
        if obj.advancebond_amount is not None:
            return ProjectBondSchema(
                amount=obj.advancebond_amount,
                policycost=obj.advancebond_policycost,
                validitystartdate=obj.advancebond_validitystartdate,
                validityenddate=obj.advancebond_validityenddate,
            )
        return None

    @staticmethod
    def resolve_completionbond(obj):
        if obj.completionbond_amount is not None:
            return ProjectBondSchema(
                amount=obj.completionbond_amount,
                policycost=obj.completionbond_policycost,
                validitystartdate=obj.completionbond_validitystartdate,
                validityenddate=obj.completionbond_validityenddate,
            )
        return None

    @staticmethod
    def resolve_defectsbond(obj):
        if obj.defectsbond_amount is not None:
            return ProjectBondSchema(
                amount=obj.defectsbond_amount,
                policycost=obj.defectsbond_policycost,
                validitystartdate=obj.defectsbond_validitystartdate,
                validityenddate=obj.defectsbond_validityenddate,
            )
        return None

    @staticmethod
    def resolve_carinsurance(obj):
        if obj.carinsurance_amount is not None:
            return ProjectBondSchema(
                amount=obj.carinsurance_amount,
                policycost=obj.carinsurance_policycost,
                validitystartdate=obj.carinsurance_validitystartdate,
                validityenddate=obj.carinsurance_validityenddate,
            )
        return None

    @staticmethod
    def resolve_liabilityinsurance(obj):
        if obj.liabilityinsurance_amount is not None:
            return ProjectBondSchema(
                amount=obj.liabilityinsurance_amount,
                policycost=obj.liabilityinsurance_policycost,
                validitystartdate=obj.liabilityinsurance_validitystartdate,
                validityenddate=obj.liabilityinsurance_validityenddate,
            )
        return None


class CreateProjectDto(Schema):
    """DTO for creating a construction project."""
    name: str
    description: Optional[str] = None
    accountid: UUID
    opportunityid: Optional[UUID] = None
    presentationdate: Optional[date] = None
    awarddate: Optional[date] = None
    startdate: date
    contractenddate: date
    expectedenddate: Optional[date] = None
    durationmonths: int
    projecttype: int
    biddingtype: int
    contractamount_notax: Decimal
    contractamount_withtax: Decimal
    advancepayment_notax: Optional[Decimal] = None
    advancepayment_withtax: Optional[Decimal] = None
    exchangerate_mxn_usd: Optional[Decimal] = None
    advancebond: Optional[ProjectBondDto] = None
    completionbond: Optional[ProjectBondDto] = None
    defectsbond: Optional[ProjectBondDto] = None
    carinsurance: Optional[ProjectBondDto] = None
    liabilityinsurance: Optional[ProjectBondDto] = None
    projectemail: Optional[str] = None
    emailprotocol: Optional[int] = None
    periodtype: int = 0
    alertthreshold_warning: Optional[Decimal] = None
    alertthreshold_critical: Optional[Decimal] = None
    alertthreshold_exceeded: Optional[Decimal] = None
    ownerid: Optional[UUID] = None


class UpdateProjectDto(Schema):
    """DTO for updating a construction project."""
    name: Optional[str] = None
    description: Optional[str] = None
    statecode: Optional[int] = None
    accountid: Optional[UUID] = None
    opportunityid: Optional[UUID] = None
    presentationdate: Optional[date] = None
    awarddate: Optional[date] = None
    startdate: Optional[date] = None
    contractenddate: Optional[date] = None
    expectedenddate: Optional[date] = None
    durationmonths: Optional[int] = None
    projecttype: Optional[int] = None
    biddingtype: Optional[int] = None
    contractamount_notax: Optional[Decimal] = None
    contractamount_withtax: Optional[Decimal] = None
    advancepayment_notax: Optional[Decimal] = None
    advancepayment_withtax: Optional[Decimal] = None
    exchangerate_mxn_usd: Optional[Decimal] = None
    advancebond: Optional[ProjectBondDto] = None
    completionbond: Optional[ProjectBondDto] = None
    defectsbond: Optional[ProjectBondDto] = None
    carinsurance: Optional[ProjectBondDto] = None
    liabilityinsurance: Optional[ProjectBondDto] = None
    projectemail: Optional[str] = None
    emailconfigured: Optional[bool] = None
    emailprotocol: Optional[int] = None
    periodtype: Optional[int] = None
    alertthreshold_warning: Optional[Decimal] = None
    alertthreshold_critical: Optional[Decimal] = None
    alertthreshold_exceeded: Optional[Decimal] = None


# ============================================================================
# ProjectRisk Schemas
# ============================================================================

class ProjectRiskSchema(ModelSchema):
    """Full risk response schema."""

    class Meta:
        model = ProjectRisk
        fields = [
            'riskid', 'projectid', 'description',
            'production_variance', 'cost_variance', 'result_variance',
            'statuscode', 'createdon', 'modifiedon',
        ]


class CreateRiskDto(Schema):
    """DTO for creating a project risk."""
    projectid: UUID
    description: str
    production_variance: Optional[Decimal] = Decimal('0')
    cost_variance: Optional[Decimal] = Decimal('0')
    result_variance: Optional[Decimal] = Decimal('0')


class UpdateRiskDto(Schema):
    """DTO for updating a project risk."""
    description: Optional[str] = None
    production_variance: Optional[Decimal] = None
    cost_variance: Optional[Decimal] = None
    result_variance: Optional[Decimal] = None
    statuscode: Optional[int] = None


# ============================================================================
# ProjectAssetUsage Schemas
# ============================================================================

class ProjectAssetUsageSchema(ModelSchema):
    """Full asset usage response schema."""
    category_label: Optional[str] = None

    class Meta:
        model = ProjectAssetUsage
        fields = [
            'assetusageid', 'projectid', 'category', 'description',
            'plannedamount', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_category_label(obj):
        try:
            return AssetCategoryCode(obj.category).label
        except ValueError:
            return None


class CreateAssetUsageDto(Schema):
    """DTO for creating a project asset usage."""
    projectid: UUID
    category: int
    description: str
    plannedamount: Optional[Decimal] = Decimal('0')


class UpdateAssetUsageDto(Schema):
    """DTO for updating a project asset usage."""
    category: Optional[int] = None
    description: Optional[str] = None
    plannedamount: Optional[Decimal] = None


# ============================================================================
# Executive Summary Schemas
# ============================================================================

class BondSummarySchema(Schema):
    amount: Optional[Decimal] = None
    policycost: Optional[Decimal] = None
    validity_start: Optional[date] = None
    validity_end: Optional[date] = None


class ProjectInfoSchema(Schema):
    name: str
    client: Optional[str] = None
    presentation_date: Optional[date] = None
    award_date: Optional[date] = None
    start_date: Optional[date] = None
    project_type: Optional[int] = None
    bidding_type: Optional[int] = None
    contract_amount_notax: Decimal
    contract_amount_withtax: Decimal
    advance_payment_notax: Optional[Decimal] = None
    advance_payment_withtax: Optional[Decimal] = None
    advance_bond: Optional[BondSummarySchema] = None
    completion_bond: Optional[BondSummarySchema] = None
    defects_bond: Optional[BondSummarySchema] = None
    car_insurance: Optional[BondSummarySchema] = None
    liability_insurance: Optional[BondSummarySchema] = None


class AdvanceSummarySchema(Schema):
    amortized_notax: Decimal
    pending_notax: Decimal
    amortized_net: Decimal
    pending_net: Decimal
    last_updated_period: Optional[str] = None


class CertificationSummarySchema(Schema):
    invoiced_notax: Decimal
    debt_notax: Decimal
    invoiced_net: Decimal
    debt_net: Decimal
    oldest_overdue_days: int
    last_updated_period: Optional[str] = None


class GuaranteeSummarySchema(Schema):
    accumulated_notax: Decimal
    paid_notax: Decimal
    accumulated_net: Decimal
    paid_net: Decimal
    last_updated_period: Optional[str] = None


class ProductionSummarySchema(Schema):
    accumulated: Decimal
    estimated: Decimal
    executed_unestimated: Decimal


class ResultSummarySchema(Schema):
    planned: Decimal
    actual: Decimal
    variance_pct: Decimal


class CurrentStatusSchema(Schema):
    advance: AdvanceSummarySchema
    certification: CertificationSummarySchema
    guarantee_retention: GuaranteeSummarySchema
    production: ProductionSummarySchema
    result: ResultSummarySchema


class MainItemSchema(Schema):
    name: str
    study: Decimal
    contract: Decimal
    accumulated: Decimal
    type: str


class CategoryBreakdownSchema(Schema):
    name: str
    costtype: int
    study: Decimal
    accumulated: Decimal
    pending: Decimal
    deviation_ratio: Decimal


class FamilyRollupSchema(Schema):
    study: Decimal
    current_contract: Decimal
    accumulated: Decimal
    pending: Decimal
    deviation_ratio: Optional[Decimal] = None


class ProductionRollupSchema(Schema):
    study: Decimal
    current_contract: Decimal
    accumulated: Decimal
    pending: Decimal


class ResultByFamilySchema(Schema):
    direct_cost: FamilyRollupSchema
    indirect_cost: FamilyRollupSchema
    production: ProductionRollupSchema
    by_category: List[CategoryBreakdownSchema]


class TechnicalEconomicSchema(Schema):
    main_items: List[MainItemSchema]
    result_by_family: ResultByFamilySchema


class RiskSummarySchema(Schema):
    riskid: UUID
    description: str
    production_variance: Decimal
    cost_variance: Decimal
    result_variance: Decimal
    statuscode: int


class AssetUsageSummarySchema(Schema):
    assetusageid: UUID
    category: int
    description: str
    planned: Decimal
    accumulated_actual: Decimal
    pending: Decimal
    deviation_pct: Decimal


class ExecutiveSummarySchema(Schema):
    project_info: ProjectInfoSchema
    current_status: CurrentStatusSchema
    technical_economic: TechnicalEconomicSchema
    risks: List[RiskSummarySchema]
    asset_usages: List[AssetUsageSummarySchema]
