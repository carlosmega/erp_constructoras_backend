"""
Business logic services for User Management.

Implements authentication, user CRUD, and role management.
All business logic resides here per Four-Layer Architecture principle.

Phase 3 Implementation (User Story 1)
Tasks T040-T046: All service methods for user management
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from django.contrib.auth.hashers import check_password
from django.db.models import Q
from apps.users.models import SystemUser, SecurityRole
from apps.users.schemas import CreateUserDto, UpdateUserDto
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.middleware import get_current_user
from apps.audit.services import audit_action


class UserService:
    """
    Service class for user management operations.
    Handles authentication, CRUD, and business logic.
    """

    @staticmethod
    @audit_action(action='create', entity='systemuser', id_field='systemuserid')
    def create_user(payload: CreateUserDto) -> SystemUser:
        """
        Create a new user with audit fields (T040).

        Args:
            payload: User creation data

        Returns:
            Created SystemUser instance

        Raises:
            ValidationError: If email already exists or role doesn't exist
        """
        # Check if email already exists
        if SystemUser.objects.filter(emailaddress1=payload.emailaddress1).exists():
            raise ValidationError(f"User with email {payload.emailaddress1} already exists")

        # Verify security role exists
        try:
            security_role = SecurityRole.objects.get(securityroleid=payload.securityroleid)
        except SecurityRole.DoesNotExist:
            raise ValidationError(f"Security role {payload.securityroleid} does not exist")

        # Get current user for audit trail
        current_user = get_current_user()

        # Create user
        user = SystemUser(
            emailaddress1=payload.emailaddress1,
            fullname=payload.fullname,
            securityroleid=security_role,
            isdisabled=payload.isdisabled,
            failedloginattempts=0,
        )
        user.set_password(payload.password)

        # Set audit fields if current user exists
        if current_user:
            user.createdby = current_user
            user.modifiedby = current_user

        user.save()
        return user

    @staticmethod
    @audit_action(action='update', entity='systemuser', record_arg='user_id', id_field='systemuserid')
    def update_user(user_id: UUID, payload: UpdateUserDto) -> SystemUser:
        """
        Update user with modifiedby audit field (T041).

        Args:
            user_id: UUID of user to update
            payload: Update data (partial)

        Returns:
            Updated SystemUser instance

        Raises:
            NotFound: If user doesn't exist
            ValidationError: If email conflict or invalid data
        """
        # Get user
        try:
            user = SystemUser.objects.get(systemuserid=user_id)
        except SystemUser.DoesNotExist:
            raise NotFound(f"User {user_id} not found")

        # Update email if provided
        if payload.emailaddress1:
            # Check for conflicts (excluding current user)
            if SystemUser.objects.filter(emailaddress1=payload.emailaddress1).exclude(systemuserid=user_id).exists():
                raise ValidationError(f"Email {payload.emailaddress1} already in use")
            user.emailaddress1 = payload.emailaddress1

        # Update full name if provided
        if payload.fullname:
            user.fullname = payload.fullname

        # Update security role if provided
        if payload.securityroleid:
            try:
                security_role = SecurityRole.objects.get(securityroleid=payload.securityroleid)
                user.securityroleid = security_role
            except SecurityRole.DoesNotExist:
                raise ValidationError(f"Security role {payload.securityroleid} does not exist")

        # Update disabled status if provided
        if payload.isdisabled is not None:
            user.isdisabled = payload.isdisabled

        # Set modified by
        current_user = get_current_user()
        if current_user:
            user.modifiedby = current_user

        user.save()
        return user

    @staticmethod
    def authenticate_user(email: str, password: str) -> SystemUser:
        """
        Authenticate user and handle account lockout (T042).

        Implements 3-strike lockout policy:
        - After 3 failed attempts, account is locked
        - On successful login, reset failed attempts and update last login

        Args:
            email: User email
            password: Plain text password

        Returns:
            Authenticated SystemUser instance

        Raises:
            PermissionDenied: If credentials invalid or account locked/disabled
        """
        try:
            user = SystemUser.objects.get(emailaddress1=email)
        except SystemUser.DoesNotExist:
            raise PermissionDenied("Invalid email or password")

        # Check if account is disabled
        if user.isdisabled:
            raise PermissionDenied("Account is disabled")

        # Check if account is locked (3+ failed attempts)
        if user.is_locked:
            raise PermissionDenied("Account is locked due to multiple failed login attempts. Contact administrator.")

        # Verify password
        if not user.check_password(password):
            # Increment failed login attempts
            user.failedloginattempts += 1
            user.save(update_fields=['failedloginattempts'])

            # Return appropriate error message
            if user.failedloginattempts >= 3:
                raise PermissionDenied("Account is now locked due to multiple failed login attempts. Contact administrator.")
            else:
                raise PermissionDenied("Invalid email or password")

        # Successful login - reset failed attempts and update last login
        user.failedloginattempts = 0
        user.lastlogindate = datetime.now()
        user.save(update_fields=['failedloginattempts', 'lastlogindate'])

        return user

    @staticmethod
    def change_password(user: SystemUser, current_password: str, new_password: str) -> bool:
        """
        Change user password after verifying current password (T043).

        Args:
            user: SystemUser instance
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password changed successfully

        Raises:
            ValidationError: If current password is incorrect or new password invalid
        """
        # Verify current password
        if not user.check_password(current_password):
            raise ValidationError("Current password is incorrect")

        # Validate new password (Django validators will run)
        if len(new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long")

        # Set new password
        user.set_password(new_password)
        user.save(update_fields=['password'])

        return True

    @staticmethod
    def get_user_by_id(user_id: UUID) -> SystemUser:
        """
        Get user by ID with optimized query (T044).

        Uses select_related to avoid N+1 queries.

        Args:
            user_id: UUID of user

        Returns:
            SystemUser instance

        Raises:
            NotFound: If user doesn't exist
        """
        try:
            return SystemUser.objects.select_related(
                'securityroleid',
                'createdby',
                'modifiedby'
            ).get(systemuserid=user_id)
        except SystemUser.DoesNotExist:
            raise NotFound(f"User {user_id} not found")

    @staticmethod
    def list_users(
        role_filter: Optional[str] = None,
        is_disabled: Optional[bool] = None,
        search: Optional[str] = None
    ) -> List[SystemUser]:
        """
        List users with filtering and optimization (T045).

        Args:
            role_filter: Filter by role name (optional)
            is_disabled: Filter by disabled status (optional)
            search: Search in email or full name (optional)

        Returns:
            QuerySet of SystemUser instances
        """
        queryset = SystemUser.objects.select_related('securityroleid').all()

        # Filter by role
        if role_filter:
            queryset = queryset.filter(securityroleid__name=role_filter)

        # Filter by disabled status
        if is_disabled is not None:
            queryset = queryset.filter(isdisabled=is_disabled)

        # Search filter
        if search:
            queryset = queryset.filter(
                Q(emailaddress1__icontains=search) |
                Q(fullname__icontains=search)
            )

        return queryset.order_by('fullname')

    @staticmethod
    @audit_action(action='delete', entity='systemuser', record_arg='user_id', id_field='systemuserid')
    def deactivate_user(user_id: UUID) -> SystemUser:
        """
        Soft delete user by setting isdisabled=True (T046).

        Args:
            user_id: UUID of user to deactivate

        Returns:
            Deactivated SystemUser instance

        Raises:
            NotFound: If user doesn't exist
        """
        try:
            user = SystemUser.objects.get(systemuserid=user_id)
        except SystemUser.DoesNotExist:
            raise NotFound(f"User {user_id} not found")

        user.isdisabled = True

        # Set modified by
        current_user = get_current_user()
        if current_user:
            user.modifiedby = current_user

        user.save(update_fields=['isdisabled', 'modifiedby', 'modifiedon'])
        return user

    @staticmethod
    def list_users_for_lookup(search: Optional[str] = None) -> List[SystemUser]:
        """
        List active users for lookup/selector dialogs.
        Returns lightweight list (max 50) for search-based selection.
        """
        queryset = SystemUser.objects.filter(isdisabled=False)

        if search:
            queryset = queryset.filter(
                Q(fullname__icontains=search) |
                Q(emailaddress1__icontains=search)
            )

        return queryset.order_by('fullname')[:50]

    @staticmethod
    def list_security_roles() -> List[SecurityRole]:
        """
        Get all available security roles.

        Returns:
            QuerySet of SecurityRole instances
        """
        return SecurityRole.objects.all().order_by('name')
