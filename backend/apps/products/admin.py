"""
Django admin configuration for Product models.

Phase 11 Implementation: Product Catalog Management
"""

from django.contrib import admin
from apps.products.models import Product, PriceList, PriceListItem


class PriceListItemInline(admin.TabularInline):
    """Inline admin for price list items."""
    model = PriceListItem
    extra = 1
    fields = ['productid', 'amount']
    autocomplete_fields = ['productid']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model."""
    list_display = [
        'productnumber', 'name', 'statecode', 'price', 'standardcost',
        'quantityonhand', 'available_quantity', 'createdon'
    ]
    list_filter = ['statecode', 'productstructure', 'producttypecode', 'createdon']
    search_fields = ['name', 'productnumber', 'description']
    readonly_fields = [
        'productid', 'available_quantity', 'createdon', 'modifiedon',
        'createdby', 'modifiedby'
    ]
    autocomplete_fields = ['parentproductid']

    fieldsets = (
        ('Product Information', {
            'fields': ('productid', 'name', 'productnumber', 'description')
        }),
        ('Product Type', {
            'fields': ('productstructure', 'producttypecode')
        }),
        ('Pricing', {
            'fields': ('price', 'standardcost', 'currentcost')
        }),
        ('Inventory', {
            'fields': (
                'quantityonhand', 'quantityallocated', 'available_quantity',
                'stockvolume', 'stockweight'
            )
        }),
        ('Vendor Information', {
            'fields': ('vendorid', 'vendorpartnumber', 'vendorname', 'suppliername'),
            'classes': ('collapse',)
        }),
        ('Attributes', {
            'fields': ('size', 'color', 'style'),
            'classes': ('collapse',)
        }),
        ('Hierarchy', {
            'fields': ('parentproductid',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('statecode',)
        }),
        ('Audit', {
            'fields': ('createdon', 'modifiedon', 'createdby', 'modifiedby'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:
            obj.modifiedby = request.user
        super().save_model(request, obj, form, change)


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    """Admin interface for PriceList model."""
    list_display = ['name', 'statecode', 'begindate', 'enddate', 'is_active', 'createdon']
    list_filter = ['statecode', 'createdon']
    search_fields = ['name', 'description']
    readonly_fields = ['pricelevelid', 'is_active', 'createdon', 'modifiedon']
    inlines = [PriceListItemInline]

    fieldsets = (
        ('Price List Information', {
            'fields': ('pricelevelid', 'name', 'description')
        }),
        ('Validity Period', {
            'fields': ('begindate', 'enddate', 'is_active')
        }),
        ('Status', {
            'fields': ('statecode',)
        }),
        ('Audit', {
            'fields': ('createdon', 'modifiedon'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PriceListItem)
class PriceListItemAdmin(admin.ModelAdmin):
    """Admin interface for PriceListItem model."""
    list_display = [
        'productpricelevelid', 'pricelevelid', 'productid', 'amount', 'createdon'
    ]
    list_filter = ['pricelevelid', 'createdon']
    search_fields = ['productid__name', 'pricelevelid__name']
    readonly_fields = ['productpricelevelid', 'createdon', 'modifiedon']
    autocomplete_fields = ['pricelevelid', 'productid']

    fieldsets = (
        ('Price List Item', {
            'fields': ('productpricelevelid', 'pricelevelid', 'productid', 'amount')
        }),
        ('Audit', {
            'fields': ('createdon', 'modifiedon'),
            'classes': ('collapse',)
        }),
    )
