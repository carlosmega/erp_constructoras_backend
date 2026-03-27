"""
Smart Notification Engine.

Optimizes notification routing:
- Batch notifications of same type within 15-min window
- Priority override rules (budget exceeded -> critical)
- Daily limit per user (configurable, default 30)
- Quiet hours filtering (configurable, default 20:00-08:00)
"""

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.notifications.models import Notification, NotificationPriorityCode
except ImportError:
    Notification = None
    NotificationPriorityCode = None

logger = logging.getLogger(__name__)

# Priority override rules: keywords -> priority
PRIORITY_OVERRIDE_KEYWORDS = {
    'budget exceeded': 2,   # HIGH
    'presupuesto excedido': 2,
    'sla breach': 2,
    'sla violation': 2,
    'critical': 2,
    'overdue': 2,
}


@register_agent
class SmartNotificationAgent(BaseAgent):
    """Optimizes notification delivery by batching, filtering, and prioritizing."""

    AGENT_TYPE = AgentTypeCode.SMART_NOTIFICATION

    def execute(self, **kwargs) -> Any:
        if Notification is None:
            raise RuntimeError("Notification model not available")

        now = timezone.now()

        # Config
        batch_window_min = self.config.get('batch_window_min', 15)
        daily_limit = self.config.get('daily_limit', 30)
        quiet_hours_start = self.config.get('quiet_hours_start', 20)
        quiet_hours_end = self.config.get('quiet_hours_end', 8)

        # Get unread notifications from today
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        pending = Notification.objects.filter(
            isread=False,
            isarchived=False,
            createdon__gte=today_start,
        ).select_related('ownerid').order_by('createdon')

        processed = 0
        batched = 0
        suppressed = 0
        priority_overrides = 0

        # Track per-user daily counts
        user_daily_counts = defaultdict(int)
        daily_counts = (
            Notification.objects.filter(
                createdon__gte=today_start,
                isarchived=False,
            )
            .values('ownerid')
            .annotate(count=Count('notificationid'))
        )
        for entry in daily_counts:
            user_daily_counts[str(entry['ownerid'])] = entry['count']

        # Group pending notifications by user + type for batching
        user_type_groups = defaultdict(list)
        for notif in pending:
            user_id = str(notif.ownerid_id)
            key = (user_id, notif.typecode)
            user_type_groups[key].append(notif)

        notifications_to_suppress = []
        notifications_to_batch = []

        for (user_id, typecode), notifs in user_type_groups.items():
            processed += len(notifs)

            # ---- 1. Priority overrides ----
            for notif in notifs:
                title_lower = (notif.title or '').lower()
                desc_lower = (notif.description or '').lower()
                text = f"{title_lower} {desc_lower}"
                for keyword, new_priority in PRIORITY_OVERRIDE_KEYWORDS.items():
                    if keyword in text and notif.prioritycode < new_priority:
                        notif.prioritycode = new_priority
                        notif.save(update_fields=['prioritycode'])
                        priority_overrides += 1
                        break

            # ---- 2. Batch similar notifications within time window ----
            if len(notifs) > 1:
                # Sort by creation time
                notifs.sort(key=lambda n: n.createdon)
                batch_groups = []
                current_batch = [notifs[0]]

                for i in range(1, len(notifs)):
                    time_diff = (notifs[i].createdon - current_batch[0].createdon)
                    if time_diff <= timedelta(minutes=batch_window_min):
                        current_batch.append(notifs[i])
                    else:
                        batch_groups.append(current_batch)
                        current_batch = [notifs[i]]
                batch_groups.append(current_batch)

                for batch in batch_groups:
                    if len(batch) > 1:
                        # Keep the first, mark rest for batching note
                        notifications_to_batch.extend(batch[1:])
                        batched += len(batch) - 1

            # ---- 3. Daily limit per user ----
            current_count = user_daily_counts.get(user_id, 0)
            if current_count > daily_limit:
                # Suppress lowest priority notifications
                low_priority = sorted(notifs, key=lambda n: n.prioritycode)
                excess = current_count - daily_limit
                for notif in low_priority[:excess]:
                    if notif.prioritycode < 2:  # Don't suppress HIGH priority
                        notifications_to_suppress.append(notif)
                        suppressed += 1

            # ---- 4. Quiet hours filtering ----
            current_hour = now.hour
            is_quiet = (
                current_hour >= quiet_hours_start or current_hour < quiet_hours_end
            )
            if is_quiet:
                for notif in notifs:
                    # Only suppress non-high-priority during quiet hours
                    if notif.prioritycode < 2 and notif not in notifications_to_suppress:
                        notifications_to_suppress.append(notif)
                        suppressed += 1

        # Archive suppressed notifications
        for notif in notifications_to_suppress:
            notif.isarchived = True
            notif.save(update_fields=['isarchived'])

        summary = (
            f"Processed {processed} pending notification(s). "
            f"Batched {batched}, suppressed {suppressed}, "
            f"priority overrides {priority_overrides}."
        )

        # Create suggestion if significant suppressions
        if suppressed > 5:
            self._create_suggestion(
                title=f"Notification optimization: {suppressed} suppressed",
                description=summary,
                confidence=0.8,
                severity=SuggestionSeverity.INFO,
                suggested_action='review_notification_rules',
                suggested_data={
                    'suppressed': suppressed,
                    'batched': batched,
                    'priority_overrides': priority_overrides,
                },
            )

        return {
            'processed': processed,
            'batched': batched,
            'suppressed': suppressed,
            'priority_overrides': priority_overrides,
            'summary': summary,
        }
