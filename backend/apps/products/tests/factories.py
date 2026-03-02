"""Factory Boy factories for Product and PriceList models."""

import factory
from factory.django import DjangoModelFactory
from decimal import Decimal
from apps.products.models import Product, PriceList, PriceListItem, ProductStateCode
from apps.users.tests.factories import SalespersonFactory


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f'Product {n}')
    productnumber = factory.Sequence(lambda n: f'SKU-{n:05d}')
    price = factory.LazyFunction(lambda: Decimal('99.99'))
    statecode = ProductStateCode.ACTIVE
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class PriceListFactory(DjangoModelFactory):
    class Meta:
        model = PriceList

    name = factory.Sequence(lambda n: f'Price List {n}')
    statecode = ProductStateCode.ACTIVE


class PriceListItemFactory(DjangoModelFactory):
    class Meta:
        model = PriceListItem

    pricelevelid = factory.SubFactory(PriceListFactory)
    productid = factory.SubFactory(ProductFactory)
    amount = factory.LazyFunction(lambda: Decimal('49.99'))
