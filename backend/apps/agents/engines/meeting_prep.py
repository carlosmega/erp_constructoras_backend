"""
Meeting Prep Engine.

Generates a meeting preparation brief by gathering customer info,
open opportunities, pending quotes, recent activities, open cases,
key talking points, and risks (overdue invoices, complaints).
"""

import logging
from typing import Any, Optional

from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.activities.models import Activity, Appointment, ActivityTypeCode
except ImportError:
    Activity = None
    Appointment = None
    ActivityTypeCode = None

try:
    from apps.opportunities.models import Opportunity, OpportunityStateCode, SalesStage
except ImportError:
    Opportunity = None
    OpportunityStateCode = None
    SalesStage = None

try:
    from apps.quotes.models import Quote, QuoteStateCode
except ImportError:
    Quote = None
    QuoteStateCode = None

try:
    from apps.invoices.models import Invoice, InvoiceStateCode
except ImportError:
    Invoice = None
    InvoiceStateCode = None

try:
    from apps.cases.models import Case, CaseStateCode
except ImportError:
    Case = None
    CaseStateCode = None

try:
    from apps.accounts.models import Account
except ImportError:
    Account = None

try:
    from apps.contacts.models import Contact
except ImportError:
    Contact = None

logger = logging.getLogger(__name__)


@register_agent
class MeetingPrepAgent(BaseAgent):
    """Generates a comprehensive meeting preparation brief."""

    AGENT_TYPE = AgentTypeCode.MEETING_PREP

    def execute(self, appointment_id: str = None, **kwargs) -> Any:
        if not appointment_id:
            raise ValueError("appointment_id is required")

        if Activity is None or Appointment is None:
            raise RuntimeError("Activity/Appointment models not available")

        # ---- Fetch appointment ----
        try:
            activity = Activity.objects.select_related('ownerid').get(
                activityid=appointment_id
            )
        except Activity.DoesNotExist:
            raise ValueError(f"Appointment activity {appointment_id} not found")

        meeting_title = activity.subject or ''
        meeting_datetime = (
            activity.scheduledstart.isoformat() if activity.scheduledstart else None
        )

        # ---- Determine customer from regardingobjectid ----
        entity_type = activity.regardingobjectidtype or ''
        entity_id = activity.regardingobjectid

        customer_summary = {}
        account = None
        contact = None

        if entity_type == 'account' and entity_id and Account is not None:
            try:
                account = Account.objects.get(accountid=entity_id)
                customer_summary = {
                    'type': 'account',
                    'id': str(account.accountid),
                    'name': account.name,
                    'email': getattr(account, 'emailaddress1', '') or '',
                    'phone': getattr(account, 'telephone1', '') or '',
                }
            except Account.DoesNotExist:
                pass
        elif entity_type == 'contact' and entity_id and Contact is not None:
            try:
                contact = Contact.objects.select_related('parentcustomerid').get(
                    contactid=entity_id
                )
                customer_summary = {
                    'type': 'contact',
                    'id': str(contact.contactid),
                    'name': contact.fullname or '',
                    'email': getattr(contact, 'emailaddress1', '') or '',
                    'phone': getattr(contact, 'telephone1', '') or '',
                }
                # Also try to get account from contact
                if hasattr(contact, 'parentcustomerid') and contact.parentcustomerid:
                    account = contact.parentcustomerid
            except Contact.DoesNotExist:
                pass

        # ---- Open opportunities ----
        open_opportunities = []
        if Opportunity is not None and entity_id:
            opp_qs = Opportunity.objects.filter(
                statecode=OpportunityStateCode.OPEN
            )
            if account:
                opp_qs = opp_qs.filter(accountid=account)
            elif contact:
                opp_qs = opp_qs.filter(contactid=contact)
            else:
                opp_qs = opp_qs.none()

            for opp in opp_qs.order_by('-estimatedrevenue')[:10]:
                stage_label = (
                    SalesStage(opp.salesstage).label
                    if SalesStage and opp.salesstage is not None
                    else ''
                )
                open_opportunities.append({
                    'name': opp.name,
                    'stage': stage_label,
                    'value': float(opp.estimatedrevenue or 0),
                })

        # ---- Pending/active quotes ----
        pending_quotes = []
        if Quote is not None and entity_id:
            quote_qs = Quote.objects.filter(
                statecode__in=[QuoteStateCode.DRAFT, QuoteStateCode.ACTIVE]
            )
            if account:
                quote_qs = quote_qs.filter(accountid=account)
            elif contact:
                quote_qs = quote_qs.filter(contactid=contact)
            else:
                quote_qs = quote_qs.none()

            for q in quote_qs.order_by('-createdon')[:10]:
                pending_quotes.append({
                    'name': q.name,
                    'number': q.quotenumber,
                    'total': float(q.totalamount or 0),
                    'state': q.get_statecode_display(),
                })

        # ---- Recent activities (last 5) ----
        recent_activities = []
        if Activity is not None and entity_id:
            act_qs = Activity.objects.filter(
                regardingobjectid=entity_id,
            ).order_by('-createdon')[:5]
            for act in act_qs:
                recent_activities.append({
                    'type': act.activitytypecode,
                    'subject': act.subject or '',
                    'date': act.createdon.isoformat() if act.createdon else None,
                    'state': act.get_statecode_display(),
                })

        # ---- Open cases ----
        open_cases = []
        if Case is not None:
            case_qs = Case.objects.filter(statecode=CaseStateCode.ACTIVE)
            if account:
                case_qs = case_qs.filter(accountid=account)
            elif contact:
                case_qs = case_qs.filter(contactid=contact)
            else:
                case_qs = case_qs.none()

            for c in case_qs.order_by('-createdon')[:10]:
                open_cases.append({
                    'title': c.title,
                    'ticket': c.ticketnumber,
                    'priority': c.get_prioritycode_display(),
                    'status': c.get_statuscode_display(),
                })

        # ---- Risks ----
        risks = []

        # Overdue invoices
        if Invoice is not None and InvoiceStateCode is not None:
            today = timezone.now().date()
            inv_qs = Invoice.objects.filter(
                statecode=InvoiceStateCode.ACTIVE,
                duedate__lt=today,
            )
            if account:
                inv_qs = inv_qs.filter(accountid=account)
            elif contact:
                inv_qs = inv_qs.filter(contactid=contact)
            else:
                inv_qs = inv_qs.none()

            overdue_count = inv_qs.count()
            if overdue_count > 0:
                total_overdue = sum(float(inv.totalamount or 0) for inv in inv_qs[:20])
                risks.append({
                    'type': 'overdue_invoices',
                    'details': f"{overdue_count} overdue invoice(s) totaling ${total_overdue:,.2f}",
                })

        # Recent complaints (cases created in last 30 days)
        if Case is not None:
            cutoff = timezone.now() - timezone.timedelta(days=30)
            complaint_qs = Case.objects.filter(createdon__gte=cutoff)
            if account:
                complaint_qs = complaint_qs.filter(accountid=account)
            elif contact:
                complaint_qs = complaint_qs.filter(contactid=contact)
            else:
                complaint_qs = complaint_qs.none()

            complaint_count = complaint_qs.count()
            if complaint_count > 0:
                risks.append({
                    'type': 'recent_complaints',
                    'details': f"{complaint_count} case(s) opened in the last 30 days",
                })

        # ---- Key talking points ----
        key_talking_points = []
        if open_opportunities:
            key_talking_points.append(
                f"{len(open_opportunities)} open opportunity(ies) to discuss"
            )
        if pending_quotes:
            key_talking_points.append(
                f"{len(pending_quotes)} pending/active quote(s) awaiting decision"
            )
        if open_cases:
            key_talking_points.append(
                f"{len(open_cases)} open case(s) to address"
            )
        if risks:
            key_talking_points.append("Address outstanding risks before advancing deals")
        if not recent_activities:
            key_talking_points.append("No recent activity logged -- re-establish relationship")

        # ---- Create suggestion ----
        risk_count = len(risks)
        if risk_count > 0:
            self._create_suggestion(
                title=f"Meeting prep: {risk_count} risk(s) identified",
                description=f"Meeting '{meeting_title}' has {risk_count} risk(s) to review.",
                confidence=0.8,
                severity=(
                    SuggestionSeverity.WARNING if risk_count <= 2
                    else SuggestionSeverity.CRITICAL
                ),
                suggested_action='review_risks',
                suggested_data={'appointment_id': appointment_id, 'risks': risks},
                relatedentityid=activity.activityid,
                relatedentitytype='appointment',
            )

        return {
            'appointment_id': appointment_id,
            'meeting_title': meeting_title,
            'meeting_datetime': meeting_datetime,
            'customer_summary': customer_summary,
            'open_opportunities': open_opportunities,
            'pending_quotes': pending_quotes,
            'recent_activities': recent_activities,
            'open_cases': open_cases,
            'key_talking_points': key_talking_points,
            'risks': risks,
        }
