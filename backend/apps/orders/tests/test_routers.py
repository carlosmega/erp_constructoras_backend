"""Router tests for Order Management API endpoints."""

import uuid
import pytest
from apps.orders.tests.factories import (
    SalesOrderFactory, SalesOrderDetailFactory,
    SubmittedOrderFactory, FulfilledOrderFactory,
)
from apps.quotes.tests.factories import WonQuoteFactory


@pytest.mark.contract
class TestListOrders:
    def test_returns_200(self, auth_client, salesperson):
        SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/orders/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/orders/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/orders/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateOrder:
    def test_creates_order(self, auth_client, salesperson):
        from apps.accounts.tests.factories import AccountFactory
        account = AccountFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        payload = {
            'name': 'Test Order',
            'accountid': str(account.accountid),
        }
        response = auth_client.post('/api/orders/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['name'] == 'Test Order'

    def test_readonly_denied(self, readonly_auth_client):
        payload = {'name': 'Blocked'}
        response = readonly_auth_client.post('/api/orders/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetOrder:
    def test_returns_order(self, auth_client, salesperson):
        order = SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/orders/{order.salesorderid}')
        assert response.status_code == 200
        assert response.json()['salesorderid'] == str(order.salesorderid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/orders/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestUpdateOrder:
    def test_updates_order(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/orders/{order.salesorderid}',
            {'name': 'Updated Order'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Order'


@pytest.mark.contract
class TestDeleteOrder:
    def test_deletes_active_order(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/orders/{order.salesorderid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestOrderDetails:
    def test_get_detail(self, auth_client, salesperson):
        order = SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        response = auth_client.get(f'/api/orders/details/{detail.salesorderdetailid}')
        assert response.status_code == 200

    def test_remove_detail(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        detail = SalesOrderDetailFactory(salesorderid=order)
        response = admin_auth_client.delete(f'/api/orders/details/{detail.salesorderdetailid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestOrderActions:
    def test_submit_order(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(f'/api/orders/{order.salesorderid}/submit')
        assert response.status_code == 200

    def test_fulfill_order(self, admin_auth_client, system_admin):
        order = SubmittedOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(
            f'/api/orders/{order.salesorderid}/fulfill',
            {},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_cancel_order(self, admin_auth_client, system_admin):
        order = SalesOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(f'/api/orders/{order.salesorderid}/cancel')
        assert response.status_code == 200


@pytest.mark.contract
class TestOrderStats:
    def test_returns_stats(self, auth_client, salesperson):
        SalesOrderFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/orders/stats/summary')
        assert response.status_code == 200
