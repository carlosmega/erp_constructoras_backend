"""
Lead API schemas (DTOs).

Defines request/response schemas for Lead API endpoints using Django Ninja.

Phase 5 Implementation (User Story 3)
"""

from ninja import ModelSchema, Schema
from pydantic import field_validator
from typing import Optional
from uuid import UUID
from datetime import date
from decimal import Decimal
from apps.leads.models import Lead, LeadStatusCode


# ============================================================================
# Response Schemas
# ============================================================================

class LeadSchema(ModelSchema):
    """
    Full Lead response schema.
    """
    # Computed/display fields
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    quality_name: Optional[str] = None
    source_name: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = Lead
        fields = [
            'leadid',
            'firstname',
            'lastname',
            'fullname',
            'emailaddress1',
            'telephone1',
            'mobilephone',
            'companyname',
            'jobtitle',
            'subject',
            'description',
            'leadqualitycode',
            'leadsourcecode',
            'statecode',
            'statuscode',
            'estimatedvalue',
            'estimatedclosedate',
            'ownerid',
            'qualifyingopportunityid',
            'createdon',
            'modifiedon',
            'createdby',
            'modifiedby',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_quality_name(obj):
        return obj.quality_name

    @staticmethod
    def resolve_source_name(obj):
        return obj.source_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class LeadListSchema(ModelSchema):
    """
    Simplified Lead schema for list views (performance optimization).
    """
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = Lead
        fields = [
            'leadid',
            'fullname',
            'emailaddress1',
            'telephone1',
            'companyname',
            'jobtitle',
            'subject',
            'leadqualitycode',
            'statecode',
            'statuscode',
            'estimatedvalue',
            'estimatedclosedate',
            'ownerid',
            'createdon',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


# ============================================================================
# Request Schemas (DTOs)
# ============================================================================

class CreateLeadDto(Schema):
    """
    DTO for creating a new lead.
    """
    # Required fields
    lastname: str

    # Optional personal information
    firstname: Optional[str] = None

    # Optional contact information
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    mobilephone: Optional[str] = None

    # Optional company information
    companyname: Optional[str] = None
    jobtitle: Optional[str] = None

    # Optional lead details
    subject: Optional[str] = None
    description: Optional[str] = None

    # Optional classification
    leadqualitycode: Optional[int] = None
    leadsourcecode: Optional[int] = None

    # Optional sales information
    estimatedvalue: Optional[Decimal] = None
    estimatedclosedate: Optional[date] = None

    # Owner (if not specified, will use current user)
    ownerid: Optional[UUID] = None


class UpdateLeadDto(Schema):
    """
    DTO for updating an existing lead.
    All fields are optional for partial updates.
    """
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    mobilephone: Optional[str] = None
    companyname: Optional[str] = None
    jobtitle: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    leadqualitycode: Optional[int] = None
    leadsourcecode: Optional[int] = None
    estimatedvalue: Optional[Decimal] = None
    estimatedclosedate: Optional[date] = None
    ownerid: Optional[UUID] = None
    statuscode: Optional[int] = None

    @field_validator('statuscode')
    @classmethod
    def validate_open_statuscode(cls, v):
        """Open leads may only transition between NEW and CONTACTED via this DTO.

        Qualify / disqualify transitions go through dedicated endpoints, so any
        other value here is a frontend bug.
        """
        if v is None:
            return v
        valid = {LeadStatusCode.NEW, LeadStatusCode.CONTACTED}
        if v not in valid:
            raise ValueError(
                f"statuscode must be {LeadStatusCode.NEW} (New) or "
                f"{LeadStatusCode.CONTACTED} (Contacted) for open leads; "
                "use the qualify/disqualify endpoints for other transitions."
            )
        return v


class QualifyLeadDto(Schema):
    """
    DTO for qualifying a lead (convert to Opportunity).
    Accepts camelCase field names matching frontend conventions.
    """
    # Account options (B2B)
    createAccount: bool = True
    existingAccountId: Optional[UUID] = None

    # Contact options
    createContact: bool = True
    existingContactId: Optional[UUID] = None

    # Opportunity details
    opportunityName: Optional[str] = None
    estimatedValue: Optional[Decimal] = None
    estimatedCloseDate: Optional[date] = None
    description: Optional[str] = None


class QualifyLeadResponseAccount(Schema):
    """Nested account info in qualify response."""
    accountid: str
    name: str


class QualifyLeadResponseContact(Schema):
    """Nested contact info in qualify response."""
    contactid: str
    fullname: str


class QualifyLeadResponseOpportunity(Schema):
    """Nested opportunity info in qualify response."""
    opportunityid: str
    name: str


class QualifyLeadResponse(Schema):
    """
    Response schema for lead qualification.
    Returns IDs and nested objects for created/linked entities.
    """
    leadId: str
    accountId: Optional[str] = None
    contactId: Optional[str] = None
    opportunityId: str
    account: Optional[QualifyLeadResponseAccount] = None
    contact: Optional[QualifyLeadResponseContact] = None
    opportunity: QualifyLeadResponseOpportunity


class DisqualifyLeadDto(Schema):
    """
    DTO for disqualifying a lead.
    Frontend sends just an optional reason string.
    """
    reason: Optional[str] = None


class LeadStatsSchema(Schema):
    """
    DTO for lead statistics (dashboard metrics).
    """
    total_leads: int
    open_leads: int
    qualified_leads: int
    disqualified_leads: int
    leads_by_quality: dict
    leads_by_source: dict
    total_estimated_value: Optional[Decimal] = None
    avg_estimated_value: Optional[Decimal] = None


# ============================================================================
# Filter Schema
# ============================================================================

class LeadFilterSchema(Schema):
    """
    DTO for filtering leads.
    """
    statecode: Optional[int] = None
    statuscode: Optional[int] = None
    leadqualitycode: Optional[int] = None
    leadsourcecode: Optional[int] = None
    ownerid: Optional[UUID] = None
    search: Optional[str] = None  # Search in fullname, email, company
    created_from: Optional[date] = None
    created_to: Optional[date] = None
