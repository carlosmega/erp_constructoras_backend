"""
Notification business logic service layer.

Handles notification queries, mutations, and event-driven creation.
"""

import logging
from typing import Optional, List
from uuid import UUID

from django.db.models import QuerySet
from django.utils import timezone

from apps.notifications.models import (
    Notification,
    NotificationTypeCode,
    NotificationPriorityCode,
)
from apps.users.models import SystemUser

logger = logging.getLogger(__name__)


class NotificationService:
    """Service class for Notification operations."""

    # =========================================================================
    # Queries (for API endpoints)
    # =========================================================================

    @staticmethod
    def list_notifications(
        user: SystemUser,
        is_read: Optional[bool] = None,
        typecode: Optional[str] = None,
        search: Optional[str] = None,
    ) -> QuerySet[Notification]:
        """List notifications for the current user (always per-user, no admin override)."""
        queryset = Notification.objects.filter(ownerid=user, isarchived=False)

        if is_read is not None:
            queryset = queryset.filter(isread=is_read)

        if typecode:
            queryset = queryset.filter(typecode=typecode)

        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset.select_related('actorid')

    @staticmethod
    def get_unread_count(user: SystemUser) -> int:
        """Lightweight count query for bell badge polling."""
        return Notification.objects.filter(ownerid=user, isread=False, isarchived=False).count()

    # =========================================================================
    # Mutations (for API endpoints)
    # =========================================================================

    @staticmethod
    def mark_as_read(notification_id: UUID, user: SystemUser) -> Notification:
        """Mark a single notification as read."""
        from core.exceptions import NotFound

        try:
            notification = Notification.objects.get(notificationid=notification_id, ownerid=user)
        except Notification.DoesNotExist:
            raise NotFound(f"Notification with ID {notification_id} not found")

        if not notification.isread:
            notification.isread = True
            notification.readon = timezone.now()
            notification.save(update_fields=['isread', 'readon'])

        return notification

    @staticmethod
    def mark_all_as_read(user: SystemUser) -> int:
        """Mark all unread notifications as read. Returns count updated."""
        now = timezone.now()
        count = Notification.objects.filter(
            ownerid=user, isread=False
        ).update(isread=True, readon=now)
        return count

    @staticmethod
    def archive_notifications(notification_ids: List[UUID], user: SystemUser) -> int:
        """Archive selected notifications. Returns count archived."""
        count = Notification.objects.filter(
            notificationid__in=notification_ids, ownerid=user
        ).update(isarchived=True)
        return count

    @staticmethod
    def delete_notifications(notification_ids: List[UUID], user: SystemUser) -> int:
        """Delete selected notifications. Returns count deleted."""
        count, _ = Notification.objects.filter(
            notificationid__in=notification_ids, ownerid=user
        ).delete()
        return count

    # =========================================================================
    # Internal: Notification Generators (called from other services)
    # =========================================================================

    @staticmethod
    def _create_notification(
        owner: SystemUser,
        typecode: str,
        title: str,
        description: str = '',
        priority: int = NotificationPriorityCode.MEDIUM,
        related_entity_id: Optional[str] = None,
        related_entity_type: Optional[str] = None,
        related_entity_name: Optional[str] = None,
        action_url: Optional[str] = None,
        actor: Optional[SystemUser] = None,
    ) -> Optional[Notification]:
        """Internal helper to create a notification. Skips self-notifications."""
        # Don't notify the actor about their own actions
        if actor and owner.systemuserid == actor.systemuserid:
            return None

        try:
            return Notification.objects.create(
                ownerid=owner,
                typecode=typecode,
                prioritycode=priority,
                title=title,
                description=description,
                relatedentityid=related_entity_id,
                relatedentitytype=related_entity_type,
                relatedentityname=related_entity_name,
                actionurl=action_url,
                actorid=actor,
            )
        except Exception as e:
            logger.error("Failed to create notification: %s", e, exc_info=True)
            return None

    @staticmethod
    def notify_record_assigned(
        entity_type: str,
        entity_id: str,
        entity_name: str,
        new_owner: SystemUser,
        actor: Optional[SystemUser] = None,
    ) -> Optional[Notification]:
        """Notify a user that a record was assigned to them."""
        actor_name = actor.fullname if actor else 'System'
        return NotificationService._create_notification(
            owner=new_owner,
            typecode=entity_type,
            title=f"New {entity_type} assigned to you",
            description=f"{actor_name} assigned '{entity_name}' to you",
            priority=NotificationPriorityCode.HIGH,
            related_entity_id=entity_id,
            related_entity_type=entity_type,
            related_entity_name=entity_name,
            action_url=f"/{entity_type}s/{entity_id}",
            actor=actor,
        )

    @staticmethod
    def notify_state_changed(
        entity_type: str,
        entity_id: str,
        entity_name: str,
        new_state: str,
        owner: SystemUser,
        actor: Optional[SystemUser] = None,
        priority: int = NotificationPriorityCode.MEDIUM,
    ) -> Optional[Notification]:
        """Notify owner that a record's state changed."""
        return NotificationService._create_notification(
            owner=owner,
            typecode=entity_type,
            title=f"{entity_type.capitalize()} status changed",
            description=f"'{entity_name}' is now {new_state}",
            priority=priority,
            related_entity_id=entity_id,
            related_entity_type=entity_type,
            related_entity_name=entity_name,
            action_url=f"/{entity_type}s/{entity_id}" if entity_type != 'opportunity' else f"/opportunities/{entity_id}",
            actor=actor,
        )

    @staticmethod
    def notify_lead_qualified(lead, opportunity, actor: SystemUser) -> Optional[Notification]:
        """Notify lead owner that their lead was qualified."""
        return NotificationService._create_notification(
            owner=lead.ownerid,
            typecode=NotificationTypeCode.LEAD,
            title="Lead qualified",
            description=f"'{lead.fullname}' has been qualified. Opportunity '{opportunity.name}' created.",
            priority=NotificationPriorityCode.MEDIUM,
            related_entity_id=str(lead.leadid),
            related_entity_type='lead',
            related_entity_name=lead.fullname,
            action_url=f"/opportunities/{opportunity.opportunityid}",
            actor=actor,
        )

    @staticmethod
    def notify_opportunity_won(opportunity, actor: SystemUser) -> Optional[Notification]:
        """Notify opportunity owner that it was won."""
        return NotificationService._create_notification(
            owner=opportunity.ownerid,
            typecode=NotificationTypeCode.OPPORTUNITY,
            title="Opportunity won!",
            description=f"'{opportunity.name}' has been closed as Won",
            priority=NotificationPriorityCode.HIGH,
            related_entity_id=str(opportunity.opportunityid),
            related_entity_type='opportunity',
            related_entity_name=opportunity.name,
            action_url=f"/opportunities/{opportunity.opportunityid}",
            actor=actor,
        )

    @staticmethod
    def notify_opportunity_lost(opportunity, actor: SystemUser) -> Optional[Notification]:
        """Notify opportunity owner that it was lost."""
        return NotificationService._create_notification(
            owner=opportunity.ownerid,
            typecode=NotificationTypeCode.OPPORTUNITY,
            title="Opportunity lost",
            description=f"'{opportunity.name}' has been closed as Lost",
            priority=NotificationPriorityCode.MEDIUM,
            related_entity_id=str(opportunity.opportunityid),
            related_entity_type='opportunity',
            related_entity_name=opportunity.name,
            action_url=f"/opportunities/{opportunity.opportunityid}",
            actor=actor,
        )

    @staticmethod
    def notify_quote_activated(quote, actor: SystemUser) -> Optional[Notification]:
        """Notify quote owner that their quote was activated."""
        return NotificationService._create_notification(
            owner=quote.ownerid,
            typecode=NotificationTypeCode.QUOTE,
            title="Quote activated",
            description=f"Quote '{quote.name}' ({quote.quotenumber}) is now active and ready for review",
            priority=NotificationPriorityCode.HIGH,
            related_entity_id=str(quote.quoteid),
            related_entity_type='quote',
            related_entity_name=quote.name,
            action_url=f"/quotes/{quote.quoteid}",
            actor=actor,
        )

    @staticmethod
    def notify_quote_won(quote, actor: SystemUser) -> Optional[Notification]:
        """Notify quote owner that their quote was won."""
        return NotificationService._create_notification(
            owner=quote.ownerid,
            typecode=NotificationTypeCode.QUOTE,
            title="Quote won!",
            description=f"Quote '{quote.name}' ({quote.quotenumber}) has been won",
            priority=NotificationPriorityCode.HIGH,
            related_entity_id=str(quote.quoteid),
            related_entity_type='quote',
            related_entity_name=quote.name,
            action_url=f"/quotes/{quote.quoteid}",
            actor=actor,
        )

    @staticmethod
    def notify_activity_assigned(
        activity_type: str,
        activity_id: str,
        activity_subject: str,
        owner: SystemUser,
        actor: Optional[SystemUser] = None,
    ) -> Optional[Notification]:
        """Notify user that an activity was assigned to them."""
        actor_name = actor.fullname if actor else 'System'
        return NotificationService._create_notification(
            owner=owner,
            typecode=NotificationTypeCode.TASK,
            title=f"New {activity_type} assigned",
            description=f"{actor_name} assigned '{activity_subject}' to you",
            priority=NotificationPriorityCode.MEDIUM,
            related_entity_id=activity_id,
            related_entity_type=activity_type,
            related_entity_name=activity_subject,
            action_url=f"/activities/{activity_id}",
            actor=actor,
        )
