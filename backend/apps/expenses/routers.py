"""API routers for Expense Management."""

from ninja import Router, File, Form
from ninja.files import UploadedFile
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest, FileResponse

from apps.expenses.schemas import (
    ProjectExpenseSchema,
    CreateProjectExpenseDto,
    UpdateProjectExpenseDto,
    ExpenseLineSchema,
    CreateExpenseLineDto,
    UpdateExpenseLineDto,
    ExpenseAttachmentSchema,
    ClassificationLogSchema,
    ClassifyExpenseDto,
    BulkClassifyDto,
    VerifyExpenseDto,
    ExpenseSummarySchema,
    ClientEstimateSchema,
    CreateClientEstimateDto,
    UpdateClientEstimateDto,
)
from apps.expenses.models import ProjectExpense, ExpenseStateCode
from apps.expenses.services import (
    ExpenseService,
    ClassificationService,
    VerificationService,
    ExpenseLineService,
    AttachmentService,
    ProvisionService,
    EstimateService,
)
from core.pagination import paginate_queryset, create_paginated_response
from core.permissions import require_permission, Permission


# =============================================================================
# Expense Router
# =============================================================================

expenses_router = Router(tags=["Expenses"])

PaginatedProjectExpenseList = create_paginated_response(ProjectExpenseSchema)


@expenses_router.get(
    "/projects/{project_id}/expenses/",
    response=List[ProjectExpenseSchema],
)
@require_permission(Permission.EXPENSE_READ)
def list_expenses(
    request: HttpRequest,
    project_id: UUID,
    period_id: Optional[UUID] = None,
    documenttype: Optional[int] = None,
    classificationstatus: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List expenses for a project with optional filtering (non-paginated)."""
    expenses = ExpenseService.list_expenses(
        project_id=project_id,
        user=request.user,
        period_id=period_id,
        documenttype=documenttype,
        classificationstatus=classificationstatus,
        statecode=statecode,
    )
    return list(expenses)


@expenses_router.get(
    "/projects/{project_id}/expenses/paginated/",
    response=PaginatedProjectExpenseList,
)
@require_permission(Permission.EXPENSE_READ)
def list_expenses_paginated(
    request: HttpRequest,
    project_id: UUID,
    page: int = 1,
    page_size: int = 50,
    period_id: Optional[UUID] = None,
    documenttype: Optional[int] = None,
    classificationstatus: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List expenses with offset-based pagination.

    Opt-in alternative to the legacy list endpoint; same filters apply.
    """
    queryset = ExpenseService.list_expenses(
        project_id=project_id,
        user=request.user,
        period_id=period_id,
        documenttype=documenttype,
        classificationstatus=classificationstatus,
        statecode=statecode,
    )
    return paginate_queryset(queryset, page=page, page_size=page_size, request_url=request.path)


@expenses_router.post(
    "/projects/{project_id}/expenses/",
    response={201: ProjectExpenseSchema},
)
@require_permission(Permission.EXPENSE_CREATE)
def create_expense(request: HttpRequest, project_id: UUID, payload: CreateProjectExpenseDto):
    """Create a new project expense."""
    payload.projectid = project_id
    expense = ExpenseService.create_expense(payload, request.user)
    return 201, expense


@expenses_router.get(
    "/expenses/check-uuid/",
    response={200: dict},
)
@require_permission(Permission.EXPENSE_READ)
def check_uuid_exists(request: HttpRequest, uuid: str):
    """Check if an invoice UUID already exists (across all projects).

    Invoice UUIDs are issued by SAT (fiscal authority) and must be globally
    unique across all projects, so this endpoint intentionally scans without
    project/ownership scoping. Access still requires EXPENSE_READ.
    """
    exists = ProjectExpense.objects.filter(
        invoiceuuid=uuid,
        statecode=ExpenseStateCode.ACTIVE,
    ).exists()
    return 200, {"exists": exists}


@expenses_router.get(
    "/expenses/{expense_id}/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_READ)
def get_expense(request: HttpRequest, expense_id: UUID):
    """Get expense by ID."""
    return ExpenseService.get_expense_by_id(expense_id, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_UPDATE)
def update_expense(request: HttpRequest, expense_id: UUID, payload: UpdateProjectExpenseDto):
    """Update an existing project expense."""
    return ExpenseService.update_expense(expense_id, payload, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/cancel/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_DELETE)
def cancel_expense(request: HttpRequest, expense_id: UUID):
    """Cancel a project expense."""
    return ExpenseService.cancel_expense(expense_id, request.user)


@expenses_router.post(
    "/expenses/{expense_id}/classify/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_CLASSIFY)
def classify_expense(request: HttpRequest, expense_id: UUID, payload: ClassifyExpenseDto):
    """Classify an expense with an imputation code."""
    return ClassificationService.classify_expense(
        expense_id, payload.imputationcodeid, payload.notes, request.user
    )


@expenses_router.post(
    "/expenses/bulk-classify/",
    response=List[ProjectExpenseSchema],
)
@require_permission(Permission.EXPENSE_CLASSIFY)
def bulk_classify(request: HttpRequest, payload: BulkClassifyDto):
    """Classify multiple expenses with the same imputation code."""
    return ClassificationService.bulk_classify(
        payload.expenseids, payload.imputationcodeid, payload.notes, request.user
    )


@expenses_router.post(
    "/expenses/{expense_id}/unclassify/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_CLASSIFY)
def unclassify_expense(request: HttpRequest, expense_id: UUID):
    """Remove classification from an expense."""
    return ClassificationService.unclassify_expense(expense_id, None, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/verify/",
    response=ProjectExpenseSchema,
)
@require_permission(Permission.EXPENSE_VERIFY)
def verify_expense(request: HttpRequest, expense_id: UUID, payload: VerifyExpenseDto):
    """Update verification status on an expense."""
    return VerificationService.update_verification(
        expense_id, payload.verificationstatus, payload.verificationnotes, request.user
    )


@expenses_router.post(
    "/expenses/{expense_id}/convert-provision/",
    response={201: ProjectExpenseSchema},
)
@require_permission(Permission.EXPENSE_CREATE)
def convert_provision(request: HttpRequest, expense_id: UUID, payload: CreateProjectExpenseDto):
    """Convert a provision to a real expense."""
    new_expense = ProvisionService.convert_provision(expense_id, payload, request.user)
    return 201, new_expense


@expenses_router.get(
    "/projects/{project_id}/expenses/unclassified/",
    response=List[ProjectExpenseSchema],
)
@require_permission(Permission.EXPENSE_READ)
def list_unclassified_expenses(request: HttpRequest, project_id: UUID):
    """Get unclassified expenses for a project."""
    expenses = ExpenseService.get_unclassified_expenses(project_id, request.user)
    return list(expenses)


@expenses_router.get(
    "/projects/{project_id}/expenses/summary/",
    response=ExpenseSummarySchema,
)
@require_permission(Permission.EXPENSE_READ)
def get_expense_summary(request: HttpRequest, project_id: UUID):
    """Get aggregate expense summary for a project."""
    return ExpenseService.get_expense_summary(project_id, request.user)


# =============================================================================
# Expense Lines Router
# =============================================================================

expense_lines_router = Router(tags=["Expense Lines"])


@expense_lines_router.get(
    "/expenses/{expense_id}/lines/",
    response=List[ExpenseLineSchema],
)
@require_permission(Permission.EXPENSE_READ)
def list_lines(request: HttpRequest, expense_id: UUID):
    """List all lines for an expense."""
    return list(ExpenseLineService.list_lines(expense_id))


@expense_lines_router.post(
    "/expenses/{expense_id}/lines/",
    response={201: ExpenseLineSchema},
)
@require_permission(Permission.EXPENSE_UPDATE)
def add_line(request: HttpRequest, expense_id: UUID, payload: CreateExpenseLineDto):
    """Add a line to an expense."""
    line = ExpenseLineService.add_line(expense_id, payload, request.user)
    return 201, line


@expense_lines_router.patch(
    "/expense-lines/{line_id}/",
    response=ExpenseLineSchema,
)
@require_permission(Permission.EXPENSE_UPDATE)
def update_line(request: HttpRequest, line_id: UUID, payload: UpdateExpenseLineDto):
    """Update an expense line."""
    return ExpenseLineService.update_line(line_id, payload, request.user)


@expense_lines_router.delete(
    "/expense-lines/{line_id}/",
    response={204: None},
)
@require_permission(Permission.EXPENSE_DELETE)
def delete_line(request: HttpRequest, line_id: UUID):
    """Delete an expense line."""
    ExpenseLineService.remove_line(line_id, request.user)
    return 204, None


# =============================================================================
# Attachments Router
# =============================================================================

attachments_router = Router(tags=["Expense Attachments"])


@attachments_router.get(
    "/expenses/{expense_id}/attachments/",
    response=List[ExpenseAttachmentSchema],
)
@require_permission(Permission.EXPENSE_READ)
def list_attachments(request: HttpRequest, expense_id: UUID):
    """List all attachments for an expense."""
    return list(AttachmentService.list_attachments(expense_id))


@attachments_router.post(
    "/expenses/{expense_id}/attachments/",
    response={201: ExpenseAttachmentSchema},
)
@require_permission(Permission.EXPENSE_UPDATE)
def add_attachment(
    request: HttpRequest,
    expense_id: UUID,
    file: UploadedFile = File(...),
    filename: str = Form(...),
    suggestedfilename: str = Form(...),
    filetype: int = Form(...),
    filesize: int = Form(...),
    mimetype: str = Form(...),
):
    """Add an attachment to an expense (multipart file upload)."""
    attachment = AttachmentService.add_attachment(
        expense_id=expense_id,
        filename=filename,
        suggestedfilename=suggestedfilename,
        filetype=filetype,
        filesize=filesize,
        mimetype=mimetype,
        file=file,
        user=request.user,
    )
    return 201, attachment


@attachments_router.get(
    "/attachments/{attachment_id}/download/",
)
@require_permission(Permission.EXPENSE_READ)
def download_attachment(request: HttpRequest, attachment_id: UUID):
    """Download an attachment file."""
    attachment = AttachmentService.get_attachment(attachment_id)
    if not attachment.file:
        from core.exceptions import NotFound
        raise NotFound("No file stored for this attachment")
    return FileResponse(
        attachment.file.open('rb'),
        content_type=attachment.mimetype,
        as_attachment=True,
        filename=attachment.suggestedfilename or attachment.filename,
    )


@attachments_router.delete(
    "/attachments/{attachment_id}/",
    response={204: None},
)
@require_permission(Permission.EXPENSE_DELETE)
def delete_attachment(request: HttpRequest, attachment_id: UUID):
    """Delete an attachment."""
    AttachmentService.remove_attachment(attachment_id, request.user)
    return 204, None


# =============================================================================
# Classification Logs (on expenses_router)
# =============================================================================

@expenses_router.get(
    "/expenses/{expense_id}/logs/",
    response=List[ClassificationLogSchema],
)
@require_permission(Permission.EXPENSE_READ)
def list_classification_logs(request: HttpRequest, expense_id: UUID):
    """Get classification logs for an expense."""
    return list(ClassificationService.get_classification_logs(expense_id))


# =============================================================================
# Estimates Router
# =============================================================================

estimates_router = Router(tags=["Client Estimates"])


@estimates_router.get(
    "/projects/{project_id}/estimates/",
    response=List[ClientEstimateSchema],
)
@require_permission(Permission.ESTIMATE_READ)
def list_estimates(request: HttpRequest, project_id: UUID):
    """List all estimates for a project."""
    return list(EstimateService.list_estimates(project_id, request.user))


@estimates_router.get(
    "/estimates/{estimate_id}/",
    response=ClientEstimateSchema,
)
@require_permission(Permission.ESTIMATE_READ)
def get_estimate(request: HttpRequest, estimate_id: UUID):
    """Get a single client estimate by ID."""
    return EstimateService.get_estimate_by_id(estimate_id, request.user)


@estimates_router.post(
    "/projects/{project_id}/estimates/",
    response={201: ClientEstimateSchema},
)
@require_permission(Permission.ESTIMATE_CREATE)
def create_estimate(request: HttpRequest, project_id: UUID, payload: CreateClientEstimateDto):
    """Create a new client estimate."""
    payload.projectid = project_id
    estimate = EstimateService.create_estimate(payload, request.user)
    return 201, estimate


@estimates_router.patch(
    "/estimates/{estimate_id}/",
    response=ClientEstimateSchema,
)
@require_permission(Permission.ESTIMATE_UPDATE)
def update_estimate(request: HttpRequest, estimate_id: UUID, payload: UpdateClientEstimateDto):
    """Update a client estimate."""
    return EstimateService.update_estimate(estimate_id, payload, request.user)


@estimates_router.delete(
    "/estimates/{estimate_id}/",
    response={204: None},
)
@require_permission(Permission.ESTIMATE_DELETE)
def delete_estimate(request: HttpRequest, estimate_id: UUID):
    """Cancel a client estimate."""
    EstimateService.delete_estimate(estimate_id, request.user)
    return 204, None
