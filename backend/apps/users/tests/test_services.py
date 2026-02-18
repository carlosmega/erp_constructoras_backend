"""
Unit tests for User services.

Tests authentication, user CRUD, password management, and role management.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, Mock
from uuid import uuid4

from apps.users.models import SystemUser, SecurityRole
from apps.users.services import UserService
from apps.users.schemas import CreateUserDto, UpdateUserDto
from apps.users.tests.factories import (
    SecurityRoleFactory,
    SystemUserFactory,
    SalespersonFactory,
    SystemAdminFactory,
)
from core.exceptions import ValidationError, NotFound, PermissionDenied


@pytest.mark.unit
class TestCreateUser:
    """Tests for UserService.create_user method."""

    @patch('apps.users.services.get_current_user')
    def test_create_user_success(self, mock_get_current_user, db, salesperson_role):
        """Test successful user creation."""
        admin = SystemAdminFactory()
        mock_get_current_user.return_value = admin

        payload = CreateUserDto(
            emailaddress1='newuser@test.com',
            fullname='New User',
            password='testpass123',
            securityroleid=salesperson_role.securityroleid,
            isdisabled=False,
        )

        user = UserService.create_user(payload)

        assert user.systemuserid is not None
        assert user.emailaddress1 == 'newuser@test.com'
        assert user.fullname == 'New User'
        assert user.check_password('testpass123')
        assert user.securityroleid == salesperson_role
        assert user.isdisabled is False
        assert user.failedloginattempts == 0
        assert user.createdby == admin
        assert user.modifiedby == admin

    @patch('apps.users.services.get_current_user')
    def test_create_user_duplicate_email(self, mock_get_current_user, db, salesperson_role):
        """Test creating user with duplicate email fails."""
        mock_get_current_user.return_value = None

        # Create existing user
        SystemUserFactory(emailaddress1='existing@test.com')

        # Try to create user with same email
        payload = CreateUserDto(
            emailaddress1='existing@test.com',
            fullname='Duplicate User',
            password='testpass123',
            securityroleid=salesperson_role.securityroleid,
            isdisabled=False,
        )

        with pytest.raises(ValidationError, match='already exists'):
            UserService.create_user(payload)

    @patch('apps.users.services.get_current_user')
    def test_create_user_invalid_role(self, mock_get_current_user, db):
        """Test creating user with non-existent role fails."""
        mock_get_current_user.return_value = None

        invalid_role_id = uuid4()
        payload = CreateUserDto(
            emailaddress1='newuser@test.com',
            fullname='New User',
            password='testpass123',
            securityroleid=invalid_role_id,
            isdisabled=False,
        )

        with pytest.raises(ValidationError, match='does not exist'):
            UserService.create_user(payload)

    @patch('apps.users.services.get_current_user')
    def test_create_user_without_current_user(self, mock_get_current_user, db, salesperson_role):
        """Test creating user without current user (no audit trail)."""
        mock_get_current_user.return_value = None

        payload = CreateUserDto(
            emailaddress1='newuser@test.com',
            fullname='New User',
            password='testpass123',
            securityroleid=salesperson_role.securityroleid,
            isdisabled=False,
        )

        user = UserService.create_user(payload)

        assert user.systemuserid is not None
        assert user.createdby is None
        assert user.modifiedby is None


@pytest.mark.unit
class TestUpdateUser:
    """Tests for UserService.update_user method."""

    @patch('apps.users.services.get_current_user')
    def test_update_user_email(self, mock_get_current_user, db):
        """Test updating user email."""
        admin = SystemAdminFactory()
        user = SalespersonFactory(emailaddress1='old@test.com')
        mock_get_current_user.return_value = admin

        payload = UpdateUserDto(emailaddress1='new@test.com')
        updated_user = UserService.update_user(user.systemuserid, payload)

        assert updated_user.emailaddress1 == 'new@test.com'
        assert updated_user.modifiedby == admin

    @patch('apps.users.services.get_current_user')
    def test_update_user_fullname(self, mock_get_current_user, db):
        """Test updating user fullname."""
        mock_get_current_user.return_value = None
        user = SalespersonFactory(fullname='Old Name')

        payload = UpdateUserDto(fullname='New Name')
        updated_user = UserService.update_user(user.systemuserid, payload)

        assert updated_user.fullname == 'New Name'

    @patch('apps.users.services.get_current_user')
    def test_update_user_role(self, mock_get_current_user, db, sales_manager_role):
        """Test updating user security role."""
        mock_get_current_user.return_value = None
        user = SalespersonFactory()

        payload = UpdateUserDto(securityroleid=sales_manager_role.securityroleid)
        updated_user = UserService.update_user(user.systemuserid, payload)

        assert updated_user.securityroleid == sales_manager_role
        assert updated_user.role_name == 'Sales Manager'

    @patch('apps.users.services.get_current_user')
    def test_update_user_disabled_status(self, mock_get_current_user, db):
        """Test updating user disabled status."""
        mock_get_current_user.return_value = None
        user = SalespersonFactory(isdisabled=False)

        payload = UpdateUserDto(isdisabled=True)
        updated_user = UserService.update_user(user.systemuserid, payload)

        assert updated_user.isdisabled is True

    def test_update_user_not_found(self, db):
        """Test updating non-existent user."""
        invalid_id = uuid4()
        payload = UpdateUserDto(fullname='New Name')

        with pytest.raises(NotFound, match='not found'):
            UserService.update_user(invalid_id, payload)

    @patch('apps.users.services.get_current_user')
    def test_update_user_duplicate_email(self, mock_get_current_user, db):
        """Test updating to an email that already exists."""
        mock_get_current_user.return_value = None
        user1 = SalespersonFactory(emailaddress1='user1@test.com')
        user2 = SalespersonFactory(emailaddress1='user2@test.com')

        payload = UpdateUserDto(emailaddress1='user2@test.com')

        with pytest.raises(ValidationError, match='already in use'):
            UserService.update_user(user1.systemuserid, payload)

    @patch('apps.users.services.get_current_user')
    def test_update_user_invalid_role(self, mock_get_current_user, db):
        """Test updating user with invalid role."""
        mock_get_current_user.return_value = None
        user = SalespersonFactory()

        invalid_role_id = uuid4()
        payload = UpdateUserDto(securityroleid=invalid_role_id)

        with pytest.raises(ValidationError, match='does not exist'):
            UserService.update_user(user.systemuserid, payload)


@pytest.mark.unit
class TestAuthenticateUser:
    """Tests for UserService.authenticate_user method."""

    def test_authenticate_user_success(self, db):
        """Test successful authentication."""
        user = SalespersonFactory(emailaddress1='test@test.com')

        authenticated_user = UserService.authenticate_user('test@test.com', 'testpass123')

        assert authenticated_user.systemuserid == user.systemuserid
        assert authenticated_user.failedloginattempts == 0
        assert authenticated_user.lastlogindate is not None

    def test_authenticate_user_invalid_email(self, db):
        """Test authentication with invalid email."""
        with pytest.raises(PermissionDenied, match='Invalid email or password'):
            UserService.authenticate_user('nonexistent@test.com', 'password')

    def test_authenticate_user_invalid_password(self, db):
        """Test authentication with invalid password."""
        user = SalespersonFactory(emailaddress1='test@test.com', failedloginattempts=0)

        with pytest.raises(PermissionDenied, match='Invalid email or password'):
            UserService.authenticate_user('test@test.com', 'wrongpassword')

        # Check that failed attempts incremented
        user.refresh_from_db()
        assert user.failedloginattempts == 1

    def test_authenticate_user_disabled_account(self, db):
        """Test authentication with disabled account."""
        SalespersonFactory(emailaddress1='disabled@test.com', isdisabled=True)

        with pytest.raises(PermissionDenied, match='Account is disabled'):
            UserService.authenticate_user('disabled@test.com', 'testpass123')

    def test_authenticate_user_locked_account(self, db):
        """Test authentication with locked account (3+ failed attempts)."""
        SalespersonFactory(emailaddress1='locked@test.com', failedloginattempts=3)

        with pytest.raises(PermissionDenied, match='Account is locked'):
            UserService.authenticate_user('locked@test.com', 'testpass123')

    def test_authenticate_user_account_lockout_on_third_failure(self, db):
        """Test that account locks on 3rd failed attempt."""
        user = SalespersonFactory(emailaddress1='test@test.com', failedloginattempts=2)

        with pytest.raises(PermissionDenied, match='Account is now locked'):
            UserService.authenticate_user('test@test.com', 'wrongpassword')

        user.refresh_from_db()
        assert user.failedloginattempts == 3
        assert user.is_locked is True

    def test_authenticate_user_resets_failed_attempts_on_success(self, db):
        """Test that successful login resets failed attempts."""
        user = SalespersonFactory(emailaddress1='test@test.com', failedloginattempts=2)

        UserService.authenticate_user('test@test.com', 'testpass123')

        user.refresh_from_db()
        assert user.failedloginattempts == 0


@pytest.mark.unit
class TestChangePassword:
    """Tests for UserService.change_password method."""

    def test_change_password_success(self, db):
        """Test successful password change."""
        user = SalespersonFactory()

        result = UserService.change_password(user, 'testpass123', 'newpass456')

        assert result is True
        user.refresh_from_db()
        assert user.check_password('newpass456')
        assert not user.check_password('testpass123')

    def test_change_password_invalid_current_password(self, db):
        """Test password change with wrong current password."""
        user = SalespersonFactory()

        with pytest.raises(ValidationError, match='Current password is incorrect'):
            UserService.change_password(user, 'wrongpassword', 'newpass456')

    def test_change_password_too_short(self, db):
        """Test password change with password too short."""
        user = SalespersonFactory()

        with pytest.raises(ValidationError, match='at least 8 characters'):
            UserService.change_password(user, 'testpass123', 'short')


@pytest.mark.unit
class TestGetUserById:
    """Tests for UserService.get_user_by_id method."""

    def test_get_user_by_id_success(self, db):
        """Test getting user by ID."""
        user = SalespersonFactory()

        retrieved_user = UserService.get_user_by_id(user.systemuserid)

        assert retrieved_user.systemuserid == user.systemuserid
        assert retrieved_user.emailaddress1 == user.emailaddress1

    def test_get_user_by_id_not_found(self, db):
        """Test getting non-existent user."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            UserService.get_user_by_id(invalid_id)

    def test_get_user_by_id_with_related_data(self, db):
        """Test that get_user_by_id retrieves related data successfully."""
        admin = SystemAdminFactory()
        user = SalespersonFactory(createdby=admin, modifiedby=admin)

        # Should successfully retrieve user with related data
        retrieved_user = UserService.get_user_by_id(user.systemuserid)

        # Verify related data is accessible
        assert retrieved_user.securityroleid.name == 'Salesperson'
        assert retrieved_user.createdby.fullname == admin.fullname
        assert retrieved_user.modifiedby.fullname == admin.fullname


@pytest.mark.unit
class TestListUsers:
    """Tests for UserService.list_users method."""

    def test_list_all_users(self, db):
        """Test listing all users."""
        SalespersonFactory.create_batch(3)
        SystemAdminFactory()

        users = UserService.list_users()

        assert users.count() == 4

    def test_list_users_filter_by_role(self, db):
        """Test filtering users by role."""
        SalespersonFactory.create_batch(2)
        SystemAdminFactory()

        users = UserService.list_users(role_filter='Salesperson')

        assert users.count() == 2
        assert all(u.role_name == 'Salesperson' for u in users)

    def test_list_users_filter_by_disabled_status(self, db):
        """Test filtering users by disabled status."""
        SalespersonFactory.create_batch(2, isdisabled=False)
        SalespersonFactory(isdisabled=True)

        active_users = UserService.list_users(is_disabled=False)
        disabled_users = UserService.list_users(is_disabled=True)

        assert active_users.count() == 2
        assert disabled_users.count() == 1

    def test_list_users_search(self, db):
        """Test searching users by email or fullname."""
        SalespersonFactory(emailaddress1='john@test.com', fullname='John Doe')
        SalespersonFactory(emailaddress1='jane@test.com', fullname='Jane Smith')
        SalespersonFactory(emailaddress1='bob@test.com', fullname='Bob Johnson')

        # Search by email
        results = UserService.list_users(search='john')
        assert results.count() == 2  # john@test.com and Bob Johnson

        # Search by fullname
        results = UserService.list_users(search='Jane')
        assert results.count() == 1

    def test_list_users_ordered_by_fullname(self, db):
        """Test that users are ordered by fullname."""
        SalespersonFactory(fullname='Charlie')
        SalespersonFactory(fullname='Alice')
        SalespersonFactory(fullname='Bob')

        users = list(UserService.list_users())

        assert users[0].fullname == 'Alice'
        assert users[1].fullname == 'Bob'
        assert users[2].fullname == 'Charlie'


@pytest.mark.unit
class TestDeactivateUser:
    """Tests for UserService.deactivate_user method."""

    @patch('apps.users.services.get_current_user')
    def test_deactivate_user_success(self, mock_get_current_user, db):
        """Test successful user deactivation."""
        admin = SystemAdminFactory()
        user = SalespersonFactory(isdisabled=False)
        mock_get_current_user.return_value = admin

        deactivated_user = UserService.deactivate_user(user.systemuserid)

        assert deactivated_user.isdisabled is True
        assert deactivated_user.modifiedby == admin

    def test_deactivate_user_not_found(self, db):
        """Test deactivating non-existent user."""
        invalid_id = uuid4()

        with pytest.raises(NotFound, match='not found'):
            UserService.deactivate_user(invalid_id)

    @patch('apps.users.services.get_current_user')
    def test_deactivate_already_disabled_user(self, mock_get_current_user, db):
        """Test deactivating already disabled user."""
        mock_get_current_user.return_value = None
        user = SalespersonFactory(isdisabled=True)

        deactivated_user = UserService.deactivate_user(user.systemuserid)

        assert deactivated_user.isdisabled is True


@pytest.mark.unit
class TestListSecurityRoles:
    """Tests for UserService.list_security_roles method."""

    def test_list_security_roles(self, db):
        """Test listing all security roles."""
        roles = UserService.list_security_roles()

        assert roles.count() == 5
        role_names = [r.name for r in roles]
        assert 'System Administrator' in role_names
        assert 'Sales Manager' in role_names
        assert 'Salesperson' in role_names
        assert 'Marketing User' in role_names
        assert 'Read-Only User' in role_names

    def test_list_security_roles_ordered(self, db):
        """Test that security roles are ordered by name."""
        roles = list(UserService.list_security_roles())

        # Check alphabetical order
        for i in range(len(roles) - 1):
            assert roles[i].name <= roles[i + 1].name
