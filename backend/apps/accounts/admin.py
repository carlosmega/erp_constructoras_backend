"""Django Admin for Account entity. Phase 7 Implementation"""

from django.contrib import admin
from apps.accounts.models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'accountnumber', 'telephone1', 'address1_city', 'get_state_name', 'get_owner_name', 'createdon')
    list_filter = ('statecode', 'createdon')
    search_fields = ('name', 'accountnumber', 'emailaddress1')
    readonly_fields = ('accountid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')

    @admin.display(description='State')
    def get_state_name(self, obj):
        return obj.state_name

    @admin.display(description='Owner')
    def get_owner_name(self, obj):
        return obj.ownerid.fullname if obj.ownerid else '-'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:
            obj.modifiedby = request.user
        super().save_model(request, obj, form, change)
