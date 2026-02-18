"""
Unit tests for User models.

Tests SystemUser and SecurityRole models including validation,
properties, authentication, and role management.
"""

import pytest
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from apps.users.models import SecurityRole, SystemUser
from apps.users.tests.factories import (
    SecurityRoleFactory,
    SystemUserFactory,
    SystemAdminFactory,
    SalespersonFactory,
)


@pytest.mark.unit
class TestSecurityRoleModel:
    """Tests for SecurityRole model."""

    def test_create_security_role(self, db):
        """Test creating a security role."""
        role = SecurityRole.objects.create(
            name='Test Role',
            description='Test role description'
        )

        assert role.securityroleid is not None
        assert role.name == 'Test Role'
        assert role.description == 'Test role description'
        assert str(role) == 'Test Role'

    def test_security_role_unique_name(self, db):
        """Test that role names must be unique."""
        SecurityRole.objects.create(name='Unique Role')

        with pytest.raises(IntegrityError):
            SecurityRole.objects.create(name='Unique Role')

    def test_security_role_factory(self, db):
        """Test SecurityRoleFactory creates valid roles."""
        role = SecurityRoleFactory(name='Factory Role')

        assert role.securityroleid is not None
        assert role.name == 'Factory Role'
        assert 'Factory Role' in role.description

    def test_security_role_ordering(self, db):
        """Test that roles are ordered by name."""
        role_c = SecurityRoleFactory(name='C Role')
        role_a = SecurityRoleFactory(name='A Role')
        role_b = SecurityRoleFactory(name='B Role')

        roles = list(SecurityRole.objects.all())
        assert roles[0] == role_a
        assert roles[1] == role_b
        assert roles[2] == role_c


@pytest.mark.unit
class TestSystemUserModel:
    """Tests for SystemUser model."""

    def test_create_system_user(self, db, salesperson_role):
        """Test creating a system user."""
        user = SystemUser.objects.create(
            emailaddress1='test@crm.test',
            fullname='Test User',
            securityroleid=salesperson_role,
        )
        user.set_password('testpass123')
        user.save()

        assert user.systemuserid is not None
        assert user.emailaddress1 == 'test@crm.test'
        assert user.fullname == 'Test User'
        assert user.check_password('testpass123')
        assert user.isdisabled is False
        assert user.failedloginattempts == 0

    def test_system_user_unique_email(self, db):
        """Test that email addresses must be unique."""
        SystemUserFactory(emailaddress1='unique@test.com')

        with pytest.raises(IntegrityError):
            SystemUserFactory(emailaddress1='unique@test.com')

    def test_system_user_str_representation(self, db):
        """Test __str__ method."""
        user = SystemUserFactory(
            fullname='John Doe',
            emailaddress1='john@test.com'
        )

        assert str(user) == 'John Doe (john@test.com)'

    def test_system_user_factory(self, db):
        """Test SystemUserFactory creates valid users."""
        user = SystemUserFactory()

        assert user.systemuserid is not None
        assert user.emailaddress1 is not None
        assert user.fullname is not None
        assert user.check_password('testpass123')
        assert user.securityroleid.name == 'Salesperson'

    def test_system_user_password_hashing(self, db):
        """Test that passwords are properly hashed."""
        user = SystemUserFactory()

        # Password should be hashed, not plain text
        assert user.password != 'testpass123'
        assert user.check_password('testpass123')
        assert not user.check_password('wrongpassword')


@pytest.mark.unit
class TestSystemUserProperties:
    """Tests for SystemUser properties and computed fields."""

    def test_is_active_property(self, db):
        """Test is_active property."""
        active_user = SystemUserFactory(isdisabled=False)
        disabled_user = SystemUserFactory(isdisabled=True)

        assert active_user.is_active is True
        assert disabled_user.is_active is False

    def test_is_locked_property(self, db):
        """Test is_locked property (locked after 3 failed attempts)."""
        user = SystemUserFactory(failedloginattempts=0)
        assert user.is_locked is False

        user.failedloginattempts = 2
        assert user.is_locked is False

        user.failedloginattempts = 3
        assert user.is_locked is True

        user.failedloginattempts = 5
        assert user.is_locked is True

    def test_role_name_property(self, db):
        """Test role_name property."""
        admin = SystemAdminFactory()
        salesperson = SalespersonFactory()

        assert admin.role_name == 'System Administrator'
        assert salesperson.role_name == 'Salesperson'

    def test_role_name_property_no_role(self, db, salesperson_role):
        """Test role_name property returns correct role name."""
        # Note: securityroleid is required, so we test with a role
        user = SystemUserFactory(securityroleid=salesperson_role)

        assert user.role_name == 'Salesperson'

    def test_is_staff_property(self, db):
        """Test is_staff property (only System Administrators)."""
        admin = SystemAdminFactory()
        salesperson = SalespersonFactory()

        assert admin.is_staff is True
        assert salesperson.is_staff is False

    def test_is_superuser_property(self, db):
        """Test is_superuser property (only System Administrators)."""
        admin = SystemAdminFactory()
        salesperson = SalespersonFactory()

        assert admin.is_superuser is True
        assert salesperson.is_superuser is False

    def test_has_perm_method(self, db):
        """Test has_perm method."""
        admin = SystemAdminFactory()
        salesperson = SalespersonFactory()

        assert admin.has_perm('any.permission') is True
        assert salesperson.has_perm('any.permission') is False

    def test_has_module_perms_method(self, db):
        """Test has_module_perms method."""
        admin = SystemAdminFactory()
        salesperson = SalespersonFactory()

        assert admin.has_module_perms('leads') is True
        assert salesperson.has_module_perms('leads') is False


@pytest.mark.unit
class TestSystemUserManager:
    """Tests for SystemUserManager custom methods."""

    def test_create_user_method(self, db, salesperson_role):
        """Test create_user manager method."""
        user = SystemUser.objects.create_user(
            emailaddress1='newuser@test.com',
            fullname='New User',
            password='newpass123',
            securityroleid=salesperson_role,
        )

        assert user.systemuserid is not None
        assert user.emailaddress1 == 'newuser@test.com'
        assert user.fullname == 'New User'
        assert user.check_password('newpass123')

    def test_create_user_without_email(self, db, salesperson_role):
        """Test create_user fails without email."""
        with pytest.raises(ValueError, match='Email address is required'):
            SystemUser.objects.create_user(
                emailaddress1='',
                fullname='Test User',
                password='test123',
                securityroleid=salesperson_role,
            )

    def test_create_user_without_fullname(self, db, salesperson_role):
        """Test create_user fails without fullname."""
        with pytest.raises(ValueError, match='Full name is required'):
            SystemUser.objects.create_user(
                emailaddress1='test@test.com',
                fullname='',
                password='test123',
                securityroleid=salesperson_role,
            )

    def test_create_superuser_method(self, db):
        """Test create_superuser manager method."""
        user = SystemUser.objects.create_superuser(
            emailaddress1='admin@test.com',
            fullname='Admin User',
            password='admin123',
        )

        assert user.systemuserid is not None
        assert user.emailaddress1 == 'admin@test.com'
        assert user.check_password('admin123')
        assert user.role_name == 'System Administrator'
        assert user.is_superuser is True
        assert user.is_staff is True
        assert user.isdisabled is False

    def test_create_superuser_creates_admin_role_if_missing(self, db):
        """Test create_superuser creates System Administrator role if needed."""
        # Delete all roles
        SecurityRole.objects.all().delete()

        user = SystemUser.objects.create_superuser(
            emailaddress1='admin@test.com',
            fullname='Admin User',
            password='admin123',
        )

        # Should have created the role
        assert SecurityRole.objects.filter(name='System Administrator').exists()
        assert user.role_name == 'System Administrator'


@pytest.mark.unit
class TestSystemUserValidation:
    """Tests for SystemUser model validation."""

    def test_email_format_validation(self, db, salesperson_role):
        """Test email format validation."""
        # Valid email
        user = SystemUser(
            emailaddress1='valid@email.com',
            fullname='Test User',
            securityroleid=salesperson_role,
        )
        user.set_password('testpass123')  # Set password before validation
        user.full_clean()  # Should not raise

        # Invalid email format will be caught by EmailField
        user_invalid = SystemUser(
            emailaddress1='invalid-email',
            fullname='Test User',
            securityroleid=salesperson_role,
        )
        user_invalid.set_password('testpass123')

        with pytest.raises(ValidationError):
            user_invalid.full_clean()

    def test_required_fields(self, db, salesperson_role):
        """Test required fields validation."""
        # Test that emailaddress1 is required
        user1 = SystemUser(
            emailaddress1='',
            fullname='Test User',
            securityroleid=salesperson_role,
        )
        user1.set_password('test123')

        with pytest.raises(ValidationError):
            user1.full_clean()

        # Test that fullname is required via manager method
        with pytest.raises(ValueError, match='Full name is required'):
            SystemUser.objects.create_user(
                emailaddress1='test@test.com',
                fullname='',
                password='test123',
                securityroleid=salesperson_role,
            )

    def test_role_protection(self, db):
        """Test that roles cannot be deleted if users are assigned."""
        role = SecurityRoleFactory(name='Protected Role')
        user = SystemUserFactory(securityroleid=role)

        # Should not be able to delete role with assigned users
        with pytest.raises(Exception):  # PROTECT constraint
            role.delete()


@pytest.mark.unit
class TestSystemUserAuthentication:
    """Tests for SystemUser authentication behavior."""

    def test_disabled_user_authentication(self, db):
        """Test that disabled users cannot authenticate."""
        user = SystemUserFactory(isdisabled=True)

        assert user.is_active is False
        # Note: Authentication behavior depends on Django auth backend

    def test_locked_user_due_to_failed_attempts(self, db):
        """Test account locking after failed login attempts."""
        user = SystemUserFactory(failedloginattempts=0)

        assert user.is_locked is False

        # Simulate failed login attempts
        user.failedloginattempts += 1
        user.save()
        assert user.is_locked is False

        user.failedloginattempts += 1
        user.save()
        assert user.is_locked is False

        user.failedloginattempts += 1
        user.save()
        assert user.is_locked is True

    def test_reset_failed_login_attempts(self, db):
        """Test resetting failed login attempts."""
        user = SystemUserFactory(failedloginattempts=5)

        assert user.is_locked is True

        # Reset attempts
        user.failedloginattempts = 0
        user.save()

        assert user.is_locked is False
