"""Basic model tests for Machinery module."""

import pytest
from django.db import IntegrityError
from apps.machinery.tests.factories import (
    EquipmentCategoryFactory,
    EquipmentBrandFactory,
    EquipmentModelFactory,
    EquipmentFactory,
    RentedEquipmentFactory,
    EquipmentInsuranceFactory,
)
from apps.machinery.models import (
    EquipmentStateCode,
    OwnershipTypeCode,
    OperationalStatusCode,
    InsuranceStateCode,
)


@pytest.mark.unit
class TestEquipmentCategory:
    def test_create_category(self, db):
        category = EquipmentCategoryFactory()
        assert category.categoryid is not None
        assert category.statecode == EquipmentStateCode.ACTIVE
        assert category.code is not None

    def test_str_representation(self, db):
        category = EquipmentCategoryFactory(code='EXC', name='Excavadoras')
        assert str(category) == 'EXC - Excavadoras'

    def test_unique_code_constraint(self, db):
        EquipmentCategoryFactory(code='UNIQ01')
        with pytest.raises(IntegrityError):
            EquipmentCategoryFactory(code='UNIQ01')


@pytest.mark.unit
class TestEquipmentBrand:
    def test_create_brand(self, db):
        brand = EquipmentBrandFactory()
        assert brand.brandid is not None
        assert brand.statecode == EquipmentStateCode.ACTIVE
        assert brand.code is not None

    def test_str_representation(self, db):
        brand = EquipmentBrandFactory(name='Caterpillar')
        assert str(brand) == 'Caterpillar'

    def test_unique_name_constraint(self, db):
        EquipmentBrandFactory(name='UniqueBrand')
        with pytest.raises(IntegrityError):
            EquipmentBrandFactory(name='UniqueBrand')

    def test_unique_code_constraint(self, db):
        EquipmentBrandFactory(code='UNQ')
        with pytest.raises(IntegrityError):
            EquipmentBrandFactory(code='UNQ')


@pytest.mark.unit
class TestEquipmentModel:
    def test_create_model(self, db):
        eq_model = EquipmentModelFactory()
        assert eq_model.modelid is not None
        assert eq_model.statecode == EquipmentStateCode.ACTIVE
        assert eq_model.brandid is not None

    def test_str_representation(self, db):
        brand = EquipmentBrandFactory(name='Caterpillar')
        eq_model = EquipmentModelFactory(brandid=brand, name='320F')
        assert str(eq_model) == 'Caterpillar 320F'

    def test_unique_model_per_brand(self, db):
        brand = EquipmentBrandFactory()
        EquipmentModelFactory(brandid=brand, name='SameModel')
        with pytest.raises(IntegrityError):
            EquipmentModelFactory(brandid=brand, name='SameModel')

    def test_same_model_name_different_brands(self, db):
        brand1 = EquipmentBrandFactory()
        brand2 = EquipmentBrandFactory()
        m1 = EquipmentModelFactory(brandid=brand1, name='200')
        m2 = EquipmentModelFactory(brandid=brand2, name='200')
        assert m1.modelid != m2.modelid


@pytest.mark.unit
class TestEquipment:
    def test_create_equipment(self, db):
        equipment = EquipmentFactory()
        assert equipment.equipmentid is not None
        assert equipment.statecode == EquipmentStateCode.ACTIVE
        assert equipment.operationalstatus == OperationalStatusCode.DISPONIBLE
        assert equipment.ownershiptype == OwnershipTypeCode.PROPIO
        assert equipment.brandid is not None
        assert equipment.modelid is not None

    def test_str_representation(self, db):
        brand = EquipmentBrandFactory(name='Caterpillar')
        eq_model = EquipmentModelFactory(brandid=brand, name='320D')
        equipment = EquipmentFactory(
            equipmentnumber='MAQ-001',
            brandid=brand,
            modelid=eq_model,
            brand='Caterpillar',
            model='320D'
        )
        assert str(equipment) == 'MAQ-001 - Caterpillar 320D'

    def test_unique_equipmentnumber_constraint(self, db):
        EquipmentFactory(equipmentnumber='MAQ-DUP')
        with pytest.raises(IntegrityError):
            EquipmentFactory(equipmentnumber='MAQ-DUP')

    def test_rented_equipment(self, db):
        equipment = RentedEquipmentFactory()
        assert equipment.ownershiptype == OwnershipTypeCode.RENTADO_DE_TERCERO
        assert equipment.acquisitioncost is None
        assert equipment.purchasedate is None

    def test_denormalized_brand_model(self, db):
        brand = EquipmentBrandFactory(name='Komatsu')
        eq_model = EquipmentModelFactory(brandid=brand, name='PC200-8')
        equipment = EquipmentFactory(
            brandid=brand,
            modelid=eq_model,
        )
        assert equipment.brand == 'Komatsu'
        assert equipment.model == 'PC200-8'


@pytest.mark.unit
class TestEquipmentInsurance:
    def test_create_insurance(self, db):
        insurance = EquipmentInsuranceFactory()
        assert insurance.insuranceid is not None
        assert insurance.statecode == InsuranceStateCode.VIGENTE
        assert insurance.equipmentid is not None

    def test_str_representation(self, db):
        insurance = EquipmentInsuranceFactory(policynumber='POL-TEST-001')
        assert 'POL-TEST-001' in str(insurance)

    def test_cascade_delete(self, db):
        insurance = EquipmentInsuranceFactory()
        equipment_id = insurance.equipmentid.equipmentid
        # Deleting equipment should cascade to insurance
        insurance.equipmentid.delete()
        from apps.machinery.models import EquipmentInsurance
        assert not EquipmentInsurance.objects.filter(
            equipmentid=equipment_id
        ).exists()
