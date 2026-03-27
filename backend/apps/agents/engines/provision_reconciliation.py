"""
Provision Reconciliation Agent (Type 11).

Identifies provisions that can be reconciled with real expenses
by matching supplier RFC and similar amounts.
"""

import logging
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent
from apps.expenses.models import ProjectExpense, DocumentTypeCode, ProvisionStatusCode, ExpenseStateCode

logger = logging.getLogger(__name__)


@register_agent
class ProvisionReconciliationAgent(BaseAgent):
    """Matches active provisions with real expenses by supplier RFC and amount."""

    AGENT_TYPE = AgentTypeCode.PROVISION_RECONCILIATION

    def execute(self, *, project_id: str, **kwargs) -> list:
        tolerance = self.config.get('amount_tolerance', 0.10)
        stale_days = self.config.get('stale_days', 60)
        now = timezone.now()

        # Fetch active provisions for the project
        provisions = ProjectExpense.objects.filter(
            projectid=project_id,
            documenttype=DocumentTypeCode.PROVISION,
            provisionstatus=ProvisionStatusCode.ACTIVE,
            statecode=ExpenseStateCode.ACTIVE,
        ).select_related('projectid')

        # Fetch real invoices for the project
        invoices = ProjectExpense.objects.filter(
            projectid=project_id,
            documenttype=DocumentTypeCode.INVOICE,
            statecode=ExpenseStateCode.ACTIVE,
        )

        results = []

        for provision in provisions:
            days_active = (now.date() - provision.createdon.date()).days if provision.createdon else 0
            provision_amount = float(provision.netamount or 0)
            matched = False

            if provision.supplierrfc:
                # Try to find matching invoices by RFC and similar amount
                matching_invoices = invoices.filter(
                    supplierrfc=provision.supplierrfc,
                )

                for invoice in matching_invoices:
                    invoice_amount = float(invoice.netamount or 0)
                    if provision_amount == 0:
                        continue

                    diff_pct = abs(invoice_amount - provision_amount) / provision_amount
                    if diff_pct <= tolerance:
                        confidence = max(0.5, 1.0 - diff_pct)
                        match_type = 'exact' if diff_pct < 0.01 else 'approximate'

                        result = {
                            'provision_id': str(provision.expenseid),
                            'provision_amount': provision_amount,
                            'supplier_rfc': provision.supplierrfc,
                            'matched_expense_id': str(invoice.expenseid),
                            'matched_amount': invoice_amount,
                            'match_type': match_type,
                            'confidence': round(confidence, 2),
                            'action': 'convert',
                            'days_active': days_active,
                        }
                        results.append(result)

                        self._create_suggestion(
                            title=f"Provision matches invoice from {provision.supplierrfc}",
                            description=(
                                f"Provision ${provision_amount:,.2f} matches invoice "
                                f"${invoice_amount:,.2f} ({match_type} match, "
                                f"{diff_pct*100:.1f}% difference). "
                                f"Active for {days_active} days."
                            ),
                            confidence=confidence,
                            severity=SuggestionSeverity.INFO,
                            suggested_action='convert_provision',
                            suggested_data=result,
                            relatedentityid=provision.expenseid,
                            relatedentitytype='projectexpense',
                        )
                        matched = True
                        break

            # Flag stale provisions without a match
            if not matched and days_active > stale_days:
                result = {
                    'provision_id': str(provision.expenseid),
                    'provision_amount': provision_amount,
                    'supplier_rfc': provision.supplierrfc or '',
                    'matched_expense_id': None,
                    'matched_amount': None,
                    'match_type': 'stale',
                    'confidence': 0.7,
                    'action': 'review_or_cancel',
                    'days_active': days_active,
                }
                results.append(result)

                severity = (
                    SuggestionSeverity.CRITICAL if days_active > stale_days * 2
                    else SuggestionSeverity.WARNING
                )
                self._create_suggestion(
                    title=f"Stale provision ({days_active} days) - {provision.suppliername or 'Unknown'}",
                    description=(
                        f"Provision of ${provision_amount:,.2f} has been active for "
                        f"{days_active} days with no matching invoice. "
                        f"Consider cancellation or manual reconciliation."
                    ),
                    confidence=0.7,
                    severity=severity,
                    suggested_action='cancel_provision',
                    suggested_data=result,
                    relatedentityid=provision.expenseid,
                    relatedentitytype='projectexpense',
                )

        return results
