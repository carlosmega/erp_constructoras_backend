"""
Django Ninja schemas (DTOs) for User Management API.

Defines request/response data transfer objects for type-safe APIs.

Phase 3 Implementation (User Story 1)
Tasks T033-T039: All DTOs for authentication and user management
"""

from ninja import Schema, ModelSchema
from typing import Optional
from uuid import UUID
from datetime import datetime
from apps.users.models import SystemUser, SecurityRole


# ============================================================================
# Security Role Schemas
# ============================================================================

class SecurityRoleSchema(ModelSchema):
    """Security role response schema."""

    class Meta:
        model = SecurityRole
        fields = ['securityroleid', 'name', 'description']


# ============================================================================
# User Response Schemas
# ============================================================================

class UserSchema(ModelSchema):
    """
    Full user response schema (T033).
    Used for detailed user information (without password).
    """
    role_name: Optional[str] = None

    class Meta:
        model = SystemUser
        fields = [
            'systemuserid',
            'emailaddress1',
            'fullname',
            'isdisabled',
            'failedloginattempts',
            'lastlogindate',
            'createdon',
            'modifiedon',
        ]

    @staticmethod
    def resolve_role_name(obj):
        """Resolve role name from foreign key."""
        return obj.securityroleid.name if obj.securityroleid else None


class UserInfo(Schema):
    """
    Basic user information schema (T038).
    Used for /auth/me endpoint and login response.
    """
    systemuserid: UUID
    emailaddress1: str
    fullname: str
    role_name: str
    isdisabled: bool


# ============================================================================
# User Create/Update Schemas
# ============================================================================

class CreateUserDto(Schema):
    """
    User creation payload (T034).
    All fields required for creating a new user.
    """
    emailaddress1: str
    fullname: str
    password: str
    securityroleid: UUID
    isdisabled: bool = False


class UpdateUserDto(Schema):
    """
    User update payload (T035).
    All fields optional for partial updates.
    """
    emailaddress1: Optional[str] = None
    fullname: Optional[str] = None
    securityroleid: Optional[UUID] = None
    isdisabled: Optional[bool] = None


# ============================================================================
# Authentication Schemas
# ============================================================================

class LoginDto(Schema):
    """
    Login credentials (T036).
    Required for authentication.
    """
    emailaddress1: str
    password: str


class LoginResponse(Schema):
    """
    Login response with user info and session (T037).
    """
    success: bool
    message: str
    user: Optional[UserInfo] = None


class ChangePasswordDto(Schema):
    """
    Password change payload (T039).
    Requires current password for security.
    """
    current_password: str
    new_password: str


# ============================================================================
# List Response Schema
# ============================================================================

class UserListResponse(Schema):
    """
    Paginated user list response.
    """
    count: int
    results: list[UserSchema]


class UserLookupSchema(Schema):
    """Lightweight user schema for lookup/selector dialogs."""
    systemuserid: UUID
    fullname: str
    emailaddress1: str
