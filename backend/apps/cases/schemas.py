"""
Case API schemas (DTOs).

Defines request/response schemas for Case API endpoints using Django Ninja.
"""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from apps.cases.models import Case


# ============================================================================
# Response Schemas
# ============================================================================

class CaseSchema(ModelSchema):
    """
    Full Case response schema.
    """
    # Computed/display fields
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    priority_name: Optional[str] = None
    origin_name: Optional[str] = None
    type_name: Optional[str] = None
    customer_name: Optional[str] = None
    customerid: Optional[str] = None
    customeridtype: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = Case
        fields = [
            'incidentid',
            'title',
            'description',
            'ticketnumber',
            'casetypecode',
            'prioritycode',
            'caseorigincode',
            'statecode',
            'statuscode',
            'accountid',
            'contactid',
            'primarycontactid',
            'productid',
            'firstresponsesent',
            'resolutiontype',
            'resolutionsummary',
            'resolvedon',
            'ownerid',
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
    def resolve_priority_name(obj):
        return obj.priority_name

    @staticmethod
    def resolve_origin_name(obj):
        return obj.origin_name

    @staticmethod
    def resolve_type_name(obj):
        return obj.type_name

    @staticmethod
    def resolve_customer_name(obj):
        return obj.customer_name

    @staticmethod
    def resolve_customerid(obj):
        from core.customers import get_customerid
        return get_customerid(obj)

    @staticmethod
    def resolve_customeridtype(obj):
        from core.customers import get_customeridtype
        return get_customeridtype(obj)

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CaseListItemSchema(ModelSchema):
    """
    Simplified Case schema for list views (performance optimization).
    """
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    priority_name: Optional[str] = None
    origin_name: Optional[str] = None
    customer_name: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = Case
        fields = [
            'incidentid',
            'title',
            'ticketnumber',
            'casetypecode',
            'prioritycode',
            'caseorigincode',
            'statecode',
            'statuscode',
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
    def resolve_priority_name(obj):
        return obj.priority_name

    @staticmethod
    def resolve_origin_name(obj):
        return obj.origin_name

    @staticmethod
    def resolve_customer_name(obj):
        return obj.customer_name

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


# ============================================================================
# Request Schemas (DTOs)
# ============================================================================

class CreateCaseDto(Schema):
    """
    DTO for creating a new case.
    """
    # Required fields
    title: str
    customerid: UUID
    customerid_type: str  # 'account' or 'contact'
    caseorigincode: int
    ownerid: UUID

    # Optional fields
    description: Optional[str] = None
    primarycontactid: Optional[UUID] = None
    casetypecode: Optional[int] = None
    prioritycode: int = 2  # default Normal
    productid: Optional[UUID] = None


class UpdateCaseDto(Schema):
    """
    DTO for updating an existing case.
    All fields are optional for partial updates.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    casetypecode: Optional[int] = None
    prioritycode: Optional[int] = None
    primarycontactid: Optional[UUID] = None
    productid: Optional[UUID] = None
    ownerid: Optional[UUID] = None


class ResolveCaseDto(Schema):
    """
    DTO for resolving a case.
    """
    resolutiontype: str
    resolutionsummary: str
    billabletime: Optional[int] = None


class CancelCaseDto(Schema):
    """
    DTO for cancelling a case.
    """
    reason: Optional[str] = None
