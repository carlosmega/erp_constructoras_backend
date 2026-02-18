"""Django admin configuration for Activity models."""

from django.contrib import admin
from apps.activities.models import Activity, Email, PhoneCall, Task, Appointment


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['subject', 'activitytypecode', 'statecode', 'ownerid', 'scheduledstart', 'createdon']
    list_filter = ['activitytypecode', 'statecode', 'prioritycode', 'createdon']
    search_fields = ['subject', 'description']
    readonly_fields = ['activityid', 'createdon', 'modifiedon', 'createdby', 'modifiedby']


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ['activity', 'to', 'sender', 'directioncode']
    search_fields = ['activity__subject', 'to', 'sender']


@admin.register(PhoneCall)
class PhoneCallAdmin(admin.ModelAdmin):
    list_display = ['activity', 'phonenumber', 'directioncode']
    search_fields = ['activity__subject', 'phonenumber']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['activity', 'percentcomplete']
    search_fields = ['activity__subject']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['activity', 'location']
    search_fields = ['activity__subject', 'location']
