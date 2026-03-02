"""Router tests for Quote Management API endpoints."""

import uuid
import pytest
from apps.quotes.tests.factories import QuoteFactory, QuoteDetailFactory, ActiveQuoteFactory
from apps.accounts.tests.factories import AccountFactory
from apps.opportunities.tests.factories import OpportunityFactory


@pytest.mark.contract
class TestListQuotes:
    def test_returns_200(self, auth_client, salesperson):
        QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/quotes/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/quotes/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/quotes/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateQuote:
    def test_creates_quote(self, auth_client, salesperson):
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        opp = OpportunityFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            accountid=account,
        )
        payload = {
            'name': 'Test Quote',
            'opportunityid': str(opp.opportunityid),
            'accountid': str(account.accountid),
        }
        response = auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Quote'

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'name': 'Blocked'}
        response = readonly_auth_client.post('/api/quotes/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetQuote:
    def test_returns_quote(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/quotes/{quote.quoteid}')
        assert response.status_code == 200
        assert response.json()['quoteid'] == str(quote.quoteid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/quotes/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateQuote:
    def test_updates_quote(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.patch(
            f'/api/quotes/{quote.quoteid}',
            {'name': 'Updated Quote'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Quote'


@pytest.mark.contract
class TestDeleteQuote:
    def test_deletes_draft_quote(self, admin_auth_client, system_admin):
        quote = QuoteFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/quotes/{quote.quoteid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestQuoteDetails:
    def test_list_details(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        QuoteDetailFactory(quoteid=quote)
        response = auth_client.get(f'/api/quotes/{quote.quoteid}/details')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_add_detail(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'productname': 'Test Product',
            'quantity': 5,
            'priceperunit': '100.00',
        }
        response = auth_client.post(
            f'/api/quotes/{quote.quoteid}/details',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_get_detail(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)
        response = auth_client.get(f'/api/quotes/details/{detail.quotedetailid}')
        assert response.status_code == 200

    def test_update_detail(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)
        response = auth_client.patch(
            f'/api/quotes/details/{detail.quotedetailid}',
            {'quantity': 10},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_remove_detail(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        detail = QuoteDetailFactory(quoteid=quote)
        response = auth_client.delete(f'/api/quotes/details/{detail.quotedetailid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestQuoteActions:
    def test_activate_quote(self, auth_client, salesperson):
        quote = QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        QuoteDetailFactory(quoteid=quote)
        response = auth_client.post(
            f'/api/quotes/{quote.quoteid}/activate',
            {},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_close_quote_won(self, auth_client, salesperson):
        quote = ActiveQuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(
            f'/api/quotes/{quote.quoteid}/close',
            {'statuscode': 3},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestQuoteStats:
    def test_returns_stats(self, auth_client, salesperson):
        QuoteFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/quotes/stats/summary')
        assert response.status_code == 200


@pytest.mark.contract
class TestCreateQuoteFromOpportunity:
    def test_creates_from_opportunity(self, auth_client, salesperson):
        opp = OpportunityFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.post(f'/api/quotes/from-opportunity/{opp.opportunityid}')
        assert response.status_code == 201
