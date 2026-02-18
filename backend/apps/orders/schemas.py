"""Order schemas - Phase 9"""
from ninja import ModelSchema, Schema
from typing import Optional, List
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from apps.orders.models import SalesOrder, SalesOrderDetail


class SalesOrderDetailSchema(ModelSchema):
    """Full SalesOrderDetail response schema."""
    class Meta:
        model = SalesOrderDetail
        fields = [
            'salesorderdetailid', 'salesorderid', 'productname', 'productdescription',
            'quantity', 'priceperunit', 'manualdiscountamount', 'tax',
            'baseamount', 'extendedamount', 'sequencenumber'
        ]


class SalesOrderSchema(ModelSchema):
    """Full SalesOrder response schema with nested details."""
    order_details: List[SalesOrderDetailSchema] = []
    customer_name: Optional[str] = None

    class Meta:
        model = SalesOrder
        fields = [
            'salesorderid', 'name', 'ordernumber', 'quoteid', 'opportunityid',
            'accountid', 'contactid', 'totalamount', 'totaldiscountamount',
            'totaltax', 'totallineitemamount', 'requestdeliveryby', 'datefulfilled',
            'statecode', 'statuscode', 'description', 'ownerid',
            'createdon', 'modifiedon', 'createdby', 'modifiedby'
        ]


class SalesOrderListItemSchema(ModelSchema):
    """Simplified SalesOrder schema for list views."""
    customer_name: Optional[str] = None

    class Meta:
        model = SalesOrder
        fields = [
            'salesorderid', 'name', 'ordernumber', 'totalamount',
            'statecode', 'statuscode', 'requestdeliveryby',
            'createdon', 'ownerid'
        ]


class CreateSalesOrderDto(Schema):
    """DTO for creating a new sales order."""
    name: str
    quoteid: Optional[UUID] = None
    accountid: Optional[UUID] = None
    contactid: Optional[UUID] = None
    requestdeliveryby: Optional[date] = None
    description: Optional[str] = None


class UpdateSalesOrderDto(Schema):
    """DTO for updating a sales order."""
    name: Optional[str] = None
    requestdeliveryby: Optional[date] = None
    description: Optional[str] = None


class FulfillOrderDto(Schema):
    """DTO for fulfilling an order."""
    datefulfilled: Optional[datetime] = None


class OrderStatsSchema(Schema):
    """Statistics about orders."""
    total_orders: int
    active_orders: int
    submitted_orders: int
    fulfilled_orders: int
    canceled_orders: int
    total_value: Decimal
    fulfilled_value: Decimal
