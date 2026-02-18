"""
Django Admin configuration for User Management.

Provides admin interface for SystemUser and SecurityRole models.

Phase 3 Implementation (User Story 1)
Tasks T058-T059: Django Admin configuration
"""

from django.contrib import admin
from apps.users.models import SecurityRole, SystemUser


@admin.register(SecurityRole)
class SecurityRoleAdmin(admin.ModelAdmin):
    """
    Admin configuration for SecurityRole model (T058).
    """
    list_display = ('securityroleid', 'name', 'description')
    search_fields = ('name', 'description')
    readonly_fields = ('securityroleid',)
    ordering = ('name',)

    fieldsets = (
        ('Role Information', {
            'fields': ('securityroleid', 'name', 'description')
        }),
    )


@admin.register(SystemUser)
class SystemUserAdmin(admin.ModelAdmin):
    """
    Admin configuration for SystemUser model (T059).
    """
    # List display
    list_display = (
        'emailaddress1',
        'fullname',
        'get_role_name',
        'isdisabled',
        'failedloginattempts',
        'lastlogindate',
        'createdon',
    )

    # Filters
    list_filter = ('isdisabled', 'securityroleid', 'createdon')

    # Search
    search_fields = ('emailaddress1', 'fullname')

    # Ordering
    ordering = ('fullname',)

    # Readonly fields
    readonly_fields = (
        'systemuserid',
        'password',
        'createdon',
        'modifiedon',
        'createdby',
        'modifiedby',
        'lastlogindate',
        'failedloginattempts',
    )

    # Fieldsets for detail view
    fieldsets = (
        ('Authentication', {
            'fields': ('emailaddress1', 'password')
        }),
        ('Personal Information', {
            'fields': ('fullname',)
        }),
        ('Security & Role', {
            'fields': ('securityroleid', 'isdisabled')
        }),
        ('Login Information', {
            'fields': ('lastlogindate', 'failedloginattempts')
        }),
        ('Audit Information', {
            'fields': ('systemuserid', 'createdon', 'modifiedon', 'createdby', 'modifiedby'),
            'classes': ('collapse',)
        }),
    )

    def get_role_name(self, obj):
        """Display role name in list view."""
        return obj.role_name or '-'
    get_role_name.short_description = 'Role'
    get_role_name.admin_order_field = 'securityroleid__name'

    def save_model(self, request, obj, form, change):
        """
        Override save to set audit fields.
        """
        if not change:  # Creating new user
            obj.createdby = request.user
            obj.modifiedby = request.user
        else:  # Updating existing user
            obj.modifiedby = request.user

        super().save_model(request, obj, form, change)
