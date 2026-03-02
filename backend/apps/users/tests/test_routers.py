"""Router tests for User Management and Authentication API endpoints."""

import uuid
import pytest


@pytest.mark.contract
class TestLogin:
    def test_login_success(self, db, salesperson):
        from django.test import Client
        client = Client()
        response = client.post(
            '/api/auth/login',
            {'emailaddress1': 'sales@crm.test', 'password': 'sales123'},
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['user']['emailaddress1'] == 'sales@crm.test'

    def test_login_wrong_password(self, db, salesperson):
        from django.test import Client
        response = Client().post(
            '/api/auth/login',
            {'emailaddress1': 'sales@crm.test', 'password': 'wrongpass'},
            content_type='application/json',
        )
        assert response.status_code in (401, 403)


@pytest.mark.contract
class TestLogout:
    def test_logout_success(self, auth_client):
        response = auth_client.post('/api/auth/logout')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True


@pytest.mark.contract
class TestGetMe:
    def test_returns_current_user(self, auth_client, salesperson):
        response = auth_client.get('/api/auth/me')
        assert response.status_code == 200
        data = response.json()
        assert data['data']['emailaddress1'] == 'sales@crm.test'

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/auth/me')
        assert response.status_code == 403


@pytest.mark.contract
class TestChangePassword:
    def test_change_password_success(self, auth_client, salesperson):
        response = auth_client.post(
            '/api/auth/change-password',
            {'current_password': 'sales123', 'new_password': 'newpass456'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['success'] is True

    def test_wrong_current_password(self, auth_client):
        response = auth_client.post(
            '/api/auth/change-password',
            {'current_password': 'wrongold', 'new_password': 'newpass456'},
            content_type='application/json',
        )
        assert response.status_code == 400


@pytest.mark.contract
class TestListUsers:
    def test_admin_can_list(self, admin_auth_client, system_admin, salesperson):
        response = admin_auth_client.get('/api/users/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_salesperson_cannot_list(self, auth_client):
        response = auth_client.get('/api/users/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateUser:
    def test_admin_creates_user(self, admin_auth_client, system_admin):
        from apps.users.models import SecurityRole
        role = SecurityRole.objects.get(name='Salesperson')
        payload = {
            'emailaddress1': 'newuser@crm.test',
            'fullname': 'New User',
            'password': 'newpass123',
            'securityroleid': str(role.securityroleid),
        }
        response = admin_auth_client.post('/api/users/', payload, content_type='application/json')
        assert response.status_code == 201

    def test_salesperson_cannot_create(self, auth_client):
        from apps.users.models import SecurityRole
        role = SecurityRole.objects.get(name='Salesperson')
        payload = {
            'emailaddress1': 'blocked@crm.test',
            'fullname': 'Blocked User',
            'password': 'pass1234',
            'securityroleid': str(role.securityroleid),
        }
        response = auth_client.post('/api/users/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetUser:
    def test_admin_gets_user(self, admin_auth_client, salesperson):
        response = admin_auth_client.get(f'/api/users/{salesperson.systemuserid}')
        assert response.status_code == 200
        assert response.json()['emailaddress1'] == 'sales@crm.test'


@pytest.mark.contract
class TestUpdateUser:
    def test_admin_updates_user(self, admin_auth_client, salesperson):
        response = admin_auth_client.patch(
            f'/api/users/{salesperson.systemuserid}',
            {'fullname': 'Updated Name'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['fullname'] == 'Updated Name'


@pytest.mark.contract
class TestDeleteUser:
    def test_admin_deletes_user(self, admin_auth_client, salesperson):
        response = admin_auth_client.delete(f'/api/users/{salesperson.systemuserid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestListRoles:
    def test_returns_roles(self, db):
        from django.test import Client
        response = Client().get('/api/roles/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 5
        names = [r['name'] for r in data]
        assert 'System Administrator' in names
