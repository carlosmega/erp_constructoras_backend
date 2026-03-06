"""Account API schemas. Phase 7 Implementation"""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from decimal import Decimal
from apps.accounts.models import Account


class AccountSchema(ModelSchema):
    """Full Account response schema."""
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = Account
        fields = '__all__'

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateAccountDto(Schema):
    """DTO for creating account."""
    name: str
    accountnumber: Optional[str] = None
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    websiteurl: Optional[str] = None
    address1_line1: Optional[str] = None
    address1_city: Optional[str] = None
    address1_stateorprovince: Optional[str] = None
    address1_postalcode: Optional[str] = None
    address1_country: Optional[str] = None
    description: Optional[str] = None
    revenue: Optional[Decimal] = None
    numberofemployees: Optional[int] = None
    customertypecode: Optional[int] = None
    ownerid: Optional[UUID] = None


class AccountLookupSchema(Schema):
    """Lightweight account schema for supplier lookup."""
    accountid: UUID
    name: str
    customertypecode: Optional[int] = None
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None


class UpdateAccountDto(Schema):
    """DTO for updating account."""
    name: Optional[str] = None
    accountnumber: Optional[str] = None
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    websiteurl: Optional[str] = None
    address1_line1: Optional[str] = None
    address1_city: Optional[str] = None
    address1_stateorprovince: Optional[str] = None
    address1_postalcode: Optional[str] = None
    address1_country: Optional[str] = None
    description: Optional[str] = None
    revenue: Optional[Decimal] = None
    numberofemployees: Optional[int] = None
    customertypecode: Optional[int] = None
    statuscode: Optional[int] = None
