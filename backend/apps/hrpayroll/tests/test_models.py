"""
Unit tests for HR & Payroll models.

Tests all model entities, enum definitions, computed properties,
str representations, and auto-numbering patterns.
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta, time
from django.db import IntegrityError

from apps.hrpayroll.models import (
    Employee, EmployeeStateCode, EmployeeStatusCode, SalaryTypeCode,
    EmployeeProjectAssignment, AssignmentStateCode,
    DeductionType, AdditionType, CalculationTypeCode,
    PayrollPeriod, PeriodTypeCode, PeriodStateCode,
    PayrollRun, PayrollRunStateCode,
    PayrollEntry, PaymentStatusCode,
    AttendanceRecord, AttendanceTypeCode,
)
from apps.hrpayroll.tests.factories import (
    EmployeeFactory, ActiveEmployeeFactory, TerminatedEmployeeFactory,
    DeductionTypeFactory, AdditionTypeFactory,
    PayrollPeriodFactory, PayrollRunFactory, PayrollEntryFactory,
    AttendanceRecordFactory,
)
from apps.users.tests.factories import SalespersonFactory


# ============================================================================
# Enum Tests
# ============================================================================

@pytest.mark.unit
class TestEmployeeEnums:
    """Tests for Employee-related enum definitions."""

    def test_employee_state_code_values(self):
        assert EmployeeStateCode.ACTIVE.value == 0
        assert EmployeeStateCode.ON_LEAVE.value == 1
        assert EmployeeStateCode.TERMINATED.value == 2

        assert EmployeeStateCode.ACTIVE.label == 'Active'
        assert EmployeeStateCode.ON_LEAVE.label == 'On Leave'
        assert EmployeeStateCode.TERMINATED.label == 'Terminated'

    def test_employee_status_code_values(self):
        assert EmployeeStatusCode.PROBATION.value == 0
        assert EmployeeStatusCode.CONFIRMED.value == 1
        assert EmployeeStatusCode.ON_VACATION.value == 2
        assert EmployeeStatusCode.SICK_LEAVE.value == 3
        assert EmployeeStatusCode.SUSPENDED.value == 4
        assert EmployeeStatusCode.VOLUNTARY_EXIT.value == 5
        assert EmployeeStatusCode.DISMISSED.value == 6

    def test_salary_type_code_values(self):
        assert SalaryTypeCode.HOURLY.value == 0
        assert SalaryTypeCode.WEEKLY.value == 1
        assert SalaryTypeCode.BIWEEKLY.value == 2
        assert SalaryTypeCode.MONTHLY.value == 3

        assert SalaryTypeCode.HOURLY.label == 'Hourly'
        assert SalaryTypeCode.MONTHLY.label == 'Monthly'

    def test_assignment_state_code_values(self):
        assert AssignmentStateCode.ACTIVE.value == 0
        assert AssignmentStateCode.COMPLETED.value == 1
        assert AssignmentStateCode.CANCELED.value == 2

    def test_calculation_type_code_values(self):
        assert CalculationTypeCode.FIXED_AMOUNT.value == 0
        assert CalculationTypeCode.PERCENTAGE.value == 1
        assert CalculationTypeCode.HOURS_MULTIPLIER.value == 2


@pytest.mark.unit
class TestPayrollEnums:
    """Tests for Payroll-related enum definitions."""

    def test_period_type_code_values(self):
        assert PeriodTypeCode.WEEKLY.value == 0
        assert PeriodTypeCode.BIWEEKLY.value == 1
        assert PeriodTypeCode.MONTHLY.value == 2

    def test_period_state_code_values(self):
        assert PeriodStateCode.OPEN.value == 0
        assert PeriodStateCode.PROCESSING.value == 1
        assert PeriodStateCode.CLOSED.value == 2

    def test_payroll_run_state_code_values(self):
        assert PayrollRunStateCode.DRAFT.value == 0
        assert PayrollRunStateCode.CALCULATED.value == 1
        assert PayrollRunStateCode.PENDING_APPROVAL.value == 2
        assert PayrollRunStateCode.APPROVED.value == 3
        assert PayrollRunStateCode.PAID.value == 4
        assert PayrollRunStateCode.REJECTED.value == 5

    def test_payment_status_code_values(self):
        assert PaymentStatusCode.PENDING.value == 0
        assert PaymentStatusCode.PAID.value == 1
        assert PaymentStatusCode.FAILED.value == 2

    def test_attendance_type_code_values(self):
        assert AttendanceTypeCode.PRESENT.value == 0
        assert AttendanceTypeCode.ABSENT.value == 1
        assert AttendanceTypeCode.HALF_DAY.value == 2
        assert AttendanceTypeCode.HOLIDAY.value == 3
        assert AttendanceTypeCode.REST_DAY.value == 4


# ============================================================================
# Employee Model Tests
# ============================================================================

@pytest.mark.unit
class TestEmployeeModel:
    """Tests for Employee model creation and properties."""

    def test_create_employee_minimal(self, db):
        owner = SalespersonFactory()
        employee = Employee.objects.create(
            employeenumber='EMP-2026-001',
            firstname='Juan',
            lastname='Perez',
            hiredate=date.today(),
            position='Obrero',
            department='Obra Civil',
            basesalary=Decimal('3500.00'),
            ownerid=owner,
            createdby=owner,
            modifiedby=owner,
        )
        assert employee.employeeid is not None
        assert employee.firstname == 'Juan'
        assert employee.statecode == EmployeeStateCode.ACTIVE
        assert employee.statuscode == EmployeeStatusCode.PROBATION

    def test_fullname_computed_on_save(self, db):
        owner = SalespersonFactory()
        employee = EmployeeFactory(
            firstname='Carlos', lastname='Garcia',
            ownerid=owner, createdby=owner, modifiedby=owner,
        )
        assert employee.fullname == 'Carlos Garcia'

    def test_str_representation(self, db, salesperson):
        employee = EmployeeFactory(
            firstname='Ana', lastname='Lopez',
            employeenumber='EMP-2026-099',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert str(employee) == 'Ana Lopez (EMP-2026-099)'

    def test_state_name_property(self, db, salesperson):
        employee = EmployeeFactory(
            statecode=EmployeeStateCode.ON_LEAVE,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert employee.state_name == 'On Leave'

    def test_status_name_property(self, db, salesperson):
        employee = EmployeeFactory(
            statuscode=EmployeeStatusCode.SICK_LEAVE,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert employee.status_name == 'Sick Leave'

    def test_salary_type_name_property(self, db, salesperson):
        employee = EmployeeFactory(
            salarytype=SalaryTypeCode.MONTHLY,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert employee.salary_type_name == 'Monthly'

    def test_unique_employee_number(self, db, salesperson):
        EmployeeFactory(
            employeenumber='EMP-2026-500',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(IntegrityError):
            EmployeeFactory(
                employeenumber='EMP-2026-500',
                ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
            )

    def test_terminated_employee_factory(self, db, salesperson):
        employee = TerminatedEmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert employee.statecode == EmployeeStateCode.TERMINATED
        assert employee.statuscode == EmployeeStatusCode.VOLUNTARY_EXIT
        assert employee.terminationdate is not None


# ============================================================================
# DeductionType / AdditionType Model Tests
# ============================================================================

@pytest.mark.unit
class TestCatalogModels:
    """Tests for DeductionType and AdditionType catalog models."""

    def test_create_deduction_type(self, db, salesperson):
        dt = DeductionTypeFactory(
            code='ISR', name='Impuesto Sobre la Renta',
            calculationtype=CalculationTypeCode.PERCENTAGE,
            defaultvalue=Decimal('10.0000'),
            isstatutory=True,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert dt.deductiontypeid is not None
        assert dt.code == 'ISR'
        assert dt.isstatutory is True
        assert str(dt) == 'ISR - Impuesto Sobre la Renta'

    def test_create_addition_type(self, db, salesperson):
        at = AdditionTypeFactory(
            code='OT', name='Horas Extra',
            calculationtype=CalculationTypeCode.HOURS_MULTIPLIER,
            defaultvalue=Decimal('2.0000'),
            istaxable=True,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert at.additiontypeid is not None
        assert at.code == 'OT'
        assert at.istaxable is True
        assert str(at) == 'OT - Horas Extra'

    def test_unique_deduction_code(self, db, salesperson):
        DeductionTypeFactory(
            code='UNIQUE01',
            createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(IntegrityError):
            DeductionTypeFactory(
                code='UNIQUE01',
                createdby=salesperson, modifiedby=salesperson,
            )


# ============================================================================
# PayrollPeriod Model Tests
# ============================================================================

@pytest.mark.unit
class TestPayrollPeriodModel:
    """Tests for PayrollPeriod model."""

    def test_create_period(self, db, salesperson):
        period = PayrollPeriodFactory(
            periodnumber=1, periodtype=PeriodTypeCode.WEEKLY,
            year=2026, label='SEM-2026-01',
            createdby=salesperson, modifiedby=salesperson,
        )
        assert period.payrollperiodid is not None
        assert period.statecode == PeriodStateCode.OPEN
        assert str(period) == 'SEM-2026-01'

    def test_period_type_name_property(self, db, salesperson):
        period = PayrollPeriodFactory(
            periodtype=PeriodTypeCode.MONTHLY,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert period.period_type_name == 'Monthly'


# ============================================================================
# PayrollRun Model Tests
# ============================================================================

@pytest.mark.unit
class TestPayrollRunModel:
    """Tests for PayrollRun model."""

    def test_create_payroll_run(self, db, salesperson):
        period = PayrollPeriodFactory(
            label='SEM-2026-05',
            createdby=salesperson, modifiedby=salesperson,
        )
        run = PayrollRunFactory(
            payrollperiodid=period,
            runnumber='NOM-2026-001',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert run.payrollrunid is not None
        assert run.statecode == PayrollRunStateCode.DRAFT
        assert str(run) == 'NOM-2026-001 - SEM-2026-05'

    def test_state_name_property(self, db, salesperson):
        run = PayrollRunFactory(
            statecode=PayrollRunStateCode.APPROVED,
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert run.state_name == 'Approved'

    def test_default_totals_are_zero(self, db, salesperson):
        run = PayrollRunFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        assert run.totalgrosspay == 0
        assert run.totaldeductions == 0
        assert run.totaladditions == 0
        assert run.totalnetpay == 0
        assert run.employeecount == 0


# ============================================================================
# PayrollEntry Model Tests
# ============================================================================

@pytest.mark.unit
class TestPayrollEntryModel:
    """Tests for PayrollEntry model."""

    def test_create_payroll_entry(self, db, salesperson):
        employee = EmployeeFactory(
            firstname='Pedro', lastname='Ramirez',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        run = PayrollRunFactory(
            runnumber='NOM-2026-010',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        entry = PayrollEntryFactory(
            payrollrunid=run, employeeid=employee,
            basepay=Decimal('5000.00'),
            createdby=salesperson, modifiedby=salesperson,
        )
        assert entry.payrollentryid is not None
        assert entry.paymentstatus == PaymentStatusCode.PENDING
        assert str(entry) == 'Pedro Ramirez - NOM-2026-010'

    def test_payment_status_name_property(self, db, salesperson):
        entry = PayrollEntryFactory(
            paymentstatus=PaymentStatusCode.PAID,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert entry.payment_status_name == 'Paid'


# ============================================================================
# AttendanceRecord Model Tests
# ============================================================================

@pytest.mark.unit
class TestAttendanceRecordModel:
    """Tests for AttendanceRecord model."""

    def test_create_attendance_record(self, db, salesperson):
        employee = EmployeeFactory(
            firstname='Maria', lastname='Gonzalez',
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        record = AttendanceRecordFactory(
            employeeid=employee,
            attendancedate=date(2026, 3, 25),
            regularhoursworked=Decimal('8.00'),
            createdby=salesperson, modifiedby=salesperson,
        )
        assert record.attendanceid is not None
        assert record.attendancetype == AttendanceTypeCode.PRESENT
        assert str(record) == 'Maria Gonzalez - 2026-03-25'

    def test_attendance_type_name_property(self, db, salesperson):
        record = AttendanceRecordFactory(
            attendancetype=AttendanceTypeCode.HALF_DAY,
            createdby=salesperson, modifiedby=salesperson,
        )
        assert record.attendance_type_name == 'Half Day'

    def test_unique_attendance_per_day(self, db, salesperson):
        employee = EmployeeFactory(
            ownerid=salesperson, createdby=salesperson, modifiedby=salesperson,
        )
        AttendanceRecordFactory(
            employeeid=employee,
            attendancedate=date(2026, 3, 20),
            createdby=salesperson, modifiedby=salesperson,
        )
        with pytest.raises(IntegrityError):
            AttendanceRecordFactory(
                employeeid=employee,
                attendancedate=date(2026, 3, 20),
                createdby=salesperson, modifiedby=salesperson,
            )
