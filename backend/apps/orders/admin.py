"""
Django admin configuration for Order models.

Phase 9 Implementation: Order Management
"""

from django.contrib import admin
from apps.orders.models import SalesOrder, SalesOrderDetail


class SalesOrderDetailInline(admin.TabularInline):
    """Inline admin for order details."""
    model = SalesOrderDetail
    extra = 0
    fields = [
        'sequencenumber', 'productname', 'quantity', 'priceperunit',
        'manualdiscountamount', 'tax', 'baseamount', 'extendedamount'
    ]
    readonly_fields = ['baseamount', 'extendedamount']


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    """Admin interface for SalesOrder model."""
    list_display = [
        'ordernumber', 'name', 'customer_name', 'totalamount',
        'statecode', 'statuscode', 'requestdeliveryby', 'ownerid', 'createdon'
    ]
    list_filter = ['statecode', 'statuscode', 'createdon', 'requestdeliveryby']
    search_fields = ['ordernumber', 'name', 'accountid__name', 'contactid__fullname']
    readonly_fields = [
        'salesorderid', 'ordernumber', 'totalamount', 'totaldiscountamount',
        'totaltax', 'totallineitemamount', 'customer_name', 'datefulfilled',
        'createdon', 'modifiedon', 'createdby', 'modifiedby'
    ]
    inlines = [SalesOrderDetailInline]

    fieldsets = (
        ('Order Information', {
            'fields': ('salesorderid', 'ordernumber', 'name', 'description')
        }),
        ('Related Entities', {
            'fields': ('quoteid', 'opportunityid', 'accountid', 'contactid', 'customer_name')
        }),
        ('Financial Information', {
            'fields': (
                'totallineitemamount', 'totaldiscountamount',
                'totaltax', 'totalamount'
            )
        }),
        ('Dates', {
            'fields': ('requestdeliveryby', 'datefulfilled')
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


@admin.register(SalesOrderDetail)
class SalesOrderDetailAdmin(admin.ModelAdmin):
    """Admin interface for SalesOrderDetail model."""
    list_display = [
        'salesorderdetailid', 'salesorderid', 'sequencenumber', 'productname',
        'quantity', 'priceperunit', 'extendedamount'
    ]
    list_filter = ['salesorderid']
    search_fields = ['productname', 'salesorderid__ordernumber']
    readonly_fields = ['salesorderdetailid', 'baseamount', 'extendedamount', 'createdon', 'modifiedon']
