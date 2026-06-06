"""
Activity business logic services.

Phase 12 Implementation: Activity Management
"""

import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from uuid import UUID

from apps.activities.models import Activity, Email, PhoneCall, Task, Appointment, ActivityStateCode, ActivityTypeCode, ACTIVITY_TYPE_INT_MAP
from apps.activities.schemas import *
from apps.users.models import SystemUser
from core.exceptions import ValidationError, PermissionDenied

logger = logging.getLogger(__name__)


class ActivityService:
    """Business logic for Activity operations."""

    @staticmethod
    def create_activity(payload: CreateActivityDto, user: SystemUser) -> dict:
        """Create an activity from the generic DTO.

        Maps frontend integer activitytypecode to backend string type,
        creates the base Activity and any type-specific child record.
        Returns dict matching ActivityDetailSchema.
        """
        # Map integer type code to string
        type_code_str = ACTIVITY_TYPE_INT_MAP.get(payload.activitytypecode)
        if not type_code_str:
            raise ValidationError(
                f"Invalid activitytypecode: {payload.activitytypecode}. "
                "Must be 1 (Email), 2 (PhoneCall), 3 (Task), 4 (Appointment), 5 (Meeting), or 6 (Note)."
            )

        # Create base activity
        activity = Activity.objects.create(
            activitytypecode=type_code_str,
            subject=payload.subject,
            description=payload.description,
            scheduledstart=payload.scheduledstart,
            scheduledend=payload.scheduledend,
            prioritycode=payload.prioritycode,
            regardingobjectid=payload.regardingobjectid,
            regardingobjectidtype=payload.regardingobjectidtype,
            ownerid_id=payload.ownerid,
            createdby=user,
            modifiedby=user,
        )

        # Create type-specific child records with defaults
        result = {
            'activity': activity,
            'email': None,
            'phonecall': None,
            'task': None,
            'appointment': None,
        }

        if type_code_str == ActivityTypeCode.EMAIL:
            email = Email.objects.create(activity=activity)
            result['email'] = {
                'to': email.to,
                'sender': email.sender,
                'cc': email.cc,
                'bcc': email.bcc,
                'body': email.body,
                'directioncode': email.directioncode,
            }
        elif type_code_str == ActivityTypeCode.PHONECALL:
            phonecall = PhoneCall.objects.create(activity=activity)
            result['phonecall'] = {
                'phonenumber': phonecall.phonenumber,
                'directioncode': phonecall.directioncode,
            }
        elif type_code_str == ActivityTypeCode.TASK:
            task = Task.objects.create(activity=activity, percentcomplete=0)
            result['task'] = {
                'percentcomplete': task.percentcomplete,
            }
        elif type_code_str == ActivityTypeCode.APPOINTMENT:
            appointment = Appointment.objects.create(activity=activity)
            result['appointment'] = {
                'location': appointment.location,
                'requiredattendees': appointment.requiredattendees,
                'optionalattendees': appointment.optionalattendees,
            }
        # Meeting and Note types: base activity only, no child record needed

        # Avoid an extra SystemUser query when the owner is the acting user (common case).
        if payload.ownerid == user.systemuserid:
            owner = user
        else:
            try:
                owner = SystemUser.objects.get(systemuserid=payload.ownerid)
            except SystemUser.DoesNotExist:
                owner = None

        if owner is not None:
            from apps.notifications.signals import activity_assigned
            activity_assigned.send(
                sender=Activity,
                activity_type=str(type_code_str),
                activity_id=activity.activityid,
                activity_subject=payload.subject,
                owner=owner,
                actor=user,
            )

        return result

    @staticmethod
    def create_email(payload: CreateEmailDto, user: SystemUser) -> Email:
        """Create a new email activity."""
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject=payload.subject,
            description=payload.description,
            regardingobjectid=payload.regardingobjectid,
            regardingobjectidtype=payload.regardingobjectidtype,
            ownerid_id=payload.ownerid,
            createdby=user,
            modifiedby=user
        )

        email = Email.objects.create(
            activity=activity,
            to=payload.to,
            sender=payload.sender,
            cc=payload.cc,
            bcc=payload.bcc,
            body=payload.body,
            directioncode=payload.directioncode,
            messageid=getattr(payload, 'messageid', None),
            inreplyto=getattr(payload, 'inreplyto', None),
        )

        # Auto-match: if no regarding object provided, try to match automatically
        if not payload.regardingobjectid:
            try:
                from apps.activities.matching_service import EmailMatchingService
                match_result = EmailMatchingService.match_email(email)
                if match_result.get('matched'):
                    activity.regardingobjectid = match_result['regardingobjectid']
                    activity.regardingobjectidtype = match_result['regardingobjectidtype']
                    activity.save()
                    email.matchmethod = match_result['matchmethod']
                    email.matchconfidence = match_result['matchconfidence']
                    email.save()
            except Exception:
                logger.exception(
                    "Email auto-match failed (activity_id=%s)", activity.activityid
                )

        return email

    @staticmethod
    def create_phonecall(payload: CreatePhoneCallDto, user: SystemUser) -> PhoneCall:
        """Create a new phone call activity."""
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.PHONECALL,
            subject=payload.subject,
            description=payload.description,
            scheduledstart=payload.scheduledstart,
            scheduledend=payload.scheduledend,
            regardingobjectid=payload.regardingobjectid,
            regardingobjectidtype=payload.regardingobjectidtype,
            ownerid_id=payload.ownerid,
            createdby=user,
            modifiedby=user
        )

        phonecall = PhoneCall.objects.create(
            activity=activity,
            phonenumber=payload.phonenumber,
            directioncode=payload.directioncode
        )

        return phonecall

    @staticmethod
    def create_task(payload: CreateTaskDto, user: SystemUser) -> Task:
        """Create a new task activity."""
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.TASK,
            subject=payload.subject,
            description=payload.description,
            scheduledstart=payload.scheduledstart,
            scheduledend=payload.scheduledend,
            prioritycode=payload.prioritycode,
            regardingobjectid=payload.regardingobjectid,
            regardingobjectidtype=payload.regardingobjectidtype,
            ownerid_id=payload.ownerid,
            createdby=user,
            modifiedby=user
        )

        task = Task.objects.create(
            activity=activity,
            percentcomplete=0
        )

        return task

    @staticmethod
    def create_appointment(payload: CreateAppointmentDto, user: SystemUser) -> Appointment:
        """Create a new appointment activity."""
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.APPOINTMENT,
            subject=payload.subject,
            description=payload.description,
            scheduledstart=payload.scheduledstart,
            scheduledend=payload.scheduledend,
            statecode=ActivityStateCode.SCHEDULED,
            regardingobjectid=payload.regardingobjectid,
            regardingobjectidtype=payload.regardingobjectidtype,
            ownerid_id=payload.ownerid,
            createdby=user,
            modifiedby=user
        )

        appointment = Appointment.objects.create(
            activity=activity,
            location=payload.location,
            requiredattendees=payload.requiredattendees,
            optionalattendees=payload.optionalattendees
        )

        return appointment

    @staticmethod
    def get_activity_detail(activity_id: UUID, user: SystemUser) -> dict:
        """Get detailed activity information with type-specific details."""
        from core.permissions import check_ownership

        activity = get_object_or_404(Activity, activityid=activity_id)

        # Check if user has permission to view this activity
        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to view this activity")

        result = {
            'activity': activity,
            'email': None,
            'phonecall': None,
            'task': None,
            'appointment': None
        }

        # Get type-specific details
        if activity.activitytypecode == ActivityTypeCode.EMAIL:
            try:
                email = Email.objects.get(activity=activity)
                result['email'] = {
                    'to': email.to,
                    'sender': email.sender,
                    'cc': email.cc,
                    'bcc': email.bcc,
                    'body': email.body,
                    'directioncode': email.directioncode
                }
            except Email.DoesNotExist:
                pass

        elif activity.activitytypecode == ActivityTypeCode.PHONECALL:
            try:
                phonecall = PhoneCall.objects.get(activity=activity)
                result['phonecall'] = {
                    'phonenumber': phonecall.phonenumber,
                    'directioncode': phonecall.directioncode
                }
            except PhoneCall.DoesNotExist:
                pass

        elif activity.activitytypecode == ActivityTypeCode.TASK:
            try:
                task = Task.objects.get(activity=activity)
                result['task'] = {
                    'percentcomplete': task.percentcomplete
                }
            except Task.DoesNotExist:
                pass

        elif activity.activitytypecode == ActivityTypeCode.APPOINTMENT:
            try:
                appointment = Appointment.objects.get(activity=activity)
                result['appointment'] = {
                    'location': appointment.location,
                    'requiredattendees': appointment.requiredattendees,
                    'optionalattendees': appointment.optionalattendees
                }
            except Appointment.DoesNotExist:
                pass

        return result

    @staticmethod
    def update_activity(activity_id: UUID, payload: UpdateActivityDto, user: SystemUser) -> Activity:
        """Update an existing activity."""
        from core.permissions import check_ownership

        activity = get_object_or_404(Activity, activityid=activity_id)

        # Check if user has permission to update this activity
        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to update this activity")

        # Update fields if provided
        if payload.subject is not None:
            activity.subject = payload.subject
        if payload.description is not None:
            activity.description = payload.description
        if payload.statecode is not None:
            activity.statecode = payload.statecode
        if payload.statuscode is not None:
            activity.statuscode = payload.statuscode
        if payload.scheduledstart is not None:
            activity.scheduledstart = payload.scheduledstart
        if payload.scheduledend is not None:
            activity.scheduledend = payload.scheduledend
        if payload.actualstart is not None:
            activity.actualstart = payload.actualstart
        if payload.actualend is not None:
            activity.actualend = payload.actualend
        if payload.actualdurationminutes is not None:
            activity.actualdurationminutes = payload.actualdurationminutes
        if payload.prioritycode is not None:
            activity.prioritycode = payload.prioritycode
        if payload.regardingobjectid is not None:
            activity.regardingobjectid = payload.regardingobjectid
        if payload.regardingobjectidtype is not None:
            activity.regardingobjectidtype = payload.regardingobjectidtype

        activity.modifiedby = user
        activity.save()

        return activity

    @staticmethod
    def delete_activity(activity_id: UUID, user: SystemUser) -> None:
        """Delete an activity (soft delete by setting statecode to Canceled)."""
        from core.permissions import check_ownership

        activity = get_object_or_404(Activity, activityid=activity_id)

        # Check if user has permission to delete this activity
        if not check_ownership(user, activity):
            raise PermissionDenied("You don't have permission to delete this activity")

        # Soft delete: set state to Canceled (2)
        activity.statecode = ActivityStateCode.CANCELED
        activity.modifiedby = user
        activity.save()

    @staticmethod
    def complete_activity(activity_id: UUID, payload: CompleteActivityDto, user: SystemUser) -> Activity:
        """Mark an activity as completed.

        Accepts both CDS names and snake_case names from frontend.
        """
        activity = get_object_or_404(Activity, activityid=activity_id)

        activity.statecode = ActivityStateCode.COMPLETED
        # Accept both CDS and snake_case field names
        actual_end = payload.actualend or payload.actual_end
        actual_start = payload.actual_start
        actual_duration = payload.actualdurationminutes or payload.actual_duration_minutes

        activity.actualend = actual_end or timezone.now()
        if actual_start:
            activity.actualstart = actual_start
        if actual_duration:
            activity.actualdurationminutes = actual_duration
        activity.modifiedby = user
        activity.save()

        return activity

    @staticmethod
    def send_document_email(
        *,
        to: str,
        subject: str,
        body: str,
        document_type: str,
        document_id: str,
        sender_name: str = 'Sales Team',
        cc: str = '',
        bcc: str = '',
        pdf_content: bytes | None = None,
        pdf_filename: str | None = None,
        user: SystemUser,
    ) -> Activity:
        """Send a real email with optional PDF and create a completed Activity record.

        First sends the email; if that fails, raises ValidationError without
        creating a phantom Activity. On success, creates Activity + Email child.
        """
        from core.email_service import send_document_email as _send_email, EmailSendError

        # 1. Send the real email (fail-fast: no Activity if this fails)
        try:
            _send_email(
                to=to,
                subject=subject,
                body=body,
                document_type=document_type,
                sender_name=sender_name,
                cc=cc,
                bcc=bcc,
                pdf_content=pdf_content,
                pdf_filename=pdf_filename,
            )
        except EmailSendError as exc:
            raise ValidationError(str(exc))

        # 2. Create completed Activity + Email child
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject=subject,
            description=f'TO: {to}' + (f'\nCC: {cc}' if cc else '') + (f'\nBCC: {bcc}' if bcc else '') + f'\n\n{body}',
            statecode=ActivityStateCode.COMPLETED,
            actualend=timezone.now(),
            regardingobjectid=document_id if document_id else None,
            regardingobjectidtype=document_type,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )

        Email.objects.create(
            activity=activity,
            to=to,
            sender=sender_name,
            cc=cc or None,
            bcc=bcc or None,
            body=body,
            directioncode=True,
        )

        return activity

    @staticmethod
    def get_activity_stats(user: SystemUser):
        """Get activity statistics."""
        from django.db.models import Count, Q
        from core.permissions import filter_by_ownership

        queryset = filter_by_ownership(Activity.objects.all(), user)

        total = queryset.count()
        open_count = queryset.filter(statecode=ActivityStateCode.OPEN).count()
        completed = queryset.filter(statecode=ActivityStateCode.COMPLETED).count()

        # Overdue activities (open with scheduledend in the past)
        overdue = queryset.filter(
            statecode=ActivityStateCode.OPEN,
            scheduledend__lt=timezone.now()
        ).count()

        # Group by type
        by_type = dict(queryset.values_list('activitytypecode').annotate(count=Count('activityid')))

        return {
            'total_activities': total,
            'open_activities': open_count,
            'completed_activities': completed,
            'overdue_activities': overdue,
            'by_type': by_type
        }
