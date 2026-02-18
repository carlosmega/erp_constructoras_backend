"""
Opportunity API schemas (DTOs).
Phase 6 Implementation
"""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from apps.opportunities.models import Opportunity


class OpportunitySchema(ModelSchema):
    """Full Opportunity response schema."""
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    stage_name: Optional[str] = None
    owner_name: Optional[str] = None
    weighted_revenue: Optional[Decimal] = None

    class Meta:
        model = Opportunity
        fields = '__all__'

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_stage_name(obj):
        return obj.stage_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_weighted_revenue(obj):
        return obj.weighted_revenue


class CreateOpportunityDto(Schema):
    """DTO for creating opportunity."""
    name: str
    description: Optional[str] = None
    customername: Optional[str] = None
    estimatedrevenue: Optional[Decimal] = None
    estimatedclosedate: Optional[date] = None
    salesstage: Optional[int] = 0
    probability: Optional[int] = 0
    originatingleadid: Optional[UUID] = None
    ownerid: Optional[UUID] = None


class UpdateOpportunityDto(Schema):
    """DTO for updating opportunity."""
    name: Optional[str] = None
    description: Optional[str] = None
    customername: Optional[str] = None
    accountid: Optional[UUID] = None  # B2B customer reference
    contactid: Optional[UUID] = None  # B2C customer reference
    estimatedrevenue: Optional[Decimal] = None
    estimatedclosedate: Optional[date] = None
    salesstage: Optional[int] = None
    probability: Optional[int] = None
    statuscode: Optional[int] = None


class CloseOpportunityDto(Schema):
    """DTO for closing opportunity (Win/Loss)."""
    status: int  # 3=Won, 4=Canceled, 5=Out-Sold
    actualrevenue: Optional[Decimal] = None
    actualclosedate: Optional[date] = None
    closingnotes: Optional[str] = None


class OpportunityStatsSchema(Schema):
    """DTO for opportunity statistics."""
    total_opportunities: int
    open_opportunities: int
    won_opportunities: int
    lost_opportunities: int
    total_estimated_revenue: Optional[Decimal] = None
    total_actual_revenue: Optional[Decimal] = None
    total_weighted_revenue: Optional[Decimal] = None
    avg_probability: Optional[float] = None
    win_rate: Optional[float] = None
