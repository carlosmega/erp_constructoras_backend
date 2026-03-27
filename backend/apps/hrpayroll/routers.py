"""
API routers (endpoints) for HR & Payroll module.
Implements REST API endpoints using Django Ninja.
"""

from ninja import Router
from typing import List, Optional
from uuid import UUID
from datetime import date
from django.http import HttpRequest

from apps.hrpayroll.schemas import (
    EmployeeSchema, EmployeeListSchema, CreateEmployeeDto, UpdateEmployeeDto, TerminateEmployeeDto,
    AssignmentSchema, CreateAssignmentDto, UpdateAssignmentDto,
    DeductionTypeSchema, CreateDeductionTypeDto, UpdateDeductionTypeDto,
    AdditionTypeSchema, CreateAdditionTypeDto, UpdateAdditionTypeDto,
    PayrollPeriodSchema, CreatePayrollPeriodDto, GeneratePeriodsDto,
    PayrollRunSchema, PayrollRunListSchema, CreatePayrollRunDto, RejectPayrollDto,
    PayrollEntrySchema, UpdatePayrollEntryDto,
    AttendanceSchema, CreateAttendanceDto, UpdateAttendanceDto, BulkAttendanceDto,
)
from apps.hrpayroll.services import (
    EmployeeService, AssignmentService, CatalogService,
    PayrollPeriodService, PayrollRunService, AttendanceService,
)
from core.permissions import require_permission, Permission


# ============================================================================
# Employees Router
# ============================================================================

employees_router = Router(tags=["Employees"])


@employees_router.get("/", response=List[EmployeeListSchema])
@require_permission(Permission.EMPLOYEE_READ)
def list_employees(
    request: HttpRequest,
    statecode: Optional[int] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    ownerid: Optional[str] = None,
    projectid: Optional[str] = None,
):
    """List employees with filtering."""
    employees = EmployeeService.list_employees(
        user=request.user,
        statecode=statecode,
        department=department,
        search=search,
        ownerid=UUID(ownerid) if ownerid else None,
        projectid=UUID(projectid) if projectid else None,
    )
    return list(employees)


@employees_router.post("/", response={201: EmployeeSchema})
@require_permission(Permission.EMPLOYEE_CREATE)
def create_employee(request: HttpRequest, payload: CreateEmployeeDto):
    """Create new employee."""
    employee = EmployeeService.create_employee(payload, request.user)
    return 201, employee


@employees_router.get("/{employee_id}", response=EmployeeSchema)
@require_permission(Permission.EMPLOYEE_READ)
def get_employee(request: HttpRequest, employee_id: UUID):
    """Get single employee by ID."""
    return EmployeeService.get_employee_by_id(employee_id, request.user)


@employees_router.patch("/{employee_id}", response=EmployeeSchema)
@require_permission(Permission.EMPLOYEE_UPDATE)
def update_employee(request: HttpRequest, employee_id: UUID, payload: UpdateEmployeeDto):
    """Update employee (partial update)."""
    return EmployeeService.update_employee(employee_id, payload, request.user)


@employees_router.post("/{employee_id}/terminate", response=EmployeeSchema)
@require_permission(Permission.EMPLOYEE_TERMINATE)
def terminate_employee(request: HttpRequest, employee_id: UUID, payload: TerminateEmployeeDto):
    """Terminate an employee."""
    return EmployeeService.terminate_employee(employee_id, payload, request.user)


@employees_router.delete("/{employee_id}", response={204: None})
@require_permission(Permission.EMPLOYEE_DELETE)
def delete_employee(request: HttpRequest, employee_id: UUID):
    """Soft delete employee."""
    EmployeeService.delete_employee(employee_id, request.user)
    return 204, None


@employees_router.get("/{employee_id}/assignments", response=List[AssignmentSchema])
@require_permission(Permission.EMPLOYEE_READ)
def get_employee_assignments(request: HttpRequest, employee_id: UUID):
    """Get all project assignments for an employee."""
    return list(AssignmentService.list_assignments(request.user, employeeid=employee_id))


# ============================================================================
# Employee Assignments Router
# ============================================================================

assignments_router = Router(tags=["Employee Assignments"])


@assignments_router.get("/", response=List[AssignmentSchema])
@require_permission(Permission.EMPLOYEE_READ)
def list_assignments(
    request: HttpRequest,
    employeeid: Optional[str] = None,
    projectid: Optional[str] = None,
    statecode: Optional[int] = None,
):
    """List employee project assignments."""
    return list(AssignmentService.list_assignments(
        user=request.user,
        employeeid=UUID(employeeid) if employeeid else None,
        projectid=UUID(projectid) if projectid else None,
        statecode=statecode,
    ))


@assignments_router.post("/", response={201: AssignmentSchema})
@require_permission(Permission.EMPLOYEE_UPDATE)
def create_assignment(request: HttpRequest, payload: CreateAssignmentDto):
    """Create a new project assignment for an employee."""
    assignment = AssignmentService.create_assignment(payload, request.user)
    return 201, assignment


@assignments_router.patch("/{assignment_id}", response=AssignmentSchema)
@require_permission(Permission.EMPLOYEE_UPDATE)
def update_assignment(request: HttpRequest, assignment_id: UUID, payload: UpdateAssignmentDto):
    """Update a project assignment."""
    return AssignmentService.update_assignment(assignment_id, payload, request.user)


# ============================================================================
# Deduction Types Router
# ============================================================================

deduction_types_router = Router(tags=["Deduction Types"])


@deduction_types_router.get("/", response=List[DeductionTypeSchema])
@require_permission(Permission.EMPLOYEE_READ)
def list_deduction_types(request: HttpRequest, statecode: Optional[int] = None):
    """List deduction type catalog."""
    return list(CatalogService.list_deduction_types(statecode=statecode))


@deduction_types_router.post("/", response={201: DeductionTypeSchema})
@require_permission(Permission.HR_CATALOG_MANAGE)
def create_deduction_type(request: HttpRequest, payload: CreateDeductionTypeDto):
    """Create a new deduction type."""
    dt = CatalogService.create_deduction_type(payload, request.user)
    return 201, dt


@deduction_types_router.patch("/{dt_id}", response=DeductionTypeSchema)
@require_permission(Permission.HR_CATALOG_MANAGE)
def update_deduction_type(request: HttpRequest, dt_id: UUID, payload: UpdateDeductionTypeDto):
    """Update a deduction type."""
    return CatalogService.update_deduction_type(dt_id, payload, request.user)


@deduction_types_router.post("/seed", response=List[DeductionTypeSchema])
@require_permission(Permission.HR_CATALOG_MANAGE)
def seed_deduction_types(request: HttpRequest):
    """Seed default Mexican payroll deductions."""
    return CatalogService.seed_default_deductions(request.user)


# ============================================================================
# Addition Types Router
# ============================================================================

addition_types_router = Router(tags=["Addition Types"])


@addition_types_router.get("/", response=List[AdditionTypeSchema])
@require_permission(Permission.EMPLOYEE_READ)
def list_addition_types(request: HttpRequest, statecode: Optional[int] = None):
    """List addition type catalog."""
    return list(CatalogService.list_addition_types(statecode=statecode))


@addition_types_router.post("/", response={201: AdditionTypeSchema})
@require_permission(Permission.HR_CATALOG_MANAGE)
def create_addition_type(request: HttpRequest, payload: CreateAdditionTypeDto):
    """Create a new addition type."""
    at = CatalogService.create_addition_type(payload, request.user)
    return 201, at


@addition_types_router.patch("/{at_id}", response=AdditionTypeSchema)
@require_permission(Permission.HR_CATALOG_MANAGE)
def update_addition_type(request: HttpRequest, at_id: UUID, payload: UpdateAdditionTypeDto):
    """Update an addition type."""
    return CatalogService.update_addition_type(at_id, payload, request.user)


@addition_types_router.post("/seed", response=List[AdditionTypeSchema])
@require_permission(Permission.HR_CATALOG_MANAGE)
def seed_addition_types(request: HttpRequest):
    """Seed default construction payroll additions."""
    return CatalogService.seed_default_additions(request.user)


# ============================================================================
# Payroll Periods Router
# ============================================================================

payroll_periods_router = Router(tags=["Payroll Periods"])


@payroll_periods_router.get("/", response=List[PayrollPeriodSchema])
@require_permission(Permission.PAYROLL_READ)
def list_periods(
    request: HttpRequest,
    year: Optional[int] = None,
    periodtype: Optional[int] = None,
    statecode: Optional[int] = None,
):
    """List payroll periods."""
    return list(PayrollPeriodService.list_periods(
        year=year, periodtype=periodtype, statecode=statecode,
    ))


@payroll_periods_router.post("/", response={201: PayrollPeriodSchema})
@require_permission(Permission.PAYROLL_CREATE)
def create_period(request: HttpRequest, payload: CreatePayrollPeriodDto):
    """Create a single payroll period."""
    period = PayrollPeriodService.create_period(payload, request.user)
    return 201, period


@payroll_periods_router.post("/generate", response=List[PayrollPeriodSchema])
@require_permission(Permission.PAYROLL_CREATE)
def generate_periods(request: HttpRequest, payload: GeneratePeriodsDto):
    """Generate all periods for a year and type."""
    return PayrollPeriodService.generate_periods(payload, request.user)


# ============================================================================
# Payroll Runs Router
# ============================================================================

payroll_runs_router = Router(tags=["Payroll Runs"])


@payroll_runs_router.get("/", response=List[PayrollRunListSchema])
@require_permission(Permission.PAYROLL_READ)
def list_runs(
    request: HttpRequest,
    statecode: Optional[int] = None,
    payrollperiodid: Optional[str] = None,
    projectid: Optional[str] = None,
):
    """List payroll runs."""
    return list(PayrollRunService.list_runs(
        user=request.user,
        statecode=statecode,
        payrollperiodid=UUID(payrollperiodid) if payrollperiodid else None,
        projectid=UUID(projectid) if projectid else None,
    ))


@payroll_runs_router.post("/", response={201: PayrollRunSchema})
@require_permission(Permission.PAYROLL_CREATE)
def create_run(request: HttpRequest, payload: CreatePayrollRunDto):
    """Create payroll run and generate entries for active employees."""
    run = PayrollRunService.create_run(payload, request.user)
    return 201, run


@payroll_runs_router.get("/{run_id}", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_READ)
def get_run(request: HttpRequest, run_id: UUID):
    """Get a single payroll run."""
    return PayrollRunService.get_run_by_id(run_id, request.user)


@payroll_runs_router.get("/{run_id}/entries", response=List[PayrollEntrySchema])
@require_permission(Permission.PAYROLL_READ)
def list_run_entries(request: HttpRequest, run_id: UUID):
    """List all entries in a payroll run."""
    return list(PayrollRunService.list_entries(run_id, request.user))


@payroll_runs_router.post("/{run_id}/calculate", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_CALCULATE)
def calculate_run(request: HttpRequest, run_id: UUID):
    """Calculate payroll for all entries."""
    return PayrollRunService.calculate_payroll(run_id, request.user)


@payroll_runs_router.post("/{run_id}/submit", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_CREATE)
def submit_run(request: HttpRequest, run_id: UUID):
    """Submit payroll run for approval."""
    return PayrollRunService.submit_for_approval(run_id, request.user)


@payroll_runs_router.post("/{run_id}/approve", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_APPROVE)
def approve_run(request: HttpRequest, run_id: UUID):
    """Approve a payroll run."""
    return PayrollRunService.approve_payroll(run_id, request.user)


@payroll_runs_router.post("/{run_id}/reject", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_APPROVE)
def reject_run(request: HttpRequest, run_id: UUID, payload: RejectPayrollDto):
    """Reject a payroll run."""
    return PayrollRunService.reject_payroll(run_id, payload, request.user)


@payroll_runs_router.post("/{run_id}/mark-paid", response=PayrollRunSchema)
@require_permission(Permission.PAYROLL_APPROVE)
def mark_run_paid(request: HttpRequest, run_id: UUID):
    """Mark payroll run as paid."""
    return PayrollRunService.mark_as_paid(run_id, request.user)


# ============================================================================
# Payroll Entries Router
# ============================================================================

payroll_entries_router = Router(tags=["Payroll Entries"])


@payroll_entries_router.patch("/{entry_id}", response=PayrollEntrySchema)
@require_permission(Permission.PAYROLL_UPDATE)
def update_entry(request: HttpRequest, entry_id: UUID, payload: UpdatePayrollEntryDto):
    """Update a payroll entry (only in Draft/Calculated state)."""
    return PayrollRunService.update_entry(entry_id, payload, request.user)


# ============================================================================
# Attendance Router
# ============================================================================

attendance_router = Router(tags=["Attendance"])


@attendance_router.get("/", response=List[AttendanceSchema])
@require_permission(Permission.ATTENDANCE_READ)
def list_attendance(
    request: HttpRequest,
    employeeid: Optional[str] = None,
    projectid: Optional[str] = None,
    startdate: Optional[date] = None,
    enddate: Optional[date] = None,
    attendancetype: Optional[int] = None,
):
    """List attendance records with filtering."""
    return list(AttendanceService.list_attendance(
        user=request.user,
        employeeid=UUID(employeeid) if employeeid else None,
        projectid=UUID(projectid) if projectid else None,
        startdate=startdate,
        enddate=enddate,
        attendancetype=attendancetype,
    ))


@attendance_router.post("/", response={201: AttendanceSchema})
@require_permission(Permission.ATTENDANCE_CREATE)
def create_attendance(request: HttpRequest, payload: CreateAttendanceDto):
    """Record attendance for a single employee."""
    record = AttendanceService.create_attendance(payload, request.user)
    return 201, record


@attendance_router.post("/bulk", response=List[AttendanceSchema])
@require_permission(Permission.ATTENDANCE_CREATE)
def bulk_create_attendance(request: HttpRequest, payload: BulkAttendanceDto):
    """Record attendance for multiple employees at once."""
    records = AttendanceService.bulk_create_attendance(payload.entries, request.user)
    return records


@attendance_router.patch("/{record_id}", response=AttendanceSchema)
@require_permission(Permission.ATTENDANCE_UPDATE)
def update_attendance(request: HttpRequest, record_id: UUID, payload: UpdateAttendanceDto):
    """Update an attendance record."""
    return AttendanceService.update_attendance(record_id, payload, request.user)


@attendance_router.delete("/{record_id}", response={204: None})
@require_permission(Permission.ATTENDANCE_DELETE)
def delete_attendance(request: HttpRequest, record_id: UUID):
    """Delete an attendance record."""
    AttendanceService.delete_attendance(record_id, request.user)
    return 204, None


@attendance_router.get("/summary", response=dict)
@require_permission(Permission.ATTENDANCE_READ)
def attendance_summary(
    request: HttpRequest,
    employeeid: str,
    startdate: date,
    enddate: date,
):
    """Get attendance summary for an employee."""
    return AttendanceService.get_attendance_summary(
        UUID(employeeid), startdate, enddate,
    )
