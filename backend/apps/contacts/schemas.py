"""Contact API schemas. Phase 7 Implementation"""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from pydantic import field_validator
from apps.contacts.models import Contact


class ContactSchema(ModelSchema):
    """Full Contact response schema."""
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    owner_name: Optional[str] = None
    company_name: Optional[str] = None

    class Meta:
        model = Contact
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

    @staticmethod
    def resolve_company_name(obj):
        return obj.company_name


class CreateContactDto(Schema):
    """DTO for creating contact."""
    firstname: Optional[str] = None
    lastname: str
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    mobilephone: Optional[str] = None
    jobtitle: Optional[str] = None
    parentcustomerid: Optional[UUID] = None
    address1_line1: Optional[str] = None
    address1_city: Optional[str] = None
    address1_stateorprovince: Optional[str] = None
    address1_postalcode: Optional[str] = None
    address1_country: Optional[str] = None
    description: Optional[str] = None
    ownerid: Optional[UUID] = None

    @field_validator('parentcustomerid', 'ownerid', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields."""
        if v == '' or v is None:
            return None
        return v


class UpdateContactDto(Schema):
    """DTO for updating contact."""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    emailaddress1: Optional[str] = None
    telephone1: Optional[str] = None
    mobilephone: Optional[str] = None
    jobtitle: Optional[str] = None
    parentcustomerid: Optional[UUID] = None
    address1_line1: Optional[str] = None
    address1_city: Optional[str] = None
    address1_stateorprovince: Optional[str] = None
    address1_postalcode: Optional[str] = None
    address1_country: Optional[str] = None
    description: Optional[str] = None
    statuscode: Optional[int] = None

    @field_validator('parentcustomerid', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for UUID fields."""
        if v == '' or v is None:
            return None
        return v
