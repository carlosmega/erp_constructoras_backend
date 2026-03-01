"""API routers for Expense Management."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from apps.expenses.schemas import (
    ProjectExpenseSchema,
    CreateProjectExpenseDto,
    UpdateProjectExpenseDto,
    ExpenseLineSchema,
    CreateExpenseLineDto,
    UpdateExpenseLineDto,
    ExpenseAttachmentSchema,
    CreateExpenseAttachmentDto,
    ClassificationLogSchema,
    ClassifyExpenseDto,
    BulkClassifyDto,
    VerifyExpenseDto,
    ExpenseSummarySchema,
    ClientEstimateSchema,
    CreateClientEstimateDto,
    UpdateClientEstimateDto,
)
from apps.expenses.services import (
    ExpenseService,
    ClassificationService,
    VerificationService,
    ExpenseLineService,
    AttachmentService,
    ProvisionService,
    EstimateService,
)


# =============================================================================
# Expense Router
# =============================================================================

expenses_router = Router(tags=["Expenses"])


@expenses_router.get(
    "/projects/{project_id}/expenses/",
    response=List[ProjectExpenseSchema],
)
def list_expenses(
    request: HttpRequest,
    project_id: UUID,
    period_id: Optional[UUID] = None,
    documenttype: Optional[int] = None,
    classificationstatus: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List expenses for a project with optional filtering."""
    # TODO: add @require_permission decorator
    expenses = ExpenseService.list_expenses(
        project_id=project_id,
        user=request.user,
        period_id=period_id,
        documenttype=documenttype,
        classificationstatus=classificationstatus,
        statecode=statecode,
    )
    return list(expenses)


@expenses_router.post(
    "/projects/{project_id}/expenses/",
    response={201: ProjectExpenseSchema},
)
def create_expense(request: HttpRequest, project_id: UUID, payload: CreateProjectExpenseDto):
    """Create a new project expense."""
    # TODO: add @require_permission decorator
    payload.projectid = project_id
    expense = ExpenseService.create_expense(payload, request.user)
    return 201, expense


@expenses_router.get(
    "/expenses/{expense_id}/",
    response=ProjectExpenseSchema,
)
def get_expense(request: HttpRequest, expense_id: UUID):
    """Get expense by ID."""
    # TODO: add @require_permission decorator
    return ExpenseService.get_expense_by_id(expense_id, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/",
    response=ProjectExpenseSchema,
)
def update_expense(request: HttpRequest, expense_id: UUID, payload: UpdateProjectExpenseDto):
    """Update an existing project expense."""
    # TODO: add @require_permission decorator
    return ExpenseService.update_expense(expense_id, payload, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/cancel/",
    response=ProjectExpenseSchema,
)
def cancel_expense(request: HttpRequest, expense_id: UUID):
    """Cancel a project expense."""
    # TODO: add @require_permission decorator
    return ExpenseService.cancel_expense(expense_id, request.user)


@expenses_router.post(
    "/expenses/{expense_id}/classify/",
    response=ProjectExpenseSchema,
)
def classify_expense(request: HttpRequest, expense_id: UUID, payload: ClassifyExpenseDto):
    """Classify an expense with an imputation code."""
    # TODO: add @require_permission decorator
    return ClassificationService.classify_expense(
        expense_id, payload.imputationcodeid, payload.notes, request.user
    )


@expenses_router.post(
    "/expenses/bulk-classify/",
    response=List[ProjectExpenseSchema],
)
def bulk_classify(request: HttpRequest, payload: BulkClassifyDto):
    """Classify multiple expenses with the same imputation code."""
    # TODO: add @require_permission decorator
    return ClassificationService.bulk_classify(
        payload.expenseids, payload.imputationcodeid, payload.notes, request.user
    )


@expenses_router.post(
    "/expenses/{expense_id}/unclassify/",
    response=ProjectExpenseSchema,
)
def unclassify_expense(request: HttpRequest, expense_id: UUID):
    """Remove classification from an expense."""
    # TODO: add @require_permission decorator
    return ClassificationService.unclassify_expense(expense_id, None, request.user)


@expenses_router.patch(
    "/expenses/{expense_id}/verify/",
    response=ProjectExpenseSchema,
)
def verify_expense(request: HttpRequest, expense_id: UUID, payload: VerifyExpenseDto):
    """Update verification status on an expense."""
    # TODO: add @require_permission decorator
    return VerificationService.update_verification(
        expense_id, payload.verificationstatus, payload.verificationnotes, request.user
    )


@expenses_router.post(
    "/expenses/{expense_id}/convert-provision/",
    response={201: ProjectExpenseSchema},
)
def convert_provision(request: HttpRequest, expense_id: UUID, payload: CreateProjectExpenseDto):
    """Convert a provision to a real expense."""
    # TODO: add @require_permission decorator
    new_expense = ProvisionService.convert_provision(expense_id, payload, request.user)
    return 201, new_expense


@expenses_router.get(
    "/projects/{project_id}/expenses/unclassified/",
    response=List[ProjectExpenseSchema],
)
def list_unclassified_expenses(request: HttpRequest, project_id: UUID):
    """Get unclassified expenses for a project."""
    # TODO: add @require_permission decorator
    expenses = ExpenseService.get_unclassified_expenses(project_id, request.user)
    return list(expenses)


@expenses_router.get(
    "/projects/{project_id}/expenses/summary/",
    response=ExpenseSummarySchema,
)
def get_expense_summary(request: HttpRequest, project_id: UUID):
    """Get aggregate expense summary for a project."""
    # TODO: add @require_permission decorator
    return ExpenseService.get_expense_summary(project_id, request.user)


# =============================================================================
# Expense Lines Router
# =============================================================================

expense_lines_router = Router(tags=["Expense Lines"])


@expense_lines_router.get(
    "/expenses/{expense_id}/lines/",
    response=List[ExpenseLineSchema],
)
def list_lines(request: HttpRequest, expense_id: UUID):
    """List all lines for an expense."""
    # TODO: add @require_permission decorator
    return list(ExpenseLineService.list_lines(expense_id))


@expense_lines_router.post(
    "/expenses/{expense_id}/lines/",
    response={201: ExpenseLineSchema},
)
def add_line(request: HttpRequest, expense_id: UUID, payload: CreateExpenseLineDto):
    """Add a line to an expense."""
    # TODO: add @require_permission decorator
    line = ExpenseLineService.add_line(expense_id, payload, request.user)
    return 201, line


@expense_lines_router.patch(
    "/expense-lines/{line_id}/",
    response=ExpenseLineSchema,
)
def update_line(request: HttpRequest, line_id: UUID, payload: UpdateExpenseLineDto):
    """Update an expense line."""
    # TODO: add @require_permission decorator
    return ExpenseLineService.update_line(line_id, payload, request.user)


@expense_lines_router.delete(
    "/expense-lines/{line_id}/",
    response={204: None},
)
def delete_line(request: HttpRequest, line_id: UUID):
    """Delete an expense line."""
    # TODO: add @require_permission decorator
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
def list_attachments(request: HttpRequest, expense_id: UUID):
    """List all attachments for an expense."""
    # TODO: add @require_permission decorator
    return list(AttachmentService.list_attachments(expense_id))


@attachments_router.post(
    "/expenses/{expense_id}/attachments/",
    response={201: ExpenseAttachmentSchema},
)
def add_attachment(request: HttpRequest, expense_id: UUID, payload: CreateExpenseAttachmentDto):
    """Add an attachment to an expense."""
    # TODO: add @require_permission decorator
    payload.expenseid = expense_id
    attachment = AttachmentService.add_attachment(payload, request.user)
    return 201, attachment


@attachments_router.delete(
    "/attachments/{attachment_id}/",
    response={204: None},
)
def delete_attachment(request: HttpRequest, attachment_id: UUID):
    """Delete an attachment."""
    # TODO: add @require_permission decorator
    AttachmentService.remove_attachment(attachment_id, request.user)
    return 204, None


# =============================================================================
# Classification Logs (on expenses_router)
# =============================================================================

@expenses_router.get(
    "/expenses/{expense_id}/logs/",
    response=List[ClassificationLogSchema],
)
def list_classification_logs(request: HttpRequest, expense_id: UUID):
    """Get classification logs for an expense."""
    # TODO: add @require_permission decorator
    return list(ClassificationService.get_classification_logs(expense_id))


# =============================================================================
# Estimates Router
# =============================================================================

estimates_router = Router(tags=["Client Estimates"])


@estimates_router.get(
    "/projects/{project_id}/estimates/",
    response=List[ClientEstimateSchema],
)
def list_estimates(request: HttpRequest, project_id: UUID):
    """List all estimates for a project."""
    # TODO: add @require_permission decorator
    return list(EstimateService.list_estimates(project_id, request.user))


@estimates_router.post(
    "/projects/{project_id}/estimates/",
    response={201: ClientEstimateSchema},
)
def create_estimate(request: HttpRequest, project_id: UUID, payload: CreateClientEstimateDto):
    """Create a new client estimate."""
    # TODO: add @require_permission decorator
    payload.projectid = project_id
    estimate = EstimateService.create_estimate(payload, request.user)
    return 201, estimate


@estimates_router.patch(
    "/estimates/{estimate_id}/",
    response=ClientEstimateSchema,
)
def update_estimate(request: HttpRequest, estimate_id: UUID, payload: UpdateClientEstimateDto):
    """Update a client estimate."""
    # TODO: add @require_permission decorator
    return EstimateService.update_estimate(estimate_id, payload, request.user)


@estimates_router.delete(
    "/estimates/{estimate_id}/",
    response={204: None},
)
def delete_estimate(request: HttpRequest, estimate_id: UUID):
    """Cancel a client estimate."""
    # TODO: add @require_permission decorator
    EstimateService.delete_estimate(estimate_id, request.user)
    return 204, None
