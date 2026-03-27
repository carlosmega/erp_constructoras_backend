"""
Audit Compliance Engine.

Analyzes audit log for suspicious patterns:
- Bulk deletes (>5 deletes of same entity in 10 min)
- Off-hours access (actions between 22:00-06:00)
- Excessive updates (>50 updates by same user in 1 hour)
- Permission escalation patterns
"""

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.audit.models import AuditLog, AuditActionCode
except ImportError:
    AuditLog = None
    AuditActionCode = None

logger = logging.getLogger(__name__)


@register_agent
class AuditComplianceAgent(BaseAgent):
    """Analyzes audit log for suspicious patterns and compliance violations."""

    AGENT_TYPE = AgentTypeCode.AUDIT_COMPLIANCE

    def execute(self, days_back: int = 7, **kwargs) -> Any:
        if AuditLog is None:
            raise RuntimeError("AuditLog model not available")

        now = timezone.now()
        scan_start = now - timedelta(days=days_back)

        logs = AuditLog.objects.filter(
            timestamp__gte=scan_start
        ).select_related('userid').order_by('timestamp')

        total_actions = logs.count()
        flags = []
        unusual_patterns = []

        # ================================================================
        # 1. Bulk deletes (>5 deletes of same entity in 10 min window)
        # ================================================================
        bulk_delete_threshold = self.config.get('bulk_delete_threshold', 5)
        bulk_delete_window_min = self.config.get('bulk_delete_window_min', 10)

        delete_logs = logs.filter(action=AuditActionCode.DELETE)
        # Group by user + entity
        user_entity_deletes = defaultdict(list)
        for log in delete_logs:
            key = (
                str(log.userid_id) if log.userid_id else 'unknown',
                log.username or 'unknown',
                log.entity,
            )
            user_entity_deletes[key].append(log.timestamp)

        for (user_id, user_name, entity), timestamps in user_entity_deletes.items():
            timestamps.sort()
            # Sliding window check
            for i in range(len(timestamps)):
                window_end = timestamps[i] + timedelta(minutes=bulk_delete_window_min)
                count_in_window = sum(
                    1 for t in timestamps[i:] if t <= window_end
                )
                if count_in_window > bulk_delete_threshold:
                    flags.append({
                        'type': 'bulk_delete',
                        'severity': 'critical',
                        'user_name': user_name,
                        'details': (
                            f"{count_in_window} deletes of '{entity}' within "
                            f"{bulk_delete_window_min} min"
                        ),
                        'timestamp': timestamps[i].isoformat(),
                    })
                    break  # One flag per user+entity combo

        # ================================================================
        # 2. Off-hours access (22:00-06:00)
        # ================================================================
        off_hours_start = self.config.get('off_hours_start', 22)
        off_hours_end = self.config.get('off_hours_end', 6)

        off_hours_by_user = defaultdict(int)
        off_hours_samples = defaultdict(list)
        for log in logs:
            hour = log.timestamp.hour
            is_off_hours = (
                hour >= off_hours_start or hour < off_hours_end
            )
            if is_off_hours:
                user_name = log.username or 'unknown'
                off_hours_by_user[user_name] += 1
                if len(off_hours_samples[user_name]) < 3:
                    off_hours_samples[user_name].append(log.timestamp.isoformat())

        for user_name, count in off_hours_by_user.items():
            if count >= 3:  # Only flag if significant
                flags.append({
                    'type': 'off_hours_access',
                    'severity': 'warning',
                    'user_name': user_name,
                    'details': (
                        f"{count} action(s) between {off_hours_start}:00-{off_hours_end}:00"
                    ),
                    'timestamp': off_hours_samples[user_name][0] if off_hours_samples[user_name] else '',
                })

        # ================================================================
        # 3. Excessive updates (>50 updates by same user in 1 hour)
        # ================================================================
        excessive_update_threshold = self.config.get('excessive_update_threshold', 50)
        excessive_update_window_min = self.config.get('excessive_update_window_min', 60)

        update_logs = logs.filter(action=AuditActionCode.UPDATE)
        user_updates = defaultdict(list)
        for log in update_logs:
            key = (
                str(log.userid_id) if log.userid_id else 'unknown',
                log.username or 'unknown',
            )
            user_updates[key].append(log.timestamp)

        for (user_id, user_name), timestamps in user_updates.items():
            timestamps.sort()
            for i in range(len(timestamps)):
                window_end = timestamps[i] + timedelta(minutes=excessive_update_window_min)
                count_in_window = sum(
                    1 for t in timestamps[i:] if t <= window_end
                )
                if count_in_window > excessive_update_threshold:
                    flags.append({
                        'type': 'excessive_updates',
                        'severity': 'warning',
                        'user_name': user_name,
                        'details': (
                            f"{count_in_window} updates within "
                            f"{excessive_update_window_min} min"
                        ),
                        'timestamp': timestamps[i].isoformat(),
                    })
                    break

        # ================================================================
        # 4. Permission escalation patterns
        # ================================================================
        # Look for assign/activate actions on user-related entities
        escalation_actions = logs.filter(
            action__in=[AuditActionCode.ASSIGN, AuditActionCode.ACTIVATE],
            entity__in=['systemuser', 'securityrole'],
        )
        escalation_by_user = defaultdict(list)
        for log in escalation_actions:
            user_name = log.username or 'unknown'
            escalation_by_user[user_name].append({
                'action': log.action,
                'entity': log.entity,
                'record': log.recordname,
                'timestamp': log.timestamp.isoformat(),
            })

        for user_name, actions in escalation_by_user.items():
            if len(actions) >= 2:
                unusual_patterns.append({
                    'type': 'permission_escalation',
                    'user_name': user_name,
                    'details': (
                        f"{len(actions)} permission-related actions: "
                        f"{', '.join(a['action'] for a in actions[:3])}"
                    ),
                })

        # ================================================================
        # Summary & suggestions
        # ================================================================
        critical_flags = [f for f in flags if f['severity'] == 'critical']
        warning_flags = [f for f in flags if f['severity'] == 'warning']

        summary = (
            f"Scanned {total_actions} actions over {days_back} day(s). "
            f"Found {len(critical_flags)} critical flag(s), "
            f"{len(warning_flags)} warning(s), "
            f"{len(unusual_patterns)} unusual pattern(s)."
        )

        # Create suggestions for critical flags
        for flag in critical_flags:
            self._create_suggestion(
                title=f"Audit alert: {flag['type']}",
                description=f"User '{flag['user_name']}': {flag['details']}",
                confidence=0.85,
                severity=SuggestionSeverity.CRITICAL,
                suggested_action='investigate_audit_flag',
                suggested_data=flag,
            )

        for flag in warning_flags:
            self._create_suggestion(
                title=f"Audit warning: {flag['type']}",
                description=f"User '{flag['user_name']}': {flag['details']}",
                confidence=0.7,
                severity=SuggestionSeverity.WARNING,
                suggested_action='review_audit_warning',
                suggested_data=flag,
            )

        return {
            'scan_period': {
                'from': scan_start.isoformat(),
                'to': now.isoformat(),
                'days': days_back,
            },
            'total_actions': total_actions,
            'flags': flags,
            'unusual_patterns': unusual_patterns,
            'summary': summary,
        }
