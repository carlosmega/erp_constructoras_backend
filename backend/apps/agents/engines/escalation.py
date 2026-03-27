"""
Escalation Engine.

Detects SLA violations and triggers escalation notifications:
- Leads: open >7 days without activity -> notify owner; >14 days -> notify manager
- Opportunities: stalled > 2x stage benchmark -> notify owner
- Cases: active >24h without response -> notify owner; >48h -> notify manager
- Invoices: overdue >30 days -> notify manager; >60 days -> notify admin
- Expenses: pending classification >5 days -> notify classifier
"""

import logging
from datetime import timedelta
from typing import Any, Optional

from django.db.models import Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.leads.models import Lead, LeadStateCode
except ImportError:
    Lead = None
    LeadStateCode = None

try:
    from apps.opportunities.models import Opportunity, OpportunityStateCode, SalesStage
except ImportError:
    Opportunity = None
    OpportunityStateCode = None
    SalesStage = None

try:
    from apps.cases.models import Case, CaseStateCode
except ImportError:
    Case = None
    CaseStateCode = None

try:
    from apps.invoices.models import Invoice, InvoiceStateCode
except ImportError:
    Invoice = None
    InvoiceStateCode = None

try:
    from apps.expenses.models import ProjectExpense, ClassificationStatusCode
except ImportError:
    ProjectExpense = None
    ClassificationStatusCode = None

try:
    from apps.activities.models import Activity
except ImportError:
    Activity = None

try:
    from apps.notifications.services import NotificationService
except ImportError:
    NotificationService = None

try:
    from apps.users.models import SystemUser
except ImportError:
    SystemUser = None

logger = logging.getLogger(__name__)

# Default stage benchmarks in days (how long a deal should stay in each stage)
DEFAULT_STAGE_BENCHMARKS = {
    0: 14,   # Qualify: 14 days
    1: 21,   # Develop: 21 days
    2: 14,   # Propose: 14 days
    3: 7,    # Close: 7 days
}


@register_agent
class EscalationAgent(BaseAgent):
    """Detects SLA violations across entities and triggers escalation notifications."""

    AGENT_TYPE = AgentTypeCode.ESCALATION

    def execute(self, **kwargs) -> Any:
        now = timezone.now()
        today = now.date()
        escalations = []

        # Config overrides
        lead_warn_days = self.config.get('lead_warn_days', 7)
        lead_escalate_days = self.config.get('lead_escalate_days', 14)
        case_warn_hours = self.config.get('case_warn_hours', 24)
        case_escalate_hours = self.config.get('case_escalate_hours', 48)
        invoice_warn_days = self.config.get('invoice_warn_days', 30)
        invoice_escalate_days = self.config.get('invoice_escalate_days', 60)
        expense_classify_days = self.config.get('expense_classify_days', 5)
        stage_benchmarks = self.config.get('stage_benchmarks', DEFAULT_STAGE_BENCHMARKS)

        # ================================================================
        # 1. Leads: open without recent activity
        # ================================================================
        if Lead is not None and LeadStateCode is not None:
            open_leads = Lead.objects.filter(
                statecode=LeadStateCode.OPEN
            ).select_related('ownerid')

            warn_cutoff = now - timedelta(days=lead_warn_days)
            escalate_cutoff = now - timedelta(days=lead_escalate_days)

            for lead in open_leads:
                # Check last activity
                last_activity_date = None
                if Activity is not None:
                    last_act = Activity.objects.filter(
                        regardingobjectid=lead.leadid,
                        regardingobjectidtype='lead',
                    ).order_by('-createdon').first()
                    if last_act:
                        last_activity_date = last_act.createdon

                reference_date = last_activity_date or lead.createdon
                if not reference_date:
                    continue

                days_inactive = (now - reference_date).days

                if reference_date < escalate_cutoff:
                    escalations.append({
                        'entity_type': 'lead',
                        'entity_id': str(lead.leadid),
                        'entity_name': lead.fullname or '',
                        'rule_violated': 'lead_no_activity_escalate',
                        'sla_threshold': f'{lead_escalate_days} days',
                        'actual_value': f'{days_inactive} days inactive',
                        'escalation_level': 'manager',
                        'notify_user_id': str(lead.ownerid_id) if lead.ownerid_id else None,
                        'action_taken': 'notify_manager',
                    })
                elif reference_date < warn_cutoff:
                    escalations.append({
                        'entity_type': 'lead',
                        'entity_id': str(lead.leadid),
                        'entity_name': lead.fullname or '',
                        'rule_violated': 'lead_no_activity_warn',
                        'sla_threshold': f'{lead_warn_days} days',
                        'actual_value': f'{days_inactive} days inactive',
                        'escalation_level': 'owner',
                        'notify_user_id': str(lead.ownerid_id) if lead.ownerid_id else None,
                        'action_taken': 'notify_owner',
                    })

        # ================================================================
        # 2. Opportunities: stalled > 2x stage benchmark
        # ================================================================
        if Opportunity is not None and OpportunityStateCode is not None:
            open_opps = Opportunity.objects.filter(
                statecode=OpportunityStateCode.OPEN
            ).select_related('ownerid')

            for opp in open_opps:
                benchmark_days = stage_benchmarks.get(opp.salesstage, 14)
                stall_threshold = benchmark_days * 2
                stall_cutoff = now - timedelta(days=stall_threshold)

                if opp.modifiedon and opp.modifiedon < stall_cutoff:
                    days_stalled = (now - opp.modifiedon).days
                    escalations.append({
                        'entity_type': 'opportunity',
                        'entity_id': str(opp.opportunityid),
                        'entity_name': opp.name,
                        'rule_violated': 'opportunity_stalled',
                        'sla_threshold': f'{stall_threshold} days (2x stage benchmark)',
                        'actual_value': f'{days_stalled} days in current stage',
                        'escalation_level': 'owner',
                        'notify_user_id': str(opp.ownerid_id) if opp.ownerid_id else None,
                        'action_taken': 'notify_owner',
                    })

        # ================================================================
        # 3. Cases: no response within SLA
        # ================================================================
        if Case is not None and CaseStateCode is not None:
            active_cases = Case.objects.filter(
                statecode=CaseStateCode.ACTIVE
            ).select_related('ownerid')

            warn_cutoff = now - timedelta(hours=case_warn_hours)
            escalate_cutoff = now - timedelta(hours=case_escalate_hours)

            for case in active_cases:
                # Check for any activity response
                has_response = False
                if Activity is not None:
                    has_response = Activity.objects.filter(
                        regardingobjectid=case.incidentid,
                        regardingobjectidtype='case',
                    ).exists()

                if has_response:
                    continue

                hours_open = (now - case.createdon).total_seconds() / 3600 if case.createdon else 0

                if case.createdon and case.createdon < escalate_cutoff:
                    escalations.append({
                        'entity_type': 'case',
                        'entity_id': str(case.incidentid),
                        'entity_name': case.title,
                        'rule_violated': 'case_no_response_escalate',
                        'sla_threshold': f'{case_escalate_hours} hours',
                        'actual_value': f'{int(hours_open)} hours without response',
                        'escalation_level': 'manager',
                        'notify_user_id': str(case.ownerid_id) if case.ownerid_id else None,
                        'action_taken': 'notify_manager',
                    })
                elif case.createdon and case.createdon < warn_cutoff:
                    escalations.append({
                        'entity_type': 'case',
                        'entity_id': str(case.incidentid),
                        'entity_name': case.title,
                        'rule_violated': 'case_no_response_warn',
                        'sla_threshold': f'{case_warn_hours} hours',
                        'actual_value': f'{int(hours_open)} hours without response',
                        'escalation_level': 'owner',
                        'notify_user_id': str(case.ownerid_id) if case.ownerid_id else None,
                        'action_taken': 'notify_owner',
                    })

        # ================================================================
        # 4. Invoices: overdue
        # ================================================================
        if Invoice is not None and InvoiceStateCode is not None:
            overdue_invoices = Invoice.objects.filter(
                statecode=InvoiceStateCode.ACTIVE,
                duedate__lt=today,
            ).select_related('ownerid')

            for inv in overdue_invoices:
                days_overdue = (today - inv.duedate).days

                if days_overdue > invoice_escalate_days:
                    escalations.append({
                        'entity_type': 'invoice',
                        'entity_id': str(inv.invoiceid),
                        'entity_name': inv.name,
                        'rule_violated': 'invoice_overdue_escalate',
                        'sla_threshold': f'{invoice_escalate_days} days overdue',
                        'actual_value': f'{days_overdue} days overdue',
                        'escalation_level': 'admin',
                        'notify_user_id': str(inv.ownerid_id) if inv.ownerid_id else None,
                        'action_taken': 'notify_admin',
                    })
                elif days_overdue > invoice_warn_days:
                    escalations.append({
                        'entity_type': 'invoice',
                        'entity_id': str(inv.invoiceid),
                        'entity_name': inv.name,
                        'rule_violated': 'invoice_overdue_warn',
                        'sla_threshold': f'{invoice_warn_days} days overdue',
                        'actual_value': f'{days_overdue} days overdue',
                        'escalation_level': 'manager',
                        'notify_user_id': str(inv.ownerid_id) if inv.ownerid_id else None,
                        'action_taken': 'notify_manager',
                    })

        # ================================================================
        # 5. Expenses: pending classification
        # ================================================================
        if ProjectExpense is not None and ClassificationStatusCode is not None:
            classify_cutoff = now - timedelta(days=expense_classify_days)
            pending_expenses = ProjectExpense.objects.filter(
                classificationstatus=ClassificationStatusCode.PENDING,
                createdon__lt=classify_cutoff,
            ).select_related('projectid')

            for expense in pending_expenses:
                days_pending = (now - expense.createdon).days if expense.createdon else 0
                escalations.append({
                    'entity_type': 'expense',
                    'entity_id': str(expense.expenseid),
                    'entity_name': expense.suppliername or str(expense.expenseid)[:8],
                    'rule_violated': 'expense_pending_classification',
                    'sla_threshold': f'{expense_classify_days} days',
                    'actual_value': f'{days_pending} days pending classification',
                    'escalation_level': 'classifier',
                    'notify_user_id': None,
                    'action_taken': 'notify_classifier',
                })

        # ================================================================
        # Create suggestions for escalations
        # ================================================================
        for esc in escalations:
            severity = (
                SuggestionSeverity.CRITICAL
                if esc['escalation_level'] in ('manager', 'admin')
                else SuggestionSeverity.WARNING
            )
            self._create_suggestion(
                title=f"SLA violation: {esc['rule_violated']}",
                description=(
                    f"{esc['entity_type'].capitalize()} '{esc['entity_name']}': "
                    f"{esc['actual_value']} (threshold: {esc['sla_threshold']})"
                ),
                confidence=0.9,
                severity=severity,
                suggested_action=esc['action_taken'],
                suggested_data=esc,
                relatedentityid=esc['entity_id'],
                relatedentitytype=esc['entity_type'],
            )

        return escalations
