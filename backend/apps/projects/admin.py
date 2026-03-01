"""Django Admin for Construction Project entities."""

from django.contrib import admin
from apps.projects.models import (
    ConstructionProject, ProjectTeamMember, ProjectZone, ProjectSupplier,
)


class ProjectTeamMemberInline(admin.TabularInline):
    model = ProjectTeamMember
    extra = 0
    readonly_fields = ('teammemberid', 'createdon', 'modifiedon')


class ProjectZoneInline(admin.TabularInline):
    model = ProjectZone
    extra = 0
    readonly_fields = ('zoneid', 'createdon', 'modifiedon')


@admin.register(ConstructionProject)
class ConstructionProjectAdmin(admin.ModelAdmin):
    list_display = (
        'projectnumber', 'name', 'get_state_name', 'get_account_name',
        'startdate', 'contractenddate', 'get_owner_name', 'createdon',
    )
    list_filter = ('statecode', 'projecttype', 'biddingtype', 'createdon')
    search_fields = ('name', 'projectnumber', 'accountid__name')
    readonly_fields = ('projectid', 'projectnumber', 'createdon', 'modifiedon', 'createdby', 'modifiedby')
    inlines = [ProjectTeamMemberInline, ProjectZoneInline]

    @admin.display(description='State')
    def get_state_name(self, obj):
        return obj.state_name

    @admin.display(description='Account')
    def get_account_name(self, obj):
        return obj.accountid.name if obj.accountid else '-'

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


@admin.register(ProjectZone)
class ProjectZoneAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'name', 'projectid', 'statecode', 'sortorder')
    list_filter = ('statecode',)
    search_fields = ('name', 'prefix')
    readonly_fields = ('zoneid', 'createdon', 'modifiedon')


@admin.register(ProjectSupplier)
class ProjectSupplierAdmin(admin.ModelAdmin):
    list_display = ('suppliernumber', 'businessname', 'rfc', 'projectid', 'statecode')
    list_filter = ('statecode',)
    search_fields = ('businessname', 'rfc')
    readonly_fields = ('projectsupplierid', 'createdon', 'modifiedon')


@admin.register(ProjectTeamMember)
class ProjectTeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'projectid', 'email', 'phone')
    list_filter = ('role',)
    search_fields = ('name', 'email')
    readonly_fields = ('teammemberid', 'createdon', 'modifiedon')
