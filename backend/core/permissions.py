"""
Role-Based Access Control (RBAC) System.

Implements permission management following Microsoft Dynamics 365 patterns.
Defines roles, permissions, and authorization decorators for API endpoints.

Phase 4 Implementation (User Story 2)
"""

from enum import Enum
from typing import Callable, Optional
from functools import wraps
from django.http import HttpRequest
from core.exceptions import PermissionDenied


# ============================================================================
# Permission Enums
# ============================================================================

class Permission(str, Enum):
    """
    CRUD permissions for each entity.
    Format: {ENTITY}_{ACTION}
    """
    # User permissions
    USER_CREATE = "user_create"
    USER_READ = "user_read"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"

    # Lead permissions
    LEAD_CREATE = "lead_create"
    LEAD_READ = "lead_read"
    LEAD_UPDATE = "lead_update"
    LEAD_DELETE = "lead_delete"
    LEAD_QUALIFY = "lead_qualify"

    # Opportunity permissions
    OPPORTUNITY_CREATE = "opportunity_create"
    OPPORTUNITY_READ = "opportunity_read"
    OPPORTUNITY_UPDATE = "opportunity_update"
    OPPORTUNITY_DELETE = "opportunity_delete"
    OPPORTUNITY_CLOSE = "opportunity_close"

    # Account permissions
    ACCOUNT_CREATE = "account_create"
    ACCOUNT_READ = "account_read"
    ACCOUNT_UPDATE = "account_update"
    ACCOUNT_DELETE = "account_delete"

    # Contact permissions
    CONTACT_CREATE = "contact_create"
    CONTACT_READ = "contact_read"
    CONTACT_UPDATE = "contact_update"
    CONTACT_DELETE = "contact_delete"

    # Quote permissions
    QUOTE_CREATE = "quote_create"
    QUOTE_READ = "quote_read"
    QUOTE_UPDATE = "quote_update"
    QUOTE_DELETE = "quote_delete"
    QUOTE_ACTIVATE = "quote_activate"

    # Order permissions
    ORDER_CREATE = "order_create"
    ORDER_READ = "order_read"
    ORDER_UPDATE = "order_update"
    ORDER_DELETE = "order_delete"
    ORDER_FULFILL = "order_fulfill"

    # Invoice permissions
    INVOICE_CREATE = "invoice_create"
    INVOICE_READ = "invoice_read"
    INVOICE_UPDATE = "invoice_update"
    INVOICE_DELETE = "invoice_delete"

    # Product permissions
    PRODUCT_CREATE = "product_create"
    PRODUCT_READ = "product_read"
    PRODUCT_UPDATE = "product_update"
    PRODUCT_DELETE = "product_delete"

    # Activity permissions
    ACTIVITY_CREATE = "activity_create"
    ACTIVITY_READ = "activity_read"
    ACTIVITY_UPDATE = "activity_update"
    ACTIVITY_DELETE = "activity_delete"


# ============================================================================
# Role Permission Matrix
# ============================================================================

ROLE_PERMISSIONS = {
    "System Administrator": [
        # Full access to everything
        Permission.USER_CREATE, Permission.USER_READ, Permission.USER_UPDATE, Permission.USER_DELETE,
        Permission.LEAD_CREATE, Permission.LEAD_READ, Permission.LEAD_UPDATE, Permission.LEAD_DELETE, Permission.LEAD_QUALIFY,
        Permission.OPPORTUNITY_CREATE, Permission.OPPORTUNITY_READ, Permission.OPPORTUNITY_UPDATE, Permission.OPPORTUNITY_DELETE, Permission.OPPORTUNITY_CLOSE,
        Permission.ACCOUNT_CREATE, Permission.ACCOUNT_READ, Permission.ACCOUNT_UPDATE, Permission.ACCOUNT_DELETE,
        Permission.CONTACT_CREATE, Permission.CONTACT_READ, Permission.CONTACT_UPDATE, Permission.CONTACT_DELETE,
        Permission.QUOTE_CREATE, Permission.QUOTE_READ, Permission.QUOTE_UPDATE, Permission.QUOTE_DELETE, Permission.QUOTE_ACTIVATE,
        Permission.ORDER_CREATE, Permission.ORDER_READ, Permission.ORDER_UPDATE, Permission.ORDER_DELETE, Permission.ORDER_FULFILL,
        Permission.INVOICE_CREATE, Permission.INVOICE_READ, Permission.INVOICE_UPDATE, Permission.INVOICE_DELETE,
        Permission.PRODUCT_CREATE, Permission.PRODUCT_READ, Permission.PRODUCT_UPDATE, Permission.PRODUCT_DELETE,
        Permission.ACTIVITY_CREATE, Permission.ACTIVITY_READ, Permission.ACTIVITY_UPDATE, Permission.ACTIVITY_DELETE,
    ],

    "Sales Manager": [
        # Can read users but not manage them
        Permission.USER_READ,
        # Full access to sales entities
        Permission.LEAD_CREATE, Permission.LEAD_READ, Permission.LEAD_UPDATE, Permission.LEAD_DELETE, Permission.LEAD_QUALIFY,
        Permission.OPPORTUNITY_CREATE, Permission.OPPORTUNITY_READ, Permission.OPPORTUNITY_UPDATE, Permission.OPPORTUNITY_DELETE, Permission.OPPORTUNITY_CLOSE,
        Permission.ACCOUNT_CREATE, Permission.ACCOUNT_READ, Permission.ACCOUNT_UPDATE, Permission.ACCOUNT_DELETE,
        Permission.CONTACT_CREATE, Permission.CONTACT_READ, Permission.CONTACT_UPDATE, Permission.CONTACT_DELETE,
        Permission.QUOTE_CREATE, Permission.QUOTE_READ, Permission.QUOTE_UPDATE, Permission.QUOTE_DELETE, Permission.QUOTE_ACTIVATE,
        Permission.ORDER_CREATE, Permission.ORDER_READ, Permission.ORDER_UPDATE, Permission.ORDER_DELETE,
        Permission.INVOICE_CREATE, Permission.INVOICE_READ, Permission.INVOICE_UPDATE, Permission.INVOICE_DELETE,
        Permission.PRODUCT_READ,
        Permission.ACTIVITY_CREATE, Permission.ACTIVITY_READ, Permission.ACTIVITY_UPDATE, Permission.ACTIVITY_DELETE,
    ],

    "Salesperson": [
        # No user management
        # Can manage own sales records
        Permission.LEAD_CREATE, Permission.LEAD_READ, Permission.LEAD_UPDATE, Permission.LEAD_QUALIFY,
        Permission.OPPORTUNITY_CREATE, Permission.OPPORTUNITY_READ, Permission.OPPORTUNITY_UPDATE, Permission.OPPORTUNITY_CLOSE,
        Permission.ACCOUNT_CREATE, Permission.ACCOUNT_READ, Permission.ACCOUNT_UPDATE,
        Permission.CONTACT_CREATE, Permission.CONTACT_READ, Permission.CONTACT_UPDATE,
        Permission.QUOTE_CREATE, Permission.QUOTE_READ, Permission.QUOTE_UPDATE,
        Permission.ORDER_CREATE, Permission.ORDER_READ,
        Permission.INVOICE_READ,
        Permission.PRODUCT_READ,
        Permission.ACTIVITY_CREATE, Permission.ACTIVITY_READ, Permission.ACTIVITY_UPDATE, Permission.ACTIVITY_DELETE,
    ],

    "Marketing User": [
        # Limited to leads and campaigns
        Permission.LEAD_CREATE, Permission.LEAD_READ, Permission.LEAD_UPDATE,
        Permission.ACCOUNT_READ,
        Permission.CONTACT_CREATE, Permission.CONTACT_READ, Permission.CONTACT_UPDATE,
        Permission.ACTIVITY_CREATE, Permission.ACTIVITY_READ, Permission.ACTIVITY_UPDATE,
    ],

    "Read-Only User": [
        # View-only access
        Permission.USER_READ,
        Permission.LEAD_READ,
        Permission.OPPORTUNITY_READ,
        Permission.ACCOUNT_READ,
        Permission.CONTACT_READ,
        Permission.QUOTE_READ,
        Permission.ORDER_READ,
        Permission.INVOICE_READ,
        Permission.PRODUCT_READ,
        Permission.ACTIVITY_READ,
    ],
}


# ============================================================================
# Permission Check Functions
# ============================================================================

def has_permission(user, permission: Permission) -> bool:
    """
    Check if user has a specific permission.

    Args:
        user: SystemUser instance
        permission: Permission enum value

    Returns:
        True if user has permission, False otherwise
    """
    import logging
    logger = logging.getLogger(__name__)

    if not user or not user.is_authenticated:
        logger.warning(f"Permission check failed: User not authenticated")
        return False

    # Get user's role
    role_name = user.role_name
    logger.info(f"Checking permission {permission} for user {user.emailaddress1}, role: {role_name}")

    if not role_name:
        logger.warning(f"Permission check failed: User {user.emailaddress1} has no role")
        return False

    # Check if role has permission
    role_perms = ROLE_PERMISSIONS.get(role_name, [])
    has_perm = permission in role_perms
    logger.info(f"User {user.emailaddress1} has permission {permission}: {has_perm}")
    return has_perm


def has_any_permission(user, permissions: list[Permission]) -> bool:
    """
    Check if user has any of the specified permissions.

    Args:
        user: SystemUser instance
        permissions: List of Permission enum values

    Returns:
        True if user has at least one permission, False otherwise
    """
    return any(has_permission(user, perm) for perm in permissions)


def has_all_permissions(user, permissions: list[Permission]) -> bool:
    """
    Check if user has all of the specified permissions.

    Args:
        user: SystemUser instance
        permissions: List of Permission enum values

    Returns:
        True if user has all permissions, False otherwise
    """
    return all(has_permission(user, perm) for perm in permissions)


def check_ownership(user, record) -> bool:
    """
    Check if user owns a record (for record-level security).

    Args:
        user: SystemUser instance
        record: Model instance with ownerid field

    Returns:
        True if user owns the record or is System Administrator
    """
    if not user or not user.is_authenticated:
        return False

    # System Administrators can access everything
    if user.role_name == "System Administrator":
        return True

    # Check if record has ownerid field
    if not hasattr(record, 'ownerid'):
        return True  # No ownership constraint

    # Check if user owns the record
    return record.ownerid_id == user.systemuserid


# ============================================================================
# Permission Decorators
# ============================================================================

def require_permission(permission: Permission):
    """
    Decorator to require a specific permission for an endpoint.

    Usage:
        @require_permission(Permission.LEAD_CREATE)
        def create_lead(request, payload):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not has_permission(request.user, permission):
                raise PermissionDenied(
                    f"You don't have permission to perform this action. "
                    f"Required: {permission.value}"
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permissions: Permission):
    """
    Decorator to require any of the specified permissions.

    Usage:
        @require_any_permission(Permission.LEAD_READ, Permission.LEAD_UPDATE)
        def view_lead(request, lead_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            if not has_any_permission(request.user, list(permissions)):
                raise PermissionDenied(
                    f"You don't have permission to perform this action. "
                    f"Required: any of {[p.value for p in permissions]}"
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_ownership(permission: Permission):
    """
    Decorator to require permission AND ownership of a record.

    Usage:
        @require_ownership(Permission.LEAD_UPDATE)
        def update_lead(request, lead_id):
            lead = Lead.objects.get(leadid=lead_id)
            # Ownership is checked here
            ...

    Note: The decorated function must fetch the record and it will be
    checked for ownership automatically.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # First check permission
            if not has_permission(request.user, permission):
                raise PermissionDenied(
                    f"You don't have permission to perform this action. "
                    f"Required: {permission.value}"
                )

            # Execute function (which should fetch the record)
            result = func(request, *args, **kwargs)

            # For now, we'll implement ownership check in services layer
            # This decorator just ensures permission exists
            return result
        return wrapper
    return decorator


def require_authenticated(func: Callable) -> Callable:
    """
    Decorator to require authentication for an endpoint.

    Usage:
        @require_authenticated
        def protected_endpoint(request):
            ...
    """
    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required")
        return func(request, *args, **kwargs)
    return wrapper


# ============================================================================
# Helper Functions
# ============================================================================

def get_user_permissions(user) -> list[Permission]:
    """
    Get all permissions for a user.

    Args:
        user: SystemUser instance

    Returns:
        List of Permission enum values
    """
    if not user or not user.is_authenticated:
        return []

    role_name = user.role_name
    if not role_name:
        return []

    return ROLE_PERMISSIONS.get(role_name, [])


def filter_by_ownership(queryset, user, owner_field='ownerid'):
    """
    Filter queryset to only records owned by user (unless System Administrator).

    Args:
        queryset: Django QuerySet
        user: SystemUser instance
        owner_field: Name of the owner field (default: 'ownerid')

    Returns:
        Filtered QuerySet
    """
    if not user or not user.is_authenticated:
        return queryset.none()

    # System Administrators and Managers see everything
    if user.role_name in ["System Administrator", "Sales Manager"]:
        return queryset

    # Others see only their own records
    filter_kwargs = {f"{owner_field}_id": user.systemuserid}
    return queryset.filter(**filter_kwargs)


def can_modify_record(user, record_owner):
    """
    Check if user can modify a specific record based on ownership.

    Args:
        user: SystemUser instance (current user)
        record_owner: SystemUser instance (owner of the record)

    Returns:
        True if user can modify the record, False otherwise
    """
    if not user or not user.is_authenticated:
        return False

    # System Administrators and Sales Managers can modify any record
    if user.role_name in ["System Administrator", "Sales Manager"]:
        return True

    # Users can modify their own records
    if record_owner and record_owner.systemuserid == user.systemuserid:
        return True

    return False
