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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),  # All API endpoints under /api/
]

# Customize Django admin site
admin.site.site_header = "CRM Backend Administration"
admin.site.site_title = "CRM Backend Admin"
admin.site.index_title = "Welcome to CRM Backend Administration"
