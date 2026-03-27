"""
Unit tests for Activity models.

Tests Activity base model and type-specific models (Email, PhoneCall, Task, Appointment),
including enums, state management, validation, and computed properties.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.activities.models import (
    Activity,
    Email,
    PhoneCall,
    Task,
    Appointment,
    ActivityTypeCode,
    ActivityStateCode,
    PriorityCode,
    MatchMethod,
    ACTIVITY_TYPE_INT_MAP,
    ACTIVITY_TYPE_STR_MAP,
)
from apps.activities.tests.factories import (
    ActivityFactory,
    EmailActivityFactory,
    TaskActivityFactory,
)
from apps.users.tests.factories import SalespersonFactory


@pytest.mark.unit
class TestActivityEnums:
    """Tests for Activity enum definitions."""

    def test_activity_type_code_values(self):
        """Test ActivityTypeCode enum values."""
        assert ActivityTypeCode.EMAIL.value == 'email'
        assert ActivityTypeCode.PHONECALL.value == 'phonecall'
        assert ActivityTypeCode.TASK.value == 'task'
        assert ActivityTypeCode.APPOINTMENT.value == 'appointment'
        assert ActivityTypeCode.MEETING.value == 'meeting'
        assert ActivityTypeCode.NOTE.value == 'note'

        assert ActivityTypeCode.EMAIL.label == 'Email'
        assert ActivityTypeCode.PHONECALL.label == 'Phone Call'
        assert ActivityTypeCode.TASK.label == 'Task'
        assert ActivityTypeCode.APPOINTMENT.label == 'Appointment'

    def test_activity_state_code_values(self):
        """Test ActivityStateCode enum values."""
        assert ActivityStateCode.OPEN.value == 0
        assert ActivityStateCode.COMPLETED.value == 1
        assert ActivityStateCode.CANCELED.value == 2
        assert ActivityStateCode.SCHEDULED.value == 3

        assert ActivityStateCode.OPEN.label == 'Open'
        assert ActivityStateCode.COMPLETED.label == 'Completed'
        assert ActivityStateCode.CANCELED.label == 'Canceled'
        assert ActivityStateCode.SCHEDULED.label == 'Scheduled'

    def test_priority_code_values(self):
        """Test PriorityCode enum values."""
        assert PriorityCode.LOW.value == 0
        assert PriorityCode.NORMAL.value == 1
        assert PriorityCode.HIGH.value == 2

        assert PriorityCode.LOW.label == 'Low'
        assert PriorityCode.NORMAL.label == 'Normal'
        assert PriorityCode.HIGH.label == 'High'

    def test_match_method_values(self):
        """Test MatchMethod enum values."""
        assert MatchMethod.EMAIL_ADDRESS.value == 'email_address'
        assert MatchMethod.TRACKING_TOKEN.value == 'tracking_token'
        assert MatchMethod.THREAD_CORRELATION.value == 'thread_correlation'
        assert MatchMethod.MANUAL.value == 'manual'

    def test_activity_type_int_map(self):
        """Test integer-to-string type code mapping."""
        assert ACTIVITY_TYPE_INT_MAP[1] == ActivityTypeCode.EMAIL
        assert ACTIVITY_TYPE_INT_MAP[2] == ActivityTypeCode.PHONECALL
        assert ACTIVITY_TYPE_INT_MAP[3] == ActivityTypeCode.TASK
        assert ACTIVITY_TYPE_INT_MAP[4] == ActivityTypeCode.APPOINTMENT
        assert ACTIVITY_TYPE_INT_MAP[5] == ActivityTypeCode.MEETING
        assert ACTIVITY_TYPE_INT_MAP[6] == ActivityTypeCode.NOTE

    def test_activity_type_str_map_reverse(self):
        """Test string-to-integer reverse mapping."""
        assert ACTIVITY_TYPE_STR_MAP[ActivityTypeCode.EMAIL] == 1
        assert ACTIVITY_TYPE_STR_MAP[ActivityTypeCode.TASK] == 3


@pytest.mark.unit
class TestActivityModel:
    """Tests for Activity model creation and basic operations."""

    def test_create_activity_minimal(self, db):
        """Test creating an activity with minimal required fields."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.TASK,
            subject='Test Task',
            ownerid=owner,
        )

        assert activity.activityid is not None
        assert activity.subject == 'Test Task'
        assert activity.activitytypecode == ActivityTypeCode.TASK
        assert activity.statecode == ActivityStateCode.OPEN
        assert activity.prioritycode == PriorityCode.NORMAL
        assert activity.ownerid == owner

    def test_create_activity_full(self, db):
        """Test creating an activity with all fields."""
        from django.utils import timezone
        from uuid import uuid4

        owner = SalespersonFactory()
        now = timezone.now()
        regarding_id = uuid4()

        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject='Follow up email',
            description='Discuss project details',
            statecode=ActivityStateCode.OPEN,
            prioritycode=PriorityCode.HIGH,
            scheduledstart=now,
            scheduledend=now,
            regardingobjectid=regarding_id,
            regardingobjectidtype='lead',
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )

        assert activity.activityid is not None
        assert activity.activitytypecode == ActivityTypeCode.EMAIL
        assert activity.description == 'Discuss project details'
        assert activity.prioritycode == PriorityCode.HIGH
        assert activity.regardingobjectid == regarding_id
        assert activity.regardingobjectidtype == 'lead'

    def test_activity_factory(self, db):
        """Test ActivityFactory creates valid activities."""
        activity = ActivityFactory()

        assert activity.activityid is not None
        assert activity.subject is not None
        assert activity.ownerid is not None
        assert activity.statecode == ActivityStateCode.OPEN

    def test_activity_str_representation(self, db):
        """Test __str__ method."""
        activity = ActivityFactory(
            activitytypecode=ActivityTypeCode.TASK,
            subject='Review proposal',
        )
        assert str(activity) == 'Task: Review proposal'

        email_activity = EmailActivityFactory(subject='Follow up')
        assert str(email_activity) == 'Email: Follow up'


@pytest.mark.unit
class TestActivityProperties:
    """Tests for Activity computed properties."""

    def test_state_name_property(self, db):
        """Test state_name property returns human-readable name."""
        open_activity = ActivityFactory(statecode=ActivityStateCode.OPEN)
        completed_activity = ActivityFactory(statecode=ActivityStateCode.COMPLETED)
        canceled_activity = ActivityFactory(statecode=ActivityStateCode.CANCELED)
        scheduled_activity = ActivityFactory(statecode=ActivityStateCode.SCHEDULED)

        assert open_activity.state_name == 'Open'
        assert completed_activity.state_name == 'Completed'
        assert canceled_activity.state_name == 'Canceled'
        assert scheduled_activity.state_name == 'Scheduled'

    def test_priority_name_property(self, db):
        """Test priority_name property returns human-readable name."""
        low_activity = ActivityFactory(prioritycode=PriorityCode.LOW)
        normal_activity = ActivityFactory(prioritycode=PriorityCode.NORMAL)
        high_activity = ActivityFactory(prioritycode=PriorityCode.HIGH)

        assert low_activity.priority_name == 'Low'
        assert normal_activity.priority_name == 'Normal'
        assert high_activity.priority_name == 'High'

    def test_priority_name_none(self, db):
        """Test priority_name property when prioritycode is None."""
        activity = ActivityFactory(prioritycode=None)
        assert activity.priority_name is None


@pytest.mark.unit
class TestEmailModel:
    """Tests for Email model."""

    def test_create_email(self, db):
        """Test creating an Email with activity."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject='Test Email',
            ownerid=owner,
        )

        email = Email.objects.create(
            activity=activity,
            to='recipient@example.com',
            sender='sender@example.com',
            cc='cc@example.com',
            body='Email body content',
            directioncode=True,
        )

        assert email.activity == activity
        assert email.to == 'recipient@example.com'
        assert email.sender == 'sender@example.com'
        assert email.directioncode is True

    def test_email_str_representation(self, db):
        """Test Email __str__ method."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject='Important Email',
            ownerid=owner,
        )
        email = Email.objects.create(activity=activity)

        assert str(email) == 'Email: Important Email'

    def test_email_matching_fields(self, db):
        """Test Email matching-specific fields."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.EMAIL,
            subject='Test',
            ownerid=owner,
        )
        email = Email.objects.create(
            activity=activity,
            messageid='<msg123@example.com>',
            inreplyto='<parent@example.com>',
            trackingtokenid='CRM:OPP-abc12345',
            matchconfidence=85,
            matchmethod=MatchMethod.TRACKING_TOKEN,
        )

        assert email.messageid == '<msg123@example.com>'
        assert email.inreplyto == '<parent@example.com>'
        assert email.trackingtokenid == 'CRM:OPP-abc12345'
        assert email.matchconfidence == 85
        assert email.matchmethod == MatchMethod.TRACKING_TOKEN


@pytest.mark.unit
class TestPhoneCallModel:
    """Tests for PhoneCall model."""

    def test_create_phonecall(self, db):
        """Test creating a PhoneCall with activity."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.PHONECALL,
            subject='Call with client',
            ownerid=owner,
        )

        phonecall = PhoneCall.objects.create(
            activity=activity,
            phonenumber='555-1234',
            directioncode=True,
        )

        assert phonecall.activity == activity
        assert phonecall.phonenumber == '555-1234'
        assert phonecall.directioncode is True

    def test_phonecall_str_representation(self, db):
        """Test PhoneCall __str__ method."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.PHONECALL,
            subject='Sales Call',
            ownerid=owner,
        )
        phonecall = PhoneCall.objects.create(activity=activity)

        assert str(phonecall) == 'Phone Call: Sales Call'


@pytest.mark.unit
class TestTaskModel:
    """Tests for Task model."""

    def test_create_task(self, db):
        """Test creating a Task with activity."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.TASK,
            subject='Review document',
            ownerid=owner,
        )

        task = Task.objects.create(
            activity=activity,
            percentcomplete=50,
        )

        assert task.activity == activity
        assert task.percentcomplete == 50

    def test_task_str_representation(self, db):
        """Test Task __str__ method."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.TASK,
            subject='Prepare Report',
            ownerid=owner,
        )
        task = Task.objects.create(activity=activity)

        assert str(task) == 'Task: Prepare Report'

    def test_task_percent_complete_validation(self, db):
        """Test percentcomplete must be 0-100."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.TASK,
            subject='Test',
            ownerid=owner,
        )

        # Valid range
        task = Task(activity=activity, percentcomplete=50)
        task.full_clean()  # Should not raise

        # Out of range
        task_invalid = Task(activity=activity, percentcomplete=150)
        with pytest.raises(ValidationError):
            task_invalid.full_clean()


@pytest.mark.unit
class TestAppointmentModel:
    """Tests for Appointment model."""

    def test_create_appointment(self, db):
        """Test creating an Appointment with activity."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.APPOINTMENT,
            subject='Team Meeting',
            ownerid=owner,
        )

        appointment = Appointment.objects.create(
            activity=activity,
            location='Conference Room A',
            requiredattendees='["contact1-uuid", "contact2-uuid"]',
        )

        assert appointment.activity == activity
        assert appointment.location == 'Conference Room A'
        assert appointment.requiredattendees is not None

    def test_appointment_str_representation(self, db):
        """Test Appointment __str__ method."""
        owner = SalespersonFactory()
        activity = Activity.objects.create(
            activitytypecode=ActivityTypeCode.APPOINTMENT,
            subject='Client Meeting',
            ownerid=owner,
        )
        appointment = Appointment.objects.create(activity=activity)

        assert str(appointment) == 'Appointment: Client Meeting'


@pytest.mark.unit
class TestActivityOrdering:
    """Tests for Activity model ordering."""

    def test_activities_ordered_by_createdon_desc(self, db):
        """Test that activities are ordered by createdon descending."""
        activity1 = ActivityFactory()
        activity2 = ActivityFactory()
        activity3 = ActivityFactory()

        activities = list(Activity.objects.all())

        assert activities[0].activityid == activity3.activityid
        assert activities[1].activityid == activity2.activityid
        assert activities[2].activityid == activity1.activityid


@pytest.mark.unit
class TestActivityAuditFields:
    """Tests for Activity audit trail fields."""

    def test_activity_has_audit_fields(self, db):
        """Test that activity has createdby, modifiedby, createdon, modifiedon."""
        owner = SalespersonFactory()
        activity = ActivityFactory(ownerid=owner, createdby=owner, modifiedby=owner)

        assert activity.createdon is not None
        assert activity.modifiedon is not None
        assert activity.createdby == owner
        assert activity.modifiedby == owner

    def test_modifiedon_updates_on_save(self, db):
        """Test that modifiedon updates when activity is saved."""
        activity = ActivityFactory()
        original_modifiedon = activity.modifiedon

        import time
        time.sleep(0.01)

        activity.subject = 'Updated subject'
        activity.save()

        assert activity.modifiedon > original_modifiedon


@pytest.mark.unit
class TestActivityFactories:
    """Tests for Activity factories."""

    def test_email_activity_factory(self, db):
        """Test EmailActivityFactory creates email activities."""
        activity = EmailActivityFactory()

        assert activity.activitytypecode == ActivityTypeCode.EMAIL
        assert 'Email' in activity.subject

    def test_task_activity_factory(self, db):
        """Test TaskActivityFactory creates task activities."""
        activity = TaskActivityFactory()

        assert activity.activitytypecode == ActivityTypeCode.TASK
        assert 'Task' in activity.subject
