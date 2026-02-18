"""
Product models for CRM Backend.

Implements Product and PriceListItem entities following Dynamics CDS patterns.
Phase 11 Implementation: Product Catalog Management
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class ProductStateCode(models.IntegerChoices):
    """Product state codes."""
    ACTIVE = 0, 'Active'
    INACTIVE = 1, 'Inactive'


class ProductStructure(models.IntegerChoices):
    """Product structure types."""
    PRODUCT = 1, 'Product'
    PRODUCT_FAMILY = 2, 'Product Family'
    BUNDLE = 3, 'Bundle'


class ProductTypeCode(models.IntegerChoices):
    """Product type codes."""
    SALES_INVENTORY = 1, 'Sales Inventory'
    MISC_CHARGES = 2, 'Miscellaneous Charges'


class Product(models.Model):
    """
    Product or service in the catalog.

    CDS Entity: product
    Primary Key: productid (UUID)
    """

    # Primary Key
    productid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='productid'
    )

    # State & Status
    statecode = models.IntegerField(
        choices=ProductStateCode.choices,
        default=ProductStateCode.ACTIVE,
        db_column='statecode'
    )
    statuscode = models.IntegerField(
        null=True,
        blank=True,
        db_column='statuscode'
    )

    # Basic Information
    name = models.CharField(
        max_length=100,
        db_column='name'
    )
    productnumber = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='productnumber',
        help_text='SKU or product number'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description'
    )

    # Product Type
    productstructure = models.IntegerField(
        choices=ProductStructure.choices,
        default=ProductStructure.PRODUCT,
        null=True,
        blank=True,
        db_column='productstructure'
    )
    producttypecode = models.IntegerField(
        choices=ProductTypeCode.choices,
        default=ProductTypeCode.SALES_INVENTORY,
        null=True,
        blank=True,
        db_column='producttypecode'
    )

    # Pricing (default)
    price = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='price',
        help_text='Default selling price'
    )
    standardcost = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='standardcost',
        help_text='Standard cost of the product'
    )

    # Inventory
    currentcost = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='currentcost'
    )
    stockvolume = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='stockvolume'
    )
    stockweight = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
        db_column='stockweight'
    )
    quantityonhand = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='quantityonhand'
    )
    quantityallocated = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='quantityallocated'
    )

    # Vendor Information
    vendorid = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='vendorid'
    )
    vendorpartnumber = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='vendorpartnumber'
    )
    vendorname = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='vendorname'
    )

    # Dimensions
    size = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='size'
    )
    color = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='color'
    )
    style = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_column='style'
    )

    # Supplier
    suppliername = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='suppliername'
    )

    # Hierarchy
    parentproductid = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_products',
        db_column='parentproductid',
        help_text='Parent product for bundles/families'
    )

    # Audit Fields
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )
    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_created',
        db_column='createdby'
    )
    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products_modified',
        db_column='modifiedby'
    )

    class Meta:
        db_table = 'product'
        ordering = ['name']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        indexes = [
            models.Index(fields=['statecode']),
            models.Index(fields=['productnumber']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} ({self.productnumber or 'No SKU'})"

    @property
    def state_name(self):
        """Get display name for state code."""
        return ProductStateCode(self.statecode).label if self.statecode is not None else None

    @property
    def structure_name(self):
        """Get display name for product structure."""
        return ProductStructure(self.productstructure).label if self.productstructure is not None else None

    @property
    def type_name(self):
        """Get display name for product type."""
        return ProductTypeCode(self.producttypecode).label if self.producttypecode is not None else None

    @property
    def available_quantity(self):
        """Calculate available quantity (on hand - allocated)."""
        if self.quantityonhand is not None and self.quantityallocated is not None:
            return self.quantityonhand - self.quantityallocated
        return self.quantityonhand


class PriceList(models.Model):
    """
    Price list for products.

    CDS Entity: pricelevel
    Primary Key: pricelevelid (UUID)
    """

    # Primary Key
    pricelevelid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='pricelevelid'
    )

    # Basic Information
    name = models.CharField(
        max_length=100,
        db_column='name'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description'
    )

    # Dates
    begindate = models.DateField(
        null=True,
        blank=True,
        db_column='begindate'
    )
    enddate = models.DateField(
        null=True,
        blank=True,
        db_column='enddate'
    )

    # Status
    statecode = models.IntegerField(
        choices=ProductStateCode.choices,
        default=ProductStateCode.ACTIVE,
        db_column='statecode'
    )

    # Audit Fields
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )

    class Meta:
        db_table = 'pricelevel'
        ordering = ['name']
        verbose_name = 'Price List'
        verbose_name_plural = 'Price Lists'

    def __str__(self):
        return self.name

    @property
    def is_active(self):
        """Check if price list is currently active."""
        from django.utils import timezone
        now = timezone.now().date()

        if self.statecode != ProductStateCode.ACTIVE:
            return False

        if self.begindate and now < self.begindate:
            return False

        if self.enddate and now > self.enddate:
            return False

        return True


class PriceListItem(models.Model):
    """
    Specific price for a product in a price list.

    CDS Entity: productpricelevel
    Primary Key: productpricelevelid (UUID)
    """

    # Primary Key
    productpricelevelid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='productpricelevelid'
    )

    # Relationships
    pricelevelid = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name='price_items',
        db_column='pricelevelid'
    )
    productid = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='price_items',
        db_column='productid'
    )

    # Pricing
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal('0'))],
        db_column='amount',
        help_text='Price for this product in this price list'
    )

    # Audit Fields
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )

    class Meta:
        db_table = 'productpricelevel'
        ordering = ['pricelevelid', 'productid']
        verbose_name = 'Price List Item'
        verbose_name_plural = 'Price List Items'
        unique_together = [['pricelevelid', 'productid']]
        indexes = [
            models.Index(fields=['pricelevelid']),
            models.Index(fields=['productid']),
        ]

    def __str__(self):
        return f"{self.productid.name} - {self.pricelevelid.name}: {self.amount}"
