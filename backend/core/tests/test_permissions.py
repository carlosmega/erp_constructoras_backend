"""
Unit tests for RBAC permission system.

Tests permission checks, role assignments, ownership filtering, and decorators.
"""

import pytest
from unittest.mock import Mock
from django.db import models

from core.permissions import (
    Permission,
    ROLE_PERMISSIONS,
    has_permission,
    has_any_permission,
    has_all_permissions,
    check_ownership,
    get_user_permissions,
    filter_by_ownership,
    can_modify_record,
)
from core.exceptions import PermissionDenied


@pytest.mark.unit
@pytest.mark.permissions
class TestPermissionEnums:
    """Test Permission enum definitions."""

    def test_permission_enum_values(self):
        """Test that permission enums have correct string values."""
        assert Permission.LEAD_CREATE.value == "lead_create"
        assert Permission.LEAD_READ.value == "lead_read"
        assert Permission.LEAD_UPDATE.value == "lead_update"
        assert Permission.LEAD_DELETE.value == "lead_delete"
        assert Permission.LEAD_QUALIFY.value == "lead_qualify"

    def test_all_crud_permissions_exist(self):
        """Test that CRUD permissions exist for all entities."""
        entities = [
            'USER', 'LEAD', 'OPPORTUNITY', 'ACCOUNT', 'CONTACT',
            'QUOTE', 'ORDER', 'INVOICE', 'PRODUCT', 'ACTIVITY'
        ]
        actions = ['CREATE', 'READ', 'UPDATE', 'DELETE']

        for entity in entities:
            for action in actions:
                perm_name = f"{entity}_{action}"
                assert hasattr(Permission, perm_name), f"Missing {perm_name}"


@pytest.mark.unit
@pytest.mark.permissions
class TestRolePermissions:
    """Test role permission matrix."""

    def test_system_admin_has_all_permissions(self):
        """System Administrator should have all permissions."""
        admin_perms = ROLE_PERMISSIONS['System Administrator']

        # Should have all entity CRUD permissions
        assert Permission.LEAD_CREATE in admin_perms
        assert Permission.LEAD_DELETE in admin_perms
        assert Permission.USER_DELETE in admin_perms
        assert Permission.OPPORTUNITY_CLOSE in admin_perms
        assert Permission.QUOTE_ACTIVATE in admin_perms

    def test_sales_manager_permissions(self):
        """Sales Manager should have full sales permissions but limited user access."""
        manager_perms = ROLE_PERMISSIONS['Sales Manager']

        # Should have full lead permissions
        assert Permission.LEAD_CREATE in manager_perms
        assert Permission.LEAD_READ in manager_perms
        assert Permission.LEAD_UPDATE in manager_perms
        assert Permission.LEAD_DELETE in manager_perms
        assert Permission.LEAD_QUALIFY in manager_perms

        # Should only read users, not manage them
        assert Permission.USER_READ in manager_perms
        assert Permission.USER_CREATE not in manager_perms
        assert Permission.USER_DELETE not in manager_perms

        # Should have full opportunity permissions
        assert Permission.OPPORTUNITY_CREATE in manager_perms
        assert Permission.OPPORTUNITY_CLOSE in manager_perms

    def test_salesperson_permissions(self):
        """Salesperson should have limited CRUD, no delete on most entities."""
        sales_perms = ROLE_PERMISSIONS['Salesperson']

        # Can manage leads (but no delete)
        assert Permission.LEAD_CREATE in sales_perms
        assert Permission.LEAD_READ in sales_perms
        assert Permission.LEAD_UPDATE in sales_perms
        assert Permission.LEAD_QUALIFY in sales_perms
        assert Permission.LEAD_DELETE not in sales_perms

        # Can manage opportunities
        assert Permission.OPPORTUNITY_CREATE in sales_perms
        assert Permission.OPPORTUNITY_READ in sales_perms
        assert Permission.OPPORTUNITY_UPDATE in sales_perms
        assert Permission.OPPORTUNITY_CLOSE in sales_perms
        assert Permission.OPPORTUNITY_DELETE not in sales_perms

        # No user management
        assert Permission.USER_READ not in sales_perms
        assert Permission.USER_CREATE not in sales_perms

    def test_marketing_user_permissions(self):
        """Marketing User should only access leads and contacts."""
        marketing_perms = ROLE_PERMISSIONS['Marketing User']

        # Can manage leads (no qualify)
        assert Permission.LEAD_CREATE in marketing_perms
        assert Permission.LEAD_READ in marketing_perms
        assert Permission.LEAD_UPDATE in marketing_perms
        assert Permission.LEAD_QUALIFY not in marketing_perms
        assert Permission.LEAD_DELETE not in marketing_perms

        # Can manage contacts
        assert Permission.CONTACT_CREATE in marketing_perms
        assert Permission.CONTACT_READ in marketing_perms

        # Cannot access opportunities
        assert Permission.OPPORTUNITY_CREATE not in marketing_perms
        assert Permission.OPPORTUNITY_READ not in marketing_perms

    def test_readonly_user_permissions(self):
        """Read-Only User should only have READ permissions."""
        readonly_perms = ROLE_PERMISSIONS['Read-Only User']

        # Only read permissions
        assert Permission.LEAD_READ in readonly_perms
        assert Permission.OPPORTUNITY_READ in readonly_perms
        assert Permission.ACCOUNT_READ in readonly_perms

        # No write permissions
        assert Permission.LEAD_CREATE not in readonly_perms
        assert Permission.LEAD_UPDATE not in readonly_perms
        assert Permission.LEAD_DELETE not in readonly_perms
        assert Permission.OPPORTUNITY_CREATE not in readonly_perms


@pytest.mark.unit
@pytest.mark.permissions
class TestHasPermission:
    """Test has_permission function."""

    def test_has_permission_system_admin(self, system_admin):
        """System Administrator should have all permissions."""
        assert has_permission(system_admin, Permission.LEAD_CREATE)
        assert has_permission(system_admin, Permission.LEAD_DELETE)
        assert has_permission(system_admin, Permission.USER_DELETE)
        assert has_permission(system_admin, Permission.OPPORTUNITY_CLOSE)

    def test_has_permission_salesperson(self, salesperson):
        """Salesperson should have limited permissions."""
        # Has these permissions
        assert has_permission(salesperson, Permission.LEAD_CREATE)
        assert has_permission(salesperson, Permission.LEAD_READ)
        assert has_permission(salesperson, Permission.LEAD_UPDATE)
        assert has_permission(salesperson, Permission.LEAD_QUALIFY)

        # Does NOT have these permissions
        assert not has_permission(salesperson, Permission.LEAD_DELETE)
        assert not has_permission(salesperson, Permission.USER_CREATE)
        assert not has_permission(salesperson, Permission.OPPORTUNITY_DELETE)

    def test_has_permission_readonly_user(self, readonly_user):
        """Read-Only User should only have read permissions."""
        assert has_permission(readonly_user, Permission.LEAD_READ)
        assert has_permission(readonly_user, Permission.OPPORTUNITY_READ)

        assert not has_permission(readonly_user, Permission.LEAD_CREATE)
        assert not has_permission(readonly_user, Permission.LEAD_UPDATE)
        assert not has_permission(readonly_user, Permission.OPPORTUNITY_CREATE)

    def test_has_permission_unauthenticated_user(self):
        """Unauthenticated user should have no permissions."""
        mock_user = Mock()
        mock_user.is_authenticated = False

        assert not has_permission(mock_user, Permission.LEAD_READ)
        assert not has_permission(mock_user, Permission.LEAD_CREATE)

    def test_has_permission_user_with_unknown_role(self, db):
        """User with unknown role should have no permissions."""
        from apps.users.models import SecurityRole, SystemUser

        # Create a custom role not in ROLE_PERMISSIONS
        unknown_role = SecurityRole.objects.create(
            name='Unknown Role',
            description='Not in permission matrix'
        )

        user = SystemUser.objects.create(
            emailaddress1='unknown@test.com',
            fullname='Unknown Role User',
            securityroleid=unknown_role,
        )
        user.set_password('test123')
        user.save()

        assert not has_permission(user, Permission.LEAD_READ)


@pytest.mark.unit
@pytest.mark.permissions
class TestHasAnyPermission:
    """Test has_any_permission function."""

    def test_has_any_permission_true(self, salesperson):
        """Should return True if user has at least one permission."""
        perms = [
            Permission.LEAD_CREATE,  # Salesperson has this
            Permission.LEAD_DELETE,  # Salesperson does NOT have this
        ]
        assert has_any_permission(salesperson, perms)

    def test_has_any_permission_false(self, salesperson):
        """Should return False if user has none of the permissions."""
        perms = [
            Permission.LEAD_DELETE,
            Permission.USER_CREATE,
            Permission.OPPORTUNITY_DELETE,
        ]
        assert not has_any_permission(salesperson, perms)

    def test_has_any_permission_readonly(self, readonly_user):
        """Read-only user should only match read permissions."""
        perms = [Permission.LEAD_READ, Permission.LEAD_CREATE]
        assert has_any_permission(readonly_user, perms)

        perms = [Permission.LEAD_CREATE, Permission.LEAD_UPDATE]
        assert not has_any_permission(readonly_user, perms)


@pytest.mark.unit
@pytest.mark.permissions
class TestHasAllPermissions:
    """Test has_all_permissions function."""

    def test_has_all_permissions_true(self, system_admin):
        """System Admin should have all permissions."""
        perms = [
            Permission.LEAD_CREATE,
            Permission.LEAD_READ,
            Permission.LEAD_UPDATE,
            Permission.LEAD_DELETE,
        ]
        assert has_all_permissions(system_admin, perms)

    def test_has_all_permissions_false(self, salesperson):
        """Salesperson should not have all permissions."""
        perms = [
            Permission.LEAD_CREATE,  # Has this
            Permission.LEAD_DELETE,  # Does NOT have this
        ]
        assert not has_all_permissions(salesperson, perms)

    def test_has_all_permissions_partial(self, sales_manager):
        """Sales Manager should have all sales permissions."""
        perms = [
            Permission.LEAD_CREATE,
            Permission.LEAD_READ,
            Permission.LEAD_UPDATE,
            Permission.LEAD_DELETE,
            Permission.LEAD_QUALIFY,
        ]
        assert has_all_permissions(sales_manager, perms)


@pytest.mark.unit
@pytest.mark.permissions
class TestCheckOwnership:
    """Test check_ownership function."""

    def test_check_ownership_owner(self, salesperson):
        """User should own their own records."""
        # Create a mock record with ownerid
        mock_record = Mock()
        mock_record.ownerid_id = salesperson.systemuserid
        assert check_ownership(salesperson, mock_record)

    def test_check_ownership_not_owner(self, salesperson, salesperson2):
        """User should not own other users' records."""
        mock_record = Mock()
        mock_record.ownerid_id = salesperson2.systemuserid
        assert not check_ownership(salesperson, mock_record)

    def test_check_ownership_system_admin(self, system_admin, salesperson):
        """System Admin should access all records."""
        mock_record = Mock()
        mock_record.ownerid_id = salesperson.systemuserid
        assert check_ownership(system_admin, mock_record)

    def test_check_ownership_unauthenticated(self, salesperson):
        """Unauthenticated user should not access any record."""
        mock_user = Mock()
        mock_user.is_authenticated = False

        mock_record = Mock()
        mock_record.ownerid_id = salesperson.systemuserid
        assert not check_ownership(mock_user, mock_record)

    def test_check_ownership_no_ownerid_field(self, salesperson):
        """Records without ownerid field should be accessible."""
        mock_record = Mock(spec=[])  # No ownerid attribute
        assert check_ownership(salesperson, mock_record)


@pytest.mark.unit
@pytest.mark.permissions
class TestFilterByOwnership:
    """Test filter_by_ownership function."""

    def test_filter_by_ownership_salesperson(self, db, salesperson, salesperson2):
        """Salesperson should only see their own records."""
        # Use Account model for testing (simpler than Lead)
        from apps.accounts.models import Account

        # Create accounts owned by different users
        acc1 = Account.objects.create(name='Acc1', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        acc2 = Account.objects.create(name='Acc2', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        acc3 = Account.objects.create(name='Acc3', ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2)

        queryset = Account.objects.all()
        filtered = filter_by_ownership(queryset, salesperson)

        assert filtered.count() == 2
        assert acc1 in filtered
        assert acc2 in filtered
        assert acc3 not in filtered

    def test_filter_by_ownership_system_admin(self, db, system_admin, salesperson):
        """System Admin should see all records."""
        from apps.accounts.models import Account

        acc1 = Account.objects.create(name='Acc1', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        acc2 = Account.objects.create(name='Acc2', ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)

        queryset = Account.objects.all()
        filtered = filter_by_ownership(queryset, system_admin)

        assert filtered.count() == 2

    def test_filter_by_ownership_sales_manager(self, db, sales_manager, salesperson):
        """Sales Manager should see all records."""
        from apps.accounts.models import Account

        acc1 = Account.objects.create(name='Acc1', ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        acc2 = Account.objects.create(name='Acc2', ownerid=sales_manager, createdby=sales_manager, modifiedby=sales_manager)

        queryset = Account.objects.all()
        filtered = filter_by_ownership(queryset, sales_manager)

        assert filtered.count() == 2

    def test_filter_by_ownership_unauthenticated(self, db):
        """Unauthenticated user should see no records."""
        from apps.accounts.models import Account
        from apps.users.tests.factories import SalespersonFactory

        mock_user = Mock()
        mock_user.is_authenticated = False

        # Create some accounts
        owner = SalespersonFactory()
        Account.objects.create(name='Acc1', ownerid=owner, createdby=owner, modifiedby=owner)
        Account.objects.create(name='Acc2', ownerid=owner, createdby=owner, modifiedby=owner)

        queryset = Account.objects.all()
        filtered = filter_by_ownership(queryset, mock_user)

        assert filtered.count() == 0


@pytest.mark.unit
@pytest.mark.permissions
class TestCanModifyRecord:
    """Test can_modify_record function."""

    def test_can_modify_own_record(self, salesperson):
        """User should be able to modify their own records."""
        assert can_modify_record(salesperson, salesperson)

    def test_cannot_modify_other_record(self, salesperson, salesperson2):
        """User should not be able to modify other users' records."""
        assert not can_modify_record(salesperson, salesperson2)

    def test_system_admin_can_modify_any_record(self, system_admin, salesperson):
        """System Admin should modify any record."""
        assert can_modify_record(system_admin, salesperson)
        assert can_modify_record(system_admin, system_admin)

    def test_sales_manager_can_modify_any_record(self, sales_manager, salesperson):
        """Sales Manager should modify any record."""
        assert can_modify_record(sales_manager, salesperson)

    def test_unauthenticated_cannot_modify(self, salesperson):
        """Unauthenticated user should not modify any record."""
        mock_user = Mock()
        mock_user.is_authenticated = False

        assert not can_modify_record(mock_user, salesperson)


@pytest.mark.unit
@pytest.mark.permissions
class TestGetUserPermissions:
    """Test get_user_permissions function."""

    def test_get_user_permissions_system_admin(self, system_admin):
        """Should return all permissions for System Admin."""
        perms = get_user_permissions(system_admin)

        assert Permission.LEAD_CREATE in perms
        assert Permission.LEAD_DELETE in perms
        assert Permission.USER_DELETE in perms
        assert len(perms) > 30  # System Admin has many permissions

    def test_get_user_permissions_salesperson(self, salesperson):
        """Should return limited permissions for Salesperson."""
        perms = get_user_permissions(salesperson)

        assert Permission.LEAD_CREATE in perms
        assert Permission.LEAD_READ in perms
        assert Permission.LEAD_DELETE not in perms
        assert Permission.USER_CREATE not in perms

    def test_get_user_permissions_readonly(self, readonly_user):
        """Should return only read permissions for Read-Only User."""
        perms = get_user_permissions(readonly_user)

        assert Permission.LEAD_READ in perms
        assert Permission.OPPORTUNITY_READ in perms
        assert Permission.LEAD_CREATE not in perms
        assert Permission.LEAD_UPDATE not in perms

    def test_get_user_permissions_unauthenticated(self):
        """Should return empty list for unauthenticated user."""
        mock_user = Mock()
        mock_user.is_authenticated = False

        perms = get_user_permissions(mock_user)
        assert perms == []
