"""
Product API routers.

Phase 11 Implementation: Product Catalog Management
"""

from ninja import Router
from django.http import HttpRequest
from typing import List
from uuid import UUID

from apps.products.services import ProductService, PriceListService, PriceListItemService
from apps.products.schemas import (
    ProductSchema, ProductListItemSchema, CreateProductDto, UpdateProductDto,
    ProductStatsSchema, PriceListSchema, CreatePriceListDto, UpdatePriceListDto,
    PriceListItemSchema, CreatePriceListItemDto, UpdatePriceListItemDto
)
from core.permissions import require_permission, Permission, filter_by_ownership

products_router = Router(tags=['Products'])
pricelists_router = Router(tags=['Price Lists'])


# ============================================================================
# Product Endpoints
# ============================================================================

@products_router.get('/', response=List[ProductListItemSchema])
@require_permission(Permission.PRODUCT_READ)
def list_products(request: HttpRequest, state: int = None, search: str = None, low_inventory: int = None, min_price: float = None, max_price: float = None):
    """
    List all products with optional filtering.

    Filters:
    - state: Filter by statecode (0=Active, 1=Inactive)
    - search: Search in name or product number
    - low_inventory: Filter products with quantityonhand below threshold
    - min_price: Filter products with price >= min_price
    - max_price: Filter products with price <= max_price
    """
    from apps.products.models import Product

    queryset = Product.objects.all()

    if state is not None:
        queryset = queryset.filter(statecode=state)
    if search:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(productnumber__icontains=search)
        )
    if low_inventory is not None:
        queryset = queryset.filter(quantityonhand__lt=low_inventory)
    if min_price is not None:
        queryset = queryset.filter(price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)

    return list(queryset)


@products_router.post('/', response={201: ProductSchema})
@require_permission(Permission.PRODUCT_CREATE)
def create_product(request: HttpRequest, payload: CreateProductDto):
    """Create a new product."""
    product = ProductService.create_product(payload, request.user)
    return 201, product


@products_router.get('/{product_id}', response=ProductSchema)
@require_permission(Permission.PRODUCT_READ)
def get_product(request: HttpRequest, product_id: UUID):
    """Get a single product by ID."""
    product = ProductService.get_product_by_id(product_id, request.user)
    return product


@products_router.patch('/{product_id}', response=ProductSchema)
@require_permission(Permission.PRODUCT_UPDATE)
def update_product(request: HttpRequest, product_id: UUID, payload: UpdateProductDto):
    """Update a product."""
    product = ProductService.update_product(product_id, payload, request.user)
    return product


@products_router.delete('/{product_id}', response={204: None})
@require_permission(Permission.PRODUCT_DELETE)
def delete_product(request: HttpRequest, product_id: UUID):
    """Delete a product (sets to inactive)."""
    ProductService.delete_product(product_id, request.user)
    return 204, None


@products_router.post('/{product_id}/activate', response=ProductSchema)
@require_permission(Permission.PRODUCT_UPDATE)
def activate_product(request: HttpRequest, product_id: UUID):
    """Activate a product (set statecode to Active)."""
    from apps.products.models import Product
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(Product, productid=product_id)
    product.statecode = 0  # Active
    product.save()
    return product


@products_router.post('/{product_id}/deactivate', response=ProductSchema)
@require_permission(Permission.PRODUCT_UPDATE)
def deactivate_product(request: HttpRequest, product_id: UUID):
    """Deactivate a product (set statecode to Inactive)."""
    from apps.products.models import Product
    from django.shortcuts import get_object_or_404
    product = get_object_or_404(Product, productid=product_id)
    product.statecode = 1  # Inactive
    product.save()
    return product


@products_router.get('/stats/summary', response=ProductStatsSchema)
@require_permission(Permission.PRODUCT_READ)
def get_product_stats(request: HttpRequest):
    """Get product inventory statistics."""
    stats = ProductService.get_product_stats(request.user)
    return stats


# ============================================================================
# Price List Endpoints
# ============================================================================

@pricelists_router.get('/', response=List[PriceListSchema])
@require_permission(Permission.PRODUCT_READ)
def list_pricelists(request: HttpRequest, state: int = None):
    """List all price lists."""
    from apps.products.models import PriceList

    queryset = PriceList.objects.all()

    if state is not None:
        queryset = queryset.filter(statecode=state)

    return list(queryset)


@pricelists_router.post('/', response={201: PriceListSchema})
@require_permission(Permission.PRODUCT_CREATE)
def create_pricelist(request: HttpRequest, payload: CreatePriceListDto):
    """Create a new price list."""
    pricelist = PriceListService.create_pricelist(payload, request.user)
    return 201, pricelist


@pricelists_router.get('/{pricelist_id}', response=PriceListSchema)
@require_permission(Permission.PRODUCT_READ)
def get_pricelist(request: HttpRequest, pricelist_id: UUID):
    """Get a single price list by ID."""
    pricelist = PriceListService.get_pricelist_by_id(pricelist_id, request.user)
    return pricelist


@pricelists_router.patch('/{pricelist_id}', response=PriceListSchema)
@require_permission(Permission.PRODUCT_UPDATE)
def update_pricelist(request: HttpRequest, pricelist_id: UUID, payload: UpdatePriceListDto):
    """Update a price list."""
    pricelist = PriceListService.update_pricelist(pricelist_id, payload, request.user)
    return pricelist


@pricelists_router.delete('/{pricelist_id}', response={204: None})
@require_permission(Permission.PRODUCT_DELETE)
def delete_pricelist(request: HttpRequest, pricelist_id: UUID):
    """Delete a price list."""
    PriceListService.delete_pricelist(pricelist_id, request.user)
    return 204, None


# ============================================================================
# Price List Item Endpoints
# ============================================================================

@pricelists_router.get('/{pricelist_id}/items', response=List[PriceListItemSchema])
@require_permission(Permission.PRODUCT_READ)
def list_pricelist_items(request: HttpRequest, pricelist_id: UUID):
    """List all items in a price list."""
    from apps.products.models import PriceListItem

    items = PriceListItem.objects.filter(pricelevelid=pricelist_id).select_related('productid', 'pricelevelid')
    return list(items)


@pricelists_router.post('/items', response={201: PriceListItemSchema})
@require_permission(Permission.PRODUCT_CREATE)
def create_pricelist_item(request: HttpRequest, payload: CreatePriceListItemDto):
    """Add a product to a price list."""
    item = PriceListItemService.create_pricelist_item(payload, request.user)
    return 201, item


@pricelists_router.patch('/items/{item_id}', response=PriceListItemSchema)
@require_permission(Permission.PRODUCT_UPDATE)
def update_pricelist_item(request: HttpRequest, item_id: UUID, payload: UpdatePriceListItemDto):
    """Update a price list item."""
    item = PriceListItemService.update_pricelist_item(item_id, payload, request.user)
    return item


@pricelists_router.delete('/items/{item_id}', response={204: None})
@require_permission(Permission.PRODUCT_DELETE)
def delete_pricelist_item(request: HttpRequest, item_id: UUID):
    """Remove a product from a price list."""
    PriceListItemService.delete_pricelist_item(item_id, request.user)
    return 204, None
