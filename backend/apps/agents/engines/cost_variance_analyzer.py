"""
Cost Variance Analyzer Engine.

Compares actual vs budgeted costs:
- By cost category (P1-P10, C1-C8)
- By zone
- Top 5 overruns and top 5 savings
- Projected end cost (linear extrapolation based on project duration)
"""

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.budgets.models import ImputationCode, CostCategory
except ImportError:
    ImputationCode = None
    CostCategory = None

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

try:
    from apps.projects.models import ConstructionProject
except ImportError:
    ConstructionProject = None

logger = logging.getLogger(__name__)


@register_agent
class CostVarianceAnalyzerAgent(BaseAgent):
    """Compares actual vs budgeted costs by category, zone, and overall."""

    AGENT_TYPE = AgentTypeCode.COST_VARIANCE_ANALYZER

    def execute(self, project_id: str = '', **kwargs) -> Any:
        if not project_id:
            raise ValueError("project_id is required")
        if ImputationCode is None or ProjectExpense is None or ConstructionProject is None:
            raise RuntimeError("Required models not available")

        # Load project for duration info
        try:
            project = ConstructionProject.objects.get(projectid=project_id)
        except ConstructionProject.DoesNotExist:
            raise ValueError(f"Project {project_id} not found")

        # Load imputation codes with category and zone
        codes = list(
            ImputationCode.objects.filter(
                projectid=project_id,
            ).select_related('categoryid', 'zoneid')
        )

        # Aggregate actual spend per imputation code
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

        # --- By Category ---
        category_data = defaultdict(lambda: {
            'budget': Decimal('0'), 'actual': Decimal('0'),
        })
        category_names = {}
        category_prefixes = {}

        for code in codes:
            cat = code.categoryid
            if not cat:
                continue
            cat_key = str(cat.categoryid)
            category_names[cat_key] = cat.name
            category_prefixes[cat_key] = cat.code
            category_data[cat_key]['budget'] += code.totalbudget or Decimal('0')
            category_data[cat_key]['actual'] += spend_agg.get(
                code.imputationcodeid, Decimal('0')
            ) or Decimal('0')

        by_category = []
        for cat_key, data in category_data.items():
            budget = data['budget']
            actual = data['actual']
            variance = actual - budget
            pct = float(variance / budget * 100) if budget > 0 else 0.0
            by_category.append({
                'category': category_names.get(cat_key, cat_key),
                'prefix': category_prefixes.get(cat_key, ''),
                'budget': float(budget),
                'actual': float(actual),
                'variance': float(variance),
                'pct': round(pct, 1),
            })

        by_category.sort(key=lambda x: x['prefix'])

        # --- By Zone ---
        zone_data = defaultdict(lambda: {
            'budget': Decimal('0'), 'actual': Decimal('0'),
        })
        zone_names = {}
        zone_prefixes = {}

        for code in codes:
            zone = code.zoneid
            if not zone:
                continue
            zone_key = str(zone.zoneid)
            zone_names[zone_key] = zone.name
            zone_prefixes[zone_key] = getattr(zone, 'prefix', '') or ''
            zone_data[zone_key]['budget'] += code.totalbudget or Decimal('0')
            zone_data[zone_key]['actual'] += spend_agg.get(
                code.imputationcodeid, Decimal('0')
            ) or Decimal('0')

        by_zone = []
        for zone_key, data in zone_data.items():
            budget = data['budget']
            actual = data['actual']
            variance = actual - budget
            pct = float(variance / budget * 100) if budget > 0 else 0.0
            by_zone.append({
                'zone': zone_names.get(zone_key, zone_key),
                'prefix': zone_prefixes.get(zone_key, ''),
                'budget': float(budget),
                'actual': float(actual),
                'variance': float(variance),
                'pct': round(pct, 1),
            })

        by_zone.sort(key=lambda x: x['prefix'])

        # --- Total budget and actual ---
        total_budget = sum(
            (code.totalbudget or Decimal('0')) for code in codes
        )
        total_actual = sum(
            spend_agg.get(code.imputationcodeid, Decimal('0')) or Decimal('0')
            for code in codes
        )

        # --- Top 5 overruns and top 5 savings (by imputation code) ---
        code_variances = []
        for code in codes:
            budget = code.totalbudget or Decimal('0')
            actual = spend_agg.get(code.imputationcodeid, Decimal('0')) or Decimal('0')
            variance = actual - budget
            pct = float(variance / budget * 100) if budget > 0 else 0.0
            code_variances.append({
                'code': code.code,
                'name': code.name,
                'budget': float(budget),
                'actual': float(actual),
                'variance': float(variance),
                'pct': round(pct, 1),
            })

        code_variances.sort(key=lambda x: x['variance'], reverse=True)
        top_overruns = [v for v in code_variances if v['variance'] > 0][:5]
        top_savings = [v for v in reversed(code_variances) if v['variance'] < 0][:5]

        # --- Projected end cost (linear extrapolation) ---
        projected_end_cost = float(total_actual)
        projected_variance_pct = 0.0
        now = timezone.now().date()

        if project.startdate and project.durationmonths:
            total_days = project.durationmonths * 30
            elapsed_days = (now - project.startdate).days
            if elapsed_days > 0 and elapsed_days < total_days:
                burn_rate = float(total_actual) / elapsed_days
                projected_end_cost = burn_rate * total_days
            elif elapsed_days >= total_days:
                projected_end_cost = float(total_actual)

        if float(total_budget) > 0:
            projected_variance_pct = round(
                (projected_end_cost - float(total_budget)) / float(total_budget) * 100, 1
            )

        # Create suggestion for significant overruns
        if projected_variance_pct > 5:
            severity = (
                SuggestionSeverity.CRITICAL if projected_variance_pct > 15
                else SuggestionSeverity.WARNING
            )
            self._create_suggestion(
                title=f"Project projected to exceed budget by {projected_variance_pct:.1f}%",
                description=(
                    f"Current spend: ${float(total_actual):,.2f} of ${float(total_budget):,.2f}. "
                    f"Projected end cost: ${projected_end_cost:,.2f}. "
                    f"Top overruns: {', '.join(o['code'] for o in top_overruns[:3])}."
                ),
                confidence=0.7,
                severity=severity,
                suggested_action='review_cost_overruns',
                suggested_data={
                    'projectid': str(project_id),
                    'projected_variance_pct': projected_variance_pct,
                },
                relatedentitytype='project',
            )

        return {
            'projectid': str(project_id),
            'by_category': by_category,
            'by_zone': by_zone,
            'top_overruns': top_overruns,
            'top_savings': top_savings,
            'total_budget': float(total_budget),
            'total_actual': float(total_actual),
            'projected_end_cost': round(projected_end_cost, 2),
            'projected_variance_pct': projected_variance_pct,
        }
