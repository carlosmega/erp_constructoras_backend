"""
Unit tests for Activity services.

Tests activity CRUD operations, type-specific creation, state transitions,
completion workflow, and ownership-based access control.
"""

import pytest
from uuid import uuid4
from django.utils import timezone

from apps.activities.models import (
    Activity,
    Email,
    PhoneCall,
    Task,
    Appointment,
    ActivityTypeCode,
    ActivityStateCode,
    PriorityCode,
)
from apps.activities.services import ActivityService
from apps.activities.schemas import (
    CreateActivityDto,
    UpdateActivityDto,
    CompleteActivityDto,
    CreateEmailDto,
    CreatePhoneCallDto,
    CreateTaskDto,
    CreateAppointmentDto,
)
from apps.activities.tests.factories import ActivityFactory, EmailActivityFactory, TaskActivityFactory
from apps.users.tests.factories import SalespersonFactory
from core.exceptions import ValidationError, PermissionDenied


@pytest.mark.unit
class TestCreateActivity:
    """Tests for ActivityService.create_activity method."""

    def test_create_task_activity(self, db, salesperson):
        """Test creating a task activity via generic create."""
        dto = CreateActivityDto(
            activitytypecode=3,  # Task
            subject='Follow up',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.activityid is not None
        assert activity.subject == 'Follow up'
        assert activity.activitytypecode == ActivityTypeCode.TASK
        assert activity.statecode == ActivityStateCode.OPEN
        assert activity.ownerid == salesperson
        assert result['task'] is not None
        assert result['task']['percentcomplete'] == 0

    def test_create_email_activity_generic(self, db, salesperson):
        """Test creating an email activity via generic create."""
        dto = CreateActivityDto(
            activitytypecode=1,  # Email
            subject='Test Email',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.activitytypecode == ActivityTypeCode.EMAIL
        assert result['email'] is not None

    def test_create_phonecall_activity_generic(self, db, salesperson):
        """Test creating a phone call activity via generic create."""
        dto = CreateActivityDto(
            activitytypecode=2,  # PhoneCall
            subject='Client Call',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.activitytypecode == ActivityTypeCode.PHONECALL
        assert result['phonecall'] is not None

    def test_create_appointment_activity_generic(self, db, salesperson):
        """Test creating an appointment activity via generic create."""
        dto = CreateActivityDto(
            activitytypecode=4,  # Appointment
            subject='Team Meeting',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.activitytypecode == ActivityTypeCode.APPOINTMENT
        assert result['appointment'] is not None

    def test_create_note_activity(self, db, salesperson):
        """Test creating a note activity (no child record)."""
        dto = CreateActivityDto(
            activitytypecode=6,  # Note
            subject='General Note',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.activitytypecode == ActivityTypeCode.NOTE
        assert result['email'] is None
        assert result['phonecall'] is None
        assert result['task'] is None
        assert result['appointment'] is None

    def test_create_activity_invalid_type(self, db, salesperson):
        """Test creating an activity with invalid type code."""
        dto = CreateActivityDto(
            activitytypecode=99,
            subject='Invalid',
            ownerid=salesperson.systemuserid,
        )

        with pytest.raises(ValidationError, match='Invalid activitytypecode'):
            ActivityService.create_activity(dto, salesperson)

    def test_create_activity_with_regarding(self, db, salesperson):
        """Test creating an activity linked to a regarding object."""
        lead_id = uuid4()
        dto = CreateActivityDto(
            activitytypecode=3,
            subject='Follow up on lead',
            regardingobjectid=lead_id,
            regardingobjectidtype='lead',
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        activity = result['activity']
        assert activity.regardingobjectid == lead_id
        assert activity.regardingobjectidtype == 'lead'

    def test_create_activity_with_priority(self, db, salesperson):
        """Test creating an activity with priority code."""
        dto = CreateActivityDto(
            activitytypecode=3,
            subject='Urgent Task',
            prioritycode=PriorityCode.HIGH,
            ownerid=salesperson.systemuserid,
        )

        result = ActivityService.create_activity(dto, salesperson)

        assert result['activity'].prioritycode == PriorityCode.HIGH


@pytest.mark.unit
class TestCreateSpecificActivities:
    """Tests for type-specific activity creation methods."""

    def test_create_email(self, db, salesperson):
        """Test creating an email activity with details."""
        dto = CreateEmailDto(
            subject='Project Update',
            to='client@example.com',
            sender='sales@company.com',
            cc='manager@company.com',
            body='Here is the update...',
            directioncode=True,
            ownerid=salesperson.systemuserid,
        )

        email = ActivityService.create_email(dto, salesperson)

        assert email.activity.subject == 'Project Update'
        assert email.activity.activitytypecode == ActivityTypeCode.EMAIL
        assert email.to == 'client@example.com'
        assert email.sender == 'sales@company.com'
        assert email.directioncode is True

    def test_create_phonecall(self, db, salesperson):
        """Test creating a phone call activity with details."""
        dto = CreatePhoneCallDto(
            subject='Sales Call',
            phonenumber='555-1234',
            directioncode=False,  # Incoming
            ownerid=salesperson.systemuserid,
        )

        phonecall = ActivityService.create_phonecall(dto, salesperson)

        assert phonecall.activity.subject == 'Sales Call'
        assert phonecall.activity.activitytypecode == ActivityTypeCode.PHONECALL
        assert phonecall.phonenumber == '555-1234'
        assert phonecall.directioncode is False

    def test_create_task(self, db, salesperson):
        """Test creating a task activity."""
        dto = CreateTaskDto(
            subject='Prepare Proposal',
            description='Draft proposal for Q1',
            prioritycode=PriorityCode.HIGH,
            ownerid=salesperson.systemuserid,
        )

        task = ActivityService.create_task(dto, salesperson)

        assert task.activity.subject == 'Prepare Proposal'
        assert task.activity.activitytypecode == ActivityTypeCode.TASK
        assert task.percentcomplete == 0
        assert task.activity.prioritycode == PriorityCode.HIGH

    def test_create_appointment(self, db, salesperson):
        """Test creating an appointment activity."""
        now = timezone.now()
        dto = CreateAppointmentDto(
            subject='Client Meeting',
            location='Conference Room B',
            scheduledstart=now,
            scheduledend=now,
            ownerid=salesperson.systemuserid,
        )

        appointment = ActivityService.create_appointment(dto, salesperson)

        assert appointment.activity.subject == 'Client Meeting'
        assert appointment.activity.activitytypecode == ActivityTypeCode.APPOINTMENT
        assert appointment.activity.statecode == ActivityStateCode.SCHEDULED
        assert appointment.location == 'Conference Room B'


@pytest.mark.unit
class TestGetActivityDetail:
    """Tests for ActivityService.get_activity_detail method."""

    def test_get_task_detail(self, db, salesperson):
        """Test getting task activity detail."""
        activity = ActivityFactory(ownerid=salesperson, activitytypecode=ActivityTypeCode.TASK)
        Task.objects.create(activity=activity, percentcomplete=25)

        result = ActivityService.get_activity_detail(activity.activityid, salesperson)

        assert result['activity'].activityid == activity.activityid
        assert result['task'] is not None
        assert result['task']['percentcomplete'] == 25

    def test_get_activity_detail_permission_denied(self, db, salesperson, salesperson2):
        """Test that non-owner cannot view activity detail."""
        activity = ActivityFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied):
            ActivityService.get_activity_detail(activity.activityid, salesperson)

    def test_get_activity_detail_admin_access(self, db, system_admin, salesperson):
        """Test that admin can view any activity detail."""
        activity = ActivityFactory(ownerid=salesperson)

        result = ActivityService.get_activity_detail(activity.activityid, system_admin)

        assert result['activity'].activityid == activity.activityid


@pytest.mark.unit
class TestUpdateActivity:
    """Tests for ActivityService.update_activity method."""

    def test_update_activity_subject(self, db, salesperson):
        """Test updating activity subject."""
        activity = ActivityFactory(ownerid=salesperson, subject='Old Subject')

        dto = UpdateActivityDto(subject='New Subject')

        updated = ActivityService.update_activity(activity.activityid, dto, salesperson)

        assert updated.subject == 'New Subject'
        assert updated.modifiedby == salesperson

    def test_update_activity_state(self, db, salesperson):
        """Test updating activity state."""
        activity = ActivityFactory(ownerid=salesperson, statecode=ActivityStateCode.OPEN)

        dto = UpdateActivityDto(statecode=ActivityStateCode.COMPLETED)

        updated = ActivityService.update_activity(activity.activityid, dto, salesperson)

        assert updated.statecode == ActivityStateCode.COMPLETED

    def test_update_activity_priority(self, db, salesperson):
        """Test updating activity priority."""
        activity = ActivityFactory(ownerid=salesperson, prioritycode=PriorityCode.NORMAL)

        dto = UpdateActivityDto(prioritycode=PriorityCode.HIGH)

        updated = ActivityService.update_activity(activity.activityid, dto, salesperson)

        assert updated.prioritycode == PriorityCode.HIGH

    def test_update_activity_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot update activity."""
        activity = ActivityFactory(ownerid=salesperson2)

        dto = UpdateActivityDto(subject='Hacked')

        with pytest.raises(PermissionDenied):
            ActivityService.update_activity(activity.activityid, dto, salesperson)


@pytest.mark.unit
class TestDeleteActivity:
    """Tests for ActivityService.delete_activity method."""

    def test_delete_activity_soft_delete(self, db, salesperson):
        """Test deleting an activity (soft delete sets state to Canceled)."""
        activity = ActivityFactory(ownerid=salesperson, statecode=ActivityStateCode.OPEN)

        ActivityService.delete_activity(activity.activityid, salesperson)

        activity.refresh_from_db()
        assert activity.statecode == ActivityStateCode.CANCELED

    def test_delete_activity_not_owner(self, db, salesperson, salesperson2):
        """Test that non-owner cannot delete activity."""
        activity = ActivityFactory(ownerid=salesperson2)

        with pytest.raises(PermissionDenied):
            ActivityService.delete_activity(activity.activityid, salesperson)


@pytest.mark.unit
class TestCompleteActivity:
    """Tests for ActivityService.complete_activity method."""

    def test_complete_activity(self, db, salesperson):
        """Test completing an activity."""
        activity = ActivityFactory(ownerid=salesperson, statecode=ActivityStateCode.OPEN)

        dto = CompleteActivityDto()

        completed = ActivityService.complete_activity(activity.activityid, dto, salesperson)

        assert completed.statecode == ActivityStateCode.COMPLETED
        assert completed.actualend is not None

    def test_complete_activity_with_duration(self, db, salesperson):
        """Test completing an activity with actual duration."""
        activity = ActivityFactory(ownerid=salesperson, statecode=ActivityStateCode.OPEN)

        now = timezone.now()
        dto = CompleteActivityDto(
            actualend=now,
            actualdurationminutes=30,
        )

        completed = ActivityService.complete_activity(activity.activityid, dto, salesperson)

        assert completed.statecode == ActivityStateCode.COMPLETED
        assert completed.actualend == now
        assert completed.actualdurationminutes == 30


@pytest.mark.unit
class TestGetActivityStats:
    """Tests for ActivityService.get_activity_stats method."""

    def test_get_stats_count_by_state(self, db, salesperson):
        """Test getting activity statistics - counts by state."""
        ActivityFactory.create_batch(3, ownerid=salesperson, statecode=ActivityStateCode.OPEN)
        ActivityFactory.create_batch(2, ownerid=salesperson, statecode=ActivityStateCode.COMPLETED)
        ActivityFactory(ownerid=salesperson, statecode=ActivityStateCode.CANCELED)

        stats = ActivityService.get_activity_stats(salesperson)

        assert stats['total_activities'] == 6
        assert stats['open_activities'] == 3
        assert stats['completed_activities'] == 2

    def test_get_stats_respects_ownership(self, db, salesperson, salesperson2):
        """Test that stats only include user's own activities."""
        ActivityFactory.create_batch(3, ownerid=salesperson)
        ActivityFactory.create_batch(5, ownerid=salesperson2)

        stats = ActivityService.get_activity_stats(salesperson)

        assert stats['total_activities'] == 3
