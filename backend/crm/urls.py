"""
URL configuration for CRM Backend Foundation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse
from ninja import NinjaAPI
from core.exceptions import PermissionDenied, ValidationError, NotFound

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

@api.exception_handler(PermissionDenied)
def permission_denied_handler(request, exc):
    """Handle permission denied exceptions with clean JSON response."""
    return JsonResponse(
        {
            "detail": str(exc),
            "code": "permission_denied",
            "status": 403
        },
        status=403
    )

@api.exception_handler(ValidationError)
def validation_error_handler(request, exc):
    """Handle validation errors with clean JSON response."""
    return JsonResponse(
        {
            "detail": str(exc),
            "code": "validation_error",
            "status": 400
        },
        status=400
    )

@api.exception_handler(NotFound)
def not_found_handler(request, exc):
    """Handle not found errors with clean JSON response."""
    return JsonResponse(
        {
            "detail": str(exc),
            "code": "not_found",
            "status": 404
        },
        status=404
    )

@api.exception_handler(Exception)
def generic_exception_handler(request, exc):
    """Handle unexpected exceptions with clean JSON response."""
    import traceback
    return JsonResponse(
        {
            "detail": "An unexpected error occurred",
            "error": str(exc),
            "code": "internal_server_error",
            "status": 500,
            # Include traceback only in DEBUG mode
            "traceback": traceback.format_exc() if __debug__ else None
        },
        status=500
    )

# ============================================================================
# Register API Routers
# ============================================================================

from apps.users.routers import auth_router, users_router, roles_router
from apps.leads.routers import leads_router
from apps.opportunities.routers import opportunities_router
from apps.accounts.routers import accounts_router
from apps.contacts.routers import contacts_router
from apps.quotes.routers import quotes_router
from apps.orders.routers import orders_router
from apps.invoices.routers import invoices_router
from apps.products.routers import products_router, pricelists_router
from apps.activities.routers import activities_router

api.add_router("/auth", auth_router)
api.add_router("/users", users_router)
api.add_router("/roles", roles_router)
api.add_router("/leads", leads_router)
api.add_router("/opportunities", opportunities_router)
api.add_router("/accounts", accounts_router)
api.add_router("/contacts", contacts_router)
api.add_router("/quotes", quotes_router)
api.add_router("/orders", orders_router)
api.add_router("/invoices", invoices_router)
api.add_router("/products", products_router)
api.add_router("/pricelists", pricelists_router)
api.add_router("/activities", activities_router)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),  # All API endpoints under /api/
]

# Customize Django admin site
admin.site.site_header = "CRM Backend Administration"
admin.site.site_title = "CRM Backend Admin"
admin.site.index_title = "Welcome to CRM Backend Administration"
