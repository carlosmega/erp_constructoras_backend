"""Factory Boy factories for Machinery module models."""

import factory
from datetime import date
from decimal import Decimal
from factory.django import DjangoModelFactory
from apps.machinery.models import (
    EquipmentCategory,
    EquipmentBrand,
    EquipmentModel,
    Equipment,
    EquipmentInsurance,
    EquipmentStateCode,
    OwnershipTypeCode,
    OperationalStatusCode,
    InsuranceTypeCode,
    InsuranceStateCode,
)
from apps.users.tests.factories import SalespersonFactory


class EquipmentCategoryFactory(DjangoModelFactory):
    class Meta:
        model = EquipmentCategory

    name = factory.Sequence(lambda n: f'Category {n + 1}')
    code = factory.Sequence(lambda n: f'CAT{n + 1:03d}')
    description = 'Test equipment category'
    estimatedfuelconsumption = Decimal('15.50')
    statecode = EquipmentStateCode.ACTIVE
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class EquipmentBrandFactory(DjangoModelFactory):
    class Meta:
        model = EquipmentBrand

    name = factory.Sequence(lambda n: f'Brand {n + 1}')
    code = factory.Sequence(lambda n: f'BRD{n + 1:03d}')
    country = 'Estados Unidos'
    statecode = EquipmentStateCode.ACTIVE
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class EquipmentModelFactory(DjangoModelFactory):
    class Meta:
        model = EquipmentModel

    brandid = factory.SubFactory(EquipmentBrandFactory)
    name = factory.Sequence(lambda n: f'Model {n + 1}')
    categoryid = factory.SubFactory(EquipmentCategoryFactory)
    statecode = EquipmentStateCode.ACTIVE
    ownerid = factory.SelfAttribute('brandid.ownerid')
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class EquipmentFactory(DjangoModelFactory):
    class Meta:
        model = Equipment

    equipmentnumber = factory.Sequence(lambda n: f'MAQ-{n + 1:03d}')
    categoryid = factory.SubFactory(EquipmentCategoryFactory)
    ownershiptype = OwnershipTypeCode.PROPIO
    brandid = factory.SubFactory(EquipmentBrandFactory)
    modelid = factory.SubFactory(EquipmentModelFactory, brandid=factory.SelfAttribute('..brandid'))
    brand = factory.LazyAttribute(lambda o: o.brandid.name)
    model = factory.LazyAttribute(lambda o: o.modelid.name)
    year = 2023
    serialnumber = factory.Sequence(lambda n: f'SN{n + 1:06d}')
    engineserialnumber = factory.Sequence(lambda n: f'ESN{n + 1:06d}')
    capacity = '20 ton'
    currenthourmeter = Decimal('1500.00')
    operationalstatus = OperationalStatusCode.DISPONIBLE
    acquisitioncost = Decimal('2500000.00')
    purchasedate = factory.LazyFunction(date.today)
    estimatedusefullifehours = 20000
    salvagevalue = Decimal('250000.00')
    statecode = EquipmentStateCode.ACTIVE
    ownerid = factory.SelfAttribute('categoryid.ownerid')
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class RentedEquipmentFactory(EquipmentFactory):
    ownershiptype = OwnershipTypeCode.RENTADO_DE_TERCERO
    acquisitioncost = None
    purchasedate = None
    salvagevalue = None


class EquipmentInsuranceFactory(DjangoModelFactory):
    class Meta:
        model = EquipmentInsurance

    equipmentid = factory.SubFactory(EquipmentFactory)
    insurancetype = InsuranceTypeCode.TODO_RIESGO
    insurancecompany = 'Seguros Monterrey'
    policynumber = factory.Sequence(lambda n: f'POL-{n + 1:06d}')
    startdate = factory.LazyFunction(date.today)
    expirydate = factory.LazyFunction(lambda: date(2027, 12, 31))
    annualpremium = Decimal('45000.00')
    monthlypremium = Decimal('3750.00')
    insuredamount = Decimal('2500000.00')
    statecode = InsuranceStateCode.VIGENTE
    createdby = factory.SelfAttribute('equipmentid.ownerid')
    modifiedby = factory.SelfAttribute('equipmentid.ownerid')
