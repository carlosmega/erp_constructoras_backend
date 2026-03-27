from django.contrib import admin
from .models import (
    CorporateBudget, CorporateBudgetVersion, CorporateBudgetLine,
    CorporateExpense, CorporateAllocation, CorporateAllocationLine,
    WhatIfSimulation
)

@admin.register(CorporateBudget)
class CorporateBudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'fiscalyear', 'totalbudget', 'statecode']
    list_filter = ['statecode', 'fiscalyear']

@admin.register(CorporateBudgetVersion)
class CorporateBudgetVersionAdmin(admin.ModelAdmin):
    list_display = ['label', 'versionnumber', 'statecode']

@admin.register(CorporateBudgetLine)
class CorporateBudgetLineAdmin(admin.ModelAdmin):
    list_display = ['categorycode', 'annualamount']

@admin.register(CorporateExpense)
class CorporateExpenseAdmin(admin.ModelAdmin):
    list_display = ['categorycode', 'year', 'month', 'budgetedamount', 'actualamount']
    list_filter = ['year', 'month', 'categorycode']

@admin.register(CorporateAllocation)
class CorporateAllocationAdmin(admin.ModelAdmin):
    list_display = ['year', 'month', 'prorationmethod', 'totalamountallocated', 'statecode']

@admin.register(CorporateAllocationLine)
class CorporateAllocationLineAdmin(admin.ModelAdmin):
    list_display = ['projectid', 'weightpercent', 'allocatedamount']

@admin.register(WhatIfSimulation)
class WhatIfSimulationAdmin(admin.ModelAdmin):
    list_display = ['name', 'fiscalyear', 'statecode']
