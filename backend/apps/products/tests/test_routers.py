"""Router tests for Product and PriceList API endpoints."""

import uuid
import pytest
from apps.products.tests.factories import ProductFactory, PriceListFactory, PriceListItemFactory


@pytest.mark.contract
class TestListProducts:
    def test_returns_200(self, auth_client, salesperson):
        ProductFactory(createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/products/')
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_filter_by_state(self, auth_client, salesperson):
        ProductFactory(createdby=salesperson, modifiedby=salesperson, statecode=0)
        response = auth_client.get('/api/products/?state=0')
        assert response.status_code == 200

    def test_search(self, auth_client, salesperson):
        ProductFactory(createdby=salesperson, modifiedby=salesperson, name='UniqueWidget')
        response = auth_client.get('/api/products/?search=UniqueWidget')
        assert response.status_code == 200

    def test_unauthenticated_returns_403(self, db):
        from django.test import Client
        response = Client().get('/api/products/')
        assert response.status_code == 403


@pytest.mark.contract
class TestCreateProduct:
    def test_creates_product(self, admin_auth_client, system_admin):
        payload = {'name': 'New Product', 'price': '29.99', 'productnumber': 'NP-001'}
        response = admin_auth_client.post('/api/products/', payload, content_type='application/json')
        assert response.status_code == 201
        assert response.json()['name'] == 'New Product'

    def test_salesperson_cannot_create(self, auth_client):
        payload = {'name': 'Blocked'}
        response = auth_client.post('/api/products/', payload, content_type='application/json')
        assert response.status_code == 403


@pytest.mark.contract
class TestGetProduct:
    def test_returns_product(self, auth_client, salesperson):
        product = ProductFactory(createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get(f'/api/products/{product.productid}')
        assert response.status_code == 200
        assert response.json()['productid'] == str(product.productid)


@pytest.mark.contract
class TestUpdateProduct:
    def test_updates_product(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.patch(
            f'/api/products/{product.productid}',
            {'name': 'Updated Product'},
            content_type='application/json',
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'Updated Product'


@pytest.mark.contract
class TestDeleteProduct:
    def test_deletes_product(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin)
        response = admin_auth_client.delete(f'/api/products/{product.productid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestProductActions:
    def test_activate_product(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin, statecode=1)
        response = admin_auth_client.post(f'/api/products/{product.productid}/activate')
        assert response.status_code == 200

    def test_deactivate_product(self, admin_auth_client, system_admin):
        product = ProductFactory(createdby=system_admin, modifiedby=system_admin, statecode=0)
        response = admin_auth_client.post(f'/api/products/{product.productid}/deactivate')
        assert response.status_code == 200


@pytest.mark.contract
class TestProductStats:
    def test_returns_stats(self, auth_client, salesperson):
        ProductFactory(createdby=salesperson, modifiedby=salesperson)
        response = auth_client.get('/api/products/stats/summary')
        assert response.status_code == 200


@pytest.mark.contract
class TestPriceLists:
    def test_list_pricelists(self, auth_client, salesperson):
        PriceListFactory()
        response = auth_client.get('/api/pricelists/')
        assert response.status_code == 200

    def test_create_pricelist(self, admin_auth_client, system_admin):
        payload = {'name': 'Standard Prices'}
        response = admin_auth_client.post('/api/pricelists/', payload, content_type='application/json')
        assert response.status_code == 201

    def test_get_pricelist(self, auth_client, salesperson):
        pl = PriceListFactory()
        response = auth_client.get(f'/api/pricelists/{pl.pricelevelid}')
        assert response.status_code == 200

    def test_delete_pricelist(self, admin_auth_client, system_admin):
        pl = PriceListFactory()
        response = admin_auth_client.delete(f'/api/pricelists/{pl.pricelevelid}')
        assert response.status_code == 204


@pytest.mark.contract
class TestPriceListItems:
    def test_list_items(self, auth_client, salesperson):
        item = PriceListItemFactory()
        response = auth_client.get(f'/api/pricelists/{item.pricelevelid.pricelevelid}/items')
        assert response.status_code == 200

    def test_delete_item(self, admin_auth_client, system_admin):
        item = PriceListItemFactory()
        response = admin_auth_client.delete(f'/api/pricelists/items/{item.productpricelevelid}')
        assert response.status_code == 204
