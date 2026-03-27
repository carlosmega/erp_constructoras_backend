"""
Pipeline Forecast Engine.

Generates revenue forecasts (optimistic, realistic, conservative)
based on open opportunities, historical win rates, and per-rep breakdown.
"""

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.opportunities.models import (
        Opportunity,
        OpportunityStateCode,
        SalesStage,
    )
except ImportError:
    Opportunity = None
    OpportunityStateCode = None
    SalesStage = None

logger = logging.getLogger(__name__)

# Default stage probabilities
STAGE_PROBABILITIES = {
    0: 25,   # Qualify
    1: 50,   # Develop
    2: 75,   # Propose
    3: 100,  # Close
}


@register_agent
class PipelineForecastAgent(BaseAgent):
    """Generates pipeline revenue forecasts with multiple scenarios."""

    AGENT_TYPE = AgentTypeCode.PIPELINE_FORECAST

    def execute(self, months_back: int = 12, **kwargs) -> Any:
        if Opportunity is None:
            raise RuntimeError("Opportunity model not available")

        now = timezone.now()
        cutoff = now - timedelta(days=months_back * 30)

        # --- Open opportunities ---
        open_opps = Opportunity.objects.filter(
            statecode=OpportunityStateCode.OPEN,
        ).select_related('ownerid')

        # --- Historical closed opportunities (last N months) ---
        closed_opps = Opportunity.objects.filter(
            statecode__in=[OpportunityStateCode.WON, OpportunityStateCode.LOST],
            actualclosedate__gte=cutoff.date(),
        )

        won_opps = closed_opps.filter(statecode=OpportunityStateCode.WON)
        lost_opps = closed_opps.filter(statecode=OpportunityStateCode.LOST)

        total_closed = closed_opps.count()
        total_won = won_opps.count()
        win_rate = round(total_won / total_closed * 100, 1) if total_closed > 0 else 0.0

        # Historical win rate per stage (based on what stage they were in when they closed)
        won_by_stage = defaultdict(int)
        closed_by_stage = defaultdict(int)
        for opp in closed_opps:
            stage = opp.salesstage
            closed_by_stage[stage] += 1
            if opp.statecode == OpportunityStateCode.WON:
                won_by_stage[stage] += 1

        historical_win_rate_by_stage = {}
        for stage_val in [0, 1, 2, 3]:
            total = closed_by_stage.get(stage_val, 0)
            won = won_by_stage.get(stage_val, 0)
            historical_win_rate_by_stage[stage_val] = (
                round(won / total, 3) if total > 0 else STAGE_PROBABILITIES.get(stage_val, 25) / 100
            )

        # Average deal size and cycle days
        won_stats = won_opps.aggregate(
            avg_revenue=Avg('actualrevenue'),
            avg_est_revenue=Avg('estimatedrevenue'),
        )
        avg_deal_size = float(
            won_stats['avg_revenue'] or won_stats['avg_est_revenue'] or 0
        )

        # Average cycle days (createdon to actualclosedate)
        cycle_days_list = []
        for opp in won_opps:
            if opp.actualclosedate and opp.createdon:
                delta = opp.actualclosedate - opp.createdon.date()
                cycle_days_list.append(delta.days)
        avg_cycle_days = (
            round(sum(cycle_days_list) / len(cycle_days_list))
            if cycle_days_list else 0
        )

        # --- Forecast calculations ---
        forecast_optimistic = Decimal('0')
        forecast_realistic = Decimal('0')
        forecast_conservative = Decimal('0')

        by_rep = defaultdict(lambda: {
            'ownerid': '', 'name': '', 'forecast': 0.0,
        })
        by_stage = defaultdict(int)

        for opp in open_opps:
            est_value = opp.estimatedrevenue or Decimal('0')
            prob = opp.probability or STAGE_PROBABILITIES.get(opp.salesstage, 25)

            # Optimistic: use probability as-is
            forecast_optimistic += est_value * Decimal(str(prob)) / Decimal('100')

            # Realistic: adjusted by historical win rate for the stage
            hist_rate = historical_win_rate_by_stage.get(opp.salesstage, 0.25)
            forecast_realistic += est_value * Decimal(str(hist_rate))

            # Conservative: only Close stage * 0.8
            if opp.salesstage == 3:  # Close
                forecast_conservative += est_value * Decimal('0.8')

            # By rep
            owner_id = str(opp.ownerid_id) if opp.ownerid_id else 'unassigned'
            owner_name = (
                opp.ownerid.fullname if opp.ownerid and hasattr(opp.ownerid, 'fullname')
                else str(opp.ownerid_id)
            )
            by_rep[owner_id]['ownerid'] = owner_id
            by_rep[owner_id]['name'] = owner_name
            by_rep[owner_id]['forecast'] += float(
                est_value * Decimal(str(hist_rate))
            )

            # By stage
            by_stage[opp.salesstage] += 1

        # Create suggestion if pipeline is thin
        open_count = open_opps.count()
        if open_count < 5:
            self._create_suggestion(
                title="Low pipeline volume",
                description=(
                    f"Only {open_count} open opportunities in the pipeline. "
                    f"Consider increasing lead generation activities."
                ),
                confidence=0.8,
                severity=SuggestionSeverity.WARNING,
                suggested_action='increase_prospecting',
            )

        stage_labels = {0: 'qualify', 1: 'develop', 2: 'propose', 3: 'close'}
        by_stage_named = {
            stage_labels.get(k, str(k)): v for k, v in by_stage.items()
        }

        return {
            'period': f"last_{months_back}_months",
            'forecast_optimistic': float(round(forecast_optimistic, 2)),
            'forecast_realistic': float(round(forecast_realistic, 2)),
            'forecast_conservative': float(round(forecast_conservative, 2)),
            'win_rate': win_rate,
            'avg_deal_size': round(avg_deal_size, 2),
            'avg_cycle_days': avg_cycle_days,
            'by_rep': list(by_rep.values()),
            'by_stage': by_stage_named,
        }
