"""
Activity API schemas (DTOs).

Phase 12 Implementation: Activity Management
"""

from ninja import ModelSchema, Schema
from typing import Optional
from datetime import datetime
from uuid import UUID

from apps.activities.models import Activity, Email, PhoneCall, Task, Appointment


# ============================================================================
# Activity Base Schemas
# ============================================================================

class ActivitySchema(ModelSchema):
    """Full activity response schema."""
    state_name: Optional[str] = None
    priority_name: Optional[str] = None

    class Config:
        model = Activity
        model_fields = '__all__'


class ActivityListItemSchema(ModelSchema):
    """Simplified activity schema for list views."""
    state_name: Optional[str] = None

    class Config:
        model = Activity
        model_fields = [
            'activityid', 'activitytypecode', 'subject', 'statecode',
            'scheduledstart', 'scheduledend', 'ownerid', 'createdon'
        ]


class CreateActivityDto(Schema):
    """Base DTO for creating an activity."""
    activitytypecode: str
    subject: str
    description: Optional[str] = None
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    prioritycode: Optional[int] = 1
    ownerid: UUID


class UpdateActivityDto(Schema):
    """Base DTO for updating an activity."""
    subject: Optional[str] = None
    description: Optional[str] = None
    statecode: Optional[int] = None
    statuscode: Optional[int] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    actualstart: Optional[datetime] = None
    actualend: Optional[datetime] = None
    actualdurationminutes: Optional[int] = None
    prioritycode: Optional[int] = None
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None


class CompleteActivityDto(Schema):
    """DTO for completing an activity."""
    actualend: Optional[datetime] = None
    actualdurationminutes: Optional[int] = None


class ActivityDetailSchema(Schema):
    """Detailed activity response with type-specific details."""
    activity: ActivitySchema
    email: Optional[dict] = None
    phonecall: Optional[dict] = None
    task: Optional[dict] = None
    appointment: Optional[dict] = None


# ============================================================================
# Email Schemas
# ============================================================================

class EmailSchema(Schema):
    """Full email response schema."""
    activity: ActivitySchema
    to: Optional[str] = None
    sender: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    body: Optional[str] = None
    directioncode: bool = True


class CreateEmailDto(Schema):
    """DTO for creating an email activity."""
    subject: str
    description: Optional[str] = None
    to: Optional[str] = None
    sender: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    body: Optional[str] = None
    directioncode: bool = True
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None
    ownerid: UUID


class UpdateEmailDto(Schema):
    """DTO for updating an email."""
    subject: Optional[str] = None
    description: Optional[str] = None
    to: Optional[str] = None
    sender: Optional[str] = None
    cc: Optional[str] = None
    bcc: Optional[str] = None
    body: Optional[str] = None
    directioncode: Optional[bool] = None
    statecode: Optional[int] = None


# ============================================================================
# PhoneCall Schemas
# ============================================================================

class PhoneCallSchema(Schema):
    """Full phone call response schema."""
    activity: ActivitySchema
    phonenumber: Optional[str] = None
    directioncode: bool = True


class CreatePhoneCallDto(Schema):
    """DTO for creating a phone call activity."""
    subject: str
    description: Optional[str] = None
    phonenumber: Optional[str] = None
    directioncode: bool = True
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None
    ownerid: UUID


class UpdatePhoneCallDto(Schema):
    """DTO for updating a phone call."""
    subject: Optional[str] = None
    description: Optional[str] = None
    phonenumber: Optional[str] = None
    directioncode: Optional[bool] = None
    statecode: Optional[int] = None


# ============================================================================
# Task Schemas
# ============================================================================

class TaskSchema(Schema):
    """Full task response schema."""
    activity: ActivitySchema
    percentcomplete: int = 0


class CreateTaskDto(Schema):
    """DTO for creating a task activity."""
    subject: str
    description: Optional[str] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    prioritycode: Optional[int] = 1
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None
    ownerid: UUID


class UpdateTaskDto(Schema):
    """DTO for updating a task."""
    subject: Optional[str] = None
    description: Optional[str] = None
    percentcomplete: Optional[int] = None
    statecode: Optional[int] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None


# ============================================================================
# Appointment Schemas
# ============================================================================

class AppointmentSchema(Schema):
    """Full appointment response schema."""
    activity: ActivitySchema
    location: Optional[str] = None
    requiredattendees: Optional[str] = None
    optionalattendees: Optional[str] = None


class CreateAppointmentDto(Schema):
    """DTO for creating an appointment activity."""
    subject: str
    description: Optional[str] = None
    location: Optional[str] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    requiredattendees: Optional[str] = None
    optionalattendees: Optional[str] = None
    regardingobjectid: Optional[UUID] = None
    regardingobjectidtype: Optional[str] = None
    ownerid: UUID


class UpdateAppointmentDto(Schema):
    """DTO for updating an appointment."""
    subject: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    scheduledstart: Optional[datetime] = None
    scheduledend: Optional[datetime] = None
    requiredattendees: Optional[str] = None
    optionalattendees: Optional[str] = None
    statecode: Optional[int] = None


# ============================================================================
# Statistics
# ============================================================================

class ActivityStatsSchema(Schema):
    """Activity statistics."""
    total_activities: int
    open_activities: int
    completed_activities: int
    overdue_activities: int
    by_type: dict
