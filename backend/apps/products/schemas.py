"""
Product API schemas (DTOs).

Phase 11 Implementation: Product Catalog Management
"""

from ninja import ModelSchema, Schema
from typing import Optional
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID

from apps.products.models import Product, PriceList, PriceListItem


# ============================================================================
# Product Schemas
# ============================================================================

class ProductSchema(ModelSchema):
    """Full product response schema."""
    state_name: Optional[str] = None
    structure_name: Optional[str] = None
    type_name: Optional[str] = None
    available_quantity: Optional[Decimal] = None

    class Meta:
        model = Product
        fields = '__all__'


class ProductListItemSchema(ModelSchema):
    """Simplified product schema for list views."""
    state_name: Optional[str] = None
    available_quantity: Optional[Decimal] = None

    class Meta:
        model = Product
        fields = [
            'productid', 'name', 'productnumber', 'statecode',
            'price', 'standardcost', 'quantityonhand', 'quantityallocated',
            'createdon'
        ]


class CreateProductDto(Schema):
    """DTO for creating a new product."""
    name: str
    productnumber: Optional[str] = None
    description: Optional[str] = None
    productstructure: Optional[int] = 1
    producttypecode: Optional[int] = 1
    price: Optional[Decimal] = None
    standardcost: Optional[Decimal] = None
    currentcost: Optional[Decimal] = None
    stockvolume: Optional[Decimal] = None
    stockweight: Optional[Decimal] = None
    quantityonhand: Optional[Decimal] = None
    quantityallocated: Optional[Decimal] = None
    vendorid: Optional[str] = None
    vendorpartnumber: Optional[str] = None
    vendorname: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    style: Optional[str] = None
    suppliername: Optional[str] = None
    parentproductid: Optional[UUID] = None


class UpdateProductDto(Schema):
    """DTO for updating a product."""
    name: Optional[str] = None
    productnumber: Optional[str] = None
    description: Optional[str] = None
    statecode: Optional[int] = None
    productstructure: Optional[int] = None
    producttypecode: Optional[int] = None
    price: Optional[Decimal] = None
    standardcost: Optional[Decimal] = None
    currentcost: Optional[Decimal] = None
    stockvolume: Optional[Decimal] = None
    stockweight: Optional[Decimal] = None
    quantityonhand: Optional[Decimal] = None
    quantityallocated: Optional[Decimal] = None
    vendorid: Optional[str] = None
    vendorpartnumber: Optional[str] = None
    vendorname: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    style: Optional[str] = None
    suppliername: Optional[str] = None
    parentproductid: Optional[UUID] = None


class ProductStatsSchema(Schema):
    """Product inventory and stats."""
    total_products: int
    active_products: int
    inactive_products: int
    total_inventory_value: Decimal
    low_stock_products: int


# ============================================================================
# PriceList Schemas
# ============================================================================

class PriceListSchema(ModelSchema):
    """Full price list response schema."""
    is_active: bool

    class Meta:
        model = PriceList
        fields = '__all__'


class CreatePriceListDto(Schema):
    """DTO for creating a new price list."""
    name: str
    description: Optional[str] = None
    begindate: Optional[date] = None
    enddate: Optional[date] = None


class UpdatePriceListDto(Schema):
    """DTO for updating a price list."""
    name: Optional[str] = None
    description: Optional[str] = None
    begindate: Optional[date] = None
    enddate: Optional[date] = None
    statecode: Optional[int] = None


# ============================================================================
# PriceListItem Schemas
# ============================================================================

class PriceListItemSchema(ModelSchema):
    """Full price list item response schema."""
    product_name: Optional[str] = None
    pricelist_name: Optional[str] = None

    class Meta:
        model = PriceListItem
        fields = '__all__'


class CreatePriceListItemDto(Schema):
    """DTO for creating a new price list item."""
    pricelevelid: UUID
    productid: UUID
    amount: Decimal


class UpdatePriceListItemDto(Schema):
    """DTO for updating a price list item."""
    amount: Decimal
