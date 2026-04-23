"""Router tests for Opportunity Management API endpoints."""

import uuid
import pytest
from apps.opportunities.tests.factories import OpportunityFactory
from apps.accounts.tests.factories import AccountFactory


@pytest.mark.contract
class TestListOpportunities:
    def test_returns_200(self, auth_client, salesperson):
        OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/opportunities/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/opportunities/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/opportunities/')
        assert response.status_code == 403


@pytest.mark.contract
class TestListOpportunitiesPaginated:
    """Offset-based paginated listing (opt-in)."""

    def test_returns_paginated_shape(self, auth_client, salesperson):
        for _ in range(3):
            OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/opportunities/paginated/?page=1&page_size=2')
        assert response.status_code == 200
        body = response.json()
        assert body['count'] == 3
        assert len(body['results']) == 2
        assert body['next'] is not None

    def test_second_page(self, auth_client, salesperson):
        for _ in range(3):
            OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/opportunities/paginated/?page=2&page_size=2')
        body = response.json()
        assert len(body['results']) == 1
        assert body['previous'] is not None

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/opportunities/paginated/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateOpportunity:
    def test_creates_opportunity(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'name': 'Test Opportunity',
            'accountid': str(account.accountid),
            'estimatedrevenue': '50000.00',
        }
        response = auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Opportunity'

    def test_readonly_denied(self, readonly_auth_client, readonly_user):
        payload = {'name': 'Blocked', 'accountid': str(uuid.uuid4())}
        response = readonly_auth_client.post('/api/opportunities/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetOpportunity:
    def test_returns_opportunity(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/opportunities/{opp.opportunityid}')
        assert response.status_code == 200
        assert response.json()['opportunityid'] == str(opp.opportunityid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/opportunities/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateOpportunity:
    def test_updates_opportunity(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/opportunities/{opp.opportunityid}',
            {'name': 'Updated Opp'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Opp'


@pytest.mark.contract
class TestDeleteOpportunity:
    def test_deletes_opportunity(self, admin_auth_client, system_admin):
        opp = OpportunityFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/opportunities/{opp.opportunityid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestCloseOpportunity:
    def test_close_won(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/opportunities/{opp.opportunityid}/close',
            {'status': 3, 'actualrevenue': '50000.00'},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_close_lost(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/opportunities/{opp.opportunityid}/close',
            {'status': 5},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestOpportunityStats:
    def test_returns_stats(self, auth_client, salesperson):
        OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/opportunities/stats')
        assert response.status_code == 200
