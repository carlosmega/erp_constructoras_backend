"""
Activity models for CRM Backend.

Implements Activity base and specific activity types (Email, PhoneCall, Task, Appointment)
following Dynamics CDS patterns.

Phase 12 Implementation: Activity Management
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid


class MatchMethod(models.TextChoices):
    """Email matching method choices."""
    EMAIL_ADDRESS = 'email_address', 'Email Address'
    TRACKING_TOKEN = 'tracking_token', 'Tracking Token'
    THREAD_CORRELATION = 'thread_correlation', 'Thread Correlation'
    MANUAL = 'manual', 'Manual'


class ActivityTypeCode(models.TextChoices):
    """Activity type codes."""
    EMAIL = 'email', 'Email'
    PHONECALL = 'phonecall', 'Phone Call'
    TASK = 'task', 'Task'
    APPOINTMENT = 'appointment', 'Appointment'
    MEETING = 'meeting', 'Meeting'
    NOTE = 'note', 'Note'


# Mapping from frontend integer codes to backend string codes
ACTIVITY_TYPE_INT_MAP = {
    1: ActivityTypeCode.EMAIL,
    2: ActivityTypeCode.PHONECALL,
    3: ActivityTypeCode.TASK,
    4: ActivityTypeCode.APPOINTMENT,
    5: ActivityTypeCode.MEETING,
    6: ActivityTypeCode.NOTE,
}

# Reverse mapping: string code to integer
ACTIVITY_TYPE_STR_MAP = {v: k for k, v in ACTIVITY_TYPE_INT_MAP.items()}


class ActivityStateCode(models.IntegerChoices):
    """Activity state codes."""
    OPEN = 0, 'Open'
    COMPLETED = 1, 'Completed'
    CANCELED = 2, 'Canceled'
    SCHEDULED = 3, 'Scheduled'


class PriorityCode(models.IntegerChoices):
    """Priority codes."""
    LOW = 0, 'Low'
    NORMAL = 1, 'Normal'
    HIGH = 2, 'High'


class Activity(models.Model):
    """
    Base class for all activities.

    CDS Entity: activitypointer
    Primary Key: activityid (UUID)
    """

    # Primary Key
    activityid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='activityid'
    )

    # Activity Type
    activitytypecode = models.CharField(
        max_length=20,
        choices=ActivityTypeCode.choices,
        db_column='activitytypecode'
    )

    # State & Status
    statecode = models.IntegerField(
        choices=ActivityStateCode.choices,
        default=ActivityStateCode.OPEN,
        db_column='statecode'
    )
    statuscode = models.IntegerField(
        null=True,
        blank=True,
        db_column='statuscode'
    )

    # Basic Information
    subject = models.CharField(
        max_length=200,
        db_column='subject'
    )
    description = models.TextField(
        null=True,
        blank=True,
        db_column='description'
    )

    # Regarding (Polymorphic) - Can point to Lead, Opportunity, Account, Contact
    regardingobjectid = models.UUIDField(
        null=True,
        blank=True,
        db_column='regardingobjectid',
        help_text='ID of the related entity (Lead, Opportunity, Account, Contact)'
    )
    regardingobjectidtype = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='regardingobjectidtype',
        help_text='Type of the related entity (lead, opportunity, account, contact)'
    )

    # Scheduling
    scheduledstart = models.DateTimeField(
        null=True,
        blank=True,
        db_column='scheduledstart'
    )
    scheduledend = models.DateTimeField(
        null=True,
        blank=True,
        db_column='scheduledend'
    )
    actualdurationminutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        db_column='actualdurationminutes'
    )

    # Completion
    actualstart = models.DateTimeField(
        null=True,
        blank=True,
        db_column='actualstart'
    )
    actualend = models.DateTimeField(
        null=True,
        blank=True,
        db_column='actualend'
    )

    # Priority
    prioritycode = models.IntegerField(
        choices=PriorityCode.choices,
        default=PriorityCode.NORMAL,
        null=True,
        blank=True,
        db_column='prioritycode'
    )

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        related_name='activities_owned',
        db_column='ownerid'
    )

    # Audit Fields
    createdon = models.DateTimeField(
        auto_now_add=True,
        db_column='createdon'
    )
    modifiedon = models.DateTimeField(
        auto_now=True,
        db_column='modifiedon'
    )
    createdby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities_created',
        db_column='createdby'
    )
    modifiedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities_modified',
        db_column='modifiedby'
    )

    class Meta:
        db_table = 'activitypointer'
        ordering = ['-createdon']
        verbose_name = 'Activity'
        verbose_name_plural = 'Activities'
        indexes = [
            models.Index(fields=['statecode']),
            models.Index(fields=['ownerid']),
            models.Index(fields=['activitytypecode']),
            models.Index(fields=['regardingobjectid', 'regardingobjectidtype']),
        ]

    def __str__(self):
        return f"{self.get_activitytypecode_display()}: {self.subject}"

    @property
    def state_name(self):
        """Get display name for state code."""
        return ActivityStateCode(self.statecode).label if self.statecode is not None else None

    @property
    def priority_name(self):
        """Get display name for priority code."""
        return PriorityCode(self.prioritycode).label if self.prioritycode is not None else None


class Email(models.Model):
    """
    Email activity.

    CDS Entity: email
    Primary Key: activityid (shared with Activity)
    """

    # Primary Key (one-to-one with Activity)
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='email_details',
        db_column='activityid'
    )

    # Email Specific Fields
    to = models.TextField(
        null=True,
        blank=True,
        db_column='to',
        help_text='Recipient email addresses (semicolon separated)'
    )
    sender = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='from',
        help_text='Sender email address'
    )
    cc = models.TextField(
        null=True,
        blank=True,
        db_column='cc',
        help_text='CC email addresses (semicolon separated)'
    )
    bcc = models.TextField(
        null=True,
        blank=True,
        db_column='bcc',
        help_text='BCC email addresses (semicolon separated)'
    )
    body = models.TextField(
        null=True,
        blank=True,
        db_column='body'
    )
    directioncode = models.BooleanField(
        default=True,
        db_column='directioncode',
        help_text='True=Outgoing, False=Incoming'
    )

    # Email Matching Fields
    messageid = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='messageid',
        db_index=True,
        help_text='RFC 5322 Message-ID header for thread correlation'
    )
    inreplyto = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column='inreplyto',
        help_text='In-Reply-To header referencing parent messageid'
    )
    trackingtokenid = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='trackingtokenid',
        db_index=True,
        help_text='CRM tracking token extracted from subject [CRM:OPP-abc12345]'
    )
    matchconfidence = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_column='matchconfidence',
        help_text='Auto-match confidence score (0-100)'
    )
    matchmethod = models.CharField(
        max_length=30,
        choices=MatchMethod.choices,
        null=True,
        blank=True,
        db_column='matchmethod',
        help_text='Method used for matching: email_address, tracking_token, thread_correlation, manual'
    )

    class Meta:
        db_table = 'email'
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'

    def __str__(self):
        return f"Email: {self.activity.subject}"


class PhoneCall(models.Model):
    """
    Phone call activity.

    CDS Entity: phonecall
    Primary Key: activityid (shared with Activity)
    """

    # Primary Key (one-to-one with Activity)
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='phonecall_details',
        db_column='activityid'
    )

    # PhoneCall Specific Fields
    phonenumber = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_column='phonenumber'
    )
    directioncode = models.BooleanField(
        default=True,
        db_column='directioncode',
        help_text='True=Outgoing, False=Incoming'
    )

    class Meta:
        db_table = 'phonecall'
        verbose_name = 'Phone Call'
        verbose_name_plural = 'Phone Calls'

    def __str__(self):
        return f"Phone Call: {self.activity.subject}"


class Task(models.Model):
    """
    Task activity.

    CDS Entity: task
    Primary Key: activityid (shared with Activity)
    """

    # Primary Key (one-to-one with Activity)
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='task_details',
        db_column='activityid'
    )

    # Task Specific Fields
    percentcomplete = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_column='percentcomplete'
    )

    class Meta:
        db_table = 'task'
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

    def __str__(self):
        return f"Task: {self.activity.subject}"


class Appointment(models.Model):
    """
    Appointment/meeting activity.

    CDS Entity: appointment
    Primary Key: activityid (shared with Activity)
    """

    # Primary Key (one-to-one with Activity)
    activity = models.OneToOneField(
        Activity,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='appointment_details',
        db_column='activityid'
    )

    # Appointment Specific Fields
    location = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        db_column='location'
    )
    requiredattendees = models.TextField(
        null=True,
        blank=True,
        db_column='requiredattendees',
        help_text='JSON array of Contact IDs'
    )
    optionalattendees = models.TextField(
        null=True,
        blank=True,
        db_column='optionalattendees',
        help_text='JSON array of Contact IDs'
    )

    class Meta:
        db_table = 'appointment'
        verbose_name = 'Appointment'
        verbose_name_plural = 'Appointments'

    def __str__(self):
        return f"Appointment: {self.activity.subject}"
