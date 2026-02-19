"""
Activity API routers.

Phase 12 Implementation: Activity Management
"""

from ninja import Router, File, Form
from ninja.files import UploadedFile
from django.http import HttpRequest
from typing import List, Optional
from uuid import UUID

from apps.activities.services import ActivityService
from apps.activities.schemas import *
from core.permissions import require_permission, Permission, filter_by_ownership

activities_router = Router(tags=['Activities'])


@activities_router.get('/', response=List[ActivityListItemSchema])
@require_permission(Permission.ACTIVITY_READ)
def list_activities(
    request: HttpRequest,
    state: int = None,
    statecode: Optional[int] = None,
    type: str = None,
    activitytypecode: Optional[str] = None,
    regarding: UUID = None,
    regardingobjectid: Optional[UUID] = None,
    ownerid: Optional[str] = None,
    regardingobjectidtype: Optional[str] = None,
    upcoming: Optional[bool] = None,
    overdue: Optional[bool] = None,
):
    """List all activities with optional filtering."""
    from apps.activities.models import Activity, ActivityStateCode, ACTIVITY_TYPE_INT_MAP
    from django.utils import timezone

    queryset = filter_by_ownership(Activity.objects.all(), request.user)

    # Support both 'state' and 'statecode' param names
    effective_state = statecode if statecode is not None else state
    if effective_state is not None:
        queryset = queryset.filter(statecode=effective_state)

    # Support both 'type' and 'activitytypecode' param names
    # Accept integer codes from frontend and map to string
    effective_type = activitytypecode or type
    if effective_type:
        try:
            int_code = int(effective_type)
            mapped = ACTIVITY_TYPE_INT_MAP.get(int_code)
            if mapped:
                effective_type = mapped
        except (ValueError, TypeError):
            pass
        queryset = queryset.filter(activitytypecode=effective_type)

    # Support both 'regarding' and 'regardingobjectid' param names
    effective_regarding = regardingobjectid or regarding
    if effective_regarding:
        queryset = queryset.filter(regardingobjectid=effective_regarding)
    if ownerid:
        queryset = queryset.filter(ownerid_id=ownerid)
    if regardingobjectidtype:
        queryset = queryset.filter(regardingobjectidtype=regardingobjectidtype)
    if upcoming:
        queryset = queryset.filter(
            statecode=ActivityStateCode.OPEN,
            scheduledstart__gte=timezone.now()
        )
    if overdue:
        queryset = queryset.filter(
            statecode=ActivityStateCode.OPEN,
            scheduledend__lt=timezone.now()
        )

    queryset = queryset.select_related('ownerid')
    return list(queryset)


@activities_router.post('/', response={201: ActivityDetailSchema})
@require_permission(Permission.ACTIVITY_CREATE)
def create_activity(request: HttpRequest, payload: CreateActivityDto):
    """Create a new activity (generic endpoint).

    Accepts activitytypecode as integer:
    1=Email, 2=PhoneCall, 3=Task, 4=Appointment, 5=Meeting, 6=Note.
    Creates the base Activity and any type-specific child record.
    """
    result = ActivityService.create_activity(payload, request.user)
    return 201, result


@activities_router.post('/send-document-email', response={200: SendDocumentEmailResponse})
@require_permission(Permission.ACTIVITY_CREATE)
def send_document_email(
    request: HttpRequest,
    to: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    document_type: str = Form(...),
    document_id: str = Form(...),
    sender_name: str = Form('Sales Team'),
    cc: str = Form(''),
    bcc: str = Form(''),
    pdf_file: UploadedFile = File(None),
):
    """Send a real document email with optional PDF attachment.

    Accepts multipart/form-data with text fields and an optional PDF file.
    Creates a completed Activity + Email record on success.
    """
    pdf_content = None
    pdf_filename = None

    if pdf_file:
        pdf_content = pdf_file.read()
        pdf_filename = pdf_file.name or f'{document_type}-document.pdf'

    activity = ActivityService.send_document_email(
        to=to,
        subject=subject,
        body=body,
        document_type=document_type,
        document_id=document_id,
        sender_name=sender_name,
        cc=cc,
        bcc=bcc,
        pdf_content=pdf_content,
        pdf_filename=pdf_filename,
        user=request.user,
    )

    return {
        'success': True,
        'activityid': activity.activityid,
        'message': 'Email sent successfully',
    }


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


@activities_router.post('/{activity_id}/cancel', response=ActivitySchema)
@require_permission(Permission.ACTIVITY_UPDATE)
def cancel_activity(request: HttpRequest, activity_id: UUID):
    """Cancel an activity (soft delete by setting statecode to Canceled)."""
    ActivityService.delete_activity(activity_id, request.user)
    from apps.activities.models import Activity
    activity = Activity.objects.get(activityid=activity_id)
    return activity


@activities_router.get('/stats/summary', response=ActivityStatsSchema)
@require_permission(Permission.ACTIVITY_READ)
def get_activity_stats(request: HttpRequest, ownerid: Optional[str] = None):
    """Get activity statistics."""
    stats = ActivityService.get_activity_stats(request.user)
    return stats
