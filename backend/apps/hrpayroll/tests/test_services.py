"""
Unit tests for HR & Payroll services.

Tests all service methods: Employee CRUD, payroll run workflow,
attendance operations, catalog management, and period generation.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import patch

from apps.hrpayroll.models import (
    Employee, EmployeeStateCode, EmployeeStatusCode, SalaryTypeCode,
    EmployeeProjectAssignment, AssignmentStateCode,
    DeductionType, AdditionType, CalculationTypeCode,
    PayrollPeriod, PeriodTypeCode, PeriodStateCode,
    PayrollRun, PayrollRunStateCode,
    PayrollEntry, PaymentStatusCode,
    AttendanceRecord, AttendanceTypeCode,
)
from apps.hrpayroll.services import (
    EmployeeService, AssignmentService, CatalogService,
    PayrollPeriodService, PayrollRunService, AttendanceService,
)
from apps.hrpayroll.schemas import (
    CreateEmployeeDto, UpdateEmployeeDto, TerminateEmployeeDto,
    CreateAssignmentDto, UpdateAssignmentDto,
    CreateDeductionTypeDto, CreateAdditionTypeDto,
    UpdateDeductionTypeDto, UpdateAdditionTypeDto,
    CreatePayrollPeriodDto, GeneratePeriodsDto,
    CreatePayrollRunDto, RejectPayrollDto, UpdatePayrollEntryDto,
    CreateAttendanceDto, UpdateAttendanceDto,
)
from apps.hrpayroll.tests.factories import (
    EmployeeFactory, ActiveEmployeeFactory, TerminatedEmployeeFactory,
    DeductionTypeFactory, AdditionTypeFactory,
    PayrollPeriodFactory, PayrollRunFactory, PayrollEntryFactory,
    AttendanceRecordFactory,
)
from apps.users.tests.factories import SalespersonFactory, SystemAdminFactory
from core.exceptions import ValidationError, NotFound, PermissionDenied


# ============================================================================
# EmployeeService Tests
# ============================================================================

@pytest.mark.unit
class TestEmployeeServiceCreate:
    """Tests for EmployeeService.create_employee."""

    def test_create_employee_minimal(self, db, salesperson):
        dto = CreateEmployeeDto(
            firstname='Juan',
            lastname='Perez',
            hiredate=date.today(),
            position='Obrero General',
            department='Obra Civil',
            basesalary=Decimal('3500.00'),
        )
        employee = EmployeeService.create_employee(dto, salesperson)

        assert employee.employeeid is not None
        assert employee.firstname == 'Juan'
        assert employee.lastname == 'Perez'
        assert employee.fullname == 'Juan Perez'
        assert employee.statecode == EmployeeStateCode.ACTIVE
        assert employee.statuscode == EmployeeStatusCode.PROBATION
        assert employee.ownerid == salesperson
        assert employee.employeenumber.startswith('EMP-')

    def test_create_employee_auto_number_sequential(self, db, salesperson):
        dto1 = CreateEmployeeDto(
            firstname='A', lastname='One',
            hiredate=date.today(), position='P', department='D',
            basesalary=Decimal('1000.00'),
        )
        dto2 = CreateEmployeeDto(
            firstname='B', lastname='Two',
            hiredate=date.today(), position='P', department='D',
            basesalary=Decimal('1000.00'),
        )
        emp1 = EmployeeService.create_employee(dto1, salesperson)
        emp2 = EmployeeService.create_employee(dto2, salesperson)

        num1 = int(emp1.employeenumber.split('-')[-1])
        num2 = int(emp2.employeenumber.split('-')[-1])
        assert num2 == num1 + 1

    def test_create_employee_with_different_owner(self, db, salesperson, salesperson2):
        dto = CreateEmployeeDto(
            firstname='Carlos', lastname='Garcia',
            hiredate=date.today(), position='Ingeniero', department='Obra',
            basesalary=Decimal('8000.00'),
            ownerid=salesperson2.systemuserid,
        )
        employee = EmployeeService.create_employee(dto, salesperson)
        assert employee.ownerid == salesperson2
        assert employee.createdby == salesperson

    def test_create_employee_invalid_owner_raises(self, db, salesperson):
        dto = CreateEmployeeDto(
            firstname='Bad', lastname='Owner',
            hiredate=date.today(), position='P', department='D',
            basesalary=Decimal('1000.00'),
            ownerid=uuid4(),
        )
        with pytest.raises(ValidationError):
            EmployeeService.create_employee(dto, salesperson)


@pytest.mark.unit
class TestEmployeeServiceList:
    """Tests for EmployeeService.list_employees."""

    def test_list_employees_returns_own(self, db, salesperson):
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        result = EmployeeService.list_employees(user=salesperson)
        assert result.count() == 1

    def test_list_employees_filter_by_statecode(self, db, salesperson):
        EmployeeFactory(
            statecode=EmployeeStateCode.ACTIVE,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        TerminatedEmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = EmployeeService.list_employees(user=salesperson, statecode=0)
        assert all(e.statecode == EmployeeStateCode.ACTIVE for e in result)

    def test_list_employees_filter_by_department(self, db, salesperson):
        EmployeeFactory(
            department='Electricidad',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        EmployeeFactory(
            department='Obra Civil',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = EmployeeService.list_employees(user=salesperson, department='Electric')
        assert result.count() == 1

    def test_list_employees_search(self, db, salesperson):
        EmployeeFactory(
            firstname='UniqueSearchName', lastname='TestLast',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = EmployeeService.list_employees(user=salesperson, search='UniqueSearchName')
        assert result.count() == 1


@pytest.mark.unit
class TestEmployeeServiceGetUpdateDelete:
    """Tests for get, update, and delete employee operations."""

    def test_get_employee_by_id(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = EmployeeService.get_employee_by_id(employee.employeeid, salesperson)
        assert result.employeeid == employee.employeeid

    def test_get_employee_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            EmployeeService.get_employee_by_id(uuid4(), salesperson)

    def test_get_employee_permission_denied_for_other_owner(self, db, salesperson, salesperson2):
        employee = EmployeeFactory(
            ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2,
        )
        with pytest.raises(PermissionDenied):
            EmployeeService.get_employee_by_id(employee.employeeid, salesperson)

    def test_admin_can_access_any_employee(self, db, system_admin, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        result = EmployeeService.get_employee_by_id(employee.employeeid, system_admin)
        assert result.employeeid == employee.employeeid

    def test_update_employee(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = UpdateEmployeeDto(position='Ingeniero Senior', basesalary=Decimal('12000.00'))
        updated = EmployeeService.update_employee(employee.employeeid, dto, salesperson)
        assert updated.position == 'Ingeniero Senior'
        assert updated.basesalary == Decimal('12000.00')

    def test_delete_employee_soft_deletes(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        EmployeeService.delete_employee(employee.employeeid, salesperson)
        employee.refresh_from_db()
        assert employee.statecode == EmployeeStateCode.TERMINATED
        assert employee.statuscode == EmployeeStatusCode.DISMISSED
        assert employee.terminationdate == date.today()


@pytest.mark.unit
@pytest.mark.workflow
class TestTerminateEmployee:
    """Tests for EmployeeService.terminate_employee workflow."""

    def test_terminate_voluntary_exit(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = TerminateEmployeeDto(
            terminationdate=date.today(),
            statuscode=EmployeeStatusCode.VOLUNTARY_EXIT,
            notes='Resigned',
        )
        result = EmployeeService.terminate_employee(employee.employeeid, dto, salesperson)
        assert result.statecode == EmployeeStateCode.TERMINATED
        assert result.statuscode == EmployeeStatusCode.VOLUNTARY_EXIT
        assert result.terminationdate == date.today()
        assert 'Resigned' in result.notes

    def test_terminate_dismissed(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = TerminateEmployeeDto(
            terminationdate=date.today(),
            statuscode=EmployeeStatusCode.DISMISSED,
        )
        result = EmployeeService.terminate_employee(employee.employeeid, dto, salesperson)
        assert result.statecode == EmployeeStateCode.TERMINATED
        assert result.statuscode == EmployeeStatusCode.DISMISSED

    def test_terminate_already_terminated_raises(self, db, salesperson):
        employee = TerminatedEmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = TerminateEmployeeDto(
            terminationdate=date.today(),
            statuscode=EmployeeStatusCode.DISMISSED,
        )
        with pytest.raises(ValidationError, match="already terminated"):
            EmployeeService.terminate_employee(employee.employeeid, dto, salesperson)

    def test_terminate_invalid_status_raises(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = TerminateEmployeeDto(
            terminationdate=date.today(),
            statuscode=EmployeeStatusCode.ON_VACATION,
        )
        with pytest.raises(ValidationError, match="Voluntary Exit"):
            EmployeeService.terminate_employee(employee.employeeid, dto, salesperson)


# ============================================================================
# CatalogService Tests
# ============================================================================

@pytest.mark.unit
class TestCatalogService:
    """Tests for CatalogService (DeductionType + AdditionType)."""

    def test_create_deduction_type(self, db, salesperson):
        dto = CreateDeductionTypeDto(
            code='isr', name='Impuesto Sobre la Renta',
            calculationtype=CalculationTypeCode.PERCENTAGE,
            defaultvalue=Decimal('10.0000'),
            isstatutory=True,
        )
        dt = CatalogService.create_deduction_type(dto, salesperson)
        assert dt.code == 'ISR'  # Code uppercased
        assert dt.isstatutory is True

    def test_create_addition_type(self, db, salesperson):
        dto = CreateAdditionTypeDto(
            code='ot', name='Horas Extra',
            calculationtype=CalculationTypeCode.HOURS_MULTIPLIER,
            defaultvalue=Decimal('2.0000'),
            istaxable=True,
        )
        at = CatalogService.create_addition_type(dto, salesperson)
        assert at.code == 'OT'
        assert at.istaxable is True

    def test_update_deduction_type(self, db, salesperson):
        dt = DeductionTypeFactory(createdby=salesperson, modifiedby=salesperson)
        dto = UpdateDeductionTypeDto(name='Updated Name', defaultvalue=Decimal('15.0000'))
        updated = CatalogService.update_deduction_type(dt.deductiontypeid, dto, salesperson)
        assert updated.name == 'Updated Name'
        assert updated.defaultvalue == Decimal('15.0000')

    def test_update_deduction_type_not_found(self, db, salesperson):
        dto = UpdateDeductionTypeDto(name='X')
        with pytest.raises(NotFound):
            CatalogService.update_deduction_type(uuid4(), dto, salesperson)

    def test_list_deduction_types(self, db, salesperson):
        DeductionTypeFactory(statecode=0, createdby=salesperson, modifiedby=salesperson)
        DeductionTypeFactory(statecode=1, createdby=salesperson, modifiedby=salesperson)
        result = CatalogService.list_deduction_types(statecode=0)
        assert all(d.statecode == 0 for d in result)

    def test_seed_default_deductions(self, db, salesperson):
        created = CatalogService.seed_default_deductions(salesperson)
        assert len(created) >= 4  # ISR, IMSS, INFONAVIT, SAR at minimum
        codes = [d.code for d in created]
        assert 'ISR' in codes
        assert 'IMSS' in codes

    def test_seed_default_additions(self, db, salesperson):
        created = CatalogService.seed_default_additions(salesperson)
        assert len(created) >= 4
        codes = [a.code for a in created]
        assert 'OT' in codes
        assert 'BONUS' in codes

    def test_seed_deductions_idempotent(self, db, salesperson):
        first = CatalogService.seed_default_deductions(salesperson)
        second = CatalogService.seed_default_deductions(salesperson)
        assert len(second) == 0  # All already exist


# ============================================================================
# PayrollPeriodService Tests
# ============================================================================

@pytest.mark.unit
class TestPayrollPeriodService:
    """Tests for PayrollPeriodService."""

    def test_create_period(self, db, salesperson):
        dto = CreatePayrollPeriodDto(
            periodnumber=1, periodtype=PeriodTypeCode.WEEKLY,
            startdate=date(2026, 1, 5), enddate=date(2026, 1, 11),
            year=2026, label='SEM-2026-01',
        )
        period = PayrollPeriodService.create_period(dto, salesperson)
        assert period.payrollperiodid is not None
        assert period.statecode == PeriodStateCode.OPEN

    def test_generate_weekly_periods(self, db, salesperson):
        dto = GeneratePeriodsDto(year=2026, periodtype=PeriodTypeCode.WEEKLY)
        periods = PayrollPeriodService.generate_periods(dto, salesperson)
        assert len(periods) == 52

    def test_generate_biweekly_periods(self, db, salesperson):
        dto = GeneratePeriodsDto(year=2026, periodtype=PeriodTypeCode.BIWEEKLY)
        periods = PayrollPeriodService.generate_periods(dto, salesperson)
        assert len(periods) == 24

    def test_generate_monthly_periods(self, db, salesperson):
        dto = GeneratePeriodsDto(year=2026, periodtype=PeriodTypeCode.MONTHLY)
        periods = PayrollPeriodService.generate_periods(dto, salesperson)
        assert len(periods) == 12
        assert periods[0].label == 'MES-2026-01'
        assert periods[-1].label == 'MES-2026-12'

    def test_generate_periods_idempotent(self, db, salesperson):
        dto = GeneratePeriodsDto(year=2026, periodtype=PeriodTypeCode.MONTHLY)
        first = PayrollPeriodService.generate_periods(dto, salesperson)
        second = PayrollPeriodService.generate_periods(dto, salesperson)
        assert len(first) == 12
        assert len(second) == 0

    def test_list_periods_filter_by_year(self, db, salesperson):
        PayrollPeriodFactory(year=2026, createdby=salesperson, modifiedby=salesperson)
        PayrollPeriodFactory(year=2025, periodnumber=99, createdby=salesperson, modifiedby=salesperson)
        result = PayrollPeriodService.list_periods(year=2026)
        assert all(p.year == 2026 for p in result)


# ============================================================================
# PayrollRunService Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workflow
class TestPayrollRunServiceCreate:
    """Tests for PayrollRunService.create_run."""

    def test_create_run(self, db, system_admin, salesperson):
        period = PayrollPeriodFactory(createdby=system_admin, modifiedby=system_admin)
        # Create active employees so entries are generated
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)

        dto = CreatePayrollRunDto(payrollperiodid=period.payrollperiodid)
        run = PayrollRunService.create_run(dto, system_admin)

        assert run.payrollrunid is not None
        assert run.statecode == PayrollRunStateCode.DRAFT
        assert run.runnumber.startswith('NOM-')
        assert run.employeecount == 2

    def test_create_run_closed_period_raises(self, db, system_admin):
        period = PayrollPeriodFactory(
            statecode=PeriodStateCode.CLOSED,
            createdby=system_admin, modifiedby=system_admin,
        )
        dto = CreatePayrollRunDto(payrollperiodid=period.payrollperiodid)
        with pytest.raises(ValidationError, match="closed period"):
            PayrollRunService.create_run(dto, system_admin)

    def test_create_run_invalid_period_raises(self, db, system_admin):
        dto = CreatePayrollRunDto(payrollperiodid=uuid4())
        with pytest.raises(ValidationError):
            PayrollRunService.create_run(dto, system_admin)


@pytest.mark.unit
@pytest.mark.workflow
class TestPayrollRunWorkflow:
    """Tests for the full payroll run workflow: calculate -> submit -> approve/reject -> paid."""

    def test_calculate_payroll(self, db, system_admin, salesperson):
        period = PayrollPeriodFactory(createdby=system_admin, modifiedby=system_admin)
        employee = EmployeeFactory(
            basesalary=Decimal('5000.00'),
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        run = PayrollRunFactory(
            payrollperiodid=period,
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        PayrollEntryFactory(
            payrollrunid=run, employeeid=employee,
            basepay=Decimal('5000.00'),
            createdby=system_admin, modifiedby=system_admin,
        )
        # Seed statutory deductions for the calculation
        CatalogService.seed_default_deductions(system_admin)
        CatalogService.seed_default_additions(system_admin)

        result = PayrollRunService.calculate_payroll(run.payrollrunid, system_admin)

        assert result.statecode == PayrollRunStateCode.CALCULATED
        assert result.totalgrosspay > 0

        # Verify entries were calculated
        entry = PayrollEntry.objects.filter(payrollrunid=run).first()
        assert entry.grosspay > 0
        assert entry.totaldeductions > 0
        assert entry.netpay > 0
        assert len(entry.deductions) > 0

    def test_calculate_payroll_invalid_state_raises(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.APPROVED,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        with pytest.raises(ValidationError, match="Cannot calculate"):
            PayrollRunService.calculate_payroll(run.payrollrunid, system_admin)

    def test_submit_for_approval(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.CALCULATED,
            employeecount=5,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        result = PayrollRunService.submit_for_approval(run.payrollrunid, system_admin)
        assert result.statecode == PayrollRunStateCode.PENDING_APPROVAL

    def test_submit_empty_run_raises(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.DRAFT,
            employeecount=0,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        with pytest.raises(ValidationError, match="empty payroll"):
            PayrollRunService.submit_for_approval(run.payrollrunid, system_admin)

    def test_approve_payroll(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.PENDING_APPROVAL,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        result = PayrollRunService.approve_payroll(run.payrollrunid, system_admin)
        assert result.statecode == PayrollRunStateCode.APPROVED
        assert result.approvedby == system_admin
        assert result.approveddate is not None

    def test_approve_wrong_state_raises(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        with pytest.raises(ValidationError, match="Cannot approve"):
            PayrollRunService.approve_payroll(run.payrollrunid, system_admin)

    def test_reject_payroll(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.PENDING_APPROVAL,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        dto = RejectPayrollDto(reason='Incorrect amounts')
        result = PayrollRunService.reject_payroll(run.payrollrunid, dto, system_admin)
        assert result.statecode == PayrollRunStateCode.REJECTED
        assert 'Incorrect amounts' in result.description

    def test_reject_wrong_state_raises(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        dto = RejectPayrollDto(reason='No')
        with pytest.raises(ValidationError, match="Cannot reject"):
            PayrollRunService.reject_payroll(run.payrollrunid, dto, system_admin)

    def test_mark_as_paid(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.APPROVED,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        entry = PayrollEntryFactory(
            payrollrunid=run,
            paymentstatus=PaymentStatusCode.PENDING,
            createdby=system_admin, modifiedby=system_admin,
        )
        result = PayrollRunService.mark_as_paid(run.payrollrunid, system_admin)
        assert result.statecode == PayrollRunStateCode.PAID
        assert result.paiddate == date.today()

        entry.refresh_from_db()
        assert entry.paymentstatus == PaymentStatusCode.PAID

    def test_mark_paid_wrong_state_raises(self, db, system_admin):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        with pytest.raises(ValidationError, match="Cannot mark as paid"):
            PayrollRunService.mark_as_paid(run.payrollrunid, system_admin)


@pytest.mark.unit
class TestPayrollRunServiceEntries:
    """Tests for PayrollRunService entry-related methods."""

    def test_list_entries(self, db, system_admin, salesperson):
        run = PayrollRunFactory(
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        PayrollEntryFactory(
            payrollrunid=run, employeeid=emp,
            createdby=system_admin, modifiedby=system_admin,
        )
        entries = PayrollRunService.list_entries(run.payrollrunid, system_admin)
        assert entries.count() == 1

    def test_update_entry_in_draft(self, db, system_admin, salesperson):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        entry = PayrollEntryFactory(
            payrollrunid=run, employeeid=emp,
            createdby=system_admin, modifiedby=system_admin,
        )
        dto = UpdatePayrollEntryDto(basepay=Decimal('6000.00'), overtimehours=Decimal('4.00'))
        updated = PayrollRunService.update_entry(entry.payrollentryid, dto, system_admin)
        assert updated.basepay == Decimal('6000.00')
        assert updated.overtimehours == Decimal('4.00')

    def test_update_entry_submitted_run_raises(self, db, system_admin, salesperson):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.PENDING_APPROVAL,
            ownerid=system_admin, createdby=system_admin, modifiedby=system_admin,
        )
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        entry = PayrollEntryFactory(
            payrollrunid=run, employeeid=emp,
            createdby=system_admin, modifiedby=system_admin,
        )
        dto = UpdatePayrollEntryDto(basepay=Decimal('9999.00'))
        with pytest.raises(ValidationError, match="Cannot modify"):
            PayrollRunService.update_entry(entry.payrollentryid, dto, system_admin)

    def test_update_entry_not_found(self, db, system_admin):
        dto = UpdatePayrollEntryDto(basepay=Decimal('100.00'))
        with pytest.raises(NotFound):
            PayrollRunService.update_entry(uuid4(), dto, system_admin)

    def test_get_run_not_found(self, db, system_admin):
        with pytest.raises(NotFound):
            PayrollRunService.get_run_by_id(uuid4(), system_admin)

    def test_get_run_permission_denied(self, db, salesperson, salesperson2):
        run = PayrollRunFactory(
            ownerid=salesperson2, createdby=salesperson2, modifiedby=salesperson2,
        )
        with pytest.raises(PermissionDenied):
            PayrollRunService.get_run_by_id(run.payrollrunid, salesperson)


# ============================================================================
# AttendanceService Tests
# ============================================================================

@pytest.mark.unit
class TestAttendanceService:
    """Tests for AttendanceService."""

    def test_create_attendance(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        dto = CreateAttendanceDto(
            employeeid=employee.employeeid,
            attendancedate=date(2026, 3, 25),
            regularhoursworked=Decimal('8.00'),
            attendancetype=AttendanceTypeCode.PRESENT,
        )
        record = AttendanceService.create_attendance(dto, salesperson)
        assert record.attendanceid is not None
        assert record.regularhoursworked == Decimal('8.00')

    def test_create_attendance_invalid_employee(self, db, salesperson):
        dto = CreateAttendanceDto(
            employeeid=uuid4(),
            attendancedate=date(2026, 3, 25),
        )
        with pytest.raises(ValidationError, match="Employee"):
            AttendanceService.create_attendance(dto, salesperson)

    def test_update_attendance(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        record = AttendanceRecordFactory(
            employeeid=employee,
            attendancedate=date(2026, 3, 24),
            createdby=salesperson, modifiedby=salesperson,
        )
        dto = UpdateAttendanceDto(
            regularhoursworked=Decimal('6.00'),
            attendancetype=AttendanceTypeCode.HALF_DAY,
        )
        updated = AttendanceService.update_attendance(record.attendanceid, dto, salesperson)
        assert updated.regularhoursworked == Decimal('6.00')
        assert updated.attendancetype == AttendanceTypeCode.HALF_DAY

    def test_update_attendance_not_found(self, db, salesperson):
        dto = UpdateAttendanceDto(regularhoursworked=Decimal('4.00'))
        with pytest.raises(NotFound):
            AttendanceService.update_attendance(uuid4(), dto, salesperson)

    def test_delete_attendance(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        record = AttendanceRecordFactory(
            employeeid=employee,
            attendancedate=date(2026, 3, 23),
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceService.delete_attendance(record.attendanceid, salesperson)
        assert not AttendanceRecord.objects.filter(attendanceid=record.attendanceid).exists()

    def test_delete_attendance_not_found(self, db, salesperson):
        with pytest.raises(NotFound):
            AttendanceService.delete_attendance(uuid4(), salesperson)

    def test_list_attendance_filter_by_employee(self, db, salesperson):
        emp1 = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        emp2 = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        AttendanceRecordFactory(
            employeeid=emp1, attendancedate=date(2026, 3, 20),
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=emp2, attendancedate=date(2026, 3, 20),
            createdby=salesperson, modifiedby=salesperson,
        )
        result = AttendanceService.list_attendance(
            user=salesperson, employeeid=emp1.employeeid,
        )
        assert result.count() == 1

    def test_list_attendance_filter_by_date_range(self, db, salesperson):
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 1),
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 15),
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 28),
            createdby=salesperson, modifiedby=salesperson,
        )
        result = AttendanceService.list_attendance(
            user=salesperson,
            startdate=date(2026, 3, 10),
            enddate=date(2026, 3, 20),
        )
        assert result.count() == 1

    def test_bulk_create_attendance(self, db, salesperson):
        emp1 = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        emp2 = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        entries = [
            CreateAttendanceDto(
                employeeid=emp1.employeeid,
                attendancedate=date(2026, 3, 22),
            ),
            CreateAttendanceDto(
                employeeid=emp2.employeeid,
                attendancedate=date(2026, 3, 22),
            ),
        ]
        records = AttendanceService.bulk_create_attendance(entries, salesperson)
        assert len(records) == 2

    def test_get_attendance_summary(self, db, salesperson):
        emp = EmployeeFactory(ownerid=salesperson, createdby=salesperson, modifiedby=salesperson)
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 1),
            regularhoursworked=Decimal('8.00'), overtimehoursworked=Decimal('2.00'),
            attendancetype=AttendanceTypeCode.PRESENT,
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 2),
            regularhoursworked=Decimal('8.00'), overtimehoursworked=Decimal('0.00'),
            attendancetype=AttendanceTypeCode.PRESENT,
            createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=emp, attendancedate=date(2026, 3, 3),
            regularhoursworked=Decimal('0.00'), overtimehoursworked=Decimal('0.00'),
            attendancetype=AttendanceTypeCode.ABSENT,
            createdby=salesperson, modifiedby=salesperson,
        )

        summary = AttendanceService.get_attendance_summary(
            emp.employeeid, date(2026, 3, 1), date(2026, 3, 31),
        )
        assert summary['present_days'] == 2
        assert summary['absent_days'] == 1
        assert summary['total_records'] == 3
        assert summary['total_regular_hours'] == 16.0
        assert summary['total_overtime_hours'] == 2.0
