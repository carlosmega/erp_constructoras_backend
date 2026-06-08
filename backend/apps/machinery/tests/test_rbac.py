"""Record-level ownership (RBAC) tests for machinery owned entities.

Every machinery endpoint was already @require_permission-gated, but several
OWNED entities (Equipment, EquipmentInsurance, RentalContract,
DailyEquipmentLog, BillingEstimation) had service methods that accepted ``user``
but never enforced it — so any MACHINERY_READ user could read/modify another
owner's records, and list endpoints returned every owner's rows. These tests pin
the record-level gate (``filter_by_ownership`` on list, ``can_modify_record`` on
get/update) added by the RBAC-hardening pass:

* a non-owner Salesperson is denied / sees nothing,
* the owner and a Sales Manager (ADMIN_ROLES bypass) succeed,
* the JustificationReason CATALOG stays global (intentionally NOT owner-filtered).

Fixtures note: this module defines its own ``rbac_owner`` / ``rbac_other``
Salesperson users with fixed unique emails instead of reusing ``salesperson`` /
``salesperson2``. The machinery-local conftest shadows ``salesperson`` with a
``SalespersonFactory`` whose ``Sequence`` email eventually emits ``sales2@crm.test``
and collides with the global ``salesperson2`` fixture under --reuse-db. ``sales_manager``
(global, not shadowed) is safe to reuse for the admin-bypass case.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from core.exceptions import PermissionDenied, NotFound
from apps.users.models import SystemUser
from apps.machinery.services import (
    EquipmentCategoryService,
    EquipmentService,
    EquipmentInsuranceService,
    RentalContractService,
    DailyEquipmentLogService,
    BillingEstimationService,
    JustificationReasonService,
)
from apps.machinery.schemas import (
    CreateRentalContractDto,
    UpdateRentalContractDto,
    CreateDailyEquipmentLogDto,
    UpdateDailyEquipmentLogDto,
    GenerateEstimationDto,
    CreateEstimationDeductionDto,
    UpdateEstimationStatusDto,
    CreateEquipmentInsuranceDto,
    CreateJustificationReasonDto,
    UpdateEquipmentDto,
)
from apps.machinery.models import (
    BillingModalityCode,
    EstimationStatusCode,
    InsuranceTypeCode,
)
from apps.machinery.tests.factories import (
    EquipmentFactory,
    EquipmentBrandFactory,
    EquipmentCategoryFactory,
    EquipmentModelFactory,
)


@pytest.fixture
def rbac_owner(db, salesperson_role):
    """A Salesperson with a fixed, unique email (the record owner)."""
    user = SystemUser.objects.create(
        emailaddress1='rbac-owner@crm.test',
        fullname='RBAC Owner',
        securityroleid=salesperson_role,
        isdisabled=False,
    )
    user.set_password('testpass123')
    user.save()
    return user


@pytest.fixture
def rbac_other(db, salesperson_role):
    """A second, distinct Salesperson (the non-owner)."""
    user = SystemUser.objects.create(
        emailaddress1='rbac-other@crm.test',
        fullname='RBAC Other',
        securityroleid=salesperson_role,
        isdisabled=False,
    )
    user.set_password('testpass123')
    user.save()
    return user


def _owned_equipment(owner):
    """Build equipment + its catalog (category/brand/model) all owned by ``owner``.

    Each catalog factory gets an explicit owner so its ``SubFactory(Salesperson)``
    default doesn't spawn extra users — those collide on the unique email under
    ``--reuse-db --no-migrations`` (the pattern test_services.py already follows).
    """
    brand = EquipmentBrandFactory(ownerid=owner, createdby=owner, modifiedby=owner)
    category = EquipmentCategoryFactory(ownerid=owner, createdby=owner, modifiedby=owner)
    model = EquipmentModelFactory(
        brandid=brand, categoryid=category,
        ownerid=owner, createdby=owner, modifiedby=owner,
    )
    return EquipmentFactory(
        categoryid=category, brandid=brand, modelid=model,
        ownerid=owner, createdby=owner, modifiedby=owner,
    )


def _build_chain(owner):
    """Create equipment -> contract -> 1 imputable log -> estimation, all owned by ``owner``."""
    equipment = _owned_equipment(owner)
    contract = RentalContractService.create_contract(
        CreateRentalContractDto(
            equipmentid=equipment.equipmentid,
            lessorname='Lessor RBAC',
            economicnumber='ECO-RBAC',
            projectname='Proyecto RBAC',
            clientname='Cliente RBAC',
            billingmodality=BillingModalityCode.DAYS,
            monthlyrate=Decimal('45000.00'),
            basemeasurement=30,
            taxrate=Decimal('0.0800'),
            startdate=date(2026, 3, 1),
            enddate=date(2026, 3, 31),
        ),
        owner,
    )
    DailyEquipmentLogService.create_log(
        CreateDailyEquipmentLogDto(
            contractid=contract.contractid,
            estimationnumber=1,
            logdate=date(2026, 3, 2),
            hourmeterstart=Decimal('100.00'),
            hourmeterend=Decimal('108.00'),  # 8h worked (>4) => imputable
        ),
        owner,
    )
    estimation = BillingEstimationService.generate_estimation(
        GenerateEstimationDto(contractid=contract.contractid, estimationnumber=1),
        owner,
    )
    return equipment, contract, estimation


@pytest.mark.permissions
@pytest.mark.django_db
class TestMachineryOwnershipIsolation:
    """Owned machinery entities must be scoped to their owner (admin/manager bypass)."""

    # ---- RentalContract ----
    def test_get_contract_denies_non_owner(self, rbac_owner, rbac_other):
        _, contract, _ = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            RentalContractService.get_contract(contract.contractid, rbac_other)
        assert RentalContractService.get_contract(
            contract.contractid, rbac_owner
        ).contractid == contract.contractid

    def test_manager_can_access_any_contract(self, rbac_owner, sales_manager):
        _, contract, _ = _build_chain(rbac_owner)
        # Sales Manager is in ADMIN_ROLES -> bypass
        assert RentalContractService.get_contract(
            contract.contractid, sales_manager
        ).contractid == contract.contractid

    def test_list_contracts_scoped_to_owner(self, rbac_owner, rbac_other, sales_manager):
        _, contract, _ = _build_chain(rbac_owner)
        assert RentalContractService.list_contracts(rbac_owner).count() == 1
        assert RentalContractService.list_contracts(rbac_other).count() == 0
        # manager (admin bypass) sees it
        assert RentalContractService.list_contracts(sales_manager).filter(
            contractid=contract.contractid
        ).exists()

    def test_contract_not_found_raises_notfound(self, rbac_owner):
        with pytest.raises(NotFound):
            RentalContractService.get_contract(uuid4(), rbac_owner)

    # ---- DailyEquipmentLog ----
    def test_get_log_denies_non_owner(self, rbac_owner, rbac_other):
        _build_chain(rbac_owner)
        log = DailyEquipmentLogService.list_logs(rbac_owner).first()
        with pytest.raises(PermissionDenied, match='permission'):
            DailyEquipmentLogService.get_log(log.logid, rbac_other)
        assert DailyEquipmentLogService.get_log(log.logid, rbac_owner).logid == log.logid

    def test_list_logs_scoped_to_owner(self, rbac_owner, rbac_other):
        _build_chain(rbac_owner)
        assert DailyEquipmentLogService.list_logs(rbac_owner).count() == 1
        assert DailyEquipmentLogService.list_logs(rbac_other).count() == 0

    def test_get_period_summary_denies_non_owner(self, rbac_owner, rbac_other):
        _, contract, _ = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            DailyEquipmentLogService.get_period_summary(
                contract.contractid, 1, rbac_other
            )

    # ---- BillingEstimation ----
    def test_get_estimation_denies_non_owner(self, rbac_owner, rbac_other):
        _, _, estimation = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            BillingEstimationService.get_estimation(estimation.estimationid, rbac_other)
        assert BillingEstimationService.get_estimation(
            estimation.estimationid, rbac_owner
        ).estimationid == estimation.estimationid

    def test_list_estimations_scoped_to_owner(self, rbac_owner, rbac_other):
        _build_chain(rbac_owner)
        assert BillingEstimationService.list_estimations(rbac_owner).count() == 1
        assert BillingEstimationService.list_estimations(rbac_other).count() == 0

    def test_update_status_denies_non_owner(self, rbac_owner, rbac_other):
        # The high-risk status transition must not be reachable by a non-owner.
        _, _, estimation = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            BillingEstimationService.update_status(
                estimation.estimationid,
                UpdateEstimationStatusDto(statuscode=EstimationStatusCode.APPROVED),
                rbac_other,
            )

    def test_add_deduction_denies_non_owner(self, rbac_owner, rbac_other):
        _, _, estimation = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            BillingEstimationService.add_deduction(
                CreateEstimationDeductionDto(
                    estimationid=estimation.estimationid,
                    concept='Intento ajeno',
                    amount=Decimal('-100.00'),
                ),
                rbac_other,
            )

    # ---- Equipment + EquipmentInsurance ----
    def test_get_equipment_denies_non_owner(self, rbac_owner, rbac_other, sales_manager):
        equipment = _owned_equipment(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            EquipmentService.get_equipment(equipment.equipmentid, rbac_other)
        assert EquipmentService.get_equipment(
            equipment.equipmentid, rbac_owner
        ).equipmentid == equipment.equipmentid
        # manager bypass
        assert EquipmentService.get_equipment(
            equipment.equipmentid, sales_manager
        ).equipmentid == equipment.equipmentid

    def test_insurance_get_and_list_deny_non_owner(self, rbac_owner, rbac_other):
        equipment = _owned_equipment(rbac_owner)
        insurance = EquipmentInsuranceService.create_insurance(
            equipment.equipmentid,
            CreateEquipmentInsuranceDto(
                insurancetype=InsuranceTypeCode.TODO_RIESGO,
                insurancecompany='Aseguradora RBAC',
                policynumber='POL-RBAC-001',
                startdate=date(2026, 1, 1),
                expirydate=date(2027, 1, 1),
                annualpremium=Decimal('50000.00'),
                monthlypremium=Decimal('4166.67'),
                insuredamount=Decimal('2500000.00'),
            ),
            rbac_owner,
        )
        # non-owner of the PARENT equipment is denied on both get and list
        with pytest.raises(PermissionDenied, match='permission'):
            EquipmentInsuranceService.get_insurance(insurance.insuranceid, rbac_other)
        with pytest.raises(PermissionDenied, match='permission'):
            EquipmentInsuranceService.list_insurance(equipment.equipmentid, rbac_other)
        # owner succeeds
        assert EquipmentInsuranceService.get_insurance(
            insurance.insuranceid, rbac_owner
        ).insuranceid == insurance.insuranceid

    # ---- write-side denial: pin the gate independently of which getter the mutator calls ----
    def test_update_equipment_denies_non_owner(self, rbac_owner, rbac_other):
        equipment = _owned_equipment(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            EquipmentService.update_equipment(
                equipment.equipmentid, UpdateEquipmentDto(), rbac_other
            )

    def test_update_contract_denies_non_owner(self, rbac_owner, rbac_other):
        _, contract, _ = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            RentalContractService.update_contract(
                contract.contractid, UpdateRentalContractDto(), rbac_other
            )

    def test_update_log_denies_non_owner(self, rbac_owner, rbac_other):
        _build_chain(rbac_owner)
        log = DailyEquipmentLogService.list_logs(rbac_owner).first()
        with pytest.raises(PermissionDenied, match='permission'):
            DailyEquipmentLogService.update_log(
                log.logid, UpdateDailyEquipmentLogDto(), rbac_other
            )

    def test_create_insurance_denies_non_owner_of_parent(self, rbac_owner, rbac_other):
        equipment = _owned_equipment(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            EquipmentInsuranceService.create_insurance(
                equipment.equipmentid,
                CreateEquipmentInsuranceDto(
                    insurancetype=InsuranceTypeCode.TODO_RIESGO,
                    insurancecompany='Aseguradora Ajena',
                    policynumber='POL-DENY-001',
                    startdate=date(2026, 1, 1),
                    expirydate=date(2027, 1, 1),
                    annualpremium=Decimal('10000.00'),
                    monthlypremium=Decimal('833.33'),
                    insuredamount=Decimal('500000.00'),
                ),
                rbac_other,
            )

    def test_readonly_user_denied_non_owned_contract(self, rbac_owner, readonly_user):
        # A Read-Only User holds MACHINERY_READ but is NOT in ADMIN_ROLES, so the
        # record-level gate must still deny another owner's contract (separates the
        # permission axis from the ownership axis).
        _, contract, _ = _build_chain(rbac_owner)
        with pytest.raises(PermissionDenied, match='permission'):
            RentalContractService.get_contract(contract.contractid, readonly_user)


@pytest.mark.permissions
@pytest.mark.django_db
class TestMachineryCatalogStaysGlobal:
    """Catalogs (EquipmentCategory/Brand/Model, JustificationReason) are global
    reference data — visible to any MACHINERY_READ user, NOT owner-filtered."""

    def test_equipment_category_catalog_visible_to_non_owner(self, rbac_owner, rbac_other):
        # A category owned by one user must still be listable by another: catalogs
        # are global (this pins the removal of the erroneous owner-filter on the
        # catalog list methods).
        category = EquipmentCategoryFactory(
            ownerid=rbac_owner, createdby=rbac_owner, modifiedby=rbac_owner
        )
        listed = EquipmentCategoryService.list_categories(rbac_other)
        assert listed.filter(categoryid=category.categoryid).exists()

    def test_justification_reason_catalog_aggregates_across_owners(self, rbac_owner, rbac_other):
        # Reasons created by two different owners both appear in a single catalog
        # list — proving the catalog aggregates across owners, not scoped to one.
        JustificationReasonService.create_reason(
            CreateJustificationReasonDto(name='Motivo De Owner', imputabilityvalue=1),
            rbac_owner,
        )
        JustificationReasonService.create_reason(
            CreateJustificationReasonDto(name='Motivo De Other', imputabilityvalue=0),
            rbac_other,
        )
        names = [r.name for r in JustificationReasonService.list_reasons()]
        assert 'Motivo De Owner' in names
        assert 'Motivo De Other' in names
