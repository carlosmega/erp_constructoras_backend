"""
Client Estimate Generator Agent (Type 12).

Auto-generates client estimate preview from classified expenses,
applying configurable margins and IVA calculations.
"""

import logging
from decimal import Decimal

from django.db.models import Sum, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.expenses.models import (
    ProjectExpense,
    ClientEstimate,
    ClassificationStatusCode,
    ExpenseStateCode,
)
from apps.budgets.models import CostCategory, ImputationCode, ImputationPeriod

logger = logging.getLogger(__name__)


@register_agent
class ClientEstimateGeneratorAgent(BaseAgent):
    """Generates client estimate preview from classified expenses."""

    AGENT_TYPE = AgentTypeCode.CLIENT_ESTIMATE_GENERATOR

    def execute(self, *, project_id: str, period_id: str = None, **kwargs) -> dict:
        margin_pct = Decimal(str(self.config.get('margin_percent', 15)))
        iva_pct = Decimal(str(self.config.get('iva_percent', 16)))

        # Build expense filter
        expense_filter = Q(
            projectid=project_id,
            classificationstatus=ClassificationStatusCode.CLASSIFIED,
            statecode=ExpenseStateCode.ACTIVE,
            imputationcodeid__isnull=False,
        )
        if period_id:
            expense_filter &= Q(periodid=period_id)

        # Group classified expenses by cost category
        expenses = (
            ProjectExpense.objects
            .filter(expense_filter)
            .select_related('imputationcodeid__categoryid')
        )

        category_totals = {}
        for expense in expenses:
            imp_code = expense.imputationcodeid
            if not imp_code or not imp_code.categoryid:
                continue
            cat = imp_code.categoryid
            key = str(cat.categoryid)
            if key not in category_totals:
                category_totals[key] = {
                    'category_id': key,
                    'category_code': cat.code,
                    'category_name': cat.name,
                    'amount': Decimal('0.00'),
                }
            category_totals[key]['amount'] += expense.netamount or Decimal('0.00')

        # Build estimate lines
        lines = []
        subtotal = Decimal('0.00')
        margin_total = Decimal('0.00')

        for cat_data in sorted(category_totals.values(), key=lambda x: x['category_code']):
            amount = cat_data['amount']
            margin = (amount * margin_pct / Decimal('100')).quantize(Decimal('0.01'))
            line_subtotal = amount + margin
            iva = (line_subtotal * iva_pct / Decimal('100')).quantize(Decimal('0.01'))
            total = line_subtotal + iva

            lines.append({
                'category': cat_data['category_code'],
                'description': cat_data['category_name'],
                'amount': float(amount),
                'margin': float(margin),
                'subtotal': float(line_subtotal),
                'iva': float(iva),
                'total': float(total),
            })

            subtotal += amount
            margin_total += margin

        grand_subtotal = subtotal + margin_total
        grand_iva = (grand_subtotal * iva_pct / Decimal('100')).quantize(Decimal('0.01'))
        grand_total = grand_subtotal + grand_iva

        # Compare with previous estimate
        comparison = None
        previous_estimate = (
            ClientEstimate.objects
            .filter(projectid=project_id)
            .order_by('-estimatenumber')
            .first()
        )
        if previous_estimate:
            prev_total = float(previous_estimate.totalinvoiced or 0)
            current_total = float(grand_total)
            diff = current_total - prev_total
            diff_pct = (diff / prev_total * 100) if prev_total else 0
            comparison = {
                'previous_estimate_number': previous_estimate.estimatenumber,
                'previous_total': prev_total,
                'current_total': current_total,
                'difference': round(diff, 2),
                'difference_pct': round(diff_pct, 2),
            }

        result = {
            'projectid': project_id,
            'lines': lines,
            'subtotal': float(subtotal),
            'margin_total': float(margin_total),
            'iva': float(grand_iva),
            'total': float(grand_total),
            'comparison_vs_previous': comparison,
        }

        # Create suggestion
        severity = SuggestionSeverity.INFO
        if comparison and abs(comparison['difference_pct']) > 20:
            severity = SuggestionSeverity.WARNING

        self._create_suggestion(
            title=f"Estimate preview: ${float(grand_total):,.2f} ({len(lines)} categories)",
            description=(
                f"Generated estimate from {expenses.count()} classified expenses. "
                f"Subtotal: ${float(subtotal):,.2f}, "
                f"Margin ({float(margin_pct)}%): ${float(margin_total):,.2f}, "
                f"IVA: ${float(grand_iva):,.2f}."
                + (
                    f" Change vs previous: {comparison['difference_pct']:+.1f}%"
                    if comparison else ""
                )
            ),
            confidence=0.85,
            severity=severity,
            suggested_action='create_estimate',
            suggested_data=result,
        )

        return result
