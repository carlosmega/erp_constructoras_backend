from django.contrib import admin
from apps.invoiceinbox.models import IncomingInvoice, InboxSyncLog


@admin.register(IncomingInvoice)
class IncomingInvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'incominginvoiceid', 'uuid', 'emisornombre', 'emisorrfc',
        'total', 'moneda', 'statecode', 'projectid', 'emailreceivedon',
    ]
    list_filter = ['statecode', 'moneda']
    search_fields = ['uuid', 'emisorrfc', 'emisornombre', 'folio', 'emailsubject']
    readonly_fields = ['incominginvoiceid', 'createdon', 'modifiedon']


@admin.register(InboxSyncLog)
class InboxSyncLogAdmin(admin.ModelAdmin):
    list_display = [
        'synclogid', 'syncstatus', 'triggeredby',
        'totalemailsfetched', 'newxmlattachments', 'errorscount', 'startedon',
    ]
    list_filter = ['syncstatus', 'triggeredby']
    readonly_fields = ['synclogid', 'startedon']
