"""
URL configuration for CRM Backend Foundation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
import logging
import traceback

from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from ninja import NinjaAPI
from core.exceptions import (
    CRMBaseException,
    PermissionDenied,
    ValidationError,
    NotFound,
    AuthenticationFailed,
    AccountLocked,
    AccountDisabled,
)

logger = logging.getLogger(__name__)

# Initialize Django Ninja API with OpenAPI documentation
api = NinjaAPI(
    title="CRM Backend API",
    version="1.0.0",
    description="Microsoft Dynamics 365 CDS-compatible CRM backend with type-safe REST APIs",
    docs_url="/docs",  # Swagger UI documentation
)


# ============================================================================
# Global Exception Handlers
# ============================================================================

def _build_error_response(request, code: str, status: int, message: str, details: dict = None):
    """Build a standardized error response matching frontend expectations.

    Frontend expects: {success: false, error: {code, message, details}}
    """
    body = {
        "success": False,
        "error": {
            "code": code.upper(),
            "message": message,
        },
    }
    if details:
        body["error"]["details"] = details
    return JsonResponse(body, status=status)


@api.exception_handler(PermissionDenied)
def permission_denied_handler(request, exc):
    """Handle permission denied exceptions."""
    logger.warning("Permission denied: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "permission_denied", 403, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(AuthenticationFailed)
def authentication_failed_handler(request, exc):
    """Handle authentication failure."""
    logger.warning("Authentication failed: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "authentication_failed", 401, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(AccountLocked)
def account_locked_handler(request, exc):
    """Handle locked account."""
    logger.warning("Account locked: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "account_locked", 401, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(AccountDisabled)
def account_disabled_handler(request, exc):
    """Handle disabled account."""
    logger.warning("Account disabled: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "account_disabled", 401, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(ValidationError)
def validation_error_handler(request, exc):
    """Handle validation errors."""
    logger.info("Validation error: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "validation_error", 400, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(NotFound)
def not_found_handler(request, exc):
    """Handle not found errors."""
    logger.info("Not found: %s [path=%s]", exc, request.path)
    return _build_error_response(
        request, "not_found", 404, str(exc), getattr(exc, 'details', None)
    )


@api.exception_handler(Exception)
def generic_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.exception("Unhandled exception at %s: %s", request.path, exc)
    body = {
        "success": False,
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    }
    if settings.DEBUG:
        body["error"]["debug_message"] = str(exc)
        body["error"]["traceback"] = traceback.format_exc()
    return JsonResponse(body, status=500)

# ============================================================================
# Register API Routers
# ============================================================================

from apps.users.routers import auth_router, users_router, roles_router
from apps.leads.routers import leads_router
from apps.opportunities.routers import opportunities_router
from apps.accounts.routers import accounts_router
from apps.contacts.routers import contacts_router
from apps.quotes.routers import quotes_router
from apps.quotes.template_routers import quote_templates_router
from apps.orders.routers import orders_router
from apps.invoices.routers import invoices_router
from apps.products.routers import products_router, pricelists_router
from apps.activities.routers import activities_router
from apps.cases.routers import cases_router
from apps.notifications.routers import notifications_router
from apps.graph.routers import graph_router
from apps.projects.routers import projects_router, zones_router, suppliers_router, team_members_router
from apps.budgets.routers import categories_router, imputation_codes_router, periods_router, budget_lines_router
from apps.expenses.routers import expenses_router, expense_lines_router, attachments_router, estimates_router
from apps.invoiceinbox.routers import inbox_router
from apps.audit.routers import audit_router
from apps.proyeccion.routers import (
    estimation_projects_router,
    concept_families_router,
    budget_concepts_router,
    indirect_cost_details_router,
    offer_alternatives_router,
    external_costs_router,
    supply_explosion_router,
    workplan_router,
    analysis_router,
    supply_catalog_router,
    equipment_yields_router,
    indirect_cost_templates_router,
    concept_price_catalog_router,
    family_templates_router,
)
from apps.corporate.routers import budgets_router as corporate_budgets_router, expenses_router as corporate_expenses_router
from apps.corporate.allocation_routers import allocations_router as corporate_allocations_router, portfolio_router as corporate_portfolio_router, simulations_router as corporate_simulations_router
from apps.hrpayroll.routers import (
    employees_router, assignments_router,
    deduction_types_router, addition_types_router,
    payroll_periods_router, payroll_runs_router, payroll_entries_router,
    attendance_router,
)
from apps.machinery.routers import (
    categories_router as machinery_categories_router,
    brands_router as machinery_brands_router,
    models_router as machinery_models_router,
    equipment_router as machinery_equipment_router,
    insurance_router as machinery_insurance_router,
    reasons_router as machinery_reasons_router,
    contracts_router as machinery_contracts_router,
    daily_logs_router as machinery_daily_logs_router,
    estimations_router as machinery_estimations_router,
)
from apps.agents.routers import agents_config_router, agents_run_router, agents_suggestion_router

api.add_router("/auth", auth_router)
api.add_router("/users", users_router)
api.add_router("/roles", roles_router)
api.add_router("/leads", leads_router)
api.add_router("/opportunities", opportunities_router)
api.add_router("/accounts", accounts_router)
api.add_router("/contacts", contacts_router)
api.add_router("/quotes", quotes_router)
api.add_router("/quote-templates", quote_templates_router)
api.add_router("/orders", orders_router)
api.add_router("/invoices", invoices_router)
api.add_router("/products", products_router)
api.add_router("/pricelists", pricelists_router)
api.add_router("/activities", activities_router)
api.add_router("/cases", cases_router)
api.add_router("/notifications", notifications_router)
api.add_router("/graph", graph_router)
api.add_router("/audit-logs", audit_router)

# Operations module routers
api.add_router("/projects", projects_router)
api.add_router("/zones", zones_router)
api.add_router("/suppliers", suppliers_router)
api.add_router("/team-members", team_members_router)
api.add_router("/categories", categories_router)
api.add_router("/codes", imputation_codes_router)
api.add_router("/periods", periods_router)
api.add_router("/budget-lines", budget_lines_router)
api.add_router("/expenses", expenses_router)
api.add_router("/expense-lines", expense_lines_router)
api.add_router("/attachments", attachments_router)
api.add_router("/estimates", estimates_router)
api.add_router("/invoice-inbox", inbox_router)

# Proyección module routers
api.add_router("/estimation-projects", estimation_projects_router)
api.add_router("/proyeccion", concept_families_router)
api.add_router("/proyeccion", budget_concepts_router)
api.add_router("/proyeccion", indirect_cost_details_router)
api.add_router("/proyeccion", offer_alternatives_router)
api.add_router("/proyeccion", external_costs_router)
api.add_router("/proyeccion", supply_explosion_router)
api.add_router("/proyeccion", workplan_router)
api.add_router("/proyeccion", analysis_router)
api.add_router("/proyeccion", supply_catalog_router)
api.add_router("/proyeccion", equipment_yields_router)
api.add_router("/proyeccion", indirect_cost_templates_router)
api.add_router("/proyeccion", concept_price_catalog_router)
api.add_router("/proyeccion", family_templates_router)

# Corporate module routers
api.add_router("/corporate", corporate_budgets_router)
api.add_router("/corporate", corporate_expenses_router)
api.add_router("/corporate", corporate_allocations_router)
api.add_router("/corporate", corporate_portfolio_router)
api.add_router("/corporate", corporate_simulations_router)

# Machinery module routers
api.add_router("/machinery", machinery_categories_router)
api.add_router("/machinery", machinery_brands_router)
api.add_router("/machinery", machinery_models_router)
api.add_router("/machinery", machinery_equipment_router)
api.add_router("/machinery", machinery_insurance_router)
api.add_router("/machinery", machinery_reasons_router)
api.add_router("/machinery", machinery_contracts_router)
api.add_router("/machinery", machinery_daily_logs_router)
api.add_router("/machinery", machinery_estimations_router)

# HR/Payroll module routers
api.add_router("/employees", employees_router)
api.add_router("/employee-assignments", assignments_router)
api.add_router("/deduction-types", deduction_types_router)
api.add_router("/addition-types", addition_types_router)
api.add_router("/payroll-periods", payroll_periods_router)
api.add_router("/payroll-runs", payroll_runs_router)
api.add_router("/payroll-entries", payroll_entries_router)
api.add_router("/attendance", attendance_router)

# Agent module routers
api.add_router("/agents/config", agents_config_router)
api.add_router("/agents", agents_run_router)
api.add_router("/agents/suggestions", agents_suggestion_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),  # All API endpoints under /api/
]

# Serve media files in development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Customize Django admin site
admin.site.site_header = "CRM Backend Administration"
admin.site.site_title = "CRM Backend Admin"
admin.site.index_title = "Welcome to CRM Backend Administration"
