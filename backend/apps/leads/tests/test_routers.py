"""Router tests for Lead Management API endpoints."""

import uuid
import pytest
from apps.leads.tests.factories import LeadFactory, QualifiedLeadFactory
from apps.accounts.tests.factories import AccountFactory
from apps.contacts.tests.factories import ContactFactory


@pytest.mark.contract
class TestListLeads:
    def test_returns_200(self, auth_client, salesperson):
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/leads/')
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        QualifiedLeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/leads/?statecode=0')
        assert response.status_code == 200
        data = response.json()
        assert all(item['statecode'] == 0 for item in data)

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/leads/')
        assert response.status_code == 403


@pytest.mark.contract
class TestListLeadsPaginated:
    """Offset-based paginated listing (opt-in)."""

    def _make(self, salesperson, n=3):
        return [
            LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
            for _ in range(n)
        ]

    def test_returns_paginated_shape(self, auth_client, salesperson):
        self._make(salesperson, 3)
        response = auth_client.get('/api/leads/paginated/?page=1&page_size=2')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 3
        assert body['page'] == 1
        assert body['page_size'] == 2
        assert len(body['results']) == 2
        assert body['next'] is not None
        assert body['previous'] is None

    def test_second_page(self, auth_client, salesperson):
        self._make(salesperson, 3)
        response = auth_client.get('/api/leads/paginated/?page=2&page_size=2')
        body = response.json()
        assert len(body['results']) == 1
        assert body['previous'] is not None

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/leads/paginated/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateLead:
    def test_creates_lead(self, auth_client, salesperson):
        payload = {'lastname': 'TestDoe', 'firstname': 'John', 'emailaddress1': 'jdoe@test.com'}
        response = auth_client.post('/api/leads/', payload, content_type='application/json')
        assert response.status_code == 201
        data = response.json()
        assert data['lastname'] == 'TestDoe'

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'lastname': 'Blocked'}
        response = readonly_auth_client.post('/api/leads/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetLead:
    def test_returns_lead(self, auth_client, salesperson):
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/leads/{lead.leadid}')
        assert response.status_code == 200
        assert response.json()['leadid'] == str(lead.leadid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/leads/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateLead:
    def test_updates_lead(self, auth_client, salesperson):
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/leads/{lead.leadid}',
            {'firstname': 'Updated'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['firstname'] == 'Updated'


@pytest.mark.contract
class TestDeleteLead:
    def test_deletes_lead(self, admin_auth_client, system_admin):
        lead = LeadFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/leads/{lead.leadid}')
        assert response.status_code == 204

    def test_readonly_cannot_delete(self, readonly_auth_client, readonly_user):
        lead = LeadFactory(ownerid=readonly_user, createdby=readonly_user, modifiedby=readonly_user)
        response = readonly_auth_client.delete(f'/api/leads/{lead.leadid}')
        assert response.status_code == 403


@pytest.mark.contract
class TestQualifyLead:
    def test_qualify_lead(self, auth_client, salesperson):
        lead = LeadFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            companyname='ACME Corp', emailaddress1='lead@acme.com',
        )
        payload = {
            'createAccount': True, 'createContact': True,
            'opportunityName': 'New Opp',
        }
        response = auth_client.post(
            f'/api/leads/{lead.leadid}/qualify',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'opportunityId' in data


@pytest.mark.contract
class TestDisqualifyLead:
    def test_disqualify_lead(self, auth_client, salesperson):
        lead = LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/leads/{lead.leadid}/disqualify',
            {'reason': 'Not interested'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['statecode'] == 2  # DISQUALIFIED


@pytest.mark.contract
class TestLeadStats:
    def test_returns_stats(self, auth_client, salesperson):
        LeadFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/leads/stats')
        assert response.status_code == 200
        data = response.json()
        assert 'total_leads' in data
