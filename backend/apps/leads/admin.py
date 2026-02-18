"""
Django Admin configuration for Lead entity.

Phase 5 Implementation (User Story 3)
"""

from django.contrib import admin
from apps.leads.models import Lead, LeadStateCode, LeadStatusCode


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """
    Admin interface for Lead entity.
    """

    list_display = (
        'fullname',
        'emailaddress1',
        'telephone1',
        'companyname',
        'get_state_name',
        'get_status_name',
        'get_quality_name',
        'estimatedvalue',
        'estimatedclosedate',
        'get_owner_name',
        'createdon',
    )

    list_filter = (
        'statecode',
        'statuscode',
        'leadqualitycode',
        'leadsourcecode',
        'createdon',
    )

    search_fields = (
        'fullname',
        'firstname',
        'lastname',
        'emailaddress1',
        'companyname',
        'subject',
    )

    readonly_fields = (
        'leadid',
        'fullname',  # Auto-computed from firstname + lastname
        'qualifyingopportunityid',
        'createdon',
        'modifiedon',
        'createdby',
        'modifiedby',
        'get_state_name',
        'get_status_name',
        'get_quality_name',
        'get_source_name',
    )

    fieldsets = (
        ('Personal Information', {
            'fields': (
                'leadid',
                'firstname',
                'lastname',
                'fullname',
            )
        }),
        ('Contact Information', {
            'fields': (
                'emailaddress1',
                'telephone1',
                'mobilephone',
            )
        }),
        ('Company Information', {
            'fields': (
                'companyname',
                'jobtitle',
            )
        }),
        ('Lead Details', {
            'fields': (
                'subject',
                'description',
                'leadqualitycode',
                'get_quality_name',
                'leadsourcecode',
                'get_source_name',
            )
        }),
        ('State Management', {
            'fields': (
                'statecode',
                'get_state_name',
                'statuscode',
                'get_status_name',
            )
        }),
        ('Sales Information', {
            'fields': (
                'estimatedvalue',
                'estimatedclosedate',
                'qualifyingopportunityid',
            )
        }),
        ('Ownership', {
            'fields': (
                'ownerid',
            )
        }),
        ('Audit Information', {
            'fields': (
                'createdon',
                'createdby',
                'modifiedon',
                'modifiedby',
            ),
            'classes': ('collapse',),
        }),
    )

    ordering = ('-createdon',)

    # Custom methods for list display
    @admin.display(description='State')
    def get_state_name(self, obj):
        return obj.state_name

    @admin.display(description='Status')
    def get_status_name(self, obj):
        return obj.status_name

    @admin.display(description='Quality')
    def get_quality_name(self, obj):
        return obj.quality_name or '-'

    @admin.display(description='Source')
    def get_source_name(self, obj):
        return obj.source_name or '-'

    @admin.display(description='Owner')
    def get_owner_name(self, obj):
        return obj.ownerid.fullname if obj.ownerid else '-'

    def save_model(self, request, obj, form, change):
        """
        Override save to set createdby/modifiedby automatically.
        """
        if not change:
            # Creating new lead
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:
            # Updating existing lead
            obj.modifiedby = request.user

        super().save_model(request, obj, form, change)
