"""Service tests for Machinery module."""

import pytest
from datetime import date
from decimal import Decimal

from apps.machinery.services import (
    EquipmentCategoryService,
    EquipmentBrandService,
    EquipmentModelService,
    EquipmentService,
    EquipmentInsuranceService,
)
from apps.machinery.schemas import (
    CreateEquipmentCategoryDto,
    CreateEquipmentBrandDto,
    CreateEquipmentModelDto,
    CreateEquipmentDto,
    CreateEquipmentInsuranceDto,
)
from apps.machinery.models import (
    OwnershipTypeCode,
    InsuranceTypeCode,
)
from apps.machinery.tests.factories import (
    EquipmentCategoryFactory,
    EquipmentBrandFactory,
    EquipmentModelFactory,
    EquipmentFactory,
)
from core.exceptions import ValidationError, NotFound


@pytest.mark.unit
class TestEquipmentCategoryService:
    def test_create_category(self, system_admin):
        dto = CreateEquipmentCategoryDto(
            name='Excavadoras',
            code='EXC',
            description='Heavy excavators',
            estimatedfuelconsumption=Decimal('25.00'),
        )
        category = EquipmentCategoryService.create_category(dto, system_admin)
        assert category.name == 'Excavadoras'
        assert category.code == 'EXC'

    def test_create_category_duplicate_code(self, system_admin):
        EquipmentCategoryFactory(code='DUP')
        dto = CreateEquipmentCategoryDto(name='Duplicate', code='DUP')
        with pytest.raises(ValidationError):
            EquipmentCategoryService.create_category(dto, system_admin)

    def test_list_categories(self, system_admin):
        EquipmentCategoryFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentCategoryFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        categories = EquipmentCategoryService.list_categories(system_admin)
        assert categories.count() >= 2


@pytest.mark.unit
class TestEquipmentBrandService:
    def test_create_brand(self, system_admin):
        dto = CreateEquipmentBrandDto(
            name='Caterpillar',
            code='CAT',
            country='Estados Unidos',
        )
        brand = EquipmentBrandService.create_brand(dto, system_admin)
        assert brand.name == 'Caterpillar'
        assert brand.code == 'CAT'
        assert brand.country == 'Estados Unidos'

    def test_create_brand_duplicate_code(self, system_admin):
        EquipmentBrandFactory(code='DUP', ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        dto = CreateEquipmentBrandDto(name='Other', code='DUP')
        with pytest.raises(ValidationError):
            EquipmentBrandService.create_brand(dto, system_admin)

    def test_create_brand_duplicate_name(self, system_admin):
        EquipmentBrandFactory(name='SameName', ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        dto = CreateEquipmentBrandDto(name='SameName', code='NEW')
        with pytest.raises(ValidationError):
            EquipmentBrandService.create_brand(dto, system_admin)

    def test_list_brands(self, system_admin):
        EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        brands = EquipmentBrandService.list_brands(system_admin)
        assert brands.count() >= 2


@pytest.mark.unit
class TestEquipmentModelService:
    def test_create_model(self, system_admin):
        brand = EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        dto = CreateEquipmentModelDto(
            brandid=brand.brandid,
            name='320F',
        )
        eq_model = EquipmentModelService.create_model(dto, system_admin)
        assert eq_model.name == '320F'
        assert eq_model.brandid == brand

    def test_create_model_with_category(self, system_admin):
        brand = EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        category = EquipmentCategoryFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        dto = CreateEquipmentModelDto(
            brandid=brand.brandid,
            name='PC200-8',
            categoryid=category.categoryid,
        )
        eq_model = EquipmentModelService.create_model(dto, system_admin)
        assert eq_model.categoryid == category

    def test_create_model_duplicate_per_brand(self, system_admin):
        brand = EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentModelFactory(brandid=brand, name='320F', ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        dto = CreateEquipmentModelDto(brandid=brand.brandid, name='320F')
        with pytest.raises(ValidationError):
            EquipmentModelService.create_model(dto, system_admin)

    def test_list_models_filter_by_brand(self, system_admin):
        brand1 = EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        brand2 = EquipmentBrandFactory(ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentModelFactory(brandid=brand1, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentModelFactory(brandid=brand1, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)
        EquipmentModelFactory(brandid=brand2, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin)

        models_b1 = EquipmentModelService.list_models(system_admin, brandid=brand1.brandid)
        assert models_b1.count() == 2

        models_b2 = EquipmentModelService.list_models(system_admin, brandid=brand2.brandid)
        assert models_b2.count() == 1


@pytest.mark.unit
class TestEquipmentService:
    def test_create_equipment_auto_numbering(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.PROPIO,
            brandid=brand.brandid,
            modelid=eq_model.modelid,
            year=2023,
            serialnumber='SN000001',
            acquisitioncost=Decimal('2500000.00'),
            purchasedate=date.today(),
        )
        eq1 = EquipmentService.create_equipment(dto, system_admin)
        assert eq1.equipmentnumber == 'MAQ-001'
        assert eq1.brand == brand.name
        assert eq1.model == eq_model.name

        eq_model2 = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto2 = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.PROPIO,
            brandid=brand.brandid,
            modelid=eq_model2.modelid,
            year=2024,
            serialnumber='SN000002',
            acquisitioncost=Decimal('3000000.00'),
            purchasedate=date.today(),
        )
        eq2 = EquipmentService.create_equipment(dto2, system_admin)
        assert eq2.equipmentnumber == 'MAQ-002'

    def test_create_equipment_propio_requires_cost(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.PROPIO,
            brandid=brand.brandid,
            modelid=eq_model.modelid,
            year=2023,
            serialnumber='SN-NOCOAST',
        )
        with pytest.raises(ValidationError, match="Acquisition cost"):
            EquipmentService.create_equipment(dto, system_admin)

    def test_create_equipment_propio_requires_date(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.PROPIO,
            brandid=brand.brandid,
            modelid=eq_model.modelid,
            year=2023,
            serialnumber='SN-NODATE',
            acquisitioncost=Decimal('1000000.00'),
        )
        with pytest.raises(ValidationError, match="Purchase date"):
            EquipmentService.create_equipment(dto, system_admin)

    def test_create_rented_equipment_no_cost_required(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.RENTADO_DE_TERCERO,
            brandid=brand.brandid,
            modelid=eq_model.modelid,
            year=2022,
            serialnumber='SN-RENTED',
        )
        equipment = EquipmentService.create_equipment(dto, system_admin)
        assert equipment.ownershiptype == OwnershipTypeCode.RENTADO_DE_TERCERO
        assert equipment.acquisitioncost is None

    def test_create_equipment_model_brand_mismatch(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand1 = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand2 = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand1, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentDto(
            categoryid=category.categoryid,
            ownershiptype=OwnershipTypeCode.RENTADO_DE_TERCERO,
            brandid=brand2.brandid,  # Different brand than model's
            modelid=eq_model.modelid,
            year=2023,
            serialnumber='SN-MISMATCH',
        )
        with pytest.raises(ValidationError, match="does not belong to brand"):
            EquipmentService.create_equipment(dto, system_admin)

    def test_list_equipment_with_filters(self, system_admin):
        category = EquipmentCategoryFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        brand = EquipmentBrandFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        eq_model = EquipmentModelFactory(
            brandid=brand, ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        EquipmentFactory(
            categoryid=category, brandid=brand, modelid=eq_model,
            ownershiptype=OwnershipTypeCode.PROPIO,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        EquipmentFactory(
            categoryid=category, brandid=brand, modelid=eq_model,
            ownershiptype=OwnershipTypeCode.RENTADO_DE_TERCERO,
            acquisitioncost=None, purchasedate=None,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )

        propio = EquipmentService.list_equipment(
            system_admin, ownershiptype=OwnershipTypeCode.PROPIO
        )
        assert propio.count() >= 1

        rented = EquipmentService.list_equipment(
            system_admin, ownershiptype=OwnershipTypeCode.RENTADO_DE_TERCERO
        )
        assert rented.count() >= 1


@pytest.mark.unit
class TestEquipmentInsuranceService:
    def test_create_insurance(self, system_admin):
        equipment = EquipmentFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentInsuranceDto(
            insurancetype=InsuranceTypeCode.TODO_RIESGO,
            insurancecompany='Seguros Monterrey',
            policynumber='POL-SVC-001',
            startdate=date(2026, 1, 1),
            expirydate=date(2027, 1, 1),
            annualpremium=Decimal('50000.00'),
            monthlypremium=Decimal('4166.67'),
            insuredamount=Decimal('2500000.00'),
        )
        insurance = EquipmentInsuranceService.create_insurance(
            equipment.equipmentid, dto, system_admin
        )
        assert insurance.policynumber == 'POL-SVC-001'
        assert insurance.equipmentid == equipment

    def test_create_insurance_invalid_dates(self, system_admin):
        equipment = EquipmentFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        dto = CreateEquipmentInsuranceDto(
            insurancetype=InsuranceTypeCode.DANO_FISICO,
            insurancecompany='Test Insurance',
            policynumber='POL-BAD',
            startdate=date(2027, 1, 1),
            expirydate=date(2026, 1, 1),  # Before start
            annualpremium=Decimal('10000.00'),
            monthlypremium=Decimal('833.33'),
            insuredamount=Decimal('500000.00'),
        )
        with pytest.raises(ValidationError, match="Expiry date"):
            EquipmentInsuranceService.create_insurance(
                equipment.equipmentid, dto, system_admin
            )

    def test_create_insurance_equipment_not_found(self, system_admin):
        import uuid
        fake_id = uuid.uuid4()
        dto = CreateEquipmentInsuranceDto(
            insurancetype=InsuranceTypeCode.TODO_RIESGO,
            insurancecompany='Test',
            policynumber='POL-NF',
            startdate=date(2026, 1, 1),
            expirydate=date(2027, 1, 1),
            annualpremium=Decimal('10000.00'),
            monthlypremium=Decimal('833.33'),
            insuredamount=Decimal('500000.00'),
        )
        with pytest.raises(NotFound):
            EquipmentInsuranceService.create_insurance(fake_id, dto, system_admin)

    def test_list_insurance_by_equipment(self, system_admin):
        equipment = EquipmentFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin
        )
        from apps.machinery.tests.factories import EquipmentInsuranceFactory
        EquipmentInsuranceFactory(
            equipmentid=equipment,
            createdby=system_admin, modifiedby=system_admin
        )
        EquipmentInsuranceFactory(
            equipmentid=equipment,
            createdby=system_admin, modifiedby=system_admin
        )
        insurances = EquipmentInsuranceService.list_insurance(
            equipment.equipmentid, system_admin
        )
        assert insurances.count() == 2
