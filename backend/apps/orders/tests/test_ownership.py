"""Record-level ownership enforcement on order / order-detail operations.

Before the fix the detail endpoints fetched rows with a bare get_object_or_404
(no ownership check), so a Salesperson could read/modify/delete line items on
orders owned by other sales users. These tests pin the enforcement.
"""

from types import SimpleNamespace

import pytest

from core.exceptions import PermissionDenied
from apps.orders.services import OrderService
from apps.orders.tests.factories import SalesOrderFactory, SalesOrderDetailFactory


@pytest.mark.django_db
class TestOrderDetailOwnership:
    def test_owner_can_read_own_order_detail(self, salesperson):
        order = SalesOrderFactory(ownerid=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        got = OrderService.get_order_detail(detail.salesorderdetailid, salesperson)
        assert got.salesorderdetailid == detail.salesorderdetailid

    def test_salesperson_cannot_read_another_users_order_detail(self, salesperson, salesperson2):
        order = SalesOrderFactory(ownerid=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        with pytest.raises(PermissionDenied):
            OrderService.get_order_detail(detail.salesorderdetailid, salesperson2)

    def test_salesperson_cannot_update_another_users_order_detail(self, salesperson, salesperson2):
        order = SalesOrderFactory(ownerid=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        payload = SimpleNamespace(
            productdescription="hacked", quantity=None, priceperunit=None,
            manualdiscountamount=None, tax=None,
        )
        with pytest.raises(PermissionDenied):
            OrderService.update_order_detail(detail.salesorderdetailid, payload, salesperson2)

    def test_salesperson_cannot_remove_another_users_order_detail(self, salesperson, salesperson2):
        order = SalesOrderFactory(ownerid=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        with pytest.raises(PermissionDenied):
            OrderService.remove_order_detail(detail.salesorderdetailid, salesperson2)

    def test_admin_can_access_any_order_detail(self, salesperson, system_admin):
        order = SalesOrderFactory(ownerid=salesperson)
        detail = SalesOrderDetailFactory(salesorderid=order)
        got = OrderService.get_order_detail(detail.salesorderdetailid, system_admin)
        assert got.salesorderdetailid == detail.salesorderdetailid

    def test_salesperson_cannot_delete_another_users_order(self, salesperson, salesperson2):
        order = SalesOrderFactory(ownerid=salesperson)
        with pytest.raises(PermissionDenied):
            OrderService.delete_order(order.salesorderid, salesperson2)
