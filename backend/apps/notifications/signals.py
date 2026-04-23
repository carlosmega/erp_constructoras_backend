"""
Domain signals for notifications.

Services in `apps.leads`, `apps.opportunities`, `apps.quotes`, `apps.activities`,
`apps.hrpayroll` fire these signals after a state change; the receiver in
`apps.notifications.receivers` translates them into Notification rows.

This replaces the previous pattern of:

    try:
        from apps.notifications.services import NotificationService
        NotificationService.notify_...(...)
    except Exception:
        logger.exception(...)

which created hard cross-app imports and forced every service to know about
notifications. Signals invert that: the dispatcher knows nothing about
receivers, and a receiver failure cannot crash the main flow.
"""

from django.dispatch import Signal


# Generic record ownership change.
# Providing args: entity_type (str), entity_id (str), entity_name (str),
#                 new_owner (SystemUser), actor (SystemUser)
record_assigned = Signal()


# State or sales-stage changed.
# Providing args: entity_type, entity_id, entity_name, new_state (str),
#                 owner (SystemUser), actor (SystemUser)
state_changed = Signal()


# Lead qualified into an opportunity.
# Providing args: lead (Lead), opportunity (Opportunity), actor (SystemUser)
lead_qualified = Signal()


# Opportunity closed.
# Providing args: opportunity (Opportunity), actor (SystemUser)
opportunity_won = Signal()
opportunity_lost = Signal()


# Quote state changes.
# Providing args: quote (Quote), actor (SystemUser)
quote_activated = Signal()
quote_won = Signal()


# Activity assigned.
# Providing args: activity_type (str), activity_id (str), activity_subject (str),
#                 owner (SystemUser), actor (SystemUser)
activity_assigned = Signal()
