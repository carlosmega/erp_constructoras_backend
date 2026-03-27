"""
Cash Flow Projector Agent (Type 18).

Projects cash flow over the next N weeks by analyzing inflows (invoices,
client estimates) and outflows (payroll, provisions, expenses, corporate).
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.invoices.models import Invoice, InvoiceStateCode
from apps.expenses.models import (
    ProjectExpense,
    ClientEstimate,
    DocumentTypeCode,
    ProvisionStatusCode,
    ExpenseStateCode,
    EstimateStateCode,
)
from apps.hrpayroll.models import PayrollRun, PayrollRunStateCode
from apps.corporate.models import CorporateBudget, BudgetStateCode

logger = logging.getLogger(__name__)


@register_agent
class CashFlowProjectorAgent(BaseAgent):
    """Projects cash flow for the upcoming weeks."""

    AGENT_TYPE = AgentTypeCode.CASH_FLOW_PROJECTOR

    def execute(self, *, weeks_ahead: int = 8, **kwargs) -> dict:
        today = date.today()
        end_date = today + timedelta(weeks=weeks_ahead)

        # =====================================================================
        # INFLOWS
        # =====================================================================

        # 1. Unpaid invoices (by due date)
        unpaid_invoices = Invoice.objects.filter(
            statecode=InvoiceStateCode.ACTIVE,
            duedate__isnull=False,
            duedate__lte=end_date,
        )
        total_invoice_inflows = float(
            unpaid_invoices.aggregate(total=Sum('totalamountdue'))['total']
            or Decimal('0')
        )

        # 2. Pending client estimates
        pending_estimates = ClientEstimate.objects.filter(
            statecode=EstimateStateCode.ACTIVE,
        )
        total_estimate_inflows = float(
            pending_estimates.aggregate(total=Sum('collectableamount'))['total']
            or Decimal('0')
        )

        total_inflows = total_invoice_inflows + total_estimate_inflows

        # =====================================================================
        # OUTFLOWS
        # =====================================================================

        # 1. Upcoming payroll (draft/calculated runs)
        upcoming_payroll = PayrollRun.objects.filter(
            statecode__in=[
                PayrollRunStateCode.DRAFT,
                PayrollRunStateCode.CALCULATED,
                PayrollRunStateCode.PENDING_APPROVAL,
                PayrollRunStateCode.APPROVED,
            ],
        )
        total_payroll = float(
            upcoming_payroll.aggregate(total=Sum('totalnetpay'))['total']
            or Decimal('0')
        )

        # 2. Active provisions
        active_provisions = ProjectExpense.objects.filter(
            documenttype=DocumentTypeCode.PROVISION,
            provisionstatus=ProvisionStatusCode.ACTIVE,
            statecode=ExpenseStateCode.ACTIVE,
        )
        total_provisions = float(
            active_provisions.aggregate(total=Sum('netamount'))['total']
            or Decimal('0')
        )

        # 3. Recent expense averages (last 4 weeks, projected forward)
        four_weeks_ago = today - timedelta(weeks=4)
        recent_expenses = ProjectExpense.objects.filter(
            statecode=ExpenseStateCode.ACTIVE,
            documenttype__in=[DocumentTypeCode.INVOICE, DocumentTypeCode.NO_INVOICE_EXPENSE],
            createdon__date__gte=four_weeks_ago,
        )
        recent_total = float(
            recent_expenses.aggregate(total=Sum('netamount'))['total']
            or Decimal('0')
        )
        weekly_expense_avg = recent_total / 4 if recent_total > 0 else 0
        projected_expenses = weekly_expense_avg * weeks_ahead

        # 4. Corporate allocations (monthly estimate)
        approved_budgets = CorporateBudget.objects.filter(
            statecode=BudgetStateCode.APPROVED,
            fiscalyear=today.year,
        )
        monthly_corporate = float(
            approved_budgets.aggregate(total=Sum('monthlypromedio'))['total']
            or Decimal('0')
        )
        projected_corporate = monthly_corporate * (weeks_ahead / 4.33)

        total_outflows = (
            total_payroll + total_provisions + projected_expenses + projected_corporate
        )

        # =====================================================================
        # NET FLOW & WEEKLY BREAKDOWN
        # =====================================================================
        net_flow = total_inflows - total_outflows

        # Weekly breakdown
        weekly_breakdown = []
        cumulative = 0.0
        weekly_inflow_avg = total_inflows / weeks_ahead if weeks_ahead > 0 else 0
        weekly_outflow_avg = total_outflows / weeks_ahead if weeks_ahead > 0 else 0

        # Distribute invoice inflows by due date
        invoice_by_week = {}
        for inv in unpaid_invoices:
            if inv.duedate:
                week_num = max(0, (inv.duedate - today).days // 7)
                if week_num < weeks_ahead:
                    invoice_by_week.setdefault(week_num, 0.0)
                    invoice_by_week[week_num] += float(inv.totalamountdue or 0)

        for week in range(weeks_ahead):
            week_start = today + timedelta(weeks=week)
            week_end = week_start + timedelta(days=6)

            # Week-specific inflows (invoices by due date + evenly spread estimates)
            week_inflows = invoice_by_week.get(week, 0.0)
            week_inflows += total_estimate_inflows / weeks_ahead

            # Outflows spread evenly
            week_outflows = weekly_outflow_avg

            week_net = week_inflows - week_outflows
            cumulative += week_net

            weekly_breakdown.append({
                'week': week + 1,
                'period': f"{week_start.isoformat()} to {week_end.isoformat()}",
                'inflows': round(week_inflows, 2),
                'outflows': round(week_outflows, 2),
                'net': round(week_net, 2),
                'cumulative': round(cumulative, 2),
            })

        # =====================================================================
        # RISK ASSESSMENT
        # =====================================================================
        if weekly_outflow_avg > 0 and net_flow < 0:
            # How many months can we sustain at current outflow rate
            monthly_outflow = weekly_outflow_avg * 4.33
            runway_months = max(0, total_inflows / monthly_outflow) if monthly_outflow > 0 else 99
        elif net_flow >= 0:
            runway_months = 99  # Positive flow
        else:
            runway_months = 0

        if runway_months > 3:
            risk_assessment = 'healthy'
        elif runway_months >= 1:
            risk_assessment = 'tight'
        else:
            risk_assessment = 'critical'

        result = {
            'inflows': {
                'unpaid_invoices': round(total_invoice_inflows, 2),
                'pending_estimates': round(total_estimate_inflows, 2),
                'total': round(total_inflows, 2),
            },
            'outflows': {
                'payroll': round(total_payroll, 2),
                'provisions': round(total_provisions, 2),
                'projected_expenses': round(projected_expenses, 2),
                'corporate_allocations': round(projected_corporate, 2),
                'total': round(total_outflows, 2),
            },
            'net_flow': round(net_flow, 2),
            'cumulative_balance': round(cumulative, 2),
            'runway_months': round(runway_months, 1),
            'risk_assessment': risk_assessment,
            'weekly_breakdown': weekly_breakdown,
        }

        # Create suggestion
        severity_map = {
            'healthy': SuggestionSeverity.INFO,
            'tight': SuggestionSeverity.WARNING,
            'critical': SuggestionSeverity.CRITICAL,
        }

        self._create_suggestion(
            title=f"Cash flow projection: {risk_assessment.upper()} ({weeks_ahead} weeks)",
            description=(
                f"Inflows: ${total_inflows:,.2f}, Outflows: ${total_outflows:,.2f}, "
                f"Net: ${net_flow:,.2f}. "
                f"Runway: {runway_months:.1f} months."
            ),
            confidence=0.75,
            severity=severity_map[risk_assessment],
            suggested_action='review_cash_flow',
            suggested_data=result,
        )

        return result
