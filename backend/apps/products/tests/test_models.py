"""Unit tests for Product models and enums."""

import pytest
from decimal import Decimal
from datetime import date

from apps.products.models import (
    Product,
    PriceList,
    PriceListItem,
    ProductStateCode,
    ProductStructure,
    ProductTypeCode,
)
from apps.products.tests.factories import ProductFactory, PriceListFactory, PriceListItemFactory
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Enum Tests
# ============================================================================

@pytest.mark.unit
class TestProductStateCodeEnum:
    """Tests for ProductStateCode enum values."""

    def test_active_value(self):
        assert ProductStateCode.ACTIVE.value == 0
        assert ProductStateCode.ACTIVE.label == 'Active'

    def test_inactive_value(self):
        assert ProductStateCode.INACTIVE.value == 1
        assert ProductStateCode.INACTIVE.label == 'Inactive'


@pytest.mark.unit
class TestProductStructureEnum:
    """Tests for ProductStructure enum values."""

    def test_product_value(self):
        assert ProductStructure.PRODUCT.value == 1

    def test_product_family_value(self):
        assert ProductStructure.PRODUCT_FAMILY.value == 2

    def test_bundle_value(self):
        assert ProductStructure.BUNDLE.value == 3


@pytest.mark.unit
class TestProductTypeCodeEnum:
    """Tests for ProductTypeCode enum values."""

    def test_sales_inventory_value(self):
        assert ProductTypeCode.SALES_INVENTORY.value == 1

    def test_misc_charges_value(self):
        assert ProductTypeCode.MISC_CHARGES.value == 2


# ============================================================================
# Product Model Tests
# ============================================================================

@pytest.mark.unit
class TestProductModel:
    """Tests for Product model creation and properties."""

    def test_create_minimal(self, db):
        """Create a product with only required fields."""
        product = Product.objects.create(name='Test Product')
        assert product.pk is not None
        assert product.statecode == ProductStateCode.ACTIVE
        assert product.productstructure == ProductStructure.PRODUCT
        assert product.producttypecode == ProductTypeCode.SALES_INVENTORY

    def test_factory(self, db):
        """ProductFactory should create a valid product."""
        product = ProductFactory()
        assert product.pk is not None
        assert product.name is not None
        assert product.productnumber is not None

    def test_str_representation_with_sku(self, db):
        """String representation should include name and SKU."""
        product = ProductFactory(name='Cement', productnumber='SKU-001')
        assert str(product) == 'Cement (SKU-001)'

    def test_str_representation_without_sku(self, db):
        """String representation should show 'No SKU' when productnumber is None."""
        product = ProductFactory(name='Custom Item', productnumber=None)
        assert str(product) == 'Custom Item (No SKU)'

    def test_state_name_property(self, db):
        """state_name should return human-readable label."""
        product = ProductFactory(statecode=ProductStateCode.ACTIVE)
        assert product.state_name == 'Active'

    def test_state_name_property_inactive(self, db):
        """state_name for inactive product."""
        product = ProductFactory(statecode=ProductStateCode.INACTIVE)
        assert product.state_name == 'Inactive'

    def test_structure_name_property(self, db):
        """structure_name should return human-readable label."""
        product = ProductFactory(productstructure=ProductStructure.BUNDLE)
        assert product.structure_name == 'Bundle'

    def test_structure_name_none(self, db):
        """structure_name should return None when productstructure is None."""
        product = ProductFactory(productstructure=None)
        assert product.structure_name is None

    def test_type_name_property(self, db):
        """type_name should return human-readable label."""
        product = ProductFactory(producttypecode=ProductTypeCode.MISC_CHARGES)
        assert product.type_name == 'Miscellaneous Charges'

    def test_type_name_none(self, db):
        """type_name should return None when producttypecode is None."""
        product = ProductFactory(producttypecode=None)
        assert product.type_name is None

    def test_available_quantity_both_set(self, db):
        """available_quantity should be onhand - allocated."""
        product = ProductFactory(
            quantityonhand=Decimal('100.00'),
            quantityallocated=Decimal('30.00'),
        )
        assert product.available_quantity == Decimal('70.00')

    def test_available_quantity_no_allocated(self, db):
        """available_quantity should return onhand when allocated is None."""
        product = ProductFactory(
            quantityonhand=Decimal('50.00'),
            quantityallocated=None,
        )
        assert product.available_quantity == Decimal('50.00')

    def test_available_quantity_both_none(self, db):
        """available_quantity should return None when onhand is None."""
        product = ProductFactory(quantityonhand=None, quantityallocated=None)
        assert product.available_quantity is None

    def test_parent_product_hierarchy(self, db):
        """A product should be able to have a parent product."""
        parent = ProductFactory(name='Parent Family', productstructure=ProductStructure.PRODUCT_FAMILY)
        child = ProductFactory(name='Child Product', parentproductid=parent)
        assert child.parentproductid == parent
        assert parent.child_products.count() == 1

    def test_db_table_name(self):
        """DB table should be 'product' per CDS naming."""
        assert Product._meta.db_table == 'product'

    def test_default_ordering(self):
        """Products should be ordered by name by default."""
        assert Product._meta.ordering == ['name']


# ============================================================================
# PriceList Model Tests
# ============================================================================

@pytest.mark.unit
class TestPriceListModel:
    """Tests for PriceList model."""

    def test_factory(self, db):
        """PriceListFactory should create a valid price list."""
        pricelist = PriceListFactory()
        assert pricelist.pk is not None
        assert pricelist.name is not None

    def test_str_representation(self, db):
        """String representation should be the name."""
        pricelist = PriceListFactory(name='Standard Pricing')
        assert str(pricelist) == 'Standard Pricing'

    def test_is_active_property_active(self, db):
        """is_active should be True for active price list with no date restrictions."""
        pricelist = PriceListFactory(statecode=ProductStateCode.ACTIVE, begindate=None, enddate=None)
        assert pricelist.is_active is True

    def test_is_active_property_inactive_state(self, db):
        """is_active should be False for inactive price list."""
        pricelist = PriceListFactory(statecode=ProductStateCode.INACTIVE)
        assert pricelist.is_active is False

    def test_is_active_future_begin_date(self, db):
        """is_active should be False if begin date is in the future."""
        pricelist = PriceListFactory(
            statecode=ProductStateCode.ACTIVE,
            begindate=date(2099, 1, 1),
        )
        assert pricelist.is_active is False

    def test_is_active_past_end_date(self, db):
        """is_active should be False if end date has passed."""
        pricelist = PriceListFactory(
            statecode=ProductStateCode.ACTIVE,
            enddate=date(2020, 1, 1),
        )
        assert pricelist.is_active is False

    def test_db_table_name(self):
        """DB table should be 'pricelevel' per CDS naming."""
        assert PriceList._meta.db_table == 'pricelevel'


# ============================================================================
# PriceListItem Model Tests
# ============================================================================

@pytest.mark.unit
class TestPriceListItemModel:
    """Tests for PriceListItem model."""

    def test_factory(self, db):
        """PriceListItemFactory should create a valid price list item."""
        item = PriceListItemFactory()
        assert item.pk is not None
        assert item.amount is not None

    def test_str_representation(self, db):
        """String representation should show product, pricelist, and amount."""
        product = ProductFactory(name='Widget')
        pricelist = PriceListFactory(name='Retail')
        item = PriceListItemFactory(
            productid=product,
            pricelevelid=pricelist,
            amount=Decimal('25.0000'),
        )
        assert str(item) == 'Widget - Retail: 25.0000'

    def test_unique_together_constraint(self, db):
        """Same product should not appear twice in the same price list."""
        product = ProductFactory()
        pricelist = PriceListFactory()
        PriceListItemFactory(productid=product, pricelevelid=pricelist)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            PriceListItemFactory(productid=product, pricelevelid=pricelist)

    def test_db_table_name(self):
        """DB table should be 'productpricelevel' per CDS naming."""
        assert PriceListItem._meta.db_table == 'productpricelevel'
