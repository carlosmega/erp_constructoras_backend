"""Budget API schemas (DTOs)."""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date

from apps.budgets.models import CostCategory, ImputationCode, ImputationPeriod


# =============================================================================
# CostCategory Schemas
# =============================================================================

class CostCategorySchema(ModelSchema):
    """Full CostCategory response schema."""

    class Meta:
        model = CostCategory
        fields = '__all__'


class CreateCostCategoryDto(Schema):
    """DTO for creating a cost category."""
    projectid: UUID
    costtype: int
    code: str
    name: str
    description: Optional[str] = None
    sortorder: Optional[int] = 0


class UpdateCostCategoryDto(Schema):
    """DTO for updating a cost category."""
    name: Optional[str] = None
    description: Optional[str] = None
    sortorder: Optional[int] = None
    statecode: Optional[int] = None


# =============================================================================
# ImputationCode Schemas
# =============================================================================

class ImputationCodeSchema(ModelSchema):
    """Full ImputationCode response schema."""
    categorycode: Optional[str] = None
    categoryname: Optional[str] = None
    zonename: Optional[str] = None

    class Meta:
        model = ImputationCode
        fields = '__all__'

    @staticmethod
    def resolve_categorycode(obj):
        return obj.categoryid.code if obj.categoryid else None

    @staticmethod
    def resolve_categoryname(obj):
        return obj.categoryid.name if obj.categoryid else None

    @staticmethod
    def resolve_zonename(obj):
        return obj.zoneid.name if obj.zoneid else None


class CreateImputationCodeDto(Schema):
    """DTO for creating an imputation code."""
    projectid: UUID
    categoryid: UUID
    zoneid: Optional[UUID] = None
    costtype: int
    name: str
    description: Optional[str] = None
    estimatedsupplier: Optional[str] = None
    unitcost: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    executionmonths: Optional[int] = None
    totalbudget: Decimal = Decimal('0')
    # Personnel fields (C1 only)
    personnelname: Optional[str] = None
    personnelrole: Optional[str] = None
    personneltype: Optional[int] = None
    monthlycost: Optional[Decimal] = None
    units: Optional[Decimal] = None


class UpdateImputationCodeDto(Schema):
    """DTO for updating an imputation code."""
    name: Optional[str] = None
    description: Optional[str] = None
    estimatedsupplier: Optional[str] = None
    unitcost: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    executionmonths: Optional[int] = None
    totalbudget: Optional[Decimal] = None
    personnelname: Optional[str] = None
    personnelrole: Optional[str] = None
    personneltype: Optional[int] = None
    monthlycost: Optional[Decimal] = None
    units: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# ImputationPeriod Schemas
# =============================================================================

class ImputationPeriodSchema(ModelSchema):
    """Full ImputationPeriod response schema."""

    class Meta:
        model = ImputationPeriod
        fields = '__all__'


class CreateImputationPeriodDto(Schema):
    """DTO for creating an imputation period."""
    projectid: UUID
    periodtype: int
    year: int
    month: int
    periodnumber: int
    label: str
    startdate: date
    enddate: date
    sortorder: Optional[int] = 0


class ExtendPeriodsDto(Schema):
    """DTO for extending periods by N months."""
    months: int
