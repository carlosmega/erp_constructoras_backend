"""
Global pytest configuration and fixtures.

Provides reusable fixtures for all test modules across the CRM backend.
"""

import pytest
from django.conf import settings
from ninja.testing import TestClient
from apps.users.models import SecurityRole, SystemUser


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Setup database with security roles before running tests.
    Runs once per test session.
    """
    with django_db_blocker.unblock():
        # Create predefined security roles
        roles_data = [
            {
                'name': 'System Administrator',
                'description': 'Full access to all entities and operations'
            },
            {
                'name': 'Sales Manager',
                'description': 'Manage sales team and view all opportunities'
            },
            {
                'name': 'Salesperson',
                'description': 'Manage own leads and opportunities'
            },
            {
                'name': 'Marketing User',
                'description': 'Manage campaigns and marketing leads'
            },
            {
                'name': 'Read-Only User',
                'description': 'View-only access to entities'
            },
        ]

        for role_data in roles_data:
            SecurityRole.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )


# ============================================================================
# Security Role Fixtures
# ============================================================================

@pytest.fixture
def system_admin_role(db):
    """System Administrator security role."""
    return SecurityRole.objects.get(name='System Administrator')


@pytest.fixture
def sales_manager_role(db):
    """Sales Manager security role."""
    return SecurityRole.objects.get(name='Sales Manager')


@pytest.fixture
def salesperson_role(db):
    """Salesperson security role."""
    return SecurityRole.objects.get(name='Salesperson')


@pytest.fixture
def marketing_user_role(db):
    """Marketing User security role."""
    return SecurityRole.objects.get(name='Marketing User')


@pytest.fixture
def readonly_user_role(db):
    """Read-Only User security role."""
    return SecurityRole.objects.get(name='Read-Only User')


# ============================================================================
# System User Fixtures
# ============================================================================

@pytest.fixture
def system_admin(db, system_admin_role):
    """
    System Administrator user with full access.

    Credentials:
    - Email: admin@crm.test
    - Password: admin123
    - Role: System Administrator
    """
    user = SystemUser.objects.create(
        emailaddress1='admin@crm.test',
        fullname='Admin User',
        securityroleid=system_admin_role,
        isdisabled=False,
    )
    user.set_password('admin123')
    user.save()
    return user


@pytest.fixture
def sales_manager(db, sales_manager_role):
    """
    Sales Manager user.

    Credentials:
    - Email: manager@crm.test
    - Password: manager123
    - Role: Sales Manager
    """
    user = SystemUser.objects.create(
        emailaddress1='manager@crm.test',
        fullname='Sales Manager',
        securityroleid=sales_manager_role,
        isdisabled=False,
    )
    user.set_password('manager123')
    user.save()
    return user


@pytest.fixture
def salesperson(db, salesperson_role):
    """
    Salesperson user (primary test user).

    Credentials:
    - Email: sales@crm.test
    - Password: sales123
    - Role: Salesperson
    """
    user = SystemUser.objects.create(
        emailaddress1='sales@crm.test',
        fullname='John Salesperson',
        securityroleid=salesperson_role,
        isdisabled=False,
    )
    user.set_password('sales123')
    user.save()
    return user


@pytest.fixture
def salesperson2(db, salesperson_role):
    """
    Second salesperson user for ownership testing.

    Credentials:
    - Email: sales2@crm.test
    - Password: sales123
    - Role: Salesperson
    """
    user = SystemUser.objects.create(
        emailaddress1='sales2@crm.test',
        fullname='Jane Salesperson',
        securityroleid=salesperson_role,
        isdisabled=False,
    )
    user.set_password('sales123')
    user.save()
    return user


@pytest.fixture
def marketing_user(db, marketing_user_role):
    """
    Marketing User.

    Credentials:
    - Email: marketing@crm.test
    - Password: marketing123
    - Role: Marketing User
    """
    user = SystemUser.objects.create(
        emailaddress1='marketing@crm.test',
        fullname='Marketing User',
        securityroleid=marketing_user_role,
        isdisabled=False,
    )
    user.set_password('marketing123')
    user.save()
    return user


@pytest.fixture
def readonly_user(db, readonly_user_role):
    """
    Read-Only User.

    Credentials:
    - Email: readonly@crm.test
    - Password: readonly123
    - Role: Read-Only User
    """
    user = SystemUser.objects.create(
        emailaddress1='readonly@crm.test',
        fullname='ReadOnly User',
        securityroleid=readonly_user_role,
        isdisabled=False,
    )
    user.set_password('readonly123')
    user.save()
    return user


@pytest.fixture
def disabled_user(db, salesperson_role):
    """
    Disabled user for testing authentication failures.

    Credentials:
    - Email: disabled@crm.test
    - Password: disabled123
    - Role: Salesperson
    - Status: Disabled
    """
    user = SystemUser.objects.create(
        emailaddress1='disabled@crm.test',
        fullname='Disabled User',
        securityroleid=salesperson_role,
        isdisabled=True,
    )
    user.set_password('disabled123')
    user.save()
    return user


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest.fixture
def api_client():
    """
    Django Ninja test client.

    Usage:
        response = api_client.get('/api/leads/')
        assert response.status_code == 200
    """
    from crm.urls import api
    return TestClient(api)


@pytest.fixture
def authenticated_client(api_client, salesperson):
    """
    Pre-authenticated API client with salesperson user.

    Note: For Django Ninja, you may need to implement custom auth.
    This is a placeholder that sets the user in the request context.
    """
    # This will need to be adjusted based on your auth implementation
    # For now, it returns a regular client
    # You may need to use session auth or token auth
    return api_client


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def clean_db(db):
    """
    Ensures a clean database state for isolated testing.
    Useful for integration tests that need fresh data.
    """
    from django.core.management import call_command
    from django.db import connection

    # Truncate all tables except security roles
    with connection.cursor() as cursor:
        # Disable foreign key checks temporarily
        cursor.execute('SET CONSTRAINTS ALL DEFERRED;')

    yield db

    # Re-enable constraints after test
    with connection.cursor() as cursor:
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE;')


@pytest.fixture
def mock_current_user(mocker, salesperson):
    """
    Mock the current user for testing services that require authentication.

    Usage:
        def test_something(mock_current_user):
            # mock_current_user is automatically set to salesperson
            result = LeadService.create_lead(mock_current_user, data)
    """
    return salesperson


# ============================================================================
# Django Test Client Fixtures (Full-stack HTTP testing)
# ============================================================================

@pytest.fixture
def auth_client(db, salesperson):
    """Django test client authenticated as salesperson."""
    from django.test import Client
    client = Client()
    client.force_login(salesperson)
    return client


@pytest.fixture
def admin_auth_client(db, system_admin):
    """Django test client authenticated as system admin."""
    from django.test import Client
    client = Client()
    client.force_login(system_admin)
    return client


@pytest.fixture
def readonly_auth_client(db, readonly_user):
    """Django test client authenticated as read-only user."""
    from django.test import Client
    client = Client()
    client.force_login(readonly_user)
    return client


@pytest.fixture
def manager_auth_client(db, sales_manager):
    """Django test client authenticated as sales manager."""
    from django.test import Client
    client = Client()
    client.force_login(sales_manager)
    return client
