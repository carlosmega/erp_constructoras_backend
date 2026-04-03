"""Machinery module API schemas."""

from ninja import ModelSchema, Schema
from typing import Optional
from uuid import UUID
from decimal import Decimal
from datetime import date

from apps.machinery.models import (
    EquipmentCategory,
    EquipmentBrand,
    EquipmentModel,
    Equipment,
    EquipmentInsurance,
    JustificationReason,
    RentalContract,
    DailyEquipmentLog,
    BillingEstimation,
    EstimationDeduction,
    BillingModalityCode,
    ContractStatusCode,
    EstimationStatusCode,
    ImputabilityCode,
)


# =============================================================================
# EquipmentCategory Schemas
# =============================================================================

class EquipmentCategorySchema(ModelSchema):
    """Full equipment category response."""
    ownername: Optional[str] = None

    class Meta:
        model = EquipmentCategory
        fields = '__all__'

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class EquipmentCategoryListSchema(ModelSchema):
    """Lightweight category for list views."""
    ownername: Optional[str] = None

    class Meta:
        model = EquipmentCategory
        fields = [
            'categoryid', 'name', 'code', 'description',
            'estimatedfuelconsumption', 'statecode',
            'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateEquipmentCategoryDto(Schema):
    name: str
    code: str
    description: Optional[str] = None
    estimatedfuelconsumption: Optional[Decimal] = None


class UpdateEquipmentCategoryDto(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    estimatedfuelconsumption: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# EquipmentBrand Schemas
# =============================================================================

class EquipmentBrandSchema(ModelSchema):
    """Full equipment brand response."""
    ownername: Optional[str] = None

    class Meta:
        model = EquipmentBrand
        fields = '__all__'

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class EquipmentBrandListSchema(ModelSchema):
    """Lightweight brand for list views and selects."""

    class Meta:
        model = EquipmentBrand
        fields = ['brandid', 'name', 'code', 'country', 'statecode']


class CreateEquipmentBrandDto(Schema):
    name: str
    code: str
    country: Optional[str] = None


class UpdateEquipmentBrandDto(Schema):
    name: Optional[str] = None
    code: Optional[str] = None
    country: Optional[str] = None
    statecode: Optional[int] = None


# =============================================================================
# EquipmentModel Schemas
# =============================================================================

class EquipmentModelSchema(ModelSchema):
    """Full equipment model response."""
    brandname: Optional[str] = None
    categoryname: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = EquipmentModel
        fields = '__all__'

    @staticmethod
    def resolve_brandname(obj):
        return obj.brandid.name if obj.brandid else None

    @staticmethod
    def resolve_categoryname(obj):
        return obj.categoryid.name if obj.categoryid else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class EquipmentModelListSchema(ModelSchema):
    """Lightweight model for list views and selects."""
    brandname: Optional[str] = None

    class Meta:
        model = EquipmentModel
        fields = ['modelid', 'name', 'brandid', 'categoryid', 'statecode']

    @staticmethod
    def resolve_brandname(obj):
        return obj.brandid.name if obj.brandid else None


class CreateEquipmentModelDto(Schema):
    brandid: UUID
    name: str
    categoryid: Optional[UUID] = None


class UpdateEquipmentModelDto(Schema):
    name: Optional[str] = None
    categoryid: Optional[UUID] = None
    statecode: Optional[int] = None


# =============================================================================
# Equipment Schemas
# =============================================================================

class EquipmentSchema(ModelSchema):
    """Full equipment response with resolved FK names."""
    categoryname: Optional[str] = None
    brandname: Optional[str] = None
    modelname: Optional[str] = None
    currentprojectname: Optional[str] = None
    suppliername: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = Equipment
        fields = '__all__'

    @staticmethod
    def resolve_categoryname(obj):
        return obj.categoryid.name if obj.categoryid else None

    @staticmethod
    def resolve_brandname(obj):
        return obj.brandid.name if obj.brandid else None

    @staticmethod
    def resolve_modelname(obj):
        return obj.modelid.name if obj.modelid else None

    @staticmethod
    def resolve_currentprojectname(obj):
        return obj.currentprojectid.name if obj.currentprojectid else None

    @staticmethod
    def resolve_suppliername(obj):
        return obj.supplierid.name if obj.supplierid else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class EquipmentListSchema(ModelSchema):
    """Lightweight equipment for list views."""
    categoryname: Optional[str] = None
    brandname: Optional[str] = None
    modelname: Optional[str] = None
    currentprojectname: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = Equipment
        fields = [
            'equipmentid', 'equipmentnumber', 'ownershiptype',
            'brand', 'model', 'year', 'serialnumber',
            'currenthourmeter', 'operationalstatus',
            'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_categoryname(obj):
        return obj.categoryid.name if obj.categoryid else None

    @staticmethod
    def resolve_brandname(obj):
        return obj.brandid.name if obj.brandid else None

    @staticmethod
    def resolve_modelname(obj):
        return obj.modelid.name if obj.modelid else None

    @staticmethod
    def resolve_currentprojectname(obj):
        return obj.currentprojectid.name if obj.currentprojectid else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateEquipmentDto(Schema):
    categoryid: UUID
    ownershiptype: int
    brandid: UUID
    modelid: UUID
    year: int
    serialnumber: str
    engineserialnumber: Optional[str] = None
    capacity: Optional[str] = None
    currenthourmeter: Decimal = Decimal('0')
    operationalstatus: int = 0
    currentprojectid: Optional[UUID] = None
    acquisitioncost: Optional[Decimal] = None
    purchasedate: Optional[date] = None
    estimatedusefullifehours: Optional[int] = None
    salvagevalue: Optional[Decimal] = None
    supplierid: Optional[UUID] = None
    notes: Optional[str] = None


class UpdateEquipmentDto(Schema):
    categoryid: Optional[UUID] = None
    ownershiptype: Optional[int] = None
    brandid: Optional[UUID] = None
    modelid: Optional[UUID] = None
    year: Optional[int] = None
    serialnumber: Optional[str] = None
    engineserialnumber: Optional[str] = None
    capacity: Optional[str] = None
    currenthourmeter: Optional[Decimal] = None
    operationalstatus: Optional[int] = None
    currentprojectid: Optional[UUID] = None
    acquisitioncost: Optional[Decimal] = None
    purchasedate: Optional[date] = None
    estimatedusefullifehours: Optional[int] = None
    salvagevalue: Optional[Decimal] = None
    supplierid: Optional[UUID] = None
    notes: Optional[str] = None
    statecode: Optional[int] = None


# =============================================================================
# EquipmentInsurance Schemas
# =============================================================================

class EquipmentInsuranceSchema(ModelSchema):
    """Full insurance response."""

    class Meta:
        model = EquipmentInsurance
        fields = '__all__'


class CreateEquipmentInsuranceDto(Schema):
    insurancetype: int
    insurancecompany: str
    policynumber: str
    startdate: date
    expirydate: date
    annualpremium: Decimal
    monthlypremium: Decimal
    insuredamount: Decimal


class UpdateEquipmentInsuranceDto(Schema):
    insurancetype: Optional[int] = None
    insurancecompany: Optional[str] = None
    policynumber: Optional[str] = None
    startdate: Optional[date] = None
    expirydate: Optional[date] = None
    annualpremium: Optional[Decimal] = None
    monthlypremium: Optional[Decimal] = None
    insuredamount: Optional[Decimal] = None
    statecode: Optional[int] = None


# =============================================================================
# JustificationReason Schemas
# =============================================================================

class JustificationReasonSchema(ModelSchema):
    """Full justification reason response."""
    ownername: Optional[str] = None

    class Meta:
        model = JustificationReason
        fields = [
            'reasonid', 'name', 'imputabilityvalue',
            'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateJustificationReasonDto(Schema):
    name: str
    imputabilityvalue: int


class UpdateJustificationReasonDto(Schema):
    name: Optional[str] = None
    imputabilityvalue: Optional[int] = None
    statecode: Optional[int] = None


# =============================================================================
# RentalContract Schemas
# =============================================================================

class RentalContractSchema(ModelSchema):
    """Full rental contract response."""
    equipmentname: Optional[str] = None
    unitprice: Optional[Decimal] = None
    ownername: Optional[str] = None

    class Meta:
        model = RentalContract
        fields = [
            'contractid', 'equipmentid', 'lessorname', 'economicnumber',
            'projectname', 'clientname', 'projectid', 'billingmodality',
            'monthlyrate', 'basemeasurement', 'taxrate',
            'arrivalfreightstatus', 'departurefreightstatus',
            'startdate', 'enddate', 'notes',
            'statuscode', 'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_equipmentname(obj):
        return str(obj.equipmentid) if obj.equipmentid else None

    @staticmethod
    def resolve_unitprice(obj):
        return obj.unitprice

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class RentalContractListSchema(ModelSchema):
    """Lightweight rental contract for list views."""
    equipmentname: Optional[str] = None
    unitprice: Optional[Decimal] = None

    class Meta:
        model = RentalContract
        fields = [
            'contractid', 'equipmentid', 'lessorname', 'economicnumber',
            'projectname', 'clientname', 'billingmodality',
            'monthlyrate', 'basemeasurement',
            'statuscode', 'statecode', 'startdate', 'enddate',
        ]

    @staticmethod
    def resolve_equipmentname(obj):
        return str(obj.equipmentid) if obj.equipmentid else None

    @staticmethod
    def resolve_unitprice(obj):
        return obj.unitprice


class CreateRentalContractDto(Schema):
    equipmentid: UUID
    lessorname: str
    economicnumber: str
    projectname: str
    clientname: str
    projectid: Optional[UUID] = None
    billingmodality: int
    monthlyrate: Decimal
    basemeasurement: int
    taxrate: Decimal = Decimal('0.0800')
    arrivalfreightstatus: Optional[str] = None
    departurefreightstatus: Optional[str] = None
    startdate: date
    enddate: Optional[date] = None
    notes: Optional[str] = None


class UpdateRentalContractDto(Schema):
    equipmentid: Optional[UUID] = None
    lessorname: Optional[str] = None
    economicnumber: Optional[str] = None
    projectname: Optional[str] = None
    clientname: Optional[str] = None
    projectid: Optional[UUID] = None
    billingmodality: Optional[int] = None
    monthlyrate: Optional[Decimal] = None
    basemeasurement: Optional[int] = None
    taxrate: Optional[Decimal] = None
    arrivalfreightstatus: Optional[str] = None
    departurefreightstatus: Optional[str] = None
    startdate: Optional[date] = None
    enddate: Optional[date] = None
    notes: Optional[str] = None
    statuscode: Optional[int] = None
    statecode: Optional[int] = None


# =============================================================================
# DailyEquipmentLog Schemas
# =============================================================================

class DailyEquipmentLogSchema(ModelSchema):
    """Full daily equipment log response."""
    workedhours: Optional[Decimal] = None
    dayofweek: Optional[int] = None
    indicator: Optional[str] = None
    isimputable: Optional[int] = None
    justificationreasonname: Optional[str] = None
    authorizedbyname: Optional[str] = None
    ownername: Optional[str] = None

    class Meta:
        model = DailyEquipmentLog
        fields = [
            'logid', 'contractid', 'equipmentid', 'estimationnumber',
            'logdate', 'sequencenumber', 'hourmeterstart', 'hourmeterend',
            'justificationreasonid', 'authorizedby', 'comments',
            'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_workedhours(obj):
        return obj.workedhours

    @staticmethod
    def resolve_dayofweek(obj):
        return obj.dayofweek

    @staticmethod
    def resolve_indicator(obj):
        return obj.indicator

    @staticmethod
    def resolve_isimputable(obj):
        return obj.isimputable

    @staticmethod
    def resolve_justificationreasonname(obj):
        return obj.justificationreasonid.name if obj.justificationreasonid else None

    @staticmethod
    def resolve_authorizedbyname(obj):
        return obj.authorizedby.fullname if obj.authorizedby else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateDailyEquipmentLogDto(Schema):
    contractid: UUID
    estimationnumber: int
    logdate: date
    hourmeterstart: Decimal
    hourmeterend: Decimal
    justificationreasonid: Optional[UUID] = None
    authorizedby: Optional[UUID] = None
    comments: Optional[str] = None


class UpdateDailyEquipmentLogDto(Schema):
    contractid: Optional[UUID] = None
    estimationnumber: Optional[int] = None
    logdate: Optional[date] = None
    hourmeterstart: Optional[Decimal] = None
    hourmeterend: Optional[Decimal] = None
    justificationreasonid: Optional[UUID] = None
    authorizedby: Optional[UUID] = None
    comments: Optional[str] = None
    statecode: Optional[int] = None


# =============================================================================
# BillingEstimation & EstimationDeduction Schemas
# =============================================================================

class EstimationDeductionSchema(ModelSchema):
    """Deduction line on a billing estimation."""

    class Meta:
        model = EstimationDeduction
        fields = [
            'deductionid', 'estimationid', 'concept', 'amount', 'statecode',
        ]


class BillingEstimationSchema(ModelSchema):
    """Full billing estimation response."""
    contracteconomicnumber: Optional[str] = None
    contractclientname: Optional[str] = None
    billingmodality: Optional[int] = None
    deductions: list[EstimationDeductionSchema] = []
    ownername: Optional[str] = None

    class Meta:
        model = BillingEstimation
        fields = [
            'estimationid', 'contractid', 'estimationnumber',
            'periodstart', 'periodend',
            'totalhours', 'imputablehours', 'nonimputablehours',
            'totaldays', 'imputabledays', 'nonimputabledays', 'sundaycount',
            'measurement', 'unitprice', 'amount',
            'advancepercentage', 'accumulatedmeasurement', 'accumulatedamount',
            'taxamount', 'totalamount',
            'conceptdescription', 'observations',
            'statuscode', 'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_contracteconomicnumber(obj):
        return obj.contractid.economicnumber if obj.contractid else None

    @staticmethod
    def resolve_contractclientname(obj):
        return obj.contractid.clientname if obj.contractid else None

    @staticmethod
    def resolve_billingmodality(obj):
        return obj.contractid.billingmodality if obj.contractid else None

    @staticmethod
    def resolve_deductions(obj):
        return obj.deductions.all() if hasattr(obj, 'deductions') else []

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class BillingEstimationListSchema(ModelSchema):
    """Lightweight billing estimation for list views."""
    contracteconomicnumber: Optional[str] = None
    contractclientname: Optional[str] = None

    class Meta:
        model = BillingEstimation
        fields = [
            'estimationid', 'contractid', 'estimationnumber',
            'periodstart', 'periodend',
            'measurement', 'unitprice', 'amount', 'totalamount',
            'statuscode', 'statecode', 'createdon',
        ]

    @staticmethod
    def resolve_contracteconomicnumber(obj):
        return obj.contractid.economicnumber if obj.contractid else None

    @staticmethod
    def resolve_contractclientname(obj):
        return obj.contractid.clientname if obj.contractid else None


class GenerateEstimationDto(Schema):
    contractid: UUID
    estimationnumber: int


class CreateEstimationDeductionDto(Schema):
    estimationid: UUID
    concept: str
    amount: Decimal


class UpdateEstimationStatusDto(Schema):
    statuscode: int
