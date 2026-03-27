from django.contrib import admin
from apps.hrpayroll.models import (
    Employee, EmployeeProjectAssignment,
    DeductionType, AdditionType,
    PayrollPeriod, PayrollRun, PayrollEntry,
    AttendanceRecord,
)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('employeenumber', 'fullname', 'position', 'department', 'statecode', 'hiredate')
    list_filter = ('statecode', 'department', 'salarytype')
    search_fields = ('fullname', 'employeenumber', 'curp', 'rfc')
    readonly_fields = ('employeeid', 'employeenumber', 'fullname', 'createdon', 'modifiedon')


@admin.register(EmployeeProjectAssignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('employeeid', 'projectid', 'role', 'startdate', 'statecode')
    list_filter = ('statecode',)


@admin.register(DeductionType)
class DeductionTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'calculationtype', 'defaultvalue', 'isstatutory', 'statecode')
    list_filter = ('isstatutory', 'statecode')


@admin.register(AdditionType)
class AdditionTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'calculationtype', 'defaultvalue', 'istaxable', 'statecode')
    list_filter = ('istaxable', 'statecode')


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('label', 'periodtype', 'startdate', 'enddate', 'year', 'statecode')
    list_filter = ('periodtype', 'year', 'statecode')


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ('runnumber', 'payrollperiodid', 'employeecount', 'totalnetpay', 'statecode')
    list_filter = ('statecode',)
    readonly_fields = ('payrollrunid', 'runnumber', 'createdon', 'modifiedon')


@admin.register(PayrollEntry)
class PayrollEntryAdmin(admin.ModelAdmin):
    list_display = ('employeeid', 'payrollrunid', 'grosspay', 'totaldeductions', 'netpay', 'paymentstatus')
    list_filter = ('paymentstatus',)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('employeeid', 'attendancedate', 'attendancetype', 'regularhoursworked', 'overtimehoursworked')
    list_filter = ('attendancetype', 'attendancedate')
