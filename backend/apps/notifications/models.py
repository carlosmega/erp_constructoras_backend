"""
Notification model following CDS patterns.

Notifications are system-generated messages delivered to users
when business events occur (lead assigned, opportunity won, etc.).
"""

import uuid
from django.db import models


class NotificationTypeCode(models.TextChoices):
    LEAD = 'lead', 'Lead'
    OPPORTUNITY = 'opportunity', 'Opportunity'
    QUOTE = 'quote', 'Quote'
    TASK = 'task', 'Task'
    MENTION = 'mention', 'Mention'
    SYSTEM = 'system', 'System'


class NotificationPriorityCode(models.IntegerChoices):
    LOW = 0, 'Low'
    MEDIUM = 1, 'Medium'
    HIGH = 2, 'High'


PRIORITY_NAME_MAP = {
    0: 'low',
    1: 'medium',
    2: 'high',
}


class Notification(models.Model):
    notificationid = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False, db_column='notificationid'
    )

    # Recipient (who sees this notification)
    ownerid = models.ForeignKey(
        'users.SystemUser', on_delete=models.CASCADE,
        db_column='ownerid', related_name='notifications'
    )

    # Content
    typecode = models.CharField(
        max_length=20, choices=NotificationTypeCode.choices, db_column='typecode'
    )
    prioritycode = models.IntegerField(
        choices=NotificationPriorityCode.choices,
        default=NotificationPriorityCode.MEDIUM, db_column='prioritycode'
    )
    title = models.CharField(max_length=255, db_column='title')
    description = models.TextField(blank=True, default='', db_column='description')

    # Status
    isread = models.BooleanField(default=False, db_column='isread')
    isarchived = models.BooleanField(default=False, db_column='isarchived')
    readon = models.DateTimeField(null=True, blank=True, db_column='readon')

    # Related entity (polymorphic, like Activity pattern)
    relatedentityid = models.UUIDField(null=True, blank=True, db_column='relatedentityid')
    relatedentitytype = models.CharField(
        max_length=50, null=True, blank=True, db_column='relatedentitytype'
    )
    relatedentityname = models.CharField(
        max_length=255, null=True, blank=True, db_column='relatedentityname'
    )
    actionurl = models.CharField(max_length=500, null=True, blank=True, db_column='actionurl')

    # Actor (who triggered the notification)
    actorid = models.ForeignKey(
        'users.SystemUser', on_delete=models.SET_NULL,
        null=True, blank=True, db_column='actorid',
        related_name='notifications_triggered'
    )

    # Timestamps
    createdon = models.DateTimeField(auto_now_add=True, db_column='createdon')

    class Meta:
        db_table = 'notification'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['ownerid', 'isread']),
            models.Index(fields=['ownerid', 'isarchived']),
            models.Index(fields=['ownerid', 'typecode']),
            models.Index(fields=['createdon']),
        ]

    def __str__(self):
        return f"[{self.typecode}] {self.title} -> {self.ownerid}"

    @property
    def priority_name(self):
        return PRIORITY_NAME_MAP.get(self.prioritycode, 'medium')
