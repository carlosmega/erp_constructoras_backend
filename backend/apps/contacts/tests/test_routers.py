"""Router tests for Contact Management API endpoints."""

import uuid
import pytest
from apps.contacts.tests.factories import ContactFactory
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.contract
class TestListContacts:
    def test_returns_200(self, auth_client, salesperson):
        ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/contacts/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/contacts/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/contacts/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateContact:
    def test_creates_contact(self, auth_client, salesperson):
        payload = {'lastname': 'Doe', 'firstname': 'John', 'emailaddress1': 'john@test.com'}
        response = auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['lastname'] == 'Doe'

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'lastname': 'Blocked'}
        response = readonly_auth_client.post('/api/contacts/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetContact:
    def test_returns_contact(self, auth_client, salesperson):
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/contacts/{contact.contactid}')
        assert response.status_code == 200
        assert response.json()['contactid'] == str(contact.contactid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/contacts/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateContact:
    def test_updates_contact(self, auth_client, salesperson):
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/contacts/{contact.contactid}',
            {'firstname': 'Jane'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['firstname'] == 'Jane'


@pytest.mark.contract
class TestDeleteContact:
    def test_deletes_contact(self, admin_auth_client, system_admin):
        contact = ContactFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/contacts/{contact.contactid}')
        assert response.status_code == 204

    def test_salesperson_cannot_delete(self, auth_client, salesperson):
        contact = ContactFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.delete(f'/api/contacts/{contact.contactid}')
        assert response.status_code == 403
