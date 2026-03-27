"""
Invoice Inbox Processor Engine.

Processes incoming invoices (from email/CFDI):
- Extract key fields from IncomingInvoice metadata
- Match supplier RFC against ProjectSupplier catalog
- Check for duplicate (same RFC + folio)
- Suggest classification based on supplier history
- Determine if auto-linkable to ProjectExpense
"""

import logging
from typing import Any, Optional

from django.db.models import Q

from apps.agents.base import BaseAgent
from apps.agents.models import AgentTypeCode, SuggestionSeverity
from apps.agents.services import register_agent

try:
    from apps.invoiceinbox.models import IncomingInvoice, IncomingInvoiceStateCode
except ImportError:
    IncomingInvoice = None
    IncomingInvoiceStateCode = None

try:
    from apps.projects.models import ProjectSupplier
except ImportError:
    ProjectSupplier = None

try:
    from apps.expenses.models import ProjectExpense
except ImportError:
    ProjectExpense = None

logger = logging.getLogger(__name__)


@register_agent
class InvoiceInboxProcessorAgent(BaseAgent):
    """Processes incoming invoices by matching, deduplicating, and classifying."""

    AGENT_TYPE = AgentTypeCode.INVOICE_INBOX_PROCESSOR

    def execute(
        self,
        project_id: str = None,
        invoice_ids: Optional[list] = None,
        **kwargs,
    ) -> Any:
        if not project_id:
            raise ValueError("project_id is required")

        if IncomingInvoice is None:
            raise RuntimeError("IncomingInvoice model not available")

        # ---- Fetch incoming invoices ----
        inv_qs = IncomingInvoice.objects.filter(projectid=project_id)
        if invoice_ids:
            inv_qs = inv_qs.filter(incominginvoiceid__in=invoice_ids)
        else:
            # Process only DRAFT invoices if no specific IDs
            if IncomingInvoiceStateCode is not None:
                inv_qs = inv_qs.filter(statecode=IncomingInvoiceStateCode.DRAFT)

        inv_qs = inv_qs.select_related('projectid', 'imputationcodeid')

        # ---- Load project suppliers for matching ----
        suppliers_by_rfc = {}
        if ProjectSupplier is not None:
            for supplier in ProjectSupplier.objects.filter(projectid=project_id):
                if supplier.rfc:
                    suppliers_by_rfc[supplier.rfc.upper().strip()] = supplier

        results = []

        for inv in inv_qs:
            validation_errors = []
            duplicate_warning = False
            matched_supplier = None
            suggested_classification = None
            auto_link_ready = False

            # ---- 1. Extract key fields ----
            extracted_data = {
                'emisor_rfc': inv.emisorrfc or '',
                'emisor_nombre': inv.emisornombre or '',
                'receptor_rfc': inv.receptorrfc or '',
                'uuid': inv.uuid or '',
                'serie': inv.serie or '',
                'folio': inv.folio or '',
                'fecha': inv.fecha.isoformat() if inv.fecha else None,
                'subtotal': float(inv.subtotal or 0),
                'total': float(inv.total or 0),
                'moneda': inv.moneda or 'MXN',
            }

            emisor_rfc = (inv.emisorrfc or '').upper().strip()

            # ---- 2. Validate required fields ----
            if not emisor_rfc:
                validation_errors.append("Missing emisor RFC.")
            if not inv.uuid:
                validation_errors.append("Missing fiscal UUID.")
            if not inv.total or float(inv.total) <= 0:
                validation_errors.append("Total amount is zero or missing.")

            # ---- 3. Match supplier RFC against ProjectSupplier catalog ----
            matched_supplier_data = None
            if emisor_rfc and emisor_rfc in suppliers_by_rfc:
                supplier = suppliers_by_rfc[emisor_rfc]
                matched_supplier_data = {
                    'projectsupplierid': str(supplier.projectsupplierid),
                    'suppliernumber': supplier.suppliernumber,
                    'businessname': supplier.businessname,
                    'rfc': supplier.rfc,
                }
            elif emisor_rfc:
                validation_errors.append(
                    f"Supplier RFC '{emisor_rfc}' not found in project catalog."
                )

            # ---- 4. Check for duplicate (same RFC + folio) ----
            if emisor_rfc and inv.folio:
                duplicate = IncomingInvoice.objects.filter(
                    projectid=project_id,
                    emisorrfc=emisor_rfc,
                    folio=inv.folio,
                ).exclude(
                    incominginvoiceid=inv.incominginvoiceid,
                ).exists()

                if duplicate:
                    duplicate_warning = True
                    validation_errors.append(
                        f"Duplicate detected: RFC '{emisor_rfc}' + folio '{inv.folio}'."
                    )

            # Also check by UUID for fiscal duplicates
            if inv.uuid:
                uuid_dup = IncomingInvoice.objects.filter(
                    projectid=project_id,
                    uuid=inv.uuid,
                ).exclude(
                    incominginvoiceid=inv.incominginvoiceid,
                ).exists()

                if uuid_dup:
                    duplicate_warning = True
                    validation_errors.append(
                        f"Duplicate fiscal UUID detected: '{inv.uuid}'."
                    )

            # ---- 5. Suggest classification based on supplier history ----
            if ProjectExpense is not None and emisor_rfc:
                # Look for past expenses from same supplier in this project
                past_expenses = ProjectExpense.objects.filter(
                    projectid=project_id,
                    supplierrfc=emisor_rfc,
                    imputationcodeid__isnull=False,
                ).select_related('imputationcodeid').order_by('-createdon')[:5]

                if past_expenses.exists():
                    # Use the most common imputation code
                    code_counts = {}
                    for exp in past_expenses:
                        code_id = str(exp.imputationcodeid_id)
                        code_counts[code_id] = code_counts.get(code_id, 0) + 1

                    if code_counts:
                        best_code_id = max(code_counts, key=code_counts.get)
                        best_count = code_counts[best_code_id]
                        total_count = sum(code_counts.values())
                        confidence = round(best_count / total_count, 2)

                        # Get imputation code info from first matching expense
                        for exp in past_expenses:
                            if str(exp.imputationcodeid_id) == best_code_id:
                                suggested_classification = {
                                    'imputationcodeid': best_code_id,
                                    'code_name': str(exp.imputationcodeid) if exp.imputationcodeid else '',
                                    'confidence': confidence,
                                    'based_on': f'{total_count} past expense(s)',
                                }
                                break

            # ---- 6. Determine if auto-linkable ----
            if (
                matched_supplier_data
                and not duplicate_warning
                and not validation_errors
                and suggested_classification
                and suggested_classification.get('confidence', 0) >= 0.8
            ):
                auto_link_ready = True

            result = {
                'incoming_invoice_id': str(inv.incominginvoiceid),
                'extracted_data': extracted_data,
                'matched_project': str(project_id),
                'matched_supplier': matched_supplier_data,
                'suggested_classification': suggested_classification,
                'validation_errors': validation_errors,
                'duplicate_warning': duplicate_warning,
                'auto_link_ready': auto_link_ready,
            }
            results.append(result)

            # Create suggestions
            if duplicate_warning:
                self._create_suggestion(
                    title=f"Duplicate invoice: {emisor_rfc} / {inv.folio or inv.uuid or ''}",
                    description=(
                        f"Incoming invoice from '{inv.emisornombre or emisor_rfc}' "
                        f"appears to be a duplicate."
                    ),
                    confidence=0.95,
                    severity=SuggestionSeverity.WARNING,
                    suggested_action='review_duplicate',
                    suggested_data=result,
                    relatedentityid=inv.incominginvoiceid,
                    relatedentitytype='incominginvoice',
                )
            elif validation_errors:
                self._create_suggestion(
                    title=f"Invoice validation issues: {emisor_rfc or 'unknown'}",
                    description=f"{len(validation_errors)} issue(s): {'; '.join(validation_errors[:3])}",
                    confidence=0.8,
                    severity=SuggestionSeverity.WARNING,
                    suggested_action='fix_validation_errors',
                    suggested_data=result,
                    relatedentityid=inv.incominginvoiceid,
                    relatedentitytype='incominginvoice',
                )
            elif auto_link_ready:
                self._create_suggestion(
                    title=f"Auto-link ready: {inv.emisornombre or emisor_rfc}",
                    description=(
                        f"Invoice ${float(inv.total or 0):,.2f} from "
                        f"'{inv.emisornombre or emisor_rfc}' can be auto-linked."
                    ),
                    confidence=suggested_classification.get('confidence', 0.8),
                    severity=SuggestionSeverity.INFO,
                    suggested_action='auto_link_invoice',
                    suggested_data=result,
                    relatedentityid=inv.incominginvoiceid,
                    relatedentitytype='incominginvoice',
                )

        return results
