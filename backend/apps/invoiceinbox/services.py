"""
Invoice Inbox business logic services.

IncomingInvoiceService — CRUD + state transitions for incoming invoices
InboxMatchingService — Auto-match incoming invoices to existing expenses
InboxSyncLogService — Sync log management
"""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet, Q, Count
from django.utils import timezone

from apps.invoiceinbox.models import (
    IncomingInvoice,
    IncomingInvoiceStateCode,
    InboxSyncLog,
)
from apps.expenses.models import ProjectExpense, ExpenseStateCode
from apps.projects.models import ConstructionProject
from apps.budgets.models import ImputationCode
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound

logger = logging.getLogger(__name__)


class IncomingInvoiceService:
    """Business logic for IncomingInvoice entity."""

    @staticmethod
    def list_invoices(
        user: SystemUser,
        statecode: Optional[int] = None,
        projectid: Optional[UUID] = None,
        emisorrfc: Optional[str] = None,
        search: Optional[str] = None,
        unclassified_only: bool = False,
    ) -> QuerySet[IncomingInvoice]:
        """List incoming invoices with optional filtering."""
        queryset = IncomingInvoice.objects.all()

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)

        if unclassified_only:
            queryset = queryset.filter(statecode=IncomingInvoiceStateCode.DRAFT)

        if projectid:
            queryset = queryset.filter(projectid=projectid)

        if emisorrfc:
            queryset = queryset.filter(emisorrfc=emisorrfc)

        if search:
            queryset = queryset.filter(
                Q(emisornombre__icontains=search) |
                Q(emisorrfc__icontains=search) |
                Q(uuid__icontains=search) |
                Q(folio__icontains=search) |
                Q(emailsubject__icontains=search)
            )

        return queryset.select_related(
            'projectid', 'imputationcodeid',
            'linkedexpenseid', 'suggestedexpenseid',
            'createdby', 'modifiedby',
        )

    @staticmethod
    def get_by_id(incoming_id: UUID, user: SystemUser) -> IncomingInvoice:
        """Get single incoming invoice with related data."""
        try:
            return IncomingInvoice.objects.select_related(
                'projectid', 'imputationcodeid',
                'linkedexpenseid', 'suggestedexpenseid',
                'createdby', 'modifiedby',
            ).get(incominginvoiceid=incoming_id)
        except IncomingInvoice.DoesNotExist:
            raise NotFound(f'Incoming invoice {incoming_id} not found')

    @staticmethod
    @transaction.atomic
    def classify_invoice(
        incoming_id: UUID,
        imputation_code_id: UUID,
        user: SystemUser,
        notes: Optional[str] = None,
    ) -> IncomingInvoice:
        """
        Classify an incoming invoice by assigning its imputation code.

        Project is already set (auto-assigned from the shared mailbox).
        Transitions: Draft → Classified
        """
        incoming = IncomingInvoiceService.get_by_id(incoming_id, user)

        if incoming.statecode not in (
            IncomingInvoiceStateCode.DRAFT,
            IncomingInvoiceStateCode.CLASSIFIED,
        ):
            raise ValidationError(
                f'Cannot classify invoice in state {incoming.get_statecode_display()}'
            )

        # Validate imputation code belongs to the invoice's project
        try:
            ImputationCode.objects.get(
                imputationcodeid=imputation_code_id,
                categoryid__projectid=incoming.projectid_id,
            )
        except ImputationCode.DoesNotExist:
            raise NotFound(
                f'Imputation code {imputation_code_id} not found for project {incoming.projectid_id}'
            )

        incoming.imputationcodeid_id = imputation_code_id
        incoming.statecode = IncomingInvoiceStateCode.CLASSIFIED
        incoming.classificationnotes = notes
        incoming.modifiedby = user
        incoming.save(update_fields=[
            'imputationcodeid', 'statecode',
            'classificationnotes', 'modifiedby', 'modifiedon',
        ])

        logger.info(
            'Invoice %s classified with code %s by user %s',
            incoming_id, imputation_code_id, user.systemuserid,
        )
        return incoming

    @staticmethod
    @transaction.atomic
    def bulk_classify(
        invoice_ids: list[UUID],
        imputation_code_id: UUID,
        user: SystemUser,
        notes: Optional[str] = None,
    ) -> list[IncomingInvoice]:
        """Bulk classify multiple invoices with the same imputation code."""
        results = []
        for inv_id in invoice_ids:
            result = IncomingInvoiceService.classify_invoice(
                inv_id, imputation_code_id, user, notes
            )
            results.append(result)
        return results

    @staticmethod
    @transaction.atomic
    def reject_invoice(
        incoming_id: UUID,
        notes: str,
        user: SystemUser,
    ) -> IncomingInvoice:
        """
        Reject an incoming invoice.

        Transitions: Draft/Classified → Rejected
        """
        incoming = IncomingInvoiceService.get_by_id(incoming_id, user)

        if incoming.statecode == IncomingInvoiceStateCode.LINKED:
            raise ValidationError(
                'Cannot reject a linked invoice. Unlink it first.'
            )
        if incoming.statecode == IncomingInvoiceStateCode.REJECTED:
            raise ValidationError('Invoice is already rejected.')

        incoming.statecode = IncomingInvoiceStateCode.REJECTED
        incoming.rejectionnotes = notes
        incoming.modifiedby = user
        incoming.save(update_fields=[
            'statecode', 'rejectionnotes', 'modifiedby', 'modifiedon',
        ])

        logger.info('Invoice %s rejected by user %s', incoming_id, user.systemuserid)
        return incoming

    @staticmethod
    @transaction.atomic
    def link_to_expense(
        incoming_id: UUID,
        period_id: UUID,
        user: SystemUser,
        expense_id: Optional[UUID] = None,
    ) -> IncomingInvoice:
        """
        Link incoming invoice to an existing or new ProjectExpense.

        If expense_id is None, creates a new ProjectExpense from CFDI data.
        Transitions: Draft/Classified → Linked
        """
        from apps.expenses.services import ExpenseService, AttachmentService
        from apps.expenses.schemas import CreateProjectExpenseDto

        incoming = IncomingInvoiceService.get_by_id(incoming_id, user)

        if incoming.statecode == IncomingInvoiceStateCode.LINKED:
            raise ValidationError('Invoice is already linked to an expense.')
        if incoming.statecode == IncomingInvoiceStateCode.REJECTED:
            raise ValidationError('Cannot link a rejected invoice.')

        if expense_id:
            # Link to existing expense
            try:
                expense = ProjectExpense.objects.get(expenseid=expense_id)
            except ProjectExpense.DoesNotExist:
                raise NotFound(f'Expense {expense_id} not found')
        else:
            # Create new expense from CFDI data
            currency = 0 if incoming.moneda == 'MXN' else 1  # CurrencyCode
            dto = CreateProjectExpenseDto(
                projectid=incoming.projectid_id,
                periodid=period_id,
                documenttype=0,  # INVOICE
                imputationcodeid=incoming.imputationcodeid_id,
                supplierrfc=incoming.emisorrfc,
                suppliername=incoming.emisornombre,
                invoiceuuid=incoming.uuid,
                invoicefolio=incoming.folio,
                invoicedate=incoming.fecha.date() if incoming.fecha else None,
                currency=currency,
                exchangerate=incoming.tipocambio or Decimal('1.0000'),
                subtotal=incoming.subtotal,
                taxamount=incoming.totalimpuestostrasladados,
                retentionamount=incoming.totalimpuestosretenidos,
                discountamount=incoming.descuento,
                netamount=incoming.total,
                expensesource='Invoice Inbox',
            )
            expense = ExpenseService.create_expense(dto, user)

            # Copy attachments
            if incoming.xmlfile:
                AttachmentService.add_attachment(
                    expense_id=expense.expenseid,
                    filename=incoming.xmlfilename or 'factura.xml',
                    filetype=1,  # XML
                    filesize=incoming.xmlfilesize,
                    mimetype='text/xml',
                    file=incoming.xmlfile,
                    user=user,
                )
            if incoming.pdffile:
                AttachmentService.add_attachment(
                    expense_id=expense.expenseid,
                    filename=incoming.pdffilename or 'factura.pdf',
                    filetype=0,  # PDF
                    filesize=incoming.pdffilesize,
                    mimetype='application/pdf',
                    file=incoming.pdffile,
                    user=user,
                )

        incoming.linkedexpenseid = expense
        incoming.statecode = IncomingInvoiceStateCode.LINKED
        incoming.matchtype = 'manual'
        incoming.modifiedby = user
        incoming.save(update_fields=[
            'linkedexpenseid', 'statecode', 'matchtype',
            'modifiedby', 'modifiedon',
        ])

        logger.info(
            'Invoice %s linked to expense %s by user %s',
            incoming_id, expense.expenseid, user.systemuserid,
        )
        return incoming

    @staticmethod
    @transaction.atomic
    def unlink_invoice(
        incoming_id: UUID,
        user: SystemUser,
    ) -> IncomingInvoice:
        """Undo linking: set back to Classified, clear linkedexpenseid."""
        incoming = IncomingInvoiceService.get_by_id(incoming_id, user)

        if incoming.statecode != IncomingInvoiceStateCode.LINKED:
            raise ValidationError('Invoice is not linked.')

        incoming.linkedexpenseid = None
        incoming.statecode = IncomingInvoiceStateCode.CLASSIFIED
        incoming.matchtype = None
        incoming.modifiedby = user
        incoming.save(update_fields=[
            'linkedexpenseid', 'statecode', 'matchtype',
            'modifiedby', 'modifiedon',
        ])

        logger.info('Invoice %s unlinked by user %s', incoming_id, user.systemuserid)
        return incoming

    @staticmethod
    def get_inbox_summary(project_id: Optional[UUID] = None) -> dict:
        """Get summary counts for the inbox, optionally filtered by project."""
        qs = IncomingInvoice.objects.all()
        if project_id:
            qs = qs.filter(projectid=project_id)

        counts = qs.aggregate(
            draftcount=Count('incominginvoiceid', filter=Q(
                statecode=IncomingInvoiceStateCode.DRAFT
            )),
            classifiedcount=Count('incominginvoiceid', filter=Q(
                statecode=IncomingInvoiceStateCode.CLASSIFIED
            )),
            linkedcount=Count('incominginvoiceid', filter=Q(
                statecode=IncomingInvoiceStateCode.LINKED
            )),
            rejectedcount=Count('incominginvoiceid', filter=Q(
                statecode=IncomingInvoiceStateCode.REJECTED
            )),
            totalcount=Count('incominginvoiceid'),
        )

        sync_qs = InboxSyncLog.objects.all()
        if project_id:
            sync_qs = sync_qs.filter(projectid=project_id)
        latest_sync = sync_qs.order_by('-startedon').first()
        counts['lastsyncdate'] = latest_sync.startedon if latest_sync else None

        return counts


class InboxMatchingService:
    """Matching logic for incoming invoices against existing expenses."""

    @staticmethod
    def find_matches(incoming: IncomingInvoice) -> list[dict]:
        """
        Find potential matches for an incoming invoice.

        Strategy (in order of confidence):
        1. Exact UUID match (100%)
        2. RFC + Folio match (80%)
        3. RFC + Amount within 1% tolerance (60%)
        """
        matches = []
        expenses = ProjectExpense.objects.filter(
            statecode=ExpenseStateCode.ACTIVE,
        ).select_related('projectid')

        # 1. Exact UUID match
        if incoming.uuid:
            uuid_matches = expenses.filter(invoiceuuid=incoming.uuid)
            for exp in uuid_matches:
                matches.append({
                    'expenseid': exp.expenseid,
                    'matchtype': 'uuid_exact',
                    'confidence': 100,
                    'suppliername': exp.suppliername,
                    'supplierrfc': exp.supplierrfc,
                    'invoicefolio': exp.invoicefolio,
                    'netamount': exp.netamount,
                    'projectname': exp.projectid.name if exp.projectid else None,
                })

        # 2. RFC + Folio match
        if incoming.emisorrfc and incoming.folio and not matches:
            rfc_folio_matches = expenses.filter(
                supplierrfc=incoming.emisorrfc,
                invoicefolio=incoming.folio,
            )
            for exp in rfc_folio_matches:
                matches.append({
                    'expenseid': exp.expenseid,
                    'matchtype': 'rfc_folio',
                    'confidence': 80,
                    'suppliername': exp.suppliername,
                    'supplierrfc': exp.supplierrfc,
                    'invoicefolio': exp.invoicefolio,
                    'netamount': exp.netamount,
                    'projectname': exp.projectid.name if exp.projectid else None,
                })

        # 3. RFC + Amount match (within 1% tolerance)
        if incoming.emisorrfc and incoming.total and not matches:
            tolerance = incoming.total * Decimal('0.01')
            lower = incoming.total - tolerance
            upper = incoming.total + tolerance
            amount_matches = expenses.filter(
                supplierrfc=incoming.emisorrfc,
                netamount__gte=lower,
                netamount__lte=upper,
            )
            for exp in amount_matches:
                matches.append({
                    'expenseid': exp.expenseid,
                    'matchtype': 'rfc_amount',
                    'confidence': 60,
                    'suppliername': exp.suppliername,
                    'supplierrfc': exp.supplierrfc,
                    'invoicefolio': exp.invoicefolio,
                    'netamount': exp.netamount,
                    'projectname': exp.projectid.name if exp.projectid else None,
                })

        return matches

    @staticmethod
    def auto_suggest_match(incoming: IncomingInvoice) -> None:
        """Run matching and set suggestedexpenseid if high-confidence match found."""
        matches = InboxMatchingService.find_matches(incoming)
        if matches and matches[0]['confidence'] >= 80:
            incoming.suggestedexpenseid_id = matches[0]['expenseid']
            incoming.matchtype = matches[0]['matchtype']
            incoming.matchconfidence = matches[0]['confidence']
            incoming.save(update_fields=[
                'suggestedexpenseid', 'matchtype', 'matchconfidence',
            ])


class InboxSyncLogService:
    """Manages sync log records."""

    @staticmethod
    def list_logs(project_id: Optional[UUID] = None) -> QuerySet[InboxSyncLog]:
        """List sync logs, optionally filtered by project."""
        qs = InboxSyncLog.objects.select_related('triggeredbyuserid', 'projectid')
        if project_id:
            qs = qs.filter(projectid=project_id)
        return qs

    @staticmethod
    def get_latest(project_id: Optional[UUID] = None) -> Optional[InboxSyncLog]:
        """Get most recent sync log, optionally for a specific project."""
        qs = InboxSyncLog.objects.all()
        if project_id:
            qs = qs.filter(projectid=project_id)
        return qs.order_by('-startedon').first()
