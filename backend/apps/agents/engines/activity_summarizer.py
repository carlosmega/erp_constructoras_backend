"""
Activity Summarizer Agent (Type 19).

Summarizes the activity timeline for a given entity,
including engagement level assessment and pending task tracking.
"""

import logging
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.activities.models import Activity, ActivityTypeCode, ActivityStateCode

logger = logging.getLogger(__name__)


@register_agent
class ActivitySummarizerAgent(BaseAgent):
    """Summarizes activity timeline for CRM entities."""

    AGENT_TYPE = AgentTypeCode.ACTIVITY_SUMMARIZER

    def execute(
        self,
        *,
        entity_type: str,
        entity_id: str,
        **kwargs,
    ) -> dict:
        now = timezone.now()

        # Fetch all activities for this entity
        activities = Activity.objects.filter(
            regardingobjectid=entity_id,
            regardingobjectidtype=entity_type,
        ).order_by('-createdon')

        total_activities = activities.count()

        # Activity breakdown by type
        breakdown = (
            activities
            .values('activitytypecode')
            .annotate(count=Count('activityid'))
            .order_by('-count')
        )
        activity_breakdown = {
            item['activitytypecode']: item['count']
            for item in breakdown
        }

        # Last contact date (most recent completed or any activity)
        last_activity = activities.first()
        last_contact_date = None
        days_since_last_contact = None
        if last_activity:
            last_contact_date = last_activity.createdon.isoformat()
            days_since_last_contact = (now - last_activity.createdon).days

        # Pending tasks (open tasks)
        pending_tasks_qs = activities.filter(
            activitytypecode=ActivityTypeCode.TASK,
            statecode=ActivityStateCode.OPEN,
        ).order_by('scheduledend')

        pending_tasks = []
        for task in pending_tasks_qs[:10]:
            pending_tasks.append({
                'id': str(task.activityid),
                'subject': task.subject,
                'due': task.scheduledend.isoformat() if task.scheduledend else None,
            })

        # Next scheduled appointment
        next_scheduled = None
        upcoming = activities.filter(
            activitytypecode__in=[ActivityTypeCode.APPOINTMENT, ActivityTypeCode.MEETING],
            statecode__in=[ActivityStateCode.OPEN, ActivityStateCode.SCHEDULED],
            scheduledstart__gte=now,
        ).order_by('scheduledstart').first()

        if upcoming:
            next_scheduled = {
                'id': str(upcoming.activityid),
                'subject': upcoming.subject,
                'scheduled_start': upcoming.scheduledstart.isoformat() if upcoming.scheduledstart else None,
                'type': upcoming.activitytypecode,
            }

        # Engagement level
        if days_since_last_contact is not None:
            if days_since_last_contact <= 7:
                engagement_level = 'high'
            elif days_since_last_contact <= 14:
                engagement_level = 'medium'
            elif days_since_last_contact <= 30:
                engagement_level = 'low'
            else:
                engagement_level = 'cold'
        else:
            engagement_level = 'cold'

        # Build summary text
        type_labels = {
            ActivityTypeCode.EMAIL: 'emails',
            ActivityTypeCode.PHONECALL: 'calls',
            ActivityTypeCode.TASK: 'tasks',
            ActivityTypeCode.APPOINTMENT: 'appointments',
            ActivityTypeCode.MEETING: 'meetings',
            ActivityTypeCode.NOTE: 'notes',
        }
        breakdown_text = ', '.join(
            f"{count} {type_labels.get(atype, atype)}"
            for atype, count in activity_breakdown.items()
        )
        summary_text = (
            f"{total_activities} total activities ({breakdown_text}). "
            f"Engagement: {engagement_level}."
        )
        if days_since_last_contact is not None:
            summary_text += f" Last contact: {days_since_last_contact} days ago."
        if pending_tasks:
            summary_text += f" {len(pending_tasks)} pending tasks."
        if next_scheduled:
            summary_text += f" Next: {next_scheduled['subject']}."

        result = {
            'entity_id': entity_id,
            'entity_type': entity_type,
            'total_activities': total_activities,
            'activity_breakdown': activity_breakdown,
            'last_contact_date': last_contact_date,
            'days_since_last_contact': days_since_last_contact,
            'pending_tasks': pending_tasks,
            'next_scheduled': next_scheduled,
            'engagement_level': engagement_level,
            'summary_text': summary_text,
        }

        # Create suggestion based on engagement level
        severity_map = {
            'high': SuggestionSeverity.INFO,
            'medium': SuggestionSeverity.INFO,
            'low': SuggestionSeverity.WARNING,
            'cold': SuggestionSeverity.WARNING,
        }
        action_map = {
            'high': 'maintain_engagement',
            'medium': 'schedule_followup',
            'low': 'reactivate_contact',
            'cold': 'urgent_outreach',
        }

        self._create_suggestion(
            title=f"Activity summary ({entity_type}): {engagement_level} engagement",
            description=summary_text,
            confidence=0.9,
            severity=severity_map[engagement_level],
            suggested_action=action_map[engagement_level],
            suggested_data=result,
            relatedentityid=entity_id,
            relatedentitytype=entity_type,
        )

        return result
