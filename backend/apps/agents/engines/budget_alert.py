"""
Budget Alert Engine.

Monitors budget consumption per imputation code and generates alerts
at configurable thresholds (default: 75%, 90%, 100%).
"""

import logging
from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.budgets.models import ImputationCode
except ImportError:
    ImputationCode = None

try:
    from apps.expenses.models import (
        ProjectExpense,
        ClassificationStatusCode,
        ExpenseStateCode,
    )
except ImportError:
    ProjectExpense = None
    ClassificationStatusCode = None
    ExpenseStateCode = None

logger = logging.getLogger(__name__)


@register_agent
class BudgetAlertAgent(BaseAgent):
    """Monitors budget consumption and generates threshold-based alerts."""

    AGENT_TYPE = AgentTypeCode.BUDGET_ALERT

    def execute(self, project_id: str = '', **kwargs) -> Any:
        if not project_id:
            raise ValueError("project_id is required")
        if ImputationCode is None or ProjectExpense is None:
            raise RuntimeError("Required models not available")

        thresholds = self.config.get('thresholds', [75, 90, 100])
        thresholds = sorted(thresholds)

        # Load all imputation codes with budget for the project
        codes = ImputationCode.objects.filter(
            projectid=project_id,
        ).select_related('categoryid', 'zoneid')

        # Aggregate actual spend per imputation code from classified expenses
        spend_agg = dict(
            ProjectExpense.objects.filter(
                projectid=project_id,
                statecode=ExpenseStateCode.ACTIVE,
                classificationstatus=ClassificationStatusCode.CLASSIFIED,
                imputationcodeid__isnull=False,
            ).values('imputationcodeid').annotate(
                spent=Sum('subtotal')
            ).values_list('imputationcodeid', 'spent')
        )

        alerts = []
        codes_at_risk = 0
        codes_exceeded = 0
        total_budget = Decimal('0')
        total_spent = Decimal('0')

        for code in codes:
            budget = code.totalbudget or Decimal('0')
            spent = spend_agg.get(code.imputationcodeid, Decimal('0')) or Decimal('0')
            total_budget += budget
            total_spent += spent

            if budget <= 0:
                continue

            pct = float(spent / budget * 100)

            # Find the highest threshold crossed
            threshold_crossed = None
            for t in thresholds:
                if pct >= t:
                    threshold_crossed = t

            if threshold_crossed is None:
                continue

            # Determine severity
            if pct >= 100:
                severity = SuggestionSeverity.EXCEEDED
                codes_exceeded += 1
            elif pct >= 90:
                severity = SuggestionSeverity.CRITICAL
                codes_at_risk += 1
            else:
                severity = SuggestionSeverity.WARNING
                codes_at_risk += 1

            remaining = budget - spent
            cost_type = 'direct' if code.costtype == 0 else 'indirect'

            alert_data = {
                'imputationcodeid': str(code.imputationcodeid),
                'code': code.code,
                'name': code.name,
                'costtype': cost_type,
                'threshold_crossed': threshold_crossed,
                'actual_pct': round(pct, 1),
                'budget': float(budget),
                'spent': float(spent),
                'remaining': float(remaining),
                'severity': severity,
            }
            alerts.append(alert_data)

            # Create suggestion for each alert
            self._create_suggestion(
                title=f"Budget alert: {code.code} at {pct:.0f}%",
                description=(
                    f"Imputation code '{code.code} - {code.name}' has consumed "
                    f"{pct:.1f}% of its ${float(budget):,.2f} budget. "
                    f"Spent: ${float(spent):,.2f}. Remaining: ${float(remaining):,.2f}."
                ),
                confidence=min(pct / 100, 1.0),
                severity=severity,
                suggested_action='review_budget',
                suggested_data=alert_data,
                relatedentityid=code.imputationcodeid,
                relatedentitytype='imputationcode',
            )

        # Sort alerts by severity (exceeded first, then by percentage)
        severity_order = {
            SuggestionSeverity.EXCEEDED: 0,
            SuggestionSeverity.CRITICAL: 1,
            SuggestionSeverity.WARNING: 2,
        }
        alerts.sort(key=lambda a: (severity_order.get(a['severity'], 3), -a['actual_pct']))

        return {
            'projectid': str(project_id),
            'alerts': alerts,
            'codes_at_risk': codes_at_risk,
            'codes_exceeded': codes_exceeded,
            'total_budget': float(total_budget),
            'total_spent': float(total_spent),
        }
