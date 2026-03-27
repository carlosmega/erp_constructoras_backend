"""
HR & Payroll API schemas (DTOs).
Defines request/response schemas for all HR module endpoints.
"""

from ninja import ModelSchema, Schema
from typing import Optional, List
from uuid import UUID
from datetime import date, time
from decimal import Decimal
from apps.hrpayroll.models import (
    Employee, EmployeeProjectAssignment,
    DeductionType, AdditionType,
    PayrollPeriod, PayrollRun, PayrollEntry,
    AttendanceRecord,
)


# ============================================================================
# Employee Schemas
# ============================================================================

class EmployeeSchema(ModelSchema):
    """Full Employee response schema."""
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    salary_type_name: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = Employee
        fields = [
            'employeeid', 'employeenumber', 'firstname', 'lastname', 'fullname',
            'curp', 'rfc', 'nss', 'emailaddress', 'phonenumber', 'dateofbirth',
            'hiredate', 'terminationdate', 'position', 'department',
            'salarytype', 'basesalary',
            'bankname', 'bankaccountnumber', 'clabenumber',
            'emergencycontactname', 'emergencycontactphone', 'emergencycontactrelation',
            'statecode', 'statuscode', 'notes',
            'ownerid', 'createdon', 'modifiedon', 'createdby', 'modifiedby',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_salary_type_name(obj):
        return obj.salary_type_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class EmployeeListSchema(ModelSchema):
    """Simplified Employee schema for list views."""
    state_name: Optional[str] = None
    status_name: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = Employee
        fields = [
            'employeeid', 'employeenumber', 'fullname',
            'position', 'department', 'salarytype', 'basesalary',
            'statecode', 'statuscode', 'hiredate',
            'ownerid', 'createdon',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_status_name(obj):
        return obj.status_name

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateEmployeeDto(Schema):
    """DTO for creating a new employee."""
    firstname: str
    lastname: str
    curp: Optional[str] = None
    rfc: Optional[str] = None
    nss: Optional[str] = None
    emailaddress: Optional[str] = None
    phonenumber: Optional[str] = None
    dateofbirth: Optional[date] = None
    hiredate: date
    position: str
    department: str
    salarytype: int = 1  # Weekly default
    basesalary: Decimal
    bankname: Optional[str] = None
    bankaccountnumber: Optional[str] = None
    clabenumber: Optional[str] = None
    emergencycontactname: Optional[str] = None
    emergencycontactphone: Optional[str] = None
    emergencycontactrelation: Optional[str] = None
    notes: Optional[str] = None
    ownerid: Optional[UUID] = None


class UpdateEmployeeDto(Schema):
    """DTO for updating an employee (partial update)."""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    curp: Optional[str] = None
    rfc: Optional[str] = None
    nss: Optional[str] = None
    emailaddress: Optional[str] = None
    phonenumber: Optional[str] = None
    dateofbirth: Optional[date] = None
    position: Optional[str] = None
    department: Optional[str] = None
    salarytype: Optional[int] = None
    basesalary: Optional[Decimal] = None
    bankname: Optional[str] = None
    bankaccountnumber: Optional[str] = None
    clabenumber: Optional[str] = None
    emergencycontactname: Optional[str] = None
    emergencycontactphone: Optional[str] = None
    emergencycontactrelation: Optional[str] = None
    statuscode: Optional[int] = None
    notes: Optional[str] = None
    ownerid: Optional[UUID] = None


class TerminateEmployeeDto(Schema):
    """DTO for terminating an employee."""
    terminationdate: date
    statuscode: int  # 5=VoluntaryExit, 6=Dismissed
    notes: Optional[str] = None


# ============================================================================
# EmployeeProjectAssignment Schemas
# ============================================================================

class AssignmentSchema(ModelSchema):
    """Full assignment response schema."""
    employee_name: Optional[str] = None
    project_name: Optional[str] = None

    class Meta:
        model = EmployeeProjectAssignment
        fields = [
            'assignmentid', 'employeeid', 'projectid',
            'role', 'startdate', 'enddate', 'hoursperweek', 'isprimary',
            'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_employee_name(obj):
        return obj.employeeid.fullname if obj.employeeid else None

    @staticmethod
    def resolve_project_name(obj):
        return obj.projectid.name if obj.projectid else None


class CreateAssignmentDto(Schema):
    """DTO for creating a project assignment."""
    employeeid: UUID
    projectid: UUID
    role: str
    startdate: date
    enddate: Optional[date] = None
    hoursperweek: Optional[Decimal] = None
    isprimary: bool = False


class UpdateAssignmentDto(Schema):
    """DTO for updating a project assignment."""
    role: Optional[str] = None
    enddate: Optional[date] = None
    hoursperweek: Optional[Decimal] = None
    isprimary: Optional[bool] = None
    statecode: Optional[int] = None


# ============================================================================
# DeductionType Schemas
# ============================================================================

class DeductionTypeSchema(ModelSchema):
    """Deduction type response schema."""
    class Meta:
        model = DeductionType
        fields = [
            'deductiontypeid', 'code', 'name', 'description',
            'calculationtype', 'defaultvalue', 'isstatutory',
            'statecode', 'createdon', 'modifiedon',
        ]


class CreateDeductionTypeDto(Schema):
    code: str
    name: str
    description: Optional[str] = None
    calculationtype: int = 0
    defaultvalue: Decimal = Decimal('0')
    isstatutory: bool = False


class UpdateDeductionTypeDto(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    calculationtype: Optional[int] = None
    defaultvalue: Optional[Decimal] = None
    isstatutory: Optional[bool] = None
    statecode: Optional[int] = None


# ============================================================================
# AdditionType Schemas
# ============================================================================

class AdditionTypeSchema(ModelSchema):
    """Addition type response schema."""
    class Meta:
        model = AdditionType
        fields = [
            'additiontypeid', 'code', 'name', 'description',
            'calculationtype', 'defaultvalue', 'istaxable',
            'statecode', 'createdon', 'modifiedon',
        ]


class CreateAdditionTypeDto(Schema):
    code: str
    name: str
    description: Optional[str] = None
    calculationtype: int = 0
    defaultvalue: Decimal = Decimal('0')
    istaxable: bool = True


class UpdateAdditionTypeDto(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    calculationtype: Optional[int] = None
    defaultvalue: Optional[Decimal] = None
    istaxable: Optional[bool] = None
    statecode: Optional[int] = None


# ============================================================================
# PayrollPeriod Schemas
# ============================================================================

class PayrollPeriodSchema(ModelSchema):
    """Payroll period response schema."""
    period_type_name: Optional[str] = None

    class Meta:
        model = PayrollPeriod
        fields = [
            'payrollperiodid', 'periodnumber', 'periodtype',
            'startdate', 'enddate', 'year', 'label',
            'statecode', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_period_type_name(obj):
        return obj.period_type_name


class CreatePayrollPeriodDto(Schema):
    periodnumber: int
    periodtype: int
    startdate: date
    enddate: date
    year: int
    label: str


class GeneratePeriodsDto(Schema):
    """DTO for batch generating periods for a year."""
    year: int
    periodtype: int  # 0=Weekly, 1=Biweekly, 2=Monthly


# ============================================================================
# PayrollRun Schemas
# ============================================================================

class PayrollRunSchema(ModelSchema):
    """Full payroll run response schema."""
    state_name: Optional[str] = None
    period_label: Optional[str] = None
    project_name: Optional[str] = None
    owner_name: Optional[str] = None
    approved_by_name: Optional[str] = None

    class Meta:
        model = PayrollRun
        fields = [
            'payrollrunid', 'payrollperiodid', 'runnumber', 'description',
            'projectid',
            'totalgrosspay', 'totaldeductions', 'totaladditions', 'totalnetpay',
            'employeecount', 'statecode',
            'approvedby', 'approveddate', 'paiddate',
            'ownerid', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_period_label(obj):
        return obj.payrollperiodid.label if obj.payrollperiodid else None

    @staticmethod
    def resolve_project_name(obj):
        return obj.projectid.name if obj.projectid else None

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_approved_by_name(obj):
        return obj.approvedby.fullname if obj.approvedby else None


class PayrollRunListSchema(ModelSchema):
    """Simplified payroll run for list views."""
    state_name: Optional[str] = None
    period_label: Optional[str] = None
    owner_name: Optional[str] = None

    class Meta:
        model = PayrollRun
        fields = [
            'payrollrunid', 'runnumber', 'payrollperiodid',
            'totalnetpay', 'employeecount', 'statecode',
            'ownerid', 'createdon',
        ]

    @staticmethod
    def resolve_state_name(obj):
        return obj.state_name

    @staticmethod
    def resolve_period_label(obj):
        return obj.payrollperiodid.label if obj.payrollperiodid else None

    @staticmethod
    def resolve_owner_name(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreatePayrollRunDto(Schema):
    payrollperiodid: UUID
    description: Optional[str] = None
    projectid: Optional[UUID] = None
    ownerid: Optional[UUID] = None


class RejectPayrollDto(Schema):
    reason: Optional[str] = None


# ============================================================================
# PayrollEntry Schemas
# ============================================================================

class PayrollEntryDeductionSchema(Schema):
    """Inline deduction detail."""
    deductiontypeid: str
    code: str
    name: str
    amount: Decimal


class PayrollEntryAdditionSchema(Schema):
    """Inline addition detail."""
    additiontypeid: str
    code: str
    name: str
    amount: Decimal


class PayrollEntrySchema(ModelSchema):
    """Full payroll entry response schema."""
    employee_name: Optional[str] = None
    employee_number: Optional[str] = None
    payment_status_name: Optional[str] = None

    class Meta:
        model = PayrollEntry
        fields = [
            'payrollentryid', 'payrollrunid', 'employeeid',
            'basepay', 'regularhours', 'overtimehours',
            'grosspay', 'totaldeductions', 'totaladditions', 'netpay',
            'deductions', 'additions',
            'paymentstatus', 'notes',
            'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_employee_name(obj):
        return obj.employeeid.fullname if obj.employeeid else None

    @staticmethod
    def resolve_employee_number(obj):
        return obj.employeeid.employeenumber if obj.employeeid else None

    @staticmethod
    def resolve_payment_status_name(obj):
        return obj.payment_status_name


class UpdatePayrollEntryDto(Schema):
    """DTO for adjusting an individual payroll entry."""
    basepay: Optional[Decimal] = None
    regularhours: Optional[Decimal] = None
    overtimehours: Optional[Decimal] = None
    notes: Optional[str] = None


# ============================================================================
# AttendanceRecord Schemas
# ============================================================================

class AttendanceSchema(ModelSchema):
    """Attendance record response schema."""
    employee_name: Optional[str] = None
    project_name: Optional[str] = None
    attendance_type_name: Optional[str] = None

    class Meta:
        model = AttendanceRecord
        fields = [
            'attendanceid', 'employeeid', 'projectid',
            'attendancedate', 'checkintime', 'checkouttime',
            'regularhoursworked', 'overtimehoursworked',
            'attendancetype', 'notes',
            'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_employee_name(obj):
        return obj.employeeid.fullname if obj.employeeid else None

    @staticmethod
    def resolve_project_name(obj):
        return obj.projectid.name if obj.projectid else None

    @staticmethod
    def resolve_attendance_type_name(obj):
        return obj.attendance_type_name


class CreateAttendanceDto(Schema):
    employeeid: UUID
    projectid: Optional[UUID] = None
    attendancedate: date
    checkintime: Optional[time] = None
    checkouttime: Optional[time] = None
    regularhoursworked: Decimal = Decimal('8')
    overtimehoursworked: Decimal = Decimal('0')
    attendancetype: int = 0  # Present
    notes: Optional[str] = None


class UpdateAttendanceDto(Schema):
    projectid: Optional[UUID] = None
    checkintime: Optional[time] = None
    checkouttime: Optional[time] = None
    regularhoursworked: Optional[Decimal] = None
    overtimehoursworked: Optional[Decimal] = None
    attendancetype: Optional[int] = None
    notes: Optional[str] = None


class BulkAttendanceDto(Schema):
    """DTO for recording attendance for multiple employees at once."""
    attendancedate: date
    projectid: Optional[UUID] = None
    entries: List[CreateAttendanceDto]
