"""
Django admin configuration for Invoice models.

Phase 10 Implementation: Invoice Management
"""

from django.contrib import admin
from apps.invoices.models import Invoice, InvoiceDetail


class InvoiceDetailInline(admin.TabularInline):
    """Inline admin for invoice details."""
    model = InvoiceDetail
    extra = 0
    fields = [
        'sequencenumber', 'productname', 'quantity', 'priceperunit',
        'manualdiscountamount', 'tax', 'baseamount', 'extendedamount'
    ]
    readonly_fields = ['baseamount', 'extendedamount']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin interface for Invoice model."""
    list_display = [
        'invoicenumber', 'name', 'customer_name', 'totalamount',
        'totalpaid', 'totalamountdue', 'duedate', 'is_overdue',
        'statecode', 'statuscode', 'ownerid', 'createdon'
    ]
    list_filter = ['statecode', 'statuscode', 'createdon', 'duedate', 'paidon']
    search_fields = ['invoicenumber', 'name', 'accountid__name', 'contactid__fullname']
    readonly_fields = [
        'invoiceid', 'invoicenumber', 'totalamount', 'totaldiscountamount',
        'totaltax', 'totallineitemamount', 'totalamountless', 'totalamountdue',
        'customer_name', 'is_overdue', 'paidon',
        'createdon', 'modifiedon', 'createdby', 'modifiedby'
    ]
    inlines = [InvoiceDetailInline]

    fieldsets = (
        ('Invoice Information', {
            'fields': ('invoiceid', 'invoicenumber', 'name', 'description')
        }),
        ('Related Entities', {
            'fields': ('salesorderid', 'opportunityid', 'accountid', 'contactid', 'customer_name')
        }),
        ('Financial Information', {
            'fields': (
                'totallineitemamount', 'totaldiscountamount',
                'totaltax', 'totalamountless', 'totalamount',
                'totalpaid', 'totalamountdue'
            )
        }),
        ('Dates', {
            'fields': ('datedelivered', 'duedate', 'paidon', 'is_overdue')
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


@admin.register(InvoiceDetail)
class InvoiceDetailAdmin(admin.ModelAdmin):
    """Admin interface for InvoiceDetail model."""
    list_display = [
        'invoicedetailid', 'invoiceid', 'sequencenumber', 'productname',
        'quantity', 'priceperunit', 'extendedamount'
    ]
    list_filter = ['invoiceid']
    search_fields = ['productname', 'invoiceid__invoicenumber']
    readonly_fields = ['invoicedetailid', 'baseamount', 'extendedamount', 'createdon', 'modifiedon']
