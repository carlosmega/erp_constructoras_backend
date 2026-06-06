"""Machinery module business logic services."""

from typing import Optional
from uuid import UUID
from decimal import Decimal

from django.db import models, transaction
from django.db.models import Max, Sum, Count, Min, Q, F, Case, When, Value, DecimalField, IntegerField
from django.db.models.functions import Coalesce, ExtractIsoWeekDay

from apps.machinery.models import (
    EquipmentCategory,
    EquipmentBrand,
    EquipmentModel,
    Equipment,
    EquipmentInsurance,
    EquipmentStateCode,
    OwnershipTypeCode,
    JustificationReason,
    RentalContract,
    DailyEquipmentLog,
    BillingEstimation,
    EstimationDeduction,
    BillingModalityCode,
    ImputabilityCode,
    EstimationStatusCode,
)
from apps.machinery.schemas import (
    CreateEquipmentCategoryDto,
    UpdateEquipmentCategoryDto,
    CreateEquipmentBrandDto,
    UpdateEquipmentBrandDto,
    CreateEquipmentModelDto,
    UpdateEquipmentModelDto,
    CreateEquipmentDto,
    UpdateEquipmentDto,
    CreateEquipmentInsuranceDto,
    UpdateEquipmentInsuranceDto,
    CreateJustificationReasonDto,
    UpdateJustificationReasonDto,
    CreateRentalContractDto,
    UpdateRentalContractDto,
    CreateDailyEquipmentLogDto,
    UpdateDailyEquipmentLogDto,
    GenerateEstimationDto,
    CreateEstimationDeductionDto,
    UpdateEstimationStatusDto,
)
from core.exceptions import ValidationError, NotFound
from core.permissions import filter_by_ownership


# ============================================================================
# EquipmentCategoryService
# ============================================================================

class EquipmentCategoryService:
    """Service for equipment category CRUD."""

    @staticmethod
    def list_categories(user, statecode: Optional[int] = None):
        qs = EquipmentCategory.objects.all()
        qs = filter_by_ownership(qs, user)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('ownerid')

    @staticmethod
    def get_category(category_id: UUID, user):
        try:
            return EquipmentCategory.objects.select_related('ownerid').get(
                categoryid=category_id
            )
        except EquipmentCategory.DoesNotExist:
            raise NotFound(f"Equipment category {category_id} not found")

    @staticmethod
    def create_category(dto: CreateEquipmentCategoryDto, user):
        # Validate unique code
        if EquipmentCategory.objects.filter(code=dto.code).exists():
            raise ValidationError(f"Category code '{dto.code}' already exists")

        category = EquipmentCategory(
            name=dto.name,
            code=dto.code,
            description=dto.description,
            estimatedfuelconsumption=dto.estimatedfuelconsumption,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        category.save()
        return category

    @staticmethod
    def update_category(category_id: UUID, dto: UpdateEquipmentCategoryDto, user):
        category = EquipmentCategoryService.get_category(category_id, user)

        if dto.name is not None:
            category.name = dto.name
        if dto.code is not None:
            if dto.code != category.code and EquipmentCategory.objects.filter(code=dto.code).exists():
                raise ValidationError(f"Category code '{dto.code}' already exists")
            category.code = dto.code
        if dto.description is not None:
            category.description = dto.description
        if dto.estimatedfuelconsumption is not None:
            category.estimatedfuelconsumption = dto.estimatedfuelconsumption
        if dto.statecode is not None:
            category.statecode = dto.statecode

        category.modifiedby = user
        category.save()
        return category


# ============================================================================
# EquipmentBrandService
# ============================================================================

class EquipmentBrandService:
    """Service for equipment brand CRUD."""

    @staticmethod
    def list_brands(user, statecode: Optional[int] = None):
        qs = EquipmentBrand.objects.all()
        qs = filter_by_ownership(qs, user)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('ownerid')

    @staticmethod
    def get_brand(brand_id: UUID, user):
        try:
            return EquipmentBrand.objects.select_related('ownerid').get(
                brandid=brand_id
            )
        except EquipmentBrand.DoesNotExist:
            raise NotFound(f"Equipment brand {brand_id} not found")

    @staticmethod
    def create_brand(dto: CreateEquipmentBrandDto, user):
        if EquipmentBrand.objects.filter(code=dto.code).exists():
            raise ValidationError(f"Brand code '{dto.code}' already exists")
        if EquipmentBrand.objects.filter(name=dto.name).exists():
            raise ValidationError(f"Brand name '{dto.name}' already exists")

        brand = EquipmentBrand(
            name=dto.name,
            code=dto.code,
            country=dto.country,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        brand.save()
        return brand

    @staticmethod
    def update_brand(brand_id: UUID, dto: UpdateEquipmentBrandDto, user):
        brand = EquipmentBrandService.get_brand(brand_id, user)

        if dto.name is not None:
            if dto.name != brand.name and EquipmentBrand.objects.filter(name=dto.name).exists():
                raise ValidationError(f"Brand name '{dto.name}' already exists")
            brand.name = dto.name
        if dto.code is not None:
            if dto.code != brand.code and EquipmentBrand.objects.filter(code=dto.code).exists():
                raise ValidationError(f"Brand code '{dto.code}' already exists")
            brand.code = dto.code
        if dto.country is not None:
            brand.country = dto.country
        if dto.statecode is not None:
            brand.statecode = dto.statecode

        brand.modifiedby = user
        brand.save()
        return brand


# ============================================================================
# EquipmentModelService
# ============================================================================

class EquipmentModelService:
    """Service for equipment model CRUD."""

    @staticmethod
    def list_models(user, brandid: Optional[UUID] = None, statecode: Optional[int] = None):
        qs = EquipmentModel.objects.all()
        qs = filter_by_ownership(qs, user)
        if brandid is not None:
            qs = qs.filter(brandid=brandid)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('brandid', 'categoryid', 'ownerid')

    @staticmethod
    def get_model(model_id: UUID, user):
        try:
            return EquipmentModel.objects.select_related(
                'brandid', 'categoryid', 'ownerid'
            ).get(modelid=model_id)
        except EquipmentModel.DoesNotExist:
            raise NotFound(f"Equipment model {model_id} not found")

    @staticmethod
    def create_model(dto: CreateEquipmentModelDto, user):
        # Validate brand exists
        try:
            brand = EquipmentBrand.objects.get(brandid=dto.brandid)
        except EquipmentBrand.DoesNotExist:
            raise ValidationError(f"Equipment brand {dto.brandid} not found")

        # Validate unique name per brand
        if EquipmentModel.objects.filter(brandid=brand, name=dto.name).exists():
            raise ValidationError(
                f"Model '{dto.name}' already exists for brand '{brand.name}'"
            )

        # Validate category if provided
        category = None
        if dto.categoryid:
            try:
                category = EquipmentCategory.objects.get(categoryid=dto.categoryid)
            except EquipmentCategory.DoesNotExist:
                raise ValidationError(f"Equipment category {dto.categoryid} not found")

        eq_model = EquipmentModel(
            brandid=brand,
            name=dto.name,
            categoryid=category,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        eq_model.save()
        return eq_model

    @staticmethod
    def update_model(model_id: UUID, dto: UpdateEquipmentModelDto, user):
        eq_model = EquipmentModelService.get_model(model_id, user)

        if dto.name is not None:
            if dto.name != eq_model.name and EquipmentModel.objects.filter(
                brandid=eq_model.brandid, name=dto.name
            ).exists():
                raise ValidationError(
                    f"Model '{dto.name}' already exists for brand '{eq_model.brandid.name}'"
                )
            eq_model.name = dto.name
        if dto.categoryid is not None:
            try:
                eq_model.categoryid = EquipmentCategory.objects.get(categoryid=dto.categoryid)
            except EquipmentCategory.DoesNotExist:
                raise ValidationError(f"Equipment category {dto.categoryid} not found")
        if dto.statecode is not None:
            eq_model.statecode = dto.statecode

        eq_model.modifiedby = user
        eq_model.save()
        return eq_model


# ============================================================================
# EquipmentService
# ============================================================================

class EquipmentService:
    """Service for equipment CRUD with auto-numbering."""

    @staticmethod
    def list_equipment(
        user,
        ownershiptype: Optional[int] = None,
        operationalstatus: Optional[int] = None,
        categoryid: Optional[UUID] = None,
        brandid: Optional[UUID] = None,
        statecode: Optional[int] = None,
    ):
        qs = Equipment.objects.all()
        qs = filter_by_ownership(qs, user)

        if ownershiptype is not None:
            qs = qs.filter(ownershiptype=ownershiptype)
        if operationalstatus is not None:
            qs = qs.filter(operationalstatus=operationalstatus)
        if categoryid is not None:
            qs = qs.filter(categoryid=categoryid)
        if brandid is not None:
            qs = qs.filter(brandid=brandid)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)

        return qs.select_related(
            'categoryid', 'brandid', 'modelid', 'currentprojectid',
            'supplierid', 'ownerid'
        )

    @staticmethod
    def get_equipment(equipment_id: UUID, user):
        try:
            return Equipment.objects.select_related(
                'categoryid', 'brandid', 'modelid', 'currentprojectid',
                'supplierid', 'ownerid'
            ).get(equipmentid=equipment_id)
        except Equipment.DoesNotExist:
            raise NotFound(f"Equipment {equipment_id} not found")

    @staticmethod
    def generate_equipment_number() -> str:
        """Auto-generate equipment number in MAQ-NNN format."""
        prefix = "MAQ-"

        last_equipment = (
            Equipment.objects
            .filter(equipmentnumber__startswith=prefix)
            .order_by('-equipmentnumber')
            .first()
        )

        if last_equipment:
            last_seq = int(last_equipment.equipmentnumber.split('-')[-1])
            next_seq = last_seq + 1
        else:
            next_seq = 1

        return f"{prefix}{next_seq:03d}"

    @staticmethod
    def create_equipment(dto: CreateEquipmentDto, user):
        # Validate category exists
        try:
            category = EquipmentCategory.objects.get(categoryid=dto.categoryid)
        except EquipmentCategory.DoesNotExist:
            raise ValidationError(f"Equipment category {dto.categoryid} not found")

        # Validate brand exists
        try:
            brand = EquipmentBrand.objects.get(brandid=dto.brandid)
        except EquipmentBrand.DoesNotExist:
            raise ValidationError(f"Equipment brand {dto.brandid} not found")

        # Validate model exists and belongs to brand
        try:
            eq_model = EquipmentModel.objects.get(modelid=dto.modelid)
        except EquipmentModel.DoesNotExist:
            raise ValidationError(f"Equipment model {dto.modelid} not found")

        if eq_model.brandid != brand:
            raise ValidationError(
                f"Model '{eq_model.name}' does not belong to brand '{brand.name}'"
            )

        # Validate ownership type: if Propio, acquisitioncost and purchasedate should be present
        if dto.ownershiptype == OwnershipTypeCode.PROPIO:
            if dto.acquisitioncost is None:
                raise ValidationError(
                    "Acquisition cost is required for owned equipment (Propio)"
                )
            if dto.purchasedate is None:
                raise ValidationError(
                    "Purchase date is required for owned equipment (Propio)"
                )

        # Validate currentprojectid if provided
        current_project = None
        if dto.currentprojectid:
            from apps.projects.models import ConstructionProject
            try:
                current_project = ConstructionProject.objects.get(
                    projectid=dto.currentprojectid
                )
            except ConstructionProject.DoesNotExist:
                raise ValidationError(
                    f"Project {dto.currentprojectid} not found"
                )

        # Validate supplierid if provided
        supplier = None
        if dto.supplierid:
            from apps.accounts.models import Account
            try:
                supplier = Account.objects.get(accountid=dto.supplierid)
            except Account.DoesNotExist:
                raise ValidationError(
                    f"Supplier account {dto.supplierid} not found"
                )

        equipment_number = EquipmentService.generate_equipment_number()

        equipment = Equipment(
            equipmentnumber=equipment_number,
            categoryid=category,
            ownershiptype=dto.ownershiptype,
            brandid=brand,
            modelid=eq_model,
            brand=brand.name,
            model=eq_model.name,
            year=dto.year,
            serialnumber=dto.serialnumber,
            engineserialnumber=dto.engineserialnumber,
            capacity=dto.capacity,
            currenthourmeter=dto.currenthourmeter,
            operationalstatus=dto.operationalstatus,
            currentprojectid=current_project,
            acquisitioncost=dto.acquisitioncost,
            purchasedate=dto.purchasedate,
            estimatedusefullifehours=dto.estimatedusefullifehours,
            salvagevalue=dto.salvagevalue,
            supplierid=supplier,
            notes=dto.notes,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        equipment.save()
        return equipment

    @staticmethod
    def update_equipment(equipment_id: UUID, dto: UpdateEquipmentDto, user):
        equipment = EquipmentService.get_equipment(equipment_id, user)

        if dto.categoryid is not None:
            try:
                category = EquipmentCategory.objects.get(categoryid=dto.categoryid)
                equipment.categoryid = category
            except EquipmentCategory.DoesNotExist:
                raise ValidationError(f"Equipment category {dto.categoryid} not found")

        if dto.brandid is not None:
            try:
                brand = EquipmentBrand.objects.get(brandid=dto.brandid)
                equipment.brandid = brand
                equipment.brand = brand.name
            except EquipmentBrand.DoesNotExist:
                raise ValidationError(f"Equipment brand {dto.brandid} not found")

        if dto.modelid is not None:
            try:
                eq_model = EquipmentModel.objects.get(modelid=dto.modelid)
                # Validate model belongs to brand
                current_brand = equipment.brandid
                if eq_model.brandid != current_brand:
                    raise ValidationError(
                        f"Model '{eq_model.name}' does not belong to brand '{current_brand.name}'"
                    )
                equipment.modelid = eq_model
                equipment.model = eq_model.name
            except EquipmentModel.DoesNotExist:
                raise ValidationError(f"Equipment model {dto.modelid} not found")

        if dto.ownershiptype is not None:
            equipment.ownershiptype = dto.ownershiptype
        if dto.year is not None:
            equipment.year = dto.year
        if dto.serialnumber is not None:
            equipment.serialnumber = dto.serialnumber
        if dto.engineserialnumber is not None:
            equipment.engineserialnumber = dto.engineserialnumber
        if dto.capacity is not None:
            equipment.capacity = dto.capacity
        if dto.currenthourmeter is not None:
            equipment.currenthourmeter = dto.currenthourmeter
        if dto.operationalstatus is not None:
            equipment.operationalstatus = dto.operationalstatus

        if dto.currentprojectid is not None:
            from apps.projects.models import ConstructionProject
            try:
                equipment.currentprojectid = ConstructionProject.objects.get(
                    projectid=dto.currentprojectid
                )
            except ConstructionProject.DoesNotExist:
                raise ValidationError(f"Project {dto.currentprojectid} not found")

        if dto.acquisitioncost is not None:
            equipment.acquisitioncost = dto.acquisitioncost
        if dto.purchasedate is not None:
            equipment.purchasedate = dto.purchasedate
        if dto.estimatedusefullifehours is not None:
            equipment.estimatedusefullifehours = dto.estimatedusefullifehours
        if dto.salvagevalue is not None:
            equipment.salvagevalue = dto.salvagevalue

        if dto.supplierid is not None:
            from apps.accounts.models import Account
            try:
                equipment.supplierid = Account.objects.get(accountid=dto.supplierid)
            except Account.DoesNotExist:
                raise ValidationError(f"Supplier account {dto.supplierid} not found")

        if dto.notes is not None:
            equipment.notes = dto.notes
        if dto.statecode is not None:
            equipment.statecode = dto.statecode

        equipment.modifiedby = user
        equipment.save()
        return equipment


# ============================================================================
# EquipmentInsuranceService
# ============================================================================

class EquipmentInsuranceService:
    """Service for equipment insurance CRUD."""

    @staticmethod
    def list_insurance(equipment_id: UUID, user):
        # Validate equipment exists
        try:
            Equipment.objects.get(equipmentid=equipment_id)
        except Equipment.DoesNotExist:
            raise NotFound(f"Equipment {equipment_id} not found")

        return EquipmentInsurance.objects.filter(
            equipmentid=equipment_id
        ).select_related('equipmentid')

    @staticmethod
    def get_insurance(insurance_id: UUID, user):
        try:
            return EquipmentInsurance.objects.select_related(
                'equipmentid'
            ).get(insuranceid=insurance_id)
        except EquipmentInsurance.DoesNotExist:
            raise NotFound(f"Equipment insurance {insurance_id} not found")

    @staticmethod
    def create_insurance(equipment_id: UUID, dto: CreateEquipmentInsuranceDto, user):
        # Validate equipment exists
        try:
            equipment = Equipment.objects.get(equipmentid=equipment_id)
        except Equipment.DoesNotExist:
            raise NotFound(f"Equipment {equipment_id} not found")

        # Validate dates
        if dto.expirydate <= dto.startdate:
            raise ValidationError("Expiry date must be after start date")

        insurance = EquipmentInsurance(
            equipmentid=equipment,
            insurancetype=dto.insurancetype,
            insurancecompany=dto.insurancecompany,
            policynumber=dto.policynumber,
            startdate=dto.startdate,
            expirydate=dto.expirydate,
            annualpremium=dto.annualpremium,
            monthlypremium=dto.monthlypremium,
            insuredamount=dto.insuredamount,
            createdby=user,
            modifiedby=user,
        )
        insurance.save()
        return insurance

    @staticmethod
    def update_insurance(insurance_id: UUID, dto: UpdateEquipmentInsuranceDto, user):
        insurance = EquipmentInsuranceService.get_insurance(insurance_id, user)

        if dto.insurancetype is not None:
            insurance.insurancetype = dto.insurancetype
        if dto.insurancecompany is not None:
            insurance.insurancecompany = dto.insurancecompany
        if dto.policynumber is not None:
            insurance.policynumber = dto.policynumber
        if dto.startdate is not None:
            insurance.startdate = dto.startdate
        if dto.expirydate is not None:
            insurance.expirydate = dto.expirydate
        if dto.annualpremium is not None:
            insurance.annualpremium = dto.annualpremium
        if dto.monthlypremium is not None:
            insurance.monthlypremium = dto.monthlypremium
        if dto.insuredamount is not None:
            insurance.insuredamount = dto.insuredamount
        if dto.statecode is not None:
            insurance.statecode = dto.statecode

        # Validate dates if both are set
        start = dto.startdate or insurance.startdate
        expiry = dto.expirydate or insurance.expirydate
        if expiry <= start:
            raise ValidationError("Expiry date must be after start date")

        insurance.modifiedby = user
        insurance.save()
        return insurance


# ============================================================================
# JustificationReasonService
# ============================================================================

class JustificationReasonService:
    """Service for justification reason catalog CRUD."""

    @staticmethod
    def list_reasons(statecode: Optional[int] = None):
        qs = JustificationReason.objects.all()
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('ownerid')

    @staticmethod
    def get_reason(reason_id: UUID):
        try:
            return JustificationReason.objects.select_related('ownerid').get(
                reasonid=reason_id
            )
        except JustificationReason.DoesNotExist:
            raise NotFound(f"Justification reason {reason_id} not found")

    @staticmethod
    @transaction.atomic
    def create_reason(dto: CreateJustificationReasonDto, user):
        reason = JustificationReason(
            name=dto.name,
            imputabilityvalue=dto.imputabilityvalue,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        reason.save()
        return reason

    @staticmethod
    def update_reason(reason_id: UUID, dto: UpdateJustificationReasonDto, user):
        reason = JustificationReasonService.get_reason(reason_id)
        data = dto.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(reason, field, value)
        reason.modifiedby = user
        reason.save()
        return reason

    @staticmethod
    def seed_default_reasons(user):
        """Create the 10 standard justification reasons (idempotent)."""
        defaults = [
            ('Falla Mayor', 0),
            ('Falla Menor', 1),
            ('Falta Combustible', 0),
            ('Paro Sindical', 0),
            ('Falta Suministro de Materiales', 0),
            ('Falta Operador', 1),
            ('Condiciones Climatológicas No Satisfactorias', 0),
            ('Bloqueo de Ejidatarios', 0),
            ('Paro de Propietario de Equipo', 1),
            ('Domingo', 1),
        ]
        created = []
        for name, imputability in defaults:
            reason, was_created = JustificationReason.objects.get_or_create(
                name=name,
                defaults={
                    'imputabilityvalue': imputability,
                    'statecode': EquipmentStateCode.ACTIVE,
                    'ownerid': user,
                    'createdby': user,
                    'modifiedby': user,
                },
            )
            if was_created:
                created.append(reason)
        return created


# ============================================================================
# RentalContractService
# ============================================================================

class RentalContractService:
    """Service for rental contract CRUD."""

    @staticmethod
    def list_contracts(
        equipment_id: Optional[UUID] = None,
        statuscode: Optional[int] = None,
        statecode: Optional[int] = None,
    ):
        qs = RentalContract.objects.all()
        if equipment_id is not None:
            qs = qs.filter(equipmentid=equipment_id)
        if statuscode is not None:
            qs = qs.filter(statuscode=statuscode)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related('equipmentid', 'ownerid')

    @staticmethod
    def get_contract(contract_id: UUID):
        try:
            return RentalContract.objects.select_related(
                'equipmentid', 'projectid', 'ownerid'
            ).get(contractid=contract_id)
        except RentalContract.DoesNotExist:
            raise NotFound(f"Rental contract {contract_id} not found")

    @staticmethod
    @transaction.atomic
    def create_contract(dto: CreateRentalContractDto, user):
        # Validate equipment exists
        try:
            equipment = Equipment.objects.get(equipmentid=dto.equipmentid)
        except Equipment.DoesNotExist:
            raise ValidationError(f"Equipment {dto.equipmentid} not found")

        # Validate project if provided
        project = None
        if dto.projectid:
            from apps.projects.models import ConstructionProject
            try:
                project = ConstructionProject.objects.get(projectid=dto.projectid)
            except ConstructionProject.DoesNotExist:
                raise ValidationError(f"Project {dto.projectid} not found")

        contract = RentalContract(
            equipmentid=equipment,
            lessorname=dto.lessorname,
            economicnumber=dto.economicnumber,
            projectname=dto.projectname,
            clientname=dto.clientname,
            projectid=project,
            billingmodality=dto.billingmodality,
            monthlyrate=dto.monthlyrate,
            basemeasurement=dto.basemeasurement,
            taxrate=dto.taxrate,
            arrivalfreightstatus=dto.arrivalfreightstatus,
            departurefreightstatus=dto.departurefreightstatus,
            startdate=dto.startdate,
            enddate=dto.enddate,
            notes=dto.notes,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        contract.save()
        return contract

    @staticmethod
    def update_contract(contract_id: UUID, dto: UpdateRentalContractDto, user):
        contract = RentalContractService.get_contract(contract_id)
        data = dto.dict(exclude_unset=True)
        for field, value in data.items():
            if field == 'equipmentid':
                try:
                    contract.equipmentid = Equipment.objects.get(equipmentid=value)
                except Equipment.DoesNotExist:
                    raise ValidationError(f"Equipment {value} not found")
            elif field == 'projectid':
                if value is not None:
                    from apps.projects.models import ConstructionProject
                    try:
                        contract.projectid = ConstructionProject.objects.get(projectid=value)
                    except ConstructionProject.DoesNotExist:
                        raise ValidationError(f"Project {value} not found")
                else:
                    contract.projectid = None
            else:
                setattr(contract, field, value)
        contract.modifiedby = user
        contract.save()
        return contract


# ============================================================================
# DailyEquipmentLogService
# ============================================================================

class DailyEquipmentLogService:
    """Service for daily equipment log CRUD and period summaries."""

    @staticmethod
    def list_logs(
        contract_id: Optional[UUID] = None,
        estimation_number: Optional[int] = None,
        statecode: Optional[int] = None,
    ):
        qs = DailyEquipmentLog.objects.all()
        if contract_id is not None:
            qs = qs.filter(contractid=contract_id)
        if estimation_number is not None:
            qs = qs.filter(estimationnumber=estimation_number)
        if statecode is not None:
            qs = qs.filter(statecode=statecode)
        return qs.select_related(
            'contractid', 'equipmentid', 'justificationreasonid',
            'authorizedby', 'ownerid'
        )

    @staticmethod
    def get_log(log_id: UUID):
        try:
            return DailyEquipmentLog.objects.select_related(
                'contractid', 'equipmentid', 'justificationreasonid',
                'authorizedby', 'ownerid'
            ).get(logid=log_id)
        except DailyEquipmentLog.DoesNotExist:
            raise NotFound(f"Daily equipment log {log_id} not found")

    @staticmethod
    @transaction.atomic
    def create_log(dto: CreateDailyEquipmentLogDto, user):
        # Get contract
        contract = RentalContractService.get_contract(dto.contractid)

        # Validate hourmeter
        if dto.hourmeterend < dto.hourmeterstart:
            raise ValidationError(
                "Horómetro final debe ser mayor o igual al horómetro inicial"
            )

        # Auto-generate sequence number
        max_seq = DailyEquipmentLog.objects.filter(
            contractid=contract
        ).aggregate(max_seq=Max('sequencenumber'))['max_seq']
        sequence_number = (max_seq or 0) + 1

        # Resolve optional FKs
        justification_reason = None
        if dto.justificationreasonid:
            justification_reason = JustificationReasonService.get_reason(
                dto.justificationreasonid
            )

        authorized_by = None
        if dto.authorizedby:
            from apps.users.models import SystemUser
            try:
                authorized_by = SystemUser.objects.get(systemuserid=dto.authorizedby)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"User {dto.authorizedby} not found")

        log = DailyEquipmentLog(
            contractid=contract,
            equipmentid=contract.equipmentid,
            estimationnumber=dto.estimationnumber,
            logdate=dto.logdate,
            sequencenumber=sequence_number,
            hourmeterstart=dto.hourmeterstart,
            hourmeterend=dto.hourmeterend,
            justificationreasonid=justification_reason,
            authorizedby=authorized_by,
            comments=dto.comments,
            statecode=EquipmentStateCode.ACTIVE,
            ownerid=user,
            createdby=user,
            modifiedby=user,
        )
        log.save()

        # Update equipment hourmeter if needed
        equipment = contract.equipmentid
        if dto.hourmeterend > equipment.currenthourmeter:
            equipment.currenthourmeter = dto.hourmeterend
            equipment.save(update_fields=['currenthourmeter'])

        return log

    @staticmethod
    def update_log(log_id: UUID, dto: UpdateDailyEquipmentLogDto, user):
        log = DailyEquipmentLogService.get_log(log_id)
        data = dto.dict(exclude_unset=True)
        for field, value in data.items():
            if field == 'justificationreasonid':
                if value is not None:
                    log.justificationreasonid = JustificationReasonService.get_reason(value)
                else:
                    log.justificationreasonid = None
            elif field == 'authorizedby':
                if value is not None:
                    from apps.users.models import SystemUser
                    try:
                        log.authorizedby = SystemUser.objects.get(systemuserid=value)
                    except SystemUser.DoesNotExist:
                        raise ValidationError(f"User {value} not found")
                else:
                    log.authorizedby = None
            elif field == 'contractid':
                log.contractid = RentalContractService.get_contract(value)
            else:
                setattr(log, field, value)
        log.modifiedby = user
        log.save()
        return log

    @staticmethod
    def get_period_summary(contract_id: UUID, estimation_number: int):
        """Compute period summary for a contract's estimation number."""
        dec = DecimalField(max_digits=20, decimal_places=2)
        zero = Value(Decimal('0'), output_field=dec)

        # workedhours = hourmeterend - hourmeterstart (Decimal, per-row).
        worked_expr = F('hourmeterend') - F('hourmeterstart')

        # isimputable == IMPUTABLE iff any of:
        #   - workedhours > 4
        #   - justificationreasonid.imputabilityvalue == 1
        #   - authorizedby is set
        # (NULL FK -> imputabilityvalue lookup never equals 1; NULL authorizedby
        #  -> isnull=False is False; matches the original Python truthiness checks.)
        imputable_q = (
            Q(workedhours__gt=Decimal('4'))
            | Q(justificationreasonid__imputabilityvalue=1)
            | Q(authorizedby__isnull=False)
        )

        logs = DailyEquipmentLog.objects.filter(
            contractid=contract_id,
            estimationnumber=estimation_number,
            statecode=EquipmentStateCode.ACTIVE,
        ).annotate(
            workedhours=worked_expr,
            isoweekday=ExtractIsoWeekDay('logdate'),
        )

        aggregates = logs.aggregate(
            totalhours=Coalesce(Sum('workedhours'), zero),
            totaldays=Count('logid'),
            imputablehours=Coalesce(
                Sum(Case(When(imputable_q, then='workedhours'), output_field=dec)),
                zero,
            ),
            imputabledays=Count('logid', filter=imputable_q),
            nonimputablehours=Coalesce(
                Sum(Case(When(~imputable_q, then='workedhours'), output_field=dec)),
                zero,
            ),
            nonimputabledays=Count('logid', filter=~imputable_q),
            sundaycount=Count('logid', filter=Q(isoweekday=7)),
            periodstart=Min('logdate'),
            periodend=Max('logdate'),
        )

        return aggregates


# ============================================================================
# BillingEstimationService
# ============================================================================

class BillingEstimationService:
    """Service for billing estimation generation and management."""

    @staticmethod
    def list_estimations(
        contract_id: Optional[UUID] = None,
        statuscode: Optional[int] = None,
    ):
        qs = BillingEstimation.objects.all()
        if contract_id is not None:
            qs = qs.filter(contractid=contract_id)
        if statuscode is not None:
            qs = qs.filter(statuscode=statuscode)
        return qs.select_related('contractid', 'ownerid')

    @staticmethod
    def get_estimation(estimation_id: UUID):
        try:
            return BillingEstimation.objects.select_related(
                'contractid', 'ownerid'
            ).prefetch_related('deductions').get(
                estimationid=estimation_id
            )
        except BillingEstimation.DoesNotExist:
            raise NotFound(f"Billing estimation {estimation_id} not found")

    @staticmethod
    @transaction.atomic
    def generate_estimation(dto: GenerateEstimationDto, user):
        """Generate or regenerate a billing estimation from daily logs."""
        contract = RentalContractService.get_contract(dto.contractid)
        summary = DailyEquipmentLogService.get_period_summary(
            dto.contractid, dto.estimationnumber
        )

        if summary['totaldays'] <= 0:
            raise ValidationError(
                "No hay registros diarios para generar la estimación"
            )

        # Determine measurement based on billing modality
        if contract.billingmodality == BillingModalityCode.DAYS:
            measurement = Decimal(str(summary['imputabledays']))
        else:
            measurement = summary['imputablehours']

        unitprice = contract.unitprice
        amount = measurement * unitprice

        # Advance percentage
        base = Decimal(str(contract.basemeasurement))
        advance = (measurement / base) if base else Decimal('0')

        # Accumulated from previous estimations
        prev_agg = BillingEstimation.objects.filter(
            contractid=contract,
            estimationnumber__lt=dto.estimationnumber,
            statecode=EquipmentStateCode.ACTIVE,
        ).aggregate(
            prev_measurement=Sum('measurement'),
            prev_amount=Sum('amount'),
        )
        prev_measurement = prev_agg['prev_measurement'] or Decimal('0')
        prev_amount = prev_agg['prev_amount'] or Decimal('0')

        accumulatedmeasurement = prev_measurement + measurement
        accumulatedamount = prev_amount + amount

        # Tax and total
        tax = amount * contract.taxrate
        total = amount + tax

        # Concept description
        category_name = (
            contract.equipmentid.categoryid.name
            if contract.equipmentid and contract.equipmentid.categoryid
            else 'Equipo'
        )
        economic_number = contract.economicnumber
        period_label = ''
        if summary['periodstart'] and summary['periodend']:
            period_label = (
                f"del {summary['periodstart'].strftime('%d/%m/%Y')} "
                f"al {summary['periodend'].strftime('%d/%m/%Y')}"
            )
        conceptdescription = (
            f"Renta de {category_name} número económico "
            f"{economic_number} {period_label}"
        )

        estimation, _ = BillingEstimation.objects.update_or_create(
            contractid=contract,
            estimationnumber=dto.estimationnumber,
            defaults={
                'periodstart': summary['periodstart'],
                'periodend': summary['periodend'],
                'totalhours': summary['totalhours'],
                'imputablehours': summary['imputablehours'],
                'nonimputablehours': summary['nonimputablehours'],
                'totaldays': summary['totaldays'],
                'imputabledays': summary['imputabledays'],
                'nonimputabledays': summary['nonimputabledays'],
                'sundaycount': summary['sundaycount'],
                'measurement': measurement,
                'unitprice': unitprice,
                'amount': amount,
                'advancepercentage': advance,
                'accumulatedmeasurement': accumulatedmeasurement,
                'accumulatedamount': accumulatedamount,
                'taxamount': tax,
                'totalamount': total,
                'conceptdescription': conceptdescription,
                'statuscode': EstimationStatusCode.DRAFT,
                'statecode': EquipmentStateCode.ACTIVE,
                'ownerid': user,
                'createdby': user,
                'modifiedby': user,
            },
        )
        return estimation

    @staticmethod
    def update_status(estimation_id: UUID, dto: UpdateEstimationStatusDto, user):
        estimation = BillingEstimationService.get_estimation(estimation_id)
        estimation.statuscode = dto.statuscode
        estimation.modifiedby = user
        estimation.save()
        return estimation

    @staticmethod
    def add_deduction(dto: CreateEstimationDeductionDto, user):
        # Validate estimation exists
        estimation = BillingEstimationService.get_estimation(dto.estimationid)
        deduction = EstimationDeduction(
            estimationid=estimation,
            concept=dto.concept,
            amount=dto.amount,
            statecode=EquipmentStateCode.ACTIVE,
        )
        deduction.save()
        return deduction
