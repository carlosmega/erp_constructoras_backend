"""Corporate module API routers."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from core.permissions import require_permission, Permission

from apps.corporate.schemas import (
    CorporateBudgetSchema,
    CorporateBudgetListSchema,
    CorporateBudgetVersionSchema,
    CorporateBudgetLineSchema,
    CreateCorporateBudgetDto,
    UpdateCorporateBudgetDto,
    CreateBudgetVersionDto,
    UpdateBudgetLineDto,
    BulkUpdateBudgetLinesDto,
    CorporateExpenseSchema,
    RecordExpenseDto,
    BulkRecordExpenseDto,
    BudgetVsActualSummarySchema,
)
from apps.expenses.schemas import (
    ProjectExpenseSchema,
    CreateProjectExpenseDto,
)
from apps.expenses.models import ExpenseScopeCode
from apps.corporate.services import (
    CorporateBudgetService,
    CorporateExpenseService,
)
from apps.expenses.services import ExpenseService


# =============================================================================
# Budget Router
# =============================================================================

budgets_router = Router(tags=["Corporate Budgets"])


@budgets_router.get("/budgets/", response=List[CorporateBudgetListSchema])
@require_permission(Permission.CORPORATE_READ)
def list_budgets(
    request: HttpRequest,
    fiscal_year: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List corporate budgets with optional filtering."""
    budgets = CorporateBudgetService.list_budgets(
        user=request.user,
        fiscal_year=fiscal_year,
        statecode=statecode,
    )
    return list(budgets)


@budgets_router.post("/budgets/", response={201: CorporateBudgetSchema})
@require_permission(Permission.CORPORATE_CREATE)
def create_budget(request: HttpRequest, payload: CreateCorporateBudgetDto):
    """Create a new corporate budget with initial version and 9 category lines."""
    budget = CorporateBudgetService.create_budget(payload, request.user)
    return 201, CorporateBudgetService.get_budget(budget.corporatebudgetid, request.user)


@budgets_router.get("/budgets/{budget_id}/", response=CorporateBudgetSchema)
@require_permission(Permission.CORPORATE_READ)
def get_budget(request: HttpRequest, budget_id: UUID):
    """Get corporate budget with active version and lines."""
    return CorporateBudgetService.get_budget(budget_id, request.user)


@budgets_router.patch("/budgets/{budget_id}/", response=CorporateBudgetSchema)
@require_permission(Permission.CORPORATE_UPDATE)
def update_budget(request: HttpRequest, budget_id: UUID, payload: UpdateCorporateBudgetDto):
    """Update corporate budget name/description."""
    CorporateBudgetService.update_budget(budget_id, payload, request.user)
    return CorporateBudgetService.get_budget(budget_id, request.user)


@budgets_router.post("/budgets/{budget_id}/approve/", response=CorporateBudgetSchema)
@require_permission(Permission.CORPORATE_UPDATE)
def approve_budget(request: HttpRequest, budget_id: UUID):
    """Approve budget - computes totals. Actual tracking uses ProjectExpense."""
    CorporateBudgetService.approve_budget(budget_id, request.user)
    return CorporateBudgetService.get_budget(budget_id, request.user)


@budgets_router.post("/budgets/{budget_id}/versions/", response={201: CorporateBudgetVersionSchema})
@require_permission(Permission.CORPORATE_UPDATE)
def create_version(request: HttpRequest, budget_id: UUID, payload: CreateBudgetVersionDto):
    """Create a new version (copies lines from active version, supersedes it)."""
    version = CorporateBudgetService.create_new_version(budget_id, payload, request.user)
    return 201, version


@budgets_router.get("/budgets/{budget_id}/versions/", response=List[CorporateBudgetVersionSchema])
@require_permission(Permission.CORPORATE_READ)
def list_versions(request: HttpRequest, budget_id: UUID):
    """List all versions of a budget."""
    budget = CorporateBudgetService.get_budget(budget_id, request.user)
    return list(budget.versions.all())


@budgets_router.get("/budgets/{budget_id}/lines/", response=List[CorporateBudgetLineSchema])
@require_permission(Permission.CORPORATE_READ)
def get_budget_lines(request: HttpRequest, budget_id: UUID):
    """Get budget lines for the active version."""
    return CorporateBudgetService.get_budget_lines(budget_id, request.user)


@budgets_router.patch("/budget-lines/{line_id}/", response=CorporateBudgetLineSchema)
@require_permission(Permission.CORPORATE_UPDATE)
def update_budget_line(request: HttpRequest, line_id: UUID, payload: UpdateBudgetLineDto):
    """Update a single budget line (month amounts)."""
    return CorporateBudgetService.update_budget_line(line_id, payload, request.user)


@budgets_router.post("/budgets/{budget_id}/lines/bulk/", response=List[CorporateBudgetLineSchema])
@require_permission(Permission.CORPORATE_UPDATE)
def bulk_update_lines(request: HttpRequest, budget_id: UUID, payload: BulkUpdateBudgetLinesDto):
    """Bulk update budget lines."""
    return CorporateBudgetService.bulk_update_lines(budget_id, payload, request.user)


# =============================================================================
# Expense Router
# =============================================================================

expenses_router = Router(tags=["Corporate Expenses"])


@expenses_router.get("/budgets/{budget_id}/expenses/", response=List[CorporateExpenseSchema])
@require_permission(Permission.CORPORATE_READ)
def list_expenses(
    request: HttpRequest,
    budget_id: UUID,
    year: Optional[int] = None,
    month: Optional[int] = None,
):
    """List corporate expenses for a budget."""
    return list(CorporateExpenseService.list_expenses(budget_id, request.user, year, month))


@expenses_router.post("/budgets/{budget_id}/expenses/", response={201: CorporateExpenseSchema})
@require_permission(Permission.CORPORATE_CREATE)
def record_expense(request: HttpRequest, budget_id: UUID, payload: RecordExpenseDto):
    """Record or update an actual expense amount."""
    expense = CorporateExpenseService.record_expense(budget_id, payload, request.user)
    return 201, expense


@expenses_router.post("/budgets/{budget_id}/expenses/bulk/", response={201: List[CorporateExpenseSchema]})
@require_permission(Permission.CORPORATE_CREATE)
def bulk_record_expenses(request: HttpRequest, budget_id: UUID, payload: BulkRecordExpenseDto):
    """Bulk record expenses for a month."""
    expenses = CorporateExpenseService.bulk_record_expenses(budget_id, payload, request.user)
    return 201, expenses


@expenses_router.post("/budgets/{budget_id}/expenses/detail/", response={201: ProjectExpenseSchema})
@require_permission(Permission.CORPORATE_CREATE)
def create_detailed_corporate_expense(
    request: HttpRequest,
    budget_id: UUID,
    payload: CreateProjectExpenseDto,
):
    """Create a corporate expense with full detail (supplier, invoice, lines)."""
    # Force corporate scope and budget from URL
    payload.expensescope = ExpenseScopeCode.CORPORATE
    payload.corporatebudgetid = budget_id
    expense = ExpenseService.create_expense(payload, request.user)
    return 201, expense


@expenses_router.get("/budgets/{budget_id}/budget-vs-actual/", response=BudgetVsActualSummarySchema)
@require_permission(Permission.CORPORATE_READ)
def get_budget_vs_actual(
    request: HttpRequest,
    budget_id: UUID,
    year: Optional[int] = None,
):
    """Get budget vs actual semaphore dashboard for a fiscal year."""
    budget = CorporateBudgetService.get_budget(budget_id, request.user)
    actual_year = year or budget.fiscalyear
    return CorporateExpenseService.get_budget_vs_actual(budget_id, actual_year, request.user)
