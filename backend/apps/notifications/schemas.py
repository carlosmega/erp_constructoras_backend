"""
Notification schemas (Django Ninja DTOs).
"""

from ninja import ModelSchema, Schema
from typing import Optional, List
from uuid import UUID

from apps.notifications.models import Notification


class NotificationSchema(ModelSchema):
    actor_name: Optional[str] = None
    priority: str = 'medium'

    class Meta:
        model = Notification
        fields = [
            'notificationid', 'typecode', 'prioritycode', 'title', 'description',
            'isread', 'isarchived', 'readon',
            'relatedentityid', 'relatedentitytype', 'relatedentityname', 'actionurl',
            'ownerid', 'actorid', 'createdon',
        ]

    @staticmethod
    def resolve_actor_name(obj):
        return obj.actorid.fullname if obj.actorid else None

    @staticmethod
    def resolve_priority(obj):
        return obj.priority_name


class UnreadCountSchema(Schema):
    count: int


class BulkIdsDto(Schema):
    ids: List[UUID]
