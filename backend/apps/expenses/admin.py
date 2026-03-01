"""Django Admin for Expense Management entities."""

from django.contrib import admin
from apps.expenses.models import (
    ProjectExpense,
    ExpenseLine,
    ExpenseAttachment,
    ClassificationLog,
    ClientEstimate,
)


class ExpenseLineInline(admin.TabularInline):
    model = ExpenseLine
    extra = 0
    readonly_fields = ('expenselineid', 'createdon', 'modifiedon')


class ExpenseAttachmentInline(admin.TabularInline):
    model = ExpenseAttachment
    extra = 0
    readonly_fields = ('attachmentid', 'createdon')


@admin.register(ProjectExpense)
class ProjectExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'expenseid', 'get_documenttype', 'suppliername',
        'netamount', 'get_classification', 'get_statecode',
        'get_owner_name', 'createdon',
    )
    list_filter = ('statecode', 'documenttype', 'classificationstatus', 'createdon')
    search_fields = ('suppliername', 'supplierrfc', 'invoicefolio')
    readonly_fields = ('expenseid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')
    inlines = [ExpenseLineInline, ExpenseAttachmentInline]

    @admin.display(description='Document Type')
    def get_documenttype(self, obj):
        return obj.get_documenttype_display()

    @admin.display(description='Classification')
    def get_classification(self, obj):
        return obj.get_classificationstatus_display()

    @admin.display(description='State')
    def get_statecode(self, obj):
        return obj.get_statecode_display()

    @admin.display(description='Owner')
    def get_owner_name(self, obj):
        return obj.ownerid.fullname if obj.ownerid else '-'


@admin.register(ClassificationLog)
class ClassificationLogAdmin(admin.ModelAdmin):
    list_display = ('classificationlogid', 'expenseid', 'get_action', 'classifiedbyname', 'createdon')
    list_filter = ('action', 'createdon')
    readonly_fields = ('classificationlogid', 'createdon')

    @admin.display(description='Action')
    def get_action(self, obj):
        return obj.get_action_display()


@admin.register(ClientEstimate)
class ClientEstimateAdmin(admin.ModelAdmin):
    list_display = (
        'estimateid', 'estimatenumber', 'projectid',
        'estimatedamount', 'collectableamount', 'get_statecode', 'createdon',
    )
    list_filter = ('statecode', 'estimatetype', 'paymentstatus')
    readonly_fields = ('estimateid', 'createdon', 'modifiedon', 'createdby', 'modifiedby')

    @admin.display(description='State')
    def get_statecode(self, obj):
        return obj.get_statecode_display()
