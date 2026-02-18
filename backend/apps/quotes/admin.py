"""
Django admin configuration for Quote models.

Phase 8 Implementation: Quote Management
"""

from django.contrib import admin
from apps.quotes.models import Quote, QuoteDetail


class QuoteDetailInline(admin.TabularInline):
    """Inline admin for quote details."""
    model = QuoteDetail
    extra = 1
    fields = [
        'sequencenumber', 'productname', 'quantity', 'priceperunit',
        'manualdiscountamount', 'tax', 'baseamount', 'extendedamount'
    ]
    readonly_fields = ['baseamount', 'extendedamount']


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    """Admin interface for Quote model."""
    list_display = [
        'quotenumber', 'name', 'customer_name', 'totalamount',
        'statecode', 'statuscode', 'ownerid', 'createdon'
    ]
    list_filter = ['statecode', 'statuscode', 'createdon']
    search_fields = ['quotenumber', 'name', 'accountid__name', 'contactid__fullname']
    readonly_fields = [
        'quoteid', 'quotenumber', 'totalamount', 'totaldiscountamount',
        'totaltax', 'totallineitemamount', 'customer_name',
        'createdon', 'modifiedon', 'createdby', 'modifiedby'
    ]
    inlines = [QuoteDetailInline]

    fieldsets = (
        ('Quote Information', {
            'fields': ('quoteid', 'quotenumber', 'name', 'description')
        }),
        ('Related Entities', {
            'fields': ('opportunityid', 'accountid', 'contactid', 'customer_name')
        }),
        ('Financial Information', {
            'fields': (
                'totallineitemamount', 'discountpercentage', 'totaldiscountamount',
                'totaltax', 'totalamount'
            )
        }),
        ('Dates', {
            'fields': ('effectivefrom', 'effectiveto', 'closedon')
        }),
        ('Status', {
            'fields': ('statecode', 'statuscode')
        }),
        ('Ownership', {
            'fields': ('ownerid',)
        }),
        ('Audit', {
            'fields': ('createdon', 'modifiedon', 'createdby', 'modifiedby'),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuoteDetail)
class QuoteDetailAdmin(admin.ModelAdmin):
    """Admin interface for QuoteDetail model."""
    list_display = [
        'quotedetailid', 'quoteid', 'sequencenumber', 'productname',
        'quantity', 'priceperunit', 'extendedamount'
    ]
    list_filter = ['quoteid']
    search_fields = ['productname', 'quoteid__quotenumber']
    readonly_fields = ['quotedetailid', 'baseamount', 'extendedamount', 'createdon', 'modifiedon']
