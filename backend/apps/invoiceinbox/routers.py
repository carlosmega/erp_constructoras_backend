"""
Invoice Inbox API endpoints.

Provides endpoints for listing, classifying, linking, and syncing
incoming invoices from project shared mailboxes.
"""

import logging
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

from django.http import HttpRequest, FileResponse
from ninja import Router

from apps.invoiceinbox.models import IncomingInvoice
from apps.invoiceinbox.schemas import (
    IncomingInvoiceSchema,
    IncomingInvoiceListSchema,
    InboxSyncLogSchema,
    ClassifyInvoiceDto,
    RejectInvoiceDto,
    LinkToExpenseDto,
    BulkClassifyDto,
    InboxSummarySchema,
    SyncResultSchema,
    MatchSuggestionSchema,
    CapturedEmailsResponse,
)
from apps.invoiceinbox.services import (
    IncomingInvoiceService,
    InboxMatchingService,
    InboxSyncLogService,
)
from apps.invoiceinbox.graph_inbox_service import GraphInboxService
from apps.invoiceinbox.models import SyncTriggerCode
from apps.projects.models import ConstructionProject
from core.exceptions import NotFound
from core.permissions import require_permission, Permission

inbox_router = Router(tags=["Invoice Inbox"])


# ── Helpers ──

def _get_project(project_id: UUID) -> ConstructionProject:
    """Fetch project or raise NotFound."""
    try:
        return ConstructionProject.objects.get(projectid=project_id)
    except ConstructionProject.DoesNotExist:
        raise NotFound(f'Project {project_id} not found')


# ── List & Detail ──

@inbox_router.get("/inbox/", response=List[IncomingInvoiceListSchema])
@require_permission(Permission.INBOX_READ)
def list_incoming_invoices(
    request: HttpRequest,
    statecode: Optional[int] = None,
    projectid: Optional[UUID] = None,
    emisorrfc: Optional[str] = None,
    search: Optional[str] = None,
    unclassified: Optional[bool] = None,
):
    """List all incoming invoices with optional filtering."""
    invoices = IncomingInvoiceService.list_invoices(
        user=request.user,
        statecode=statecode,
        projectid=projectid,
        emisorrfc=emisorrfc,
        search=search,
        unclassified_only=bool(unclassified),
    )
    return list(invoices)


@inbox_router.get("/projects/{project_id}/inbox/", response=List[IncomingInvoiceListSchema])
@require_permission(Permission.INBOX_READ)
def list_project_invoices(
    request: HttpRequest,
    project_id: UUID,
    statecode: Optional[int] = None,
    emisorrfc: Optional[str] = None,
    search: Optional[str] = None,
    unclassified: Optional[bool] = None,
):
    """List incoming invoices for a specific project."""
    _get_project(project_id)
    invoices = IncomingInvoiceService.list_invoices(
        user=request.user,
        statecode=statecode,
        projectid=project_id,
        emisorrfc=emisorrfc,
        search=search,
        unclassified_only=bool(unclassified),
    )
    return list(invoices)


@inbox_router.get("/inbox/{incoming_id}/", response=IncomingInvoiceSchema)
@require_permission(Permission.INBOX_READ)
def get_incoming_invoice(request: HttpRequest, incoming_id: UUID):
    """Get full incoming invoice details including conceptos."""
    return IncomingInvoiceService.get_by_id(incoming_id, request.user)


# ── Classify ──

@inbox_router.post("/inbox/{incoming_id}/classify/", response=IncomingInvoiceSchema)
@require_permission(Permission.INBOX_CLASSIFY)
def classify_invoice(
    request: HttpRequest,
    incoming_id: UUID,
    payload: ClassifyInvoiceDto,
):
    """Classify incoming invoice by assigning imputation code."""
    return IncomingInvoiceService.classify_invoice(
        incoming_id=incoming_id,
        imputation_code_id=payload.imputationcodeid,
        user=request.user,
        notes=payload.notes,
    )


@inbox_router.post("/inbox/bulk-classify/", response=List[IncomingInvoiceSchema])
@require_permission(Permission.INBOX_CLASSIFY)
def bulk_classify_invoices(request: HttpRequest, payload: BulkClassifyDto):
    """Bulk classify multiple invoices with the same imputation code."""
    return IncomingInvoiceService.bulk_classify(
        invoice_ids=payload.invoiceids,
        imputation_code_id=payload.imputationcodeid,
        user=request.user,
        notes=payload.notes,
    )


# ── Reject ──

@inbox_router.post("/inbox/{incoming_id}/reject/", response=IncomingInvoiceSchema)
@require_permission(Permission.INBOX_CLASSIFY)
def reject_invoice(
    request: HttpRequest,
    incoming_id: UUID,
    payload: RejectInvoiceDto,
):
    """Reject an incoming invoice."""
    return IncomingInvoiceService.reject_invoice(
        incoming_id=incoming_id,
        notes=payload.notes,
        user=request.user,
    )


# ── Link to Expense ──

@inbox_router.post("/inbox/{incoming_id}/link/", response=IncomingInvoiceSchema)
@require_permission(Permission.INBOX_LINK)
def link_to_expense(
    request: HttpRequest,
    incoming_id: UUID,
    payload: LinkToExpenseDto,
):
    """Link incoming invoice to an existing or new ProjectExpense."""
    logger.info("link_to_expense payload: periodid=%s, expenseid=%s, body=%s",
                payload.periodid, payload.expenseid, request.body)
    return IncomingInvoiceService.link_to_expense(
        incoming_id=incoming_id,
        period_id=payload.periodid,
        user=request.user,
        expense_id=payload.expenseid,
    )


@inbox_router.post("/inbox/{incoming_id}/unlink/", response=IncomingInvoiceSchema)
@require_permission(Permission.INBOX_LINK)
def unlink_invoice(request: HttpRequest, incoming_id: UUID):
    """Unlink from expense, revert to Classified state."""
    return IncomingInvoiceService.unlink_invoice(incoming_id, request.user)


# ── Matching ──

@inbox_router.get("/inbox/{incoming_id}/matches/", response=List[MatchSuggestionSchema])
@require_permission(Permission.INBOX_READ)
def get_match_suggestions(request: HttpRequest, incoming_id: UUID):
    """Get potential expense matches for an incoming invoice."""
    incoming = IncomingInvoiceService.get_by_id(incoming_id, request.user)
    return InboxMatchingService.find_matches(incoming)


# ── File Downloads ──

@inbox_router.get("/inbox/{incoming_id}/xml/")
@require_permission(Permission.INBOX_READ)
def download_xml(request: HttpRequest, incoming_id: UUID):
    """Download the XML file of an incoming invoice."""
    incoming = IncomingInvoiceService.get_by_id(incoming_id, request.user)
    if not incoming.xmlfile:
        raise NotFound('No XML file stored for this invoice')
    return FileResponse(
        incoming.xmlfile.open('rb'),
        content_type='text/xml',
        as_attachment=True,
        filename=incoming.xmlfilename or 'factura.xml',
    )


@inbox_router.get("/inbox/{incoming_id}/pdf/")
@require_permission(Permission.INBOX_READ)
def download_pdf(request: HttpRequest, incoming_id: UUID):
    """Download the PDF file of an incoming invoice."""
    incoming = IncomingInvoiceService.get_by_id(incoming_id, request.user)
    if not incoming.pdffile:
        raise NotFound('No PDF file stored for this invoice')
    return FileResponse(
        incoming.pdffile.open('rb'),
        content_type='application/pdf',
        as_attachment=True,
        filename=incoming.pdffilename or 'factura.pdf',
    )


# ── Captured Emails (for Bandeja cross-reference) ──

@inbox_router.get("/projects/{project_id}/inbox/captured-emails/", response=CapturedEmailsResponse)
@require_permission(Permission.INBOX_READ)
def get_captured_emails(request: HttpRequest, project_id: UUID):
    """Returns map of Graph message IDs → IncomingInvoice IDs for cross-referencing with Bandeja."""
    _get_project(project_id)
    captured = IncomingInvoice.objects.filter(
        projectid=project_id,
        graphmessageid__isnull=False,
    ).exclude(graphmessageid='').values_list('graphmessageid', 'incominginvoiceid')

    return {'captured': {gid: str(iid) for gid, iid in captured}}


# ── Sync (project-scoped) ──

@inbox_router.post("/projects/{project_id}/inbox/sync/", response=SyncResultSchema)
@require_permission(Permission.INBOX_SYNC)
def trigger_project_sync(request: HttpRequest, project_id: UUID):
    """Trigger manual inbox sync for a specific project's shared mailbox."""
    project = _get_project(project_id)
    sync_log = GraphInboxService.sync_inbox(
        project=project,
        user=request.user,
        triggered_by=SyncTriggerCode.MANUAL,
    )
    return SyncResultSchema(
        success=sync_log.syncstatus != 2,  # Not FAILED
        totalemailsfetched=sync_log.totalemailsfetched,
        newxmlattachments=sync_log.newxmlattachments,
        newpdfattachments=sync_log.newpdfattachments,
        duplicatesskipped=sync_log.duplicatesskipped,
        errorscount=sync_log.errorscount,
        errors=sync_log.errorsdetail or [],
    )


# ── Summary & Logs (project-scoped) ──

@inbox_router.get("/projects/{project_id}/inbox/summary/", response=InboxSummarySchema)
@require_permission(Permission.INBOX_READ)
def get_project_inbox_summary(request: HttpRequest, project_id: UUID):
    """Get inbox summary counts for a specific project."""
    _get_project(project_id)
    return IncomingInvoiceService.get_inbox_summary(project_id=project_id)


@inbox_router.get("/inbox/summary/", response=InboxSummarySchema)
@require_permission(Permission.INBOX_READ)
def get_inbox_summary(request: HttpRequest):
    """Get global inbox summary counts across all projects."""
    return IncomingInvoiceService.get_inbox_summary()


@inbox_router.get("/projects/{project_id}/inbox/sync-logs/", response=List[InboxSyncLogSchema])
@require_permission(Permission.INBOX_READ)
def list_project_sync_logs(request: HttpRequest, project_id: UUID):
    """List sync history for a specific project."""
    _get_project(project_id)
    return list(InboxSyncLogService.list_logs(project_id=project_id)[:50])


@inbox_router.get("/inbox/sync-logs/", response=List[InboxSyncLogSchema])
@require_permission(Permission.INBOX_READ)
def list_sync_logs(request: HttpRequest):
    """List all sync history."""
    return list(InboxSyncLogService.list_logs()[:50])
