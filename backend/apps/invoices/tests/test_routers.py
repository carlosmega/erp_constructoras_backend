"""Router tests for Invoice Management API endpoints."""

import uuid
from decimal import Decimal
import pytest
from apps.invoices.tests.factories import InvoiceFactory, InvoiceDetailFactory
from apps.orders.tests.factories import FulfilledOrderFactory


@pytest.mark.contract
class TestListInvoices:
    def test_returns_200(self, auth_client, salesperson):
        InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/invoices/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_statecode(self, auth_client, salesperson):
        InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/invoices/?statecode=0')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/invoices/')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetInvoice:
    def test_returns_invoice(self, auth_client, salesperson):
        inv = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/invoices/{inv.invoiceid}')
        assert response.status_code == 200
        assert response.json()['invoiceid'] == str(inv.invoiceid)

    def test_not_found(self, auth_client):
        response = auth_client.get(f'/api/invoices/{uuid.uuid4()}')
        assert response.status_code == 404


@pytest.mark.contract
class TestCreateInvoice:
    def test_creates_invoice(self, admin_auth_client, system_admin):
        from apps.accounts.tests.factories import AccountFactory
        account = AccountFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'name': 'Test Invoice',
            'accountid': str(account.accountid),
        }
        response = admin_auth_client.post('/api/invoices/', payload, content_type='application/json')
        assert response.status_code == 201


@pytest.mark.contract
class TestUpdateInvoice:
    def test_updates_invoice(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/invoices/{inv.invoiceid}',
            {'name': 'Updated Invoice'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Invoice'


@pytest.mark.contract
class TestDeleteInvoice:
    def test_deletes_invoice(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/invoices/{inv.invoiceid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestInvoiceDetails:
    def test_list_details(self, auth_client, salesperson):
        inv = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        InvoiceDetailFactory(invoiceid=inv)
        response = auth_client.get(f'/api/invoices/{inv.invoiceid}/details')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_add_detail(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        payload = {
            'productname': 'Service Fee',
            'quantity': 1,
            'priceperunit': '500.00',
        }
        response = admin_auth_client.post(
            f'/api/invoices/{inv.invoiceid}/details',
            payload,
            content_type='application/json',
        )
        assert response.status_code == 201

    def test_get_detail(self, auth_client, salesperson):
        inv = InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        detail = InvoiceDetailFactory(invoiceid=inv)
        response = auth_client.get(f'/api/invoices/details/{detail.invoicedetailid}')
        assert response.status_code == 200

    def test_remove_detail(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        detail = InvoiceDetailFactory(invoiceid=inv)
        response = admin_auth_client.delete(f'/api/invoices/details/{detail.invoicedetailid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestInvoiceActions:
    def test_record_payment(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
            totalamount=Decimal('1000.00'), totalamountdue=Decimal('1000.00'),
        )
        response = admin_auth_client.post(
            f'/api/invoices/{inv.invoiceid}/record-payment',
            {'payment_amount': '100.00'},
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_cancel_invoice(self, admin_auth_client, system_admin):
        inv = InvoiceFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(
            f'/api/invoices/{inv.invoiceid}/cancel',
            {'reason': 'Duplicate'},
            content_type='application/json',
        )
        assert response.status_code == 200


@pytest.mark.contract
class TestInvoiceStats:
    def test_returns_stats(self, auth_client, salesperson):
        InvoiceFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/invoices/stats/summary')
        assert response.status_code == 200


@pytest.mark.contract
class TestCreateInvoiceFromOrder:
    def test_creates_from_order(self, admin_auth_client, system_admin):
        order = FulfilledOrderFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.post(f'/api/invoices/from-order/{order.salesorderid}')
        assert response.status_code == 201
