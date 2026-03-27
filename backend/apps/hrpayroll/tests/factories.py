"""
Factory Boy factories for HR & Payroll models.
"""

import factory
from datetime import date, timedelta
from decimal import Decimal
from factory.django import DjangoModelFactory
from apps.hrpayroll.models import (
    Employee, EmployeeStateCode, EmployeeStatusCode, SalaryTypeCode,
    EmployeeProjectAssignment, AssignmentStateCode,
    DeductionType, AdditionType, CalculationTypeCode,
    PayrollPeriod, PeriodTypeCode, PeriodStateCode,
    PayrollRun, PayrollRunStateCode,
    PayrollEntry, PaymentStatusCode,
    AttendanceRecord, AttendanceTypeCode,
)
from apps.users.tests.factories import SalespersonFactory


class EmployeeFactory(DjangoModelFactory):
    """Factory for creating Employee instances."""

    class Meta:
        model = Employee

    employeenumber = factory.Sequence(lambda n: f'EMP-2026-{n + 1:03d}')
    firstname = factory.Faker('first_name')
    lastname = factory.Faker('last_name')
    curp = factory.Sequence(lambda n: f'CURP{n:014d}')
    rfc = factory.Sequence(lambda n: f'RFC{n:010d}')
    nss = factory.Sequence(lambda n: f'{n:011d}')
    emailaddress = factory.Faker('email')
    phonenumber = factory.Faker('phone_number')
    dateofbirth = factory.LazyFunction(lambda: date(1990, 1, 15))
    hiredate = factory.LazyFunction(lambda: date.today() - timedelta(days=180))
    position = 'Obrero General'
    department = 'Obra Civil'
    salarytype = SalaryTypeCode.WEEKLY
    basesalary = Decimal('3500.00')
    statecode = EmployeeStateCode.ACTIVE
    statuscode = EmployeeStatusCode.CONFIRMED
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class ActiveEmployeeFactory(EmployeeFactory):
    statecode = EmployeeStateCode.ACTIVE
    statuscode = EmployeeStatusCode.CONFIRMED


class TerminatedEmployeeFactory(EmployeeFactory):
    statecode = EmployeeStateCode.TERMINATED
    statuscode = EmployeeStatusCode.VOLUNTARY_EXIT
    terminationdate = factory.LazyFunction(date.today)


class DeductionTypeFactory(DjangoModelFactory):
    class Meta:
        model = DeductionType

    code = factory.Sequence(lambda n: f'DED{n:03d}')
    name = factory.Faker('word')
    calculationtype = CalculationTypeCode.PERCENTAGE
    defaultvalue = Decimal('5.0000')
    isstatutory = True
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class AdditionTypeFactory(DjangoModelFactory):
    class Meta:
        model = AdditionType

    code = factory.Sequence(lambda n: f'ADD{n:03d}')
    name = factory.Faker('word')
    calculationtype = CalculationTypeCode.FIXED_AMOUNT
    defaultvalue = Decimal('500.0000')
    istaxable = True
    statecode = 0
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class PayrollPeriodFactory(DjangoModelFactory):
    class Meta:
        model = PayrollPeriod

    periodnumber = factory.Sequence(lambda n: n + 1)
    periodtype = PeriodTypeCode.WEEKLY
    startdate = factory.LazyFunction(date.today)
    enddate = factory.LazyFunction(lambda: date.today() + timedelta(days=6))
    year = factory.LazyFunction(lambda: date.today().year)
    label = factory.Sequence(lambda n: f'SEM-2026-{n + 1:02d}')
    statecode = PeriodStateCode.OPEN
    createdby = factory.SubFactory(SalespersonFactory)
    modifiedby = factory.SelfAttribute('createdby')


class PayrollRunFactory(DjangoModelFactory):
    class Meta:
        model = PayrollRun

    payrollperiodid = factory.SubFactory(PayrollPeriodFactory)
    runnumber = factory.Sequence(lambda n: f'NOM-2026-{n + 1:03d}')
    statecode = PayrollRunStateCode.DRAFT
    ownerid = factory.SubFactory(SalespersonFactory)
    createdby = factory.SelfAttribute('ownerid')
    modifiedby = factory.SelfAttribute('ownerid')


class PayrollEntryFactory(DjangoModelFactory):
    class Meta:
        model = PayrollEntry

    payrollrunid = factory.SubFactory(PayrollRunFactory)
    employeeid = factory.SubFactory(EmployeeFactory)
    basepay = Decimal('3500.00')
    grosspay = Decimal('3500.00')
    totaldeductions = Decimal('0')
    totaladditions = Decimal('0')
    netpay = Decimal('3500.00')
    paymentstatus = PaymentStatusCode.PENDING
    createdby = factory.SelfAttribute('payrollrunid.ownerid')
    modifiedby = factory.SelfAttribute('createdby')


class AttendanceRecordFactory(DjangoModelFactory):
    class Meta:
        model = AttendanceRecord

    employeeid = factory.SubFactory(EmployeeFactory)
    attendancedate = factory.LazyFunction(date.today)
    regularhoursworked = Decimal('8.00')
    overtimehoursworked = Decimal('0.00')
    attendancetype = AttendanceTypeCode.PRESENT
    createdby = factory.SelfAttribute('employeeid.ownerid')
    modifiedby = factory.SelfAttribute('createdby')
