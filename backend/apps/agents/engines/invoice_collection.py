"""
Invoice Collection Agent (Type 16).

Prioritizes invoice collection by scoring based on amount, days overdue,
payment history, and last collection activity.
"""

import logging
from datetime import date, timedelta

from django.db.models import Q, Count, Avg

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.invoices.models import Invoice, InvoiceStateCode
from apps.activities.models import Activity, ActivityTypeCode, ActivityStateCode
from apps.accounts.models import Account

logger = logging.getLogger(__name__)


@register_agent
class InvoiceCollectionAgent(BaseAgent):
    """Prioritizes unpaid invoices for collection efforts."""

    AGENT_TYPE = AgentTypeCode.INVOICE_COLLECTION

    def execute(self, *, days_overdue_min: int = 0, **kwargs) -> list:
        today = date.today()

        # Get unpaid (active) invoices
        invoices = (
            Invoice.objects
            .filter(statecode=InvoiceStateCode.ACTIVE)
            .select_related('accountid', 'contactid')
        )

        if days_overdue_min > 0:
            cutoff = today - timedelta(days=days_overdue_min)
            invoices = invoices.filter(duedate__lte=cutoff)

        results = []

        for invoice in invoices:
            amount_due = float(invoice.totalamountdue or invoice.totalamount or 0)
            if amount_due <= 0:
                continue

            # Calculate days overdue
            if invoice.duedate:
                days_overdue = max(0, (today - invoice.duedate).days)
            else:
                days_overdue = 0

            # Aging bucket
            if days_overdue == 0:
                aging_bucket = 'current'
            elif days_overdue <= 30:
                aging_bucket = '1-30'
            elif days_overdue <= 60:
                aging_bucket = '31-60'
            elif days_overdue <= 90:
                aging_bucket = '61-90'
            else:
                aging_bucket = '90+'

            # Customer name
            customer_name = invoice.customer_name or 'Unknown'

            # Priority scoring
            # Amount score (0-30 pts)
            if amount_due >= 1_000_000:
                amount_score = 30
            elif amount_due >= 500_000:
                amount_score = 25
            elif amount_due >= 100_000:
                amount_score = 20
            elif amount_due >= 50_000:
                amount_score = 15
            elif amount_due >= 10_000:
                amount_score = 10
            else:
                amount_score = 5

            # Days overdue score (0-40 pts)
            if days_overdue > 90:
                overdue_score = 40
            elif days_overdue > 60:
                overdue_score = 30
            elif days_overdue > 30:
                overdue_score = 20
            elif days_overdue > 0:
                overdue_score = 10
            else:
                overdue_score = 0

            # Payment history score (0-15 pts)
            # Check how many invoices this customer has paid vs total
            account_id = invoice.accountid_id
            payment_history_score = 0
            customer_payment_history = 'unknown'

            if account_id:
                total_invoices = Invoice.objects.filter(accountid=account_id).count()
                paid_invoices = Invoice.objects.filter(
                    accountid=account_id,
                    statecode=InvoiceStateCode.PAID,
                ).count()

                if total_invoices > 0:
                    paid_ratio = paid_invoices / total_invoices
                    if paid_ratio >= 0.8:
                        payment_history_score = 5
                        customer_payment_history = 'good'
                    elif paid_ratio >= 0.5:
                        payment_history_score = 10
                        customer_payment_history = 'fair'
                    else:
                        payment_history_score = 15
                        customer_payment_history = 'poor'

            # Last collection activity score (0-20 pts)
            last_activity = (
                Activity.objects
                .filter(
                    regardingobjectid=invoice.invoiceid,
                    regardingobjectidtype='invoice',
                )
                .order_by('-createdon')
                .first()
            )

            last_collection_date = None
            if last_activity:
                last_collection_date = last_activity.createdon.date()
                days_since_activity = (today - last_collection_date).days
                if days_since_activity > 30:
                    activity_score = 20
                elif days_since_activity > 14:
                    activity_score = 15
                elif days_since_activity > 7:
                    activity_score = 10
                else:
                    activity_score = 5
            else:
                activity_score = 20  # No activity = high priority

            priority_score = amount_score + overdue_score + payment_history_score + activity_score

            # Recommended action
            if priority_score >= 80 or days_overdue > 90:
                recommended_action = 'legal'
            elif priority_score >= 60 or days_overdue > 60:
                recommended_action = 'escalate'
            elif priority_score >= 40 or days_overdue > 30:
                recommended_action = 'call'
            else:
                recommended_action = 'send_reminder'

            result = {
                'invoiceid': str(invoice.invoiceid),
                'invoice_number': invoice.invoicenumber,
                'customer_name': customer_name,
                'amount_due': amount_due,
                'days_overdue': days_overdue,
                'aging_bucket': aging_bucket,
                'priority_score': priority_score,
                'customer_payment_history': customer_payment_history,
                'last_collection_activity_date': (
                    str(last_collection_date) if last_collection_date else None
                ),
                'recommended_action': recommended_action,
            }
            results.append(result)

        # Sort by priority score descending
        results.sort(key=lambda x: x['priority_score'], reverse=True)

        # Create suggestions for top priority items
        for result in results[:20]:
            severity = SuggestionSeverity.INFO
            if result['recommended_action'] in ('legal', 'escalate'):
                severity = SuggestionSeverity.CRITICAL
            elif result['recommended_action'] == 'call':
                severity = SuggestionSeverity.WARNING

            self._create_suggestion(
                title=(
                    f"Collect {result['invoice_number']} - "
                    f"${result['amount_due']:,.2f} ({result['aging_bucket']} days)"
                ),
                description=(
                    f"Customer: {result['customer_name']}. "
                    f"Score: {result['priority_score']}/105. "
                    f"Action: {result['recommended_action']}."
                ),
                confidence=min(result['priority_score'] / 100, 0.99),
                severity=severity,
                suggested_action=result['recommended_action'],
                suggested_data=result,
                relatedentityid=result['invoiceid'],
                relatedentitytype='invoice',
            )

        return results
