"""
Opportunity Stage Advisor Engine.

Assesses opportunity health per stage against benchmarks:
- Qualify: 14 days, 2 activities
- Develop: 21 days, 3 activities
- Propose: 14 days, 1 activity + quote
- Close: 7 days, 1 activity + quote

Health: "on_track", "at_risk" (>1.5x benchmark), "stalled" (>2x benchmark).
"""

import logging
from datetime import timedelta
from typing import Any, Optional

from django.db.models import Count, Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.opportunities.models import Opportunity, OpportunityStateCode, SalesStage
except ImportError:
    Opportunity = None
    OpportunityStateCode = None
    SalesStage = None

try:
    from apps.activities.models import Activity
except ImportError:
    Activity = None

try:
    from apps.quotes.models import Quote
except ImportError:
    Quote = None

logger = logging.getLogger(__name__)

# Stage benchmarks: (max_days, min_activities, requires_quote)
STAGE_BENCHMARKS = {
    0: {'label': 'qualify', 'days': 14, 'activities': 2, 'needs_quote': False},
    1: {'label': 'develop', 'days': 21, 'activities': 3, 'needs_quote': False},
    2: {'label': 'propose', 'days': 14, 'activities': 1, 'needs_quote': True},
    3: {'label': 'close', 'days': 7, 'activities': 1, 'needs_quote': True},
}


@register_agent
class OpportunityStageAdvisorAgent(BaseAgent):
    """Assesses opportunity health per stage against benchmarks."""

    AGENT_TYPE = AgentTypeCode.OPPORTUNITY_STAGE_ADVISOR

    def execute(
        self,
        opportunity_ids: Optional[list] = None,
        owner_id: Optional[str] = None,
        **kwargs,
    ) -> Any:
        if Opportunity is None:
            raise RuntimeError("Opportunity model not available")

        now = timezone.now()

        qs = Opportunity.objects.filter(
            statecode=OpportunityStateCode.OPEN,
        ).select_related('ownerid')

        if opportunity_ids:
            qs = qs.filter(opportunityid__in=opportunity_ids)
        if owner_id:
            qs = qs.filter(ownerid=owner_id)

        results = []
        for opp in qs:
            stage = opp.salesstage
            benchmark = STAGE_BENCHMARKS.get(stage, STAGE_BENCHMARKS[0])

            # Calculate days in stage
            # Use modifiedon as proxy for stage entry (approximate)
            days_in_stage = (now - opp.modifiedon).days if opp.modifiedon else 0

            # Count activities
            activity_count = 0
            if Activity is not None:
                activity_count = Activity.objects.filter(
                    regardingobjectid=opp.opportunityid,
                    regardingobjectidtype='opportunity',
                ).count()

            # Check for quote
            has_quote = False
            if Quote is not None:
                has_quote = Quote.objects.filter(
                    opportunityid=opp.opportunityid,
                ).exists()

            # Determine health
            benchmark_days = benchmark['days']
            ratio = days_in_stage / benchmark_days if benchmark_days > 0 else 0

            if ratio > 2.0:
                health = 'stalled'
            elif ratio > 1.5:
                health = 'at_risk'
            else:
                health = 'on_track'

            # Build recommendations and risk factors
            reasons = []
            next_steps = []
            risk_factors = []

            if days_in_stage > benchmark_days:
                reasons.append(
                    f"In {benchmark['label']} stage for {days_in_stage} days "
                    f"(benchmark: {benchmark_days} days)."
                )
                risk_factors.append('overdue')

            if activity_count < benchmark['activities']:
                reasons.append(
                    f"Only {activity_count} activities "
                    f"(minimum: {benchmark['activities']})."
                )
                next_steps.append(
                    f"Log at least {benchmark['activities'] - activity_count} more activities."
                )
                risk_factors.append('low_engagement')

            if benchmark['needs_quote'] and not has_quote:
                reasons.append("No quote attached (required for this stage).")
                next_steps.append("Create and attach a quote.")
                risk_factors.append('missing_quote')

            # Recommended action based on missing requirements
            if not next_steps:
                if stage < 3:
                    recommended_action = 'advance_stage'
                    next_steps.append(
                        f"Consider advancing to {STAGE_BENCHMARKS.get(stage + 1, {}).get('label', 'next')} stage."
                    )
                else:
                    recommended_action = 'close_deal'
                    next_steps.append("Finalize and close the deal.")
            else:
                recommended_action = next_steps[0] if next_steps else 'review'

            # Create suggestion for at_risk or stalled
            if health in ('at_risk', 'stalled'):
                severity = (
                    SuggestionSeverity.CRITICAL if health == 'stalled'
                    else SuggestionSeverity.WARNING
                )
                self._create_suggestion(
                    title=f"Opportunity '{opp.name}' is {health}",
                    description=(
                        f"In {benchmark['label']} stage for {days_in_stage} days. "
                        + '; '.join(reasons)
                    ),
                    confidence=min(ratio / 3, 1.0),
                    severity=severity,
                    suggested_action=recommended_action,
                    suggested_data={
                        'opportunityid': str(opp.opportunityid),
                        'health': health,
                        'days_in_stage': days_in_stage,
                    },
                    relatedentityid=opp.opportunityid,
                    relatedentitytype='opportunity',
                )

            results.append({
                'opportunityid': str(opp.opportunityid),
                'name': opp.name,
                'current_stage': benchmark['label'],
                'days_in_stage': days_in_stage,
                'avg_days_benchmark': benchmark_days,
                'health': health,
                'recommended_action': recommended_action,
                'reasons': reasons,
                'next_steps': next_steps,
                'risk_factors': risk_factors,
            })

        return results
