"""
API routers (endpoints) for User Management.

Implements REST API endpoints using Django Ninja.
Routers are thin - they call services for business logic.

Phase 3 Implementation (User Story 1)
Tasks T047-T055: All API endpoints for authentication and user management
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from apps.users.schemas import (
    LoginDto,
    LoginResponse,
    UserInfo,
    ChangePasswordDto,
    CreateUserDto,
    UpdateUserDto,
    UserSchema,
    SecurityRoleSchema,
)
from apps.users.services import UserService
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.permissions import (
    require_permission,
    require_authenticated,
    Permission
)
from core.pagination import paginate_queryset, create_paginated_response

PaginatedUserList = create_paginated_response(UserSchema)


# ============================================================================
# Authentication Router
# ============================================================================

auth_router = Router(tags=["Authentication"])


@auth_router.post("/login", response=LoginResponse)
def login(request: HttpRequest, payload: LoginDto):
    """
    User login endpoint (T047).

    Authenticates user and creates Django session.

    Args:
        request: HTTP request
        payload: Login credentials (email, password)

    Returns:
        LoginResponse with user info and success status

    Raises:
        PermissionDenied: If credentials are invalid or account is locked/disabled
    """
    # Authenticate user - exceptions propagate to global handlers
    user = UserService.authenticate_user(
        email=payload.emailaddress1,
        password=payload.password
    )

    # Create Django session
    from django.contrib.auth import login as django_login
    django_login(request, user)

    # Return success response with user info
    return LoginResponse(
        success=True,
        message="Login successful",
        user=UserInfo(
            systemuserid=user.systemuserid,
            emailaddress1=user.emailaddress1,
            fullname=user.fullname,
            role_name=user.role_name,
            isdisabled=user.isdisabled,
        )
    )


@auth_router.post("/logout")
def logout(request: HttpRequest):
    """
    User logout endpoint (T048).

    Destroys Django session.

    Args:
        request: HTTP request

    Returns:
        Success message
    """
    from django.contrib.auth import logout as django_logout
    django_logout(request)

    return {"success": True, "message": "Logout successful"}


@auth_router.get("/me", response=UserInfo)
@require_authenticated
def get_current_user_info(request: HttpRequest):
    """
    Get current authenticated user info (T049).

    Args:
        request: HTTP request

    Returns:
        UserInfo of current user
    """
    user = request.user

    return UserInfo(
        systemuserid=user.systemuserid,
        emailaddress1=user.emailaddress1,
        fullname=user.fullname,
        role_name=user.role_name,
        isdisabled=user.isdisabled,
    )


@auth_router.post("/change-password")
@require_authenticated
def change_password(request: HttpRequest, payload: ChangePasswordDto):
    """
    Change user password (T050).

    Args:
        request: HTTP request
        payload: Current and new password

    Returns:
        Success message

    Raises:
        ValidationError: If current password is incorrect
    """
    UserService.change_password(
        user=request.user,
        current_password=payload.current_password,
        new_password=payload.new_password
    )

    return {"success": True, "message": "Password changed successfully"}


# ============================================================================
# Users Router (CRUD)
# ============================================================================

users_router = Router(tags=["Users"])


@users_router.get("/", response=PaginatedUserList)
@require_permission(Permission.USER_READ)
def list_users(
    request: HttpRequest,
    page: int = 1,
    page_size: int = 50,
    role: Optional[str] = None,
    isdisabled: Optional[bool] = None,
    search: Optional[str] = None,
):
    """
    List users with filtering and pagination (T051).
    Requires: USER_READ permission

    Args:
        request: HTTP request
        page: Page number (1-indexed, default: 1)
        page_size: Items per page (default: 50, max: 100)
        role: Filter by role name (optional)
        isdisabled: Filter by disabled status (optional)
        search: Search in email or full name (optional)

    Returns:
        Paginated list of users
    """
    users = UserService.list_users(
        role_filter=role,
        is_disabled=isdisabled,
        search=search
    )

    return paginate_queryset(users, page=page, page_size=page_size, request_url=request.path)


@users_router.post("/", response={201: UserSchema})
@require_permission(Permission.USER_CREATE)
def create_user(request: HttpRequest, payload: CreateUserDto):
    """
    Create new user (T052).
    Requires: USER_CREATE permission (System Administrator only)

    Args:
        request: HTTP request
        payload: User creation data

    Returns:
        Created UserSchema

    Raises:
        ValidationError: If email exists or invalid data
    """
    user = UserService.create_user(payload)
    return 201, user


@users_router.get("/{user_id}", response=UserSchema)
@require_permission(Permission.USER_READ)
def get_user(request: HttpRequest, user_id: UUID):
    """
    Get user by ID (T053).
    Requires: USER_READ permission

    Args:
        request: HTTP request
        user_id: UUID of user

    Returns:
        UserSchema

    Raises:
        NotFound: If user doesn't exist
    """
    user = UserService.get_user_by_id(user_id)
    return user


@users_router.patch("/{user_id}", response=UserSchema)
@require_permission(Permission.USER_UPDATE)
def update_user(request: HttpRequest, user_id: UUID, payload: UpdateUserDto):
    """
    Update user (T054).
    Requires: USER_UPDATE permission (System Administrator only)

    Args:
        request: HTTP request
        user_id: UUID of user
        payload: Update data (partial)

    Returns:
        Updated UserSchema

    Raises:
        NotFound: If user doesn't exist
        ValidationError: If invalid data
    """
    user = UserService.update_user(user_id, payload)
    return user


@users_router.delete("/{user_id}", response={204: None})
@require_permission(Permission.USER_DELETE)
def delete_user(request: HttpRequest, user_id: UUID):
    """
    Soft delete user by disabling (T055).
    Requires: USER_DELETE permission (System Administrator only)

    Args:
        request: HTTP request
        user_id: UUID of user

    Raises:
        NotFound: If user doesn't exist
    """
    UserService.deactivate_user(user_id)
    return 204, None


# ============================================================================
# Security Roles Router
# ============================================================================

roles_router = Router(tags=["Security Roles"])


@roles_router.get("/", response=List[SecurityRoleSchema])
def list_security_roles(request: HttpRequest):
    """
    List all security roles.

    Args:
        request: HTTP request

    Returns:
        List of SecurityRoleSchema
    """
    roles = UserService.list_security_roles()
    return roles
