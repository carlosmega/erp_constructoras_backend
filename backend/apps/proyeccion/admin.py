"""Django Admin for Proyección (Budget Estimation)."""

from django.contrib import admin
from apps.proyeccion.models import (
    EstimationProject,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
    UnitCostBreakdown,
    IndirectCostDetail,
    OfferAlternative,
    ExternalCostItem,
    SupplyCatalogItem,
    IndirectCostTemplate,
    EquipmentYield,
    WorkPlanEntry,
    ConceptPriceCatalogItem,
    ConceptPriceReference,
)


@admin.register(EstimationProject)
class EstimationProjectAdmin(admin.ModelAdmin):
    list_display = ('estimationnumber', 'name', 'statecode', 'ownerid', 'createdon')
    list_filter = ('statecode', 'projecttype', 'biddingtype')
    search_fields = ('name', 'estimationnumber')
    readonly_fields = ('estimationprojectid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(ConceptFamily)
class ConceptFamilyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'projectid', 'sortorder', 'statecode', 'createdon')
    list_filter = ('statecode', 'projectid')
    search_fields = ('code', 'name')
    readonly_fields = ('familyid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(ConceptSubfamily)
class ConceptSubfamilyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'familyid', 'projectid', 'sortorder', 'statecode', 'createdon')
    list_filter = ('statecode', 'projectid')
    search_fields = ('code', 'name')
    readonly_fields = ('subfamilyid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(BudgetConcept)
class BudgetConceptAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'unit', 'quantity', 'unitprice', 'totalamount', 'statecode', 'createdon')
    list_filter = ('statecode', 'projectid', 'breakdownmethod')
    search_fields = ('code', 'description')
    readonly_fields = ('conceptid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(UnitCostBreakdown)
class UnitCostBreakdownAdmin(admin.ModelAdmin):
    list_display = ('conceptid', 'categorycode', 'linenumber', 'description', 'quantity', 'unitprice', 'amount', 'statecode')
    list_filter = ('statecode', 'categorycode')
    search_fields = ('description',)
    readonly_fields = ('breakdownid', 'createdon', 'modifiedon')


@admin.register(IndirectCostDetail)
class IndirectCostDetailAdmin(admin.ModelAdmin):
    list_display = ('projectid', 'categorycode', 'linenumber', 'description', 'monthlycost', 'units', 'months', 'amount', 'statecode')
    list_filter = ('statecode', 'projectid', 'categorycode')
    search_fields = ('description', 'imputationcode')
    readonly_fields = ('indirectcostid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(OfferAlternative)
class OfferAlternativeAdmin(admin.ModelAdmin):
    list_display = ('projectid', 'alternativenumber', 'name', 'salepricetotal', 'ischosen', 'statecode', 'createdon')
    list_filter = ('statecode', 'projectid', 'ischosen')
    search_fields = ('name',)
    readonly_fields = ('alternativeid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(ExternalCostItem)
class ExternalCostItemAdmin(admin.ModelAdmin):
    list_display = ('projectid', 'itemname', 'applies', 'percentofsale', 'amount', 'sortorder', 'statecode')
    list_filter = ('statecode', 'projectid', 'applies')
    search_fields = ('itemname',)
    readonly_fields = ('externalcostid', 'createdon', 'modifiedon')


@admin.register(SupplyCatalogItem)
class SupplyCatalogItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'unit', 'supplytype', 'referenceprice', 'referencedate', 'statecode', 'createdon')
    list_filter = ('statecode', 'supplytype')
    search_fields = ('code', 'description')
    readonly_fields = ('supplyid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(IndirectCostTemplate)
class IndirectCostTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'projectsize', 'categorycode', 'description', 'monthlycost', 'sortorder', 'statecode', 'createdon')
    list_filter = ('statecode', 'projectsize', 'categorycode')
    search_fields = ('name', 'description')
    readonly_fields = ('templateid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(EquipmentYield)
class EquipmentYieldAdmin(admin.ModelAdmin):
    list_display = ('category', 'description', 'monthlycost', 'numberofequipment', 'realyield', 'costpercubicmeter', 'statecode', 'createdon')
    list_filter = ('statecode', 'category')
    search_fields = ('category', 'description', 'suppliername')
    readonly_fields = ('equipmentyieldid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


@admin.register(WorkPlanEntry)
class WorkPlanEntryAdmin(admin.ModelAdmin):
    list_display = ('conceptid', 'projectid', 'periodnumber', 'periodlabel', 'distributedquantity', 'distributedamount', 'createdon')
    list_filter = ('projectid',)
    search_fields = ('periodlabel',)
    readonly_fields = ('workplanentryid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')


class ConceptPriceReferenceInline(admin.TabularInline):
    model = ConceptPriceReference
    extra = 0
    fields = ('projectname', 'projectlocation', 'unitprice', 'quantity', 'totalamount', 'referencedate')
    readonly_fields = ('referenceid', 'createdon', 'modifiedon')


@admin.register(ConceptPriceCatalogItem)
class ConceptPriceCatalogItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'description_short', 'unit', 'source', 'classificationl1', 'classificationl2', 'classificationl3', 'averageprice', 'referencecount', 'statecode')
    list_filter = ('source', 'statecode', 'classificationl2', 'classificationl3')
    search_fields = ('code', 'description')
    readonly_fields = ('catalogitemid', 'averageprice', 'minprice', 'maxprice', 'referencecount', 'createdon', 'modifiedon', 'createdby', 'modifiedby')
    inlines = [ConceptPriceReferenceInline]

    @admin.display(description='Descripción')
    def description_short(self, obj):
        return obj.description[:80] + '...' if len(obj.description) > 80 else obj.description


@admin.register(ConceptPriceReference)
class ConceptPriceReferenceAdmin(admin.ModelAdmin):
    list_display = ('catalogitemid', 'projectname', 'unitprice', 'quantity', 'totalamount', 'referencedate', 'statecode')
    list_filter = ('statecode', 'projectname')
    search_fields = ('projectname', 'catalogitemid__code', 'catalogitemid__description')
    readonly_fields = ('referenceid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')
