"""
Signal receivers that translate domain signals into Notification rows.

Every receiver is wrapped to isolate failures: a broken NotificationService call
never propagates to the dispatcher's transaction.

Registration happens in `apps.notifications.apps.NotificationsConfig.ready()`.
"""

import logging
from functools import wraps

from django.dispatch import receiver

from apps.notifications import signals

logger = logging.getLogger(__name__)


def _never_raise(handler):
    """Swallow + log any exception so a receiver can't crash the sender."""
    @wraps(handler)
    def wrapper(sender, **kwargs):
        try:
            return handler(sender, **kwargs)
        except Exception:
            logger.exception("Notification receiver %s failed", handler.__name__)
    return wrapper


@receiver(signals.record_assigned)
@_never_raise
def on_record_assigned(sender, *, entity_type, entity_id, entity_name, new_owner, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_record_assigned(
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_name=entity_name,
        new_owner=new_owner,
        actor=actor,
    )


@receiver(signals.state_changed)
@_never_raise
def on_state_changed(sender, *, entity_type, entity_id, entity_name, new_state, owner, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_state_changed(
        entity_type=entity_type,
        entity_id=str(entity_id),
        entity_name=entity_name,
        new_state=new_state,
        owner=owner,
        actor=actor,
    )


@receiver(signals.lead_qualified)
@_never_raise
def on_lead_qualified(sender, *, lead, opportunity, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_lead_qualified(lead, opportunity, actor=actor)


@receiver(signals.opportunity_won)
@_never_raise
def on_opportunity_won(sender, *, opportunity, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_opportunity_won(opportunity, actor=actor)


@receiver(signals.opportunity_lost)
@_never_raise
def on_opportunity_lost(sender, *, opportunity, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_opportunity_lost(opportunity, actor=actor)


@receiver(signals.quote_activated)
@_never_raise
def on_quote_activated(sender, *, quote, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_quote_activated(quote, actor=actor)


@receiver(signals.quote_won)
@_never_raise
def on_quote_won(sender, *, quote, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_quote_won(quote, actor=actor)


@receiver(signals.activity_assigned)
@_never_raise
def on_activity_assigned(sender, *, activity_type, activity_id, activity_subject, owner, actor, **_):
    from apps.notifications.services import NotificationService
    NotificationService.notify_activity_assigned(
        activity_type=activity_type,
        activity_id=str(activity_id),
        activity_subject=activity_subject,
        owner=owner,
        actor=actor,
    )
