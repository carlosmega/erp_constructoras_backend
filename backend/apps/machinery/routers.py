"""Machinery module API routers."""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest

from core.permissions import require_permission, Permission

from apps.machinery.schemas import (
    EquipmentCategorySchema,
    EquipmentCategoryListSchema,
    CreateEquipmentCategoryDto,
    UpdateEquipmentCategoryDto,
    EquipmentBrandSchema,
    EquipmentBrandListSchema,
    CreateEquipmentBrandDto,
    UpdateEquipmentBrandDto,
    EquipmentModelSchema,
    EquipmentModelListSchema,
    CreateEquipmentModelDto,
    UpdateEquipmentModelDto,
    EquipmentSchema,
    EquipmentListSchema,
    CreateEquipmentDto,
    UpdateEquipmentDto,
    EquipmentInsuranceSchema,
    CreateEquipmentInsuranceDto,
    UpdateEquipmentInsuranceDto,
    JustificationReasonSchema,
    CreateJustificationReasonDto,
    UpdateJustificationReasonDto,
    RentalContractSchema,
    RentalContractListSchema,
    CreateRentalContractDto,
    UpdateRentalContractDto,
    DailyEquipmentLogSchema,
    CreateDailyEquipmentLogDto,
    UpdateDailyEquipmentLogDto,
    BillingEstimationSchema,
    BillingEstimationListSchema,
    GenerateEstimationDto,
    CreateEstimationDeductionDto,
    UpdateEstimationStatusDto,
    EstimationDeductionSchema,
)
from apps.machinery.services import (
    EquipmentCategoryService,
    EquipmentBrandService,
    EquipmentModelService,
    EquipmentService,
    EquipmentInsuranceService,
    JustificationReasonService,
    RentalContractService,
    DailyEquipmentLogService,
    BillingEstimationService,
)


# =============================================================================
# Categories Router
# =============================================================================

categories_router = Router(tags=["Equipment Categories"])


@categories_router.get("/categories/", response=List[EquipmentCategoryListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_categories(
    request: HttpRequest,
    statecode: Optional[int] = None,
):
    """List equipment categories with optional filtering."""
    categories = EquipmentCategoryService.list_categories(
        user=request.user,
        statecode=statecode,
    )
    return list(categories)


@categories_router.post("/categories/", response={201: EquipmentCategorySchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_category(request: HttpRequest, payload: CreateEquipmentCategoryDto):
    """Create a new equipment category."""
    category = EquipmentCategoryService.create_category(payload, request.user)
    return 201, EquipmentCategoryService.get_category(category.categoryid, request.user)


@categories_router.get("/categories/{category_id}/", response=EquipmentCategorySchema)
@require_permission(Permission.MACHINERY_READ)
def get_category(request: HttpRequest, category_id: UUID):
    """Get equipment category by ID."""
    return EquipmentCategoryService.get_category(category_id, request.user)


@categories_router.patch("/categories/{category_id}/", response=EquipmentCategorySchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_category(request: HttpRequest, category_id: UUID, payload: UpdateEquipmentCategoryDto):
    """Update an equipment category."""
    EquipmentCategoryService.update_category(category_id, payload, request.user)
    return EquipmentCategoryService.get_category(category_id, request.user)


# =============================================================================
# Brands Router
# =============================================================================

brands_router = Router(tags=["Equipment Brands"])


@brands_router.get("/brands/", response=List[EquipmentBrandListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_brands(
    request: HttpRequest,
    statecode: Optional[int] = None,
):
    """List equipment brands."""
    return list(EquipmentBrandService.list_brands(request.user, statecode=statecode))


@brands_router.post("/brands/", response={201: EquipmentBrandSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_brand(request: HttpRequest, payload: CreateEquipmentBrandDto):
    """Create a new equipment brand."""
    brand = EquipmentBrandService.create_brand(payload, request.user)
    return 201, EquipmentBrandService.get_brand(brand.brandid, request.user)


@brands_router.get("/brands/{brand_id}/", response=EquipmentBrandSchema)
@require_permission(Permission.MACHINERY_READ)
def get_brand(request: HttpRequest, brand_id: UUID):
    """Get equipment brand by ID."""
    return EquipmentBrandService.get_brand(brand_id, request.user)


@brands_router.patch("/brands/{brand_id}/", response=EquipmentBrandSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_brand(request: HttpRequest, brand_id: UUID, payload: UpdateEquipmentBrandDto):
    """Update an equipment brand."""
    EquipmentBrandService.update_brand(brand_id, payload, request.user)
    return EquipmentBrandService.get_brand(brand_id, request.user)


# =============================================================================
# Models Router
# =============================================================================

models_router = Router(tags=["Equipment Models"])


@models_router.get("/models/", response=List[EquipmentModelListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_models(
    request: HttpRequest,
    brandid: Optional[UUID] = None,
    statecode: Optional[int] = None,
):
    """List equipment models with optional brand filter."""
    return list(EquipmentModelService.list_models(request.user, brandid=brandid, statecode=statecode))


@models_router.post("/models/", response={201: EquipmentModelSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_model(request: HttpRequest, payload: CreateEquipmentModelDto):
    """Create a new equipment model."""
    eq_model = EquipmentModelService.create_model(payload, request.user)
    return 201, EquipmentModelService.get_model(eq_model.modelid, request.user)


@models_router.get("/models/{model_id}/", response=EquipmentModelSchema)
@require_permission(Permission.MACHINERY_READ)
def get_model(request: HttpRequest, model_id: UUID):
    """Get equipment model by ID."""
    return EquipmentModelService.get_model(model_id, request.user)


@models_router.patch("/models/{model_id}/", response=EquipmentModelSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_model(request: HttpRequest, model_id: UUID, payload: UpdateEquipmentModelDto):
    """Update an equipment model."""
    EquipmentModelService.update_model(model_id, payload, request.user)
    return EquipmentModelService.get_model(model_id, request.user)


# =============================================================================
# Equipment Router
# =============================================================================

equipment_router = Router(tags=["Equipment"])


@equipment_router.get("/equipment/", response=List[EquipmentListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_equipment(
    request: HttpRequest,
    ownershiptype: Optional[int] = None,
    operationalstatus: Optional[int] = None,
    categoryid: Optional[UUID] = None,
    brandid: Optional[UUID] = None,
    statecode: Optional[int] = None,
):
    """List equipment with optional filtering."""
    equipment = EquipmentService.list_equipment(
        user=request.user,
        ownershiptype=ownershiptype,
        operationalstatus=operationalstatus,
        categoryid=categoryid,
        brandid=brandid,
        statecode=statecode,
    )
    return list(equipment)


@equipment_router.post("/equipment/", response={201: EquipmentSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_equipment(request: HttpRequest, payload: CreateEquipmentDto):
    """Create a new equipment record with auto-generated number."""
    equipment = EquipmentService.create_equipment(payload, request.user)
    return 201, EquipmentService.get_equipment(equipment.equipmentid, request.user)


@equipment_router.get("/equipment/{equipment_id}/", response=EquipmentSchema)
@require_permission(Permission.MACHINERY_READ)
def get_equipment(request: HttpRequest, equipment_id: UUID):
    """Get equipment by ID."""
    return EquipmentService.get_equipment(equipment_id, request.user)


@equipment_router.patch("/equipment/{equipment_id}/", response=EquipmentSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_equipment(request: HttpRequest, equipment_id: UUID, payload: UpdateEquipmentDto):
    """Update an equipment record."""
    EquipmentService.update_equipment(equipment_id, payload, request.user)
    return EquipmentService.get_equipment(equipment_id, request.user)


# =============================================================================
# Insurance Router
# =============================================================================

insurance_router = Router(tags=["Equipment Insurance"])


@insurance_router.get("/equipment/{equipment_id}/insurance/", response=List[EquipmentInsuranceSchema])
@require_permission(Permission.MACHINERY_READ)
def list_insurance(request: HttpRequest, equipment_id: UUID):
    """List insurance policies for an equipment."""
    return list(EquipmentInsuranceService.list_insurance(equipment_id, request.user))


@insurance_router.post("/equipment/{equipment_id}/insurance/", response={201: EquipmentInsuranceSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_insurance(request: HttpRequest, equipment_id: UUID, payload: CreateEquipmentInsuranceDto):
    """Create a new insurance policy for an equipment."""
    insurance = EquipmentInsuranceService.create_insurance(equipment_id, payload, request.user)
    return 201, EquipmentInsuranceService.get_insurance(insurance.insuranceid, request.user)


@insurance_router.get("/insurance/{insurance_id}/", response=EquipmentInsuranceSchema)
@require_permission(Permission.MACHINERY_READ)
def get_insurance(request: HttpRequest, insurance_id: UUID):
    """Get insurance policy by ID."""
    return EquipmentInsuranceService.get_insurance(insurance_id, request.user)


@insurance_router.patch("/insurance/{insurance_id}/", response=EquipmentInsuranceSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_insurance(request: HttpRequest, insurance_id: UUID, payload: UpdateEquipmentInsuranceDto):
    """Update an insurance policy."""
    EquipmentInsuranceService.update_insurance(insurance_id, payload, request.user)
    return EquipmentInsuranceService.get_insurance(insurance_id, request.user)


# =============================================================================
# Justification Reasons Router
# =============================================================================

reasons_router = Router(tags=["Machinery - Justification Reasons"])


@reasons_router.get("/justification-reasons/", response=List[JustificationReasonSchema])
@require_permission(Permission.MACHINERY_READ)
def list_reasons(
    request: HttpRequest,
    statecode: Optional[int] = None,
):
    """List justification reasons with optional filtering."""
    return list(JustificationReasonService.list_reasons(statecode=statecode))


@reasons_router.post("/justification-reasons/", response={201: JustificationReasonSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_reason(request: HttpRequest, payload: CreateJustificationReasonDto):
    """Create a new justification reason."""
    reason = JustificationReasonService.create_reason(payload, request.user)
    return 201, JustificationReasonService.get_reason(reason.reasonid)


@reasons_router.get("/justification-reasons/{reason_id}/", response=JustificationReasonSchema)
@require_permission(Permission.MACHINERY_READ)
def get_reason(request: HttpRequest, reason_id: UUID):
    """Get justification reason by ID."""
    return JustificationReasonService.get_reason(reason_id)


@reasons_router.patch("/justification-reasons/{reason_id}/", response=JustificationReasonSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_reason(request: HttpRequest, reason_id: UUID, payload: UpdateJustificationReasonDto):
    """Update a justification reason."""
    JustificationReasonService.update_reason(reason_id, payload, request.user)
    return JustificationReasonService.get_reason(reason_id)


@reasons_router.post("/justification-reasons/seed/", response={201: List[JustificationReasonSchema]})
@require_permission(Permission.MACHINERY_CREATE)
def seed_reasons(request: HttpRequest):
    """Seed the default justification reasons (idempotent)."""
    created = JustificationReasonService.seed_default_reasons(request.user)
    return 201, list(created)


# =============================================================================
# Rental Contracts Router
# =============================================================================

contracts_router = Router(tags=["Machinery - Rental Contracts"])


@contracts_router.get("/rental-contracts/", response=List[RentalContractListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_contracts(
    request: HttpRequest,
    equipment_id: Optional[UUID] = None,
    statuscode: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List rental contracts with optional filtering."""
    return list(RentalContractService.list_contracts(
        request.user,
        equipment_id=equipment_id,
        statuscode=statuscode,
        statecode=statecode,
    ))


@contracts_router.post("/rental-contracts/", response={201: RentalContractSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_contract(request: HttpRequest, payload: CreateRentalContractDto):
    """Create a new rental contract."""
    contract = RentalContractService.create_contract(payload, request.user)
    return 201, RentalContractService.get_contract(contract.contractid, request.user)


@contracts_router.get("/rental-contracts/{contract_id}/", response=RentalContractSchema)
@require_permission(Permission.MACHINERY_READ)
def get_contract(request: HttpRequest, contract_id: UUID):
    """Get rental contract by ID."""
    return RentalContractService.get_contract(contract_id, request.user)


@contracts_router.patch("/rental-contracts/{contract_id}/", response=RentalContractSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_contract(request: HttpRequest, contract_id: UUID, payload: UpdateRentalContractDto):
    """Update a rental contract."""
    RentalContractService.update_contract(contract_id, payload, request.user)
    return RentalContractService.get_contract(contract_id, request.user)


# =============================================================================
# Daily Equipment Logs Router
# =============================================================================

daily_logs_router = Router(tags=["Machinery - Daily Equipment Logs"])


@daily_logs_router.get("/daily-logs/", response=List[DailyEquipmentLogSchema])
@require_permission(Permission.MACHINERY_READ)
def list_logs(
    request: HttpRequest,
    contract_id: Optional[UUID] = None,
    estimation_number: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List daily equipment logs with optional filtering."""
    return list(DailyEquipmentLogService.list_logs(
        request.user,
        contract_id=contract_id,
        estimation_number=estimation_number,
        statecode=statecode,
    ))


@daily_logs_router.post("/daily-logs/", response={201: DailyEquipmentLogSchema})
@require_permission(Permission.MACHINERY_CREATE)
def create_log(request: HttpRequest, payload: CreateDailyEquipmentLogDto):
    """Create a new daily equipment log entry."""
    log = DailyEquipmentLogService.create_log(payload, request.user)
    return 201, DailyEquipmentLogService.get_log(log.logid, request.user)


@daily_logs_router.get("/daily-logs/summary/", response=dict)
@require_permission(Permission.MACHINERY_READ)
def get_period_summary(
    request: HttpRequest,
    contract_id: UUID,
    estimation_number: int,
):
    """Get period summary for a contract's estimation number."""
    return DailyEquipmentLogService.get_period_summary(contract_id, estimation_number, request.user)


@daily_logs_router.get("/daily-logs/{log_id}/", response=DailyEquipmentLogSchema)
@require_permission(Permission.MACHINERY_READ)
def get_log(request: HttpRequest, log_id: UUID):
    """Get daily equipment log by ID."""
    return DailyEquipmentLogService.get_log(log_id, request.user)


@daily_logs_router.patch("/daily-logs/{log_id}/", response=DailyEquipmentLogSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_log(request: HttpRequest, log_id: UUID, payload: UpdateDailyEquipmentLogDto):
    """Update a daily equipment log entry."""
    DailyEquipmentLogService.update_log(log_id, payload, request.user)
    return DailyEquipmentLogService.get_log(log_id, request.user)


# =============================================================================
# Billing Estimations Router
# =============================================================================

estimations_router = Router(tags=["Machinery - Billing Estimations"])


@estimations_router.get("/billing-estimations/", response=List[BillingEstimationListSchema])
@require_permission(Permission.MACHINERY_READ)
def list_estimations(
    request: HttpRequest,
    contract_id: Optional[UUID] = None,
    statuscode: Optional[int] = None,
):
    """List billing estimations with optional filtering."""
    return list(BillingEstimationService.list_estimations(
        request.user,
        contract_id=contract_id,
        statuscode=statuscode,
    ))


@estimations_router.post("/billing-estimations/generate/", response={201: BillingEstimationSchema})
@require_permission(Permission.MACHINERY_CREATE)
def generate_estimation(request: HttpRequest, payload: GenerateEstimationDto):
    """Generate or regenerate a billing estimation from daily logs."""
    estimation = BillingEstimationService.generate_estimation(payload, request.user)
    return 201, BillingEstimationService.get_estimation(estimation.estimationid, request.user)


@estimations_router.get("/billing-estimations/{estimation_id}/", response=BillingEstimationSchema)
@require_permission(Permission.MACHINERY_READ)
def get_estimation(request: HttpRequest, estimation_id: UUID):
    """Get billing estimation by ID."""
    return BillingEstimationService.get_estimation(estimation_id, request.user)


@estimations_router.patch("/billing-estimations/{estimation_id}/status/", response=BillingEstimationSchema)
@require_permission(Permission.MACHINERY_UPDATE)
def update_estimation_status(request: HttpRequest, estimation_id: UUID, payload: UpdateEstimationStatusDto):
    """Update the status of a billing estimation."""
    BillingEstimationService.update_status(estimation_id, payload, request.user)
    return BillingEstimationService.get_estimation(estimation_id, request.user)


@estimations_router.post("/billing-estimations/{estimation_id}/deductions/", response={201: EstimationDeductionSchema})
@require_permission(Permission.MACHINERY_CREATE)
def add_deduction(request: HttpRequest, estimation_id: UUID, payload: CreateEstimationDeductionDto):
    """Add a deduction to a billing estimation."""
    payload.estimationid = estimation_id
    deduction = BillingEstimationService.add_deduction(payload, request.user)
    return 201, deduction
