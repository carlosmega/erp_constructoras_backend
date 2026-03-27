"""
Product business logic services.

Phase 11 Implementation: Product Catalog Management
"""

from django.db.models import Sum, Q, F
from django.shortcuts import get_object_or_404
from decimal import Decimal
from uuid import UUID

from apps.products.models import Product, PriceList, PriceListItem, ProductStateCode
from apps.products.schemas import CreateProductDto, UpdateProductDto, CreatePriceListDto, UpdatePriceListDto, CreatePriceListItemDto
from apps.users.models import SystemUser
from core.exceptions import ValidationError, PermissionDenied
from core.permissions import can_modify_record
from apps.audit.services import audit_action


class ProductService:
    """Business logic for Product operations."""

    @staticmethod
    @audit_action(action='create', entity='product')
    def create_product(payload: CreateProductDto, user: SystemUser) -> Product:
        """Create a new product."""
        # Validate product number uniqueness
        if payload.productnumber and Product.objects.filter(productnumber=payload.productnumber).exists():
            raise ValidationError(f"Product with number '{payload.productnumber}' already exists")

        # Create product
        product = Product.objects.create(
            name=payload.name,
            productnumber=payload.productnumber,
            description=payload.description,
            productstructure=payload.productstructure,
            producttypecode=payload.producttypecode,
            price=payload.price,
            standardcost=payload.standardcost,
            currentcost=payload.currentcost,
            stockvolume=payload.stockvolume,
            stockweight=payload.stockweight,
            quantityonhand=payload.quantityonhand or Decimal('0'),
            quantityallocated=payload.quantityallocated or Decimal('0'),
            vendorid=payload.vendorid,
            vendorpartnumber=payload.vendorpartnumber,
            vendorname=payload.vendorname,
            size=payload.size,
            color=payload.color,
            style=payload.style,
            suppliername=payload.suppliername,
            parentproductid_id=payload.parentproductid,
            createdby=user,
            modifiedby=user
        )

        return product

    @staticmethod
    def get_product_by_id(product_id: UUID, user: SystemUser) -> Product:
        """Get a product by ID."""
        product = get_object_or_404(Product, productid=product_id)
        return product

    @staticmethod
    @audit_action(action='update', entity='product', record_arg='product_id')
    def update_product(product_id: UUID, payload: UpdateProductDto, user: SystemUser) -> Product:
        """Update a product."""
        product = get_object_or_404(Product, productid=product_id)

        # Update fields
        update_data = payload.dict(exclude_unset=True)

        # Validate product number uniqueness
        if 'productnumber' in update_data and update_data['productnumber']:
            if Product.objects.filter(productnumber=update_data['productnumber']).exclude(productid=product_id).exists():
                raise ValidationError(f"Product with number '{update_data['productnumber']}' already exists")

        for field, value in update_data.items():
            if field == 'parentproductid':
                setattr(product, f'{field}_id', value)
            else:
                setattr(product, field, value)

        product.modifiedby = user
        product.save()

        return product

    @staticmethod
    @audit_action(action='delete', entity='product', record_arg='product_id')
    def delete_product(product_id: UUID, user: SystemUser):
        """Delete a product (soft delete by setting to inactive)."""
        product = get_object_or_404(Product, productid=product_id)

        # Soft delete: set to inactive
        product.statecode = ProductStateCode.INACTIVE
        product.modifiedby = user
        product.save()

    @staticmethod
    def get_product_stats(user: SystemUser):
        """Get product inventory statistics."""
        queryset = Product.objects.all()

        total = queryset.count()
        active = queryset.filter(statecode=ProductStateCode.ACTIVE).count()
        inactive = queryset.filter(statecode=ProductStateCode.INACTIVE).count()

        # Calculate total inventory value (quantity * price)
        inventory_value = queryset.filter(
            statecode=ProductStateCode.ACTIVE,
            quantityonhand__isnull=False,
            price__isnull=False
        ).aggregate(
            total=Sum(F('quantityonhand') * F('price'))
        )['total'] or Decimal('0')

        # Low stock products (less than 10 units)
        low_stock = queryset.filter(
            statecode=ProductStateCode.ACTIVE,
            quantityonhand__lt=10
        ).count()

        return {
            'total_products': total,
            'active_products': active,
            'inactive_products': inactive,
            'total_inventory_value': inventory_value,
            'low_stock_products': low_stock
        }


class PriceListService:
    """Business logic for PriceList operations."""

    @staticmethod
    def create_pricelist(payload: CreatePriceListDto, user: SystemUser) -> PriceList:
        """Create a new price list."""
        pricelist = PriceList.objects.create(
            name=payload.name,
            description=payload.description,
            begindate=payload.begindate,
            enddate=payload.enddate
        )
        return pricelist

    @staticmethod
    def get_pricelist_by_id(pricelist_id: UUID, user: SystemUser) -> PriceList:
        """Get a price list by ID."""
        pricelist = get_object_or_404(PriceList, pricelevelid=pricelist_id)
        return pricelist

    @staticmethod
    def update_pricelist(pricelist_id: UUID, payload: UpdatePriceListDto, user: SystemUser) -> PriceList:
        """Update a price list."""
        pricelist = get_object_or_404(PriceList, pricelevelid=pricelist_id)

        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(pricelist, field, value)

        pricelist.save()
        return pricelist

    @staticmethod
    def delete_pricelist(pricelist_id: UUID, user: SystemUser):
        """Delete a price list."""
        pricelist = get_object_or_404(PriceList, pricelevelid=pricelist_id)
        pricelist.delete()


class PriceListItemService:
    """Business logic for PriceListItem operations."""

    @staticmethod
    def create_pricelist_item(payload: CreatePriceListItemDto, user: SystemUser) -> PriceListItem:
        """Create a new price list item."""
        # Validate price list and product exist
        pricelist = get_object_or_404(PriceList, pricelevelid=payload.pricelevelid)
        product = get_object_or_404(Product, productid=payload.productid)

        # Check if item already exists
        if PriceListItem.objects.filter(pricelevelid=pricelist, productid=product).exists():
            raise ValidationError(f"Price for product '{product.name}' already exists in price list '{pricelist.name}'")

        item = PriceListItem.objects.create(
            pricelevelid=pricelist,
            productid=product,
            amount=payload.amount
        )

        return item

    @staticmethod
    def get_pricelist_item_by_id(item_id: UUID, user: SystemUser) -> PriceListItem:
        """Get a price list item by ID."""
        item = get_object_or_404(PriceListItem, productpricelevelid=item_id)
        return item

    @staticmethod
    def update_pricelist_item(item_id: UUID, payload, user: SystemUser) -> PriceListItem:
        """Update a price list item."""
        item = get_object_or_404(PriceListItem, productpricelevelid=item_id)
        item.amount = payload.amount
        item.save()
        return item

    @staticmethod
    def delete_pricelist_item(item_id: UUID, user: SystemUser):
        """Delete a price list item."""
        item = get_object_or_404(PriceListItem, productpricelevelid=item_id)
        item.delete()
