"""Django Admin for Budget Management."""

from django.contrib import admin
from apps.budgets.models import CostCategory, ImputationCode, ImputationPeriod


@admin.register(CostCategory)
class CostCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'get_costtype', 'sortorder', 'statecode', 'createdon')
    list_filter = ('costtype', 'statecode', 'projectid')
    search_fields = ('code', 'name')
    readonly_fields = ('categoryid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')

    @admin.display(description='Cost Type')
    def get_costtype(self, obj):
        from apps.budgets.models import CostTypeCode
        return CostTypeCode(obj.costtype).label


@admin.register(ImputationCode)
class ImputationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'get_costtype', 'get_category', 'totalbudget', 'totalspent', 'statecode', 'createdon')
    list_filter = ('costtype', 'statecode', 'projectid', 'categoryid')
    search_fields = ('code', 'name')
    readonly_fields = ('imputationcodeid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')

    @admin.display(description='Cost Type')
    def get_costtype(self, obj):
        from apps.budgets.models import CostTypeCode
        return CostTypeCode(obj.costtype).label

    @admin.display(description='Category')
    def get_category(self, obj):
        return obj.categoryid.code if obj.categoryid else '-'


@admin.register(ImputationPeriod)
class ImputationPeriodAdmin(admin.ModelAdmin):
    list_display = ('label', 'year', 'month', 'periodnumber', 'startdate', 'enddate', 'sortorder', 'statecode')
    list_filter = ('statecode', 'year', 'periodtype', 'projectid')
    search_fields = ('label',)
    readonly_fields = ('periodid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')
