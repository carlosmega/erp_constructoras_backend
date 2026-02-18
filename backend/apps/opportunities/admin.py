"""Django Admin configuration for Opportunity entity. Phase 6 Implementation"""

from django.contrib import admin
from apps.opportunities.models import Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'customername', 'get_state_name', 'get_stage_name',
                   'estimatedrevenue', 'probability', 'estimatedclosedate', 'get_owner_name', 'createdon')
    list_filter = ('statecode', 'salesstage', 'createdon')
    search_fields = ('name', 'customername', 'description')
    readonly_fields = ('opportunityid', 'createdon', 'modifiedon', 'createdby', 'modifiedby',
                      'get_state_name', 'get_status_name', 'get_stage_name', 'get_weighted_revenue')
    ordering = ('-createdon',)

    @admin.display(description='State')
    def get_state_name(self, obj):
        return obj.state_name

    @admin.display(description='Status')
    def get_status_name(self, obj):
        return obj.status_name

    @admin.display(description='Stage')
    def get_stage_name(self, obj):
        return obj.stage_name

    @admin.display(description='Owner')
    def get_owner_name(self, obj):
        return obj.ownerid.fullname if obj.ownerid else '-'

    @admin.display(description='Weighted Revenue')
    def get_weighted_revenue(self, obj):
        return obj.weighted_revenue

    def save_model(self, request, obj, form, change):
        if not change:
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:
            obj.modifiedby = request.user
        super().save_model(request, obj, form, change)
