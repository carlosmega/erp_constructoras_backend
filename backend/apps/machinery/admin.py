from django.contrib import admin
from .models import EquipmentCategory, EquipmentBrand, EquipmentModel, Equipment, EquipmentInsurance


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'estimatedfuelconsumption', 'statecode']
    list_filter = ['statecode']


@admin.register(EquipmentBrand)
class EquipmentBrandAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'country', 'statecode']
    list_filter = ['statecode']


@admin.register(EquipmentModel)
class EquipmentModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'brandid', 'categoryid', 'statecode']
    list_filter = ['statecode', 'brandid']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['equipmentnumber', 'brand', 'model', 'year', 'ownershiptype', 'operationalstatus', 'statecode']
    list_filter = ['statecode', 'ownershiptype', 'operationalstatus', 'categoryid', 'brandid']


@admin.register(EquipmentInsurance)
class EquipmentInsuranceAdmin(admin.ModelAdmin):
    list_display = ['policynumber', 'insurancetype', 'insurancecompany', 'startdate', 'expirydate', 'statecode']
    list_filter = ['statecode', 'insurancetype']
