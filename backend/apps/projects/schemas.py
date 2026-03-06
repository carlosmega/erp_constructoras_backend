"""Construction Project API schemas."""

from ninja import ModelSchema, Schema
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date
from apps.projects.models import (
    ConstructionProject, ProjectTeamMember, ProjectZone, ProjectSupplier,
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
        return obj.state_name

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_accountname(obj):
        return obj.accountid.name if obj.accountid else None

    @staticmethod
    def resolve_opportunityname(obj):
        return obj.opportunityid.name if obj.opportunityid else None

    @staticmethod
    def resolve_teammembers(obj):
        return list(obj.teammembers.all())

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
    projectemail: Optional[str] = None
    emailconfigured: Optional[bool] = None
    emailprotocol: Optional[int] = None
    periodtype: Optional[int] = None
    alertthreshold_warning: Optional[Decimal] = None
    alertthreshold_critical: Optional[Decimal] = None
    alertthreshold_exceeded: Optional[Decimal] = None
