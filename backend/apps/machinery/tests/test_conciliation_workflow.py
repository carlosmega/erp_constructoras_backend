"""Integration test: full rental conciliation workflow."""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from apps.machinery.services import (
    JustificationReasonService,
    RentalContractService,
    DailyEquipmentLogService,
    BillingEstimationService,
)
from apps.machinery.models import (
    BillingModalityCode,
    EstimationStatusCode,
    ImputabilityCode,
)
from apps.machinery.schemas import (
    CreateRentalContractDto,
    CreateDailyEquipmentLogDto,
    GenerateEstimationDto,
    CreateEstimationDeductionDto,
    UpdateEstimationStatusDto,
)
from apps.machinery.tests.factories import EquipmentFactory
from apps.users.tests.factories import SystemAdminFactory


@pytest.mark.django_db
@pytest.mark.workflow
class TestFullConciliationWorkflow:
    """Replicates the full Excel flow: contract -> logs -> estimation -> deduction -> approve."""

    def test_full_workflow(self):
        # 1. Create a system user
        user = SystemAdminFactory()

        # 2. Seed justification reasons
        reasons = JustificationReasonService.seed_default_reasons(user)
        assert len(reasons) == 10

        # 3. Create an equipment instance via factory
        equipment = EquipmentFactory(ownerid=user, createdby=user, modifiedby=user)

        # 4. Create a rental contract (DAYS modality, 45000/month, base 30)
        contract_dto = CreateRentalContractDto(
            equipmentid=equipment.equipmentid,
            lessorname='ConstruPro SA de CV',
            economicnumber='ECO-001',
            projectname='Proyecto Test',
            clientname='Cliente Test',
            billingmodality=BillingModalityCode.DAYS,
            monthlyrate=Decimal('45000.00'),
            basemeasurement=30,
            taxrate=Decimal('0.0800'),
            startdate=date(2026, 3, 1),
            enddate=date(2026, 3, 31),
        )
        contract = RentalContractService.create_contract(contract_dto, user)
        assert contract.contractid is not None

        # Verify unit price: 45000 / 30 = 1500.00
        assert contract.unitprice == Decimal('1500.00')

        # 5. Create 10 daily logs with >4 hours each (all imputable)
        base_date = date(2026, 3, 2)  # Monday
        hourmeter = Decimal('1500.00')
        for i in range(10):
            log_date = base_date + timedelta(days=i)
            start = hourmeter
            end = hourmeter + Decimal('8.00')  # 8 hours worked (>4 = imputable)
            log_dto = CreateDailyEquipmentLogDto(
                contractid=contract.contractid,
                estimationnumber=1,
                logdate=log_date,
                hourmeterstart=start,
                hourmeterend=end,
            )
            log = DailyEquipmentLogService.create_log(log_dto, user)
            assert log.workedhours == Decimal('8.00')
            assert log.isimputable == ImputabilityCode.IMPUTABLE
            hourmeter = end

        # 6. Verify period summary shows 10 imputable days
        summary = DailyEquipmentLogService.get_period_summary(
            contract.contractid, estimation_number=1, user=user
        )
        assert summary['totaldays'] == 10
        assert summary['imputabledays'] == 10
        assert summary['nonimputabledays'] == 0

        # 7. Generate billing estimation
        gen_dto = GenerateEstimationDto(
            contractid=contract.contractid,
            estimationnumber=1,
        )
        estimation = BillingEstimationService.generate_estimation(gen_dto, user)

        # 8. Assert billing values
        #    measurement = 10 days (imputable)
        #    unitprice = 45000/30 = 1500.00
        #    amount = 10 * 1500 = 15000.00
        #    tax = 15000 * 0.08 = 1200.00
        #    total = 15000 + 1200 = 16200.00
        assert estimation.measurement == Decimal('10')
        assert estimation.unitprice == Decimal('1500.00')
        assert estimation.amount == Decimal('15000.00')
        assert estimation.taxamount == Decimal('1200.00')
        assert estimation.totalamount == Decimal('16200.00')
        assert estimation.statuscode == EstimationStatusCode.DRAFT

        # 9. Add a deduction (-4602.99 maintenance)
        deduction_dto = CreateEstimationDeductionDto(
            estimationid=estimation.estimationid,
            concept='Mantenimiento preventivo',
            amount=Decimal('-4602.99'),
        )
        deduction = BillingEstimationService.add_deduction(deduction_dto, user)
        assert deduction.amount == Decimal('-4602.99')

        # 10. Approve the estimation
        approve_dto = UpdateEstimationStatusDto(
            statuscode=EstimationStatusCode.APPROVED,
        )
        estimation = BillingEstimationService.update_status(
            estimation.estimationid, approve_dto, user
        )

        # 11. Assert final status is APPROVED
        assert estimation.statuscode == EstimationStatusCode.APPROVED
