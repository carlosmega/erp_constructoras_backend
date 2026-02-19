"""
Quote schemas (DTOs) for API requests and responses.

Phase 8 Implementation: Quote Management
"""

from ninja import ModelSchema, Schema
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from apps.quotes.models import Quote, QuoteDetail


# ============ QuoteDetail Schemas ============

class QuoteDetailSchema(ModelSchema):
    """Full QuoteDetail response schema."""
    class Meta:
        model = QuoteDetail
        fields = [
            'quotedetailid', 'quoteid', 'productname', 'productdescription',
            'quantity', 'priceperunit', 'manualdiscountamount', 'tax',
            'baseamount', 'extendedamount', 'sequencenumber',
            'createdon', 'modifiedon'
        ]


class CreateQuoteDetailDto(Schema):
    """DTO for creating a quote detail line item."""
    productname: str
    productdescription: Optional[str] = None
    quantity: Decimal
    priceperunit: Decimal
    manualdiscountamount: Decimal = Decimal('0.00')
    tax: Decimal = Decimal('0.00')
    sequencenumber: int = 1


class UpdateQuoteDetailDto(Schema):
    """DTO for updating a quote detail."""
    productname: Optional[str] = None
    productdescription: Optional[str] = None
    quantity: Optional[Decimal] = None
    priceperunit: Optional[Decimal] = None
    manualdiscountamount: Optional[Decimal] = None
    tax: Optional[Decimal] = None
    sequencenumber: Optional[int] = None


# ============ Quote Schemas ============

class QuoteSchema(ModelSchema):
    """Full Quote response schema with nested details."""
    quote_details: List[QuoteDetailSchema] = []
    customer_name: Optional[str] = None
    customerid: Optional[str] = None
    customeridtype: Optional[str] = None

    class Meta:
        model = Quote
        fields = [
            'quoteid', 'name', 'quotenumber', 'opportunityid', 'accountid', 'contactid',
            'totalamount', 'totaldiscountamount', 'totaltax', 'totallineitemamount',
            'discountpercentage', 'effectivefrom', 'effectiveto', 'closedon',
            'statecode', 'statuscode', 'description', 'ownerid',
            'createdon', 'modifiedon', 'createdby', 'modifiedby'
        ]

    @staticmethod
    def resolve_customerid(obj):
        from core.customers import get_customerid
        return get_customerid(obj)

    @staticmethod
    def resolve_customeridtype(obj):
        from core.customers import get_customeridtype
        return get_customeridtype(obj)


class QuoteListItemSchema(ModelSchema):
    """Simplified Quote schema for list views."""
    customer_name: Optional[str] = None
    customerid: Optional[str] = None
    customeridtype: Optional[str] = None

    class Meta:
        model = Quote
        fields = [
            'quoteid', 'name', 'quotenumber', 'totalamount',
            'statecode', 'statuscode', 'effectiveto',
            'createdon', 'ownerid'
        ]

    @staticmethod
    def resolve_customerid(obj):
        from core.customers import get_customerid
        return get_customerid(obj)

    @staticmethod
    def resolve_customeridtype(obj):
        from core.customers import get_customeridtype
        return get_customeridtype(obj)


class CreateQuoteDto(Schema):
    """DTO for creating a new quote."""
    name: str
    opportunityid: Optional[UUID] = None
    customerid: Optional[UUID] = None
    customeridtype: Optional[str] = None  # 'account' or 'contact'
    discountpercentage: Decimal = Decimal('0.00')
    effectivefrom: Optional[date] = None
    effectiveto: Optional[date] = None
    description: Optional[str] = None
    ownerid: Optional[UUID] = None
    quote_details: List[CreateQuoteDetailDto] = []


class UpdateQuoteDto(Schema):
    """DTO for updating a quote."""
    name: Optional[str] = None
    discountpercentage: Optional[Decimal] = None
    effectivefrom: Optional[date] = None
    effectiveto: Optional[date] = None
    description: Optional[str] = None
    statecode: Optional[int] = None
    statuscode: Optional[int] = None


class ActivateQuoteDto(Schema):
    """DTO for activating a quote (making it ready for customer review)."""
    effectivefrom: Optional[date] = None
    effectiveto: Optional[date] = None


class CloseQuoteDto(Schema):
    """DTO for closing a quote (won/lost/canceled)."""
    statuscode: int  # 3=Won, 4=Lost, 5=Canceled
    closedon: Optional[datetime] = None
    description: Optional[str] = None  # Reason for closing


class ReviseQuoteDto(Schema):
    """DTO for creating a revised version of a quote."""
    name: str
    description: Optional[str] = None


class QuoteStatsSchema(Schema):
    """Statistics about quotes."""
    total_quotes: int
    draft_quotes: int
    active_quotes: int
    won_quotes: int
    closed_quotes: int
    total_value: Decimal
    won_value: Decimal
    win_rate: float  # Percentage


# ============ List Response Schemas ============

class QuoteListResponseSchema(Schema):
    """Paginated list of quotes."""
    items: List[QuoteListItemSchema]
    total: int
    page: int
    page_size: int
