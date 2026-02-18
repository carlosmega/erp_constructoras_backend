"""Django Admin for Contact entity. Phase 7 Implementation"""

from django.contrib import admin
from apps.contacts.models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('fullname', 'emailaddress1', 'telephone1', 'jobtitle', 'get_company_name', 'get_state_name', 'get_owner_name', 'createdon')
    list_filter = ('statecode', 'createdon', 'parentcustomerid')
    search_fields = ('fullname', 'firstname', 'lastname', 'emailaddress1')
    readonly_fields = ('contactid', 'fullname', 'createdon', 'modifiedon', 'createdby', 'modifiedby')

    @admin.display(description='Company')
    def get_company_name(self, obj):
        return obj.company_name or '-'

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
