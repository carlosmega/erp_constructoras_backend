"""Router tests for Account Management API endpoints."""

import uuid
import pytest
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.contract
class TestListAccounts:
    def test_returns_200(self, auth_client, salesperson):
        AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/accounts/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/accounts/?statecode=0')
        assert response.status_code == 200

    def test_search(self, auth_client, salesperson):
        AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, name='Unique Corp')
        response = auth_client.get('/api/accounts/?search=Unique')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/accounts/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateAccount:
    def test_creates_account(self, auth_client, salesperson):
        payload = {'name': 'New Corp', 'emailaddress1': 'info@newcorp.com'}
        response = auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['name'] == 'New Corp'

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'name': 'Blocked'}
        response = readonly_auth_client.post('/api/accounts/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetAccount:
    def test_returns_account(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/accounts/{account.accountid}')
        assert response.status_code == 200
        assert response.json()['accountid'] == str(account.accountid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/accounts/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateAccount:
    def test_updates_account(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/accounts/{account.accountid}',
            {'name': 'Updated Corp'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Corp'


@pytest.mark.contract
class TestDeleteAccount:
    def test_deletes_account(self, admin_auth_client, system_admin):
        account = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/accounts/{account.accountid}')
        assert response.status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.delete(f'/api/accounts/{account.accountid}')
        assert response.status_code == 403
