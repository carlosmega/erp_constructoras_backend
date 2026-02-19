"""
Activity API routers.

Phase 12 Implementation: Activity Management
"""

from ninja import Router
from django.http import HttpRequest
from typing import List
from uuid import UUID

from apps.activities.services import ActivityService
from apps.activities.schemas import *
from core.permissions import require_permission, Permission, filter_by_ownership
from core.pagination import paginate_queryset, create_paginated_response

PaginatedActivityList = create_paginated_response(ActivityListItemSchema)

activities_router = Router(tags=['Activities'])


@activities_router.get('/', response=PaginatedActivityList)
@require_permission(Permission.ACTIVITY_READ)
def list_activities(request: HttpRequest, page: int = 1, page_size: int = 50, state: int = None, type: str = None, regarding: UUID = None):
    """List all activities with optional filtering and pagination."""
    from apps.activities.models import Activity

    queryset = filter_by_ownership(Activity.objects.all(), request.user)

    if state is not None:
        queryset = queryset.filter(statecode=state)
    if type:
        queryset = queryset.filter(activitytypecode=type)
    if regarding:
        queryset = queryset.filter(regardingobjectid=regarding)

    queryset = queryset.select_related('ownerid')
    return paginate_queryset(queryset, page=page, page_size=page_size, request_url=request.path)


@activities_router.get('/{activity_id}', response=ActivityDetailSchema)
@require_permission(Permission.ACTIVITY_READ)
def get_activity(request: HttpRequest, activity_id: UUID):
    """Get a single activity with full details."""
    activity = ActivityService.get_activity_detail(activity_id, request.user)
    return activity


@activities_router.post('/emails', response={201: EmailSchema})
@require_permission(Permission.ACTIVITY_CREATE)
def create_email(request: HttpRequest, payload: CreateEmailDto):
    """Create a new email activity."""
    email = ActivityService.create_email(payload, request.user)
    return 201, email


@activities_router.post('/phonecalls', response={201: PhoneCallSchema})
@require_permission(Permission.ACTIVITY_CREATE)
def create_phonecall(request: HttpRequest, payload: CreatePhoneCallDto):
    """Create a new phone call activity."""
    phonecall = ActivityService.create_phonecall(payload, request.user)
    return 201, phonecall


@activities_router.post('/tasks', response={201: TaskSchema})
@require_permission(Permission.ACTIVITY_CREATE)
def create_task(request: HttpRequest, payload: CreateTaskDto):
    """Create a new task activity."""
    task = ActivityService.create_task(payload, request.user)
    return 201, task


@activities_router.post('/appointments', response={201: AppointmentSchema})
@require_permission(Permission.ACTIVITY_CREATE)
def create_appointment(request: HttpRequest, payload: CreateAppointmentDto):
    """Create a new appointment activity."""
    appointment = ActivityService.create_appointment(payload, request.user)
    return 201, appointment


@activities_router.patch('/{activity_id}', response=ActivitySchema)
@require_permission(Permission.ACTIVITY_UPDATE)
def update_activity(request: HttpRequest, activity_id: UUID, payload: UpdateActivityDto):
    """Update an existing activity."""
    activity = ActivityService.update_activity(activity_id, payload, request.user)
    return activity


@activities_router.delete('/{activity_id}', response={204: None})
@require_permission(Permission.ACTIVITY_DELETE)
def delete_activity(request: HttpRequest, activity_id: UUID):
    """Delete an activity (soft delete)."""
    ActivityService.delete_activity(activity_id, request.user)
    return 204, None


@activities_router.post('/{activity_id}/complete', response=ActivitySchema)
@require_permission(Permission.ACTIVITY_UPDATE)
def complete_activity(request: HttpRequest, activity_id: UUID, payload: CompleteActivityDto):
    """Mark an activity as completed."""
    activity = ActivityService.complete_activity(activity_id, payload, request.user)
    return activity


@activities_router.get('/stats/summary', response=ActivityStatsSchema)
@require_permission(Permission.ACTIVITY_READ)
def get_activity_stats(request: HttpRequest):
    """Get activity statistics."""
    stats = ActivityService.get_activity_stats(request.user)
    return stats
