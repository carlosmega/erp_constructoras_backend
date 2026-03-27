"""Unit tests for Product service layer."""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import date

from apps.products.models import Product, PriceList, PriceListItem, ProductStateCode
from apps.products.services import ProductService, PriceListService, PriceListItemService
from apps.products.schemas import (
    CreateProductDto,
    UpdateProductDto,
    CreatePriceListDto,
    UpdatePriceListDto,
    CreatePriceListItemDto,
)
from apps.products.tests.factories import ProductFactory, PriceListFactory, PriceListItemFactory
from core.exceptions import ValidationError


# ============================================================================
# ProductService Tests
# ============================================================================

@pytest.mark.unit
class TestCreateProduct:
    """Tests for ProductService.create_product."""

    def test_create_product_minimal(self, db, salesperson):
        """Creating a product with just a name should succeed."""
        dto = CreateProductDto(name='Basic Widget')
        product = ProductService.create_product(dto, salesperson)
        assert product.pk is not None
        assert product.name == 'Basic Widget'
        assert product.statecode == ProductStateCode.ACTIVE
        assert product.createdby == salesperson

    def test_create_product_with_all_fields(self, db, salesperson):
        """Creating a product with full details should persist all fields."""
        dto = CreateProductDto(
            name='Premium Widget',
            productnumber='SKU-PREM-001',
            description='A high-quality widget',
            price=Decimal('199.99'),
            standardcost=Decimal('80.00'),
            quantityonhand=Decimal('500'),
            quantityallocated=Decimal('50'),
            vendorname='Acme Corp',
            size='Large',
            color='Blue',
        )
        product = ProductService.create_product(dto, salesperson)
        assert product.name == 'Premium Widget'
        assert product.productnumber == 'SKU-PREM-001'
        assert product.price == Decimal('199.99')
        assert product.quantityonhand == Decimal('500')
        assert product.vendorname == 'Acme Corp'

    def test_create_product_duplicate_number_raises(self, db, salesperson):
        """Creating a product with a duplicate productnumber should raise ValidationError."""
        ProductFactory(productnumber='DUP-001')
        dto = CreateProductDto(name='Duplicate', productnumber='DUP-001')
        with pytest.raises(ValidationError, match="already exists"):
            ProductService.create_product(dto, salesperson)

    def test_create_product_null_number_allowed(self, db, salesperson):
        """Products without a productnumber should be allowed (no uniqueness check)."""
        dto1 = CreateProductDto(name='No SKU 1')
        dto2 = CreateProductDto(name='No SKU 2')
        p1 = ProductService.create_product(dto1, salesperson)
        p2 = ProductService.create_product(dto2, salesperson)
        assert p1.pk is not None
        assert p2.pk is not None


@pytest.mark.unit
class TestGetProductById:
    """Tests for ProductService.get_product_by_id."""

    def test_get_existing_product(self, db, salesperson):
        """Getting an existing product by ID should return it."""
        product = ProductFactory()
        result = ProductService.get_product_by_id(product.productid, salesperson)
        assert result.productid == product.productid

    def test_get_nonexistent_product_raises_404(self, db, salesperson):
        """Getting a non-existent product should raise Http404."""
        from django.http import Http404
        with pytest.raises(Http404):
            ProductService.get_product_by_id(uuid4(), salesperson)


@pytest.mark.unit
class TestUpdateProduct:
    """Tests for ProductService.update_product."""

    def test_update_name(self, db, salesperson):
        """Updating a product name should persist."""
        product = ProductFactory()
        dto = UpdateProductDto(name='Updated Name')
        updated = ProductService.update_product(product.productid, dto, salesperson)
        assert updated.name == 'Updated Name'
        assert updated.modifiedby == salesperson

    def test_update_price(self, db, salesperson):
        """Updating price should persist."""
        product = ProductFactory(price=Decimal('10.00'))
        dto = UpdateProductDto(price=Decimal('25.00'))
        updated = ProductService.update_product(product.productid, dto, salesperson)
        assert updated.price == Decimal('25.00')

    def test_update_duplicate_productnumber_raises(self, db, salesperson):
        """Updating productnumber to a duplicate should raise ValidationError."""
        ProductFactory(productnumber='EXISTING-001')
        product = ProductFactory(productnumber='ORIGINAL-001')
        dto = UpdateProductDto(productnumber='EXISTING-001')
        with pytest.raises(ValidationError, match="already exists"):
            ProductService.update_product(product.productid, dto, salesperson)

    def test_update_same_productnumber_allowed(self, db, salesperson):
        """Updating a product keeping its own productnumber should not raise."""
        product = ProductFactory(productnumber='KEEP-001')
        dto = UpdateProductDto(productnumber='KEEP-001')
        updated = ProductService.update_product(product.productid, dto, salesperson)
        assert updated.productnumber == 'KEEP-001'


@pytest.mark.unit
class TestDeleteProduct:
    """Tests for ProductService.delete_product (soft delete)."""

    def test_delete_sets_inactive(self, db, salesperson):
        """Deleting a product should set statecode to INACTIVE."""
        product = ProductFactory(statecode=ProductStateCode.ACTIVE)
        ProductService.delete_product(product.productid, salesperson)
        product.refresh_from_db()
        assert product.statecode == ProductStateCode.INACTIVE

    def test_delete_nonexistent_raises_404(self, db, salesperson):
        """Deleting a non-existent product should raise Http404."""
        from django.http import Http404
        with pytest.raises(Http404):
            ProductService.delete_product(uuid4(), salesperson)


@pytest.mark.unit
class TestGetProductStats:
    """Tests for ProductService.get_product_stats."""

    def test_stats_counts(self, db, salesperson):
        """Stats should count active and inactive products."""
        ProductFactory(statecode=ProductStateCode.ACTIVE)
        ProductFactory(statecode=ProductStateCode.ACTIVE)
        ProductFactory(statecode=ProductStateCode.INACTIVE)
        stats = ProductService.get_product_stats(salesperson)
        assert stats['active_products'] >= 2
        assert stats['inactive_products'] >= 1
        assert stats['total_products'] >= 3

    def test_stats_low_stock(self, db, salesperson):
        """Stats should count low-stock products (< 10 units)."""
        ProductFactory(statecode=ProductStateCode.ACTIVE, quantityonhand=Decimal('5'))
        ProductFactory(statecode=ProductStateCode.ACTIVE, quantityonhand=Decimal('100'))
        stats = ProductService.get_product_stats(salesperson)
        assert stats['low_stock_products'] >= 1

    def test_stats_inventory_value(self, db, salesperson):
        """Stats should calculate total inventory value."""
        ProductFactory(
            statecode=ProductStateCode.ACTIVE,
            quantityonhand=Decimal('10'),
            price=Decimal('50.00'),
        )
        stats = ProductService.get_product_stats(salesperson)
        assert stats['total_inventory_value'] >= Decimal('500.00')


# ============================================================================
# PriceListService Tests
# ============================================================================

@pytest.mark.unit
class TestPriceListService:
    """Tests for PriceListService CRUD operations."""

    def test_create_pricelist(self, db, salesperson):
        """Creating a price list should persist."""
        dto = CreatePriceListDto(name='Q1 2026 Prices', description='First quarter pricing')
        pricelist = PriceListService.create_pricelist(dto, salesperson)
        assert pricelist.pk is not None
        assert pricelist.name == 'Q1 2026 Prices'

    def test_get_pricelist_by_id(self, db, salesperson):
        """Getting an existing price list should return it."""
        pricelist = PriceListFactory(name='Test List')
        result = PriceListService.get_pricelist_by_id(pricelist.pricelevelid, salesperson)
        assert result.name == 'Test List'

    def test_update_pricelist(self, db, salesperson):
        """Updating a price list name should persist."""
        pricelist = PriceListFactory(name='Old Name')
        dto = UpdatePriceListDto(name='New Name')
        updated = PriceListService.update_pricelist(pricelist.pricelevelid, dto, salesperson)
        assert updated.name == 'New Name'

    def test_delete_pricelist(self, db, salesperson):
        """Deleting a price list should remove it from the database."""
        pricelist = PriceListFactory()
        pk = pricelist.pricelevelid
        PriceListService.delete_pricelist(pk, salesperson)
        assert not PriceList.objects.filter(pricelevelid=pk).exists()


# ============================================================================
# PriceListItemService Tests
# ============================================================================

@pytest.mark.unit
class TestPriceListItemService:
    """Tests for PriceListItemService CRUD operations."""

    def test_create_pricelist_item(self, db, salesperson):
        """Creating a price list item should link product and price list."""
        product = ProductFactory()
        pricelist = PriceListFactory()
        dto = CreatePriceListItemDto(
            pricelevelid=pricelist.pricelevelid,
            productid=product.productid,
            amount=Decimal('75.00'),
        )
        item = PriceListItemService.create_pricelist_item(dto, salesperson)
        assert item.pk is not None
        assert item.amount == Decimal('75.00')
        assert item.productid == product
        assert item.pricelevelid == pricelist

    def test_create_duplicate_item_raises(self, db, salesperson):
        """Adding the same product to a price list twice should raise ValidationError."""
        product = ProductFactory()
        pricelist = PriceListFactory()
        PriceListItemFactory(productid=product, pricelevelid=pricelist)
        dto = CreatePriceListItemDto(
            pricelevelid=pricelist.pricelevelid,
            productid=product.productid,
            amount=Decimal('50.00'),
        )
        with pytest.raises(ValidationError, match="already exists"):
            PriceListItemService.create_pricelist_item(dto, salesperson)

    def test_delete_pricelist_item(self, db, salesperson):
        """Deleting a price list item should remove it from the database."""
        item = PriceListItemFactory()
        pk = item.productpricelevelid
        PriceListItemService.delete_pricelist_item(pk, salesperson)
        assert not PriceListItem.objects.filter(productpricelevelid=pk).exists()
