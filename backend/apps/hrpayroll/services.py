"""
HR & Payroll business logic service layer.
Handles employee management, payroll calculations, attendance,
and catalog operations.
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.db.models import Q, Sum, QuerySet
from django.db import transaction
from django.utils import timezone

from apps.hrpayroll.models import (
    Employee, EmployeeStateCode, EmployeeStatusCode, SalaryTypeCode,
    EmployeeProjectAssignment, AssignmentStateCode,
    DeductionType, AdditionType, CalculationTypeCode,
    PayrollPeriod, PeriodTypeCode, PeriodStateCode,
    PayrollRun, PayrollRunStateCode,
    PayrollEntry, PaymentStatusCode,
    AttendanceRecord, AttendanceTypeCode,
)
from apps.hrpayroll.schemas import (
    CreateEmployeeDto, UpdateEmployeeDto, TerminateEmployeeDto,
    CreateAssignmentDto, UpdateAssignmentDto,
    CreateDeductionTypeDto, UpdateDeductionTypeDto,
    CreateAdditionTypeDto, UpdateAdditionTypeDto,
    CreatePayrollPeriodDto, GeneratePeriodsDto,
    CreatePayrollRunDto, RejectPayrollDto, UpdatePayrollEntryDto,
    CreateAttendanceDto, UpdateAttendanceDto,
)
from apps.users.models import SystemUser
from core.exceptions import ValidationError, NotFound, PermissionDenied
from core.roles import ADMIN_ROLES
from core.permissions import filter_by_ownership
from apps.audit.services import audit_action

logger = logging.getLogger(__name__)


# ============================================================================
# Employee Service
# ============================================================================

class EmployeeService:
    """Service for Employee entity business logic."""

    @staticmethod
    def _generate_employee_number() -> str:
        """Generate next employee number: EMP-YYYY-NNN."""
        current_year = date.today().year
        prefix = f'EMP-{current_year}-'
        last = Employee.objects.filter(
            employeenumber__startswith=prefix
        ).order_by('-employeenumber').first()

        if last:
            try:
                last_num = int(last.employeenumber.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f'{prefix}{next_num:03d}'

    @staticmethod
    def list_employees(
        user: SystemUser,
        statecode: Optional[int] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        ownerid: Optional[UUID] = None,
        projectid: Optional[UUID] = None,
    ) -> QuerySet[Employee]:
        """List employees with filtering and ownership rules."""
        queryset = Employee.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if department:
            queryset = queryset.filter(department__icontains=department)
        if ownerid:
            if user.role_name not in ADMIN_ROLES:
                raise PermissionDenied("You cannot view other users' employees")
            queryset = queryset.filter(ownerid=ownerid)
        if search:
            queryset = queryset.filter(
                Q(fullname__icontains=search) |
                Q(employeenumber__icontains=search) |
                Q(emailaddress__icontains=search) |
                Q(position__icontains=search) |
                Q(curp__icontains=search)
            )
        if projectid:
            employee_ids = EmployeeProjectAssignment.objects.filter(
                projectid=projectid, statecode=AssignmentStateCode.ACTIVE
            ).values_list('employeeid', flat=True)
            queryset = queryset.filter(employeeid__in=employee_ids)

        queryset = queryset.select_related('ownerid', 'createdby', 'modifiedby')
        return queryset

    @staticmethod
    @audit_action(action='create', entity='employee')
    def create_employee(dto: CreateEmployeeDto, user: SystemUser) -> Employee:
        """Create a new employee with auto-generated number."""
        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        employee = Employee(
            employeenumber=EmployeeService._generate_employee_number(),
            firstname=dto.firstname,
            lastname=dto.lastname,
            curp=dto.curp,
            rfc=dto.rfc,
            nss=dto.nss,
            emailaddress=dto.emailaddress,
            phonenumber=dto.phonenumber,
            dateofbirth=dto.dateofbirth,
            hiredate=dto.hiredate,
            position=dto.position,
            department=dto.department,
            salarytype=dto.salarytype,
            basesalary=dto.basesalary,
            bankname=dto.bankname,
            bankaccountnumber=dto.bankaccountnumber,
            clabenumber=dto.clabenumber,
            emergencycontactname=dto.emergencycontactname,
            emergencycontactphone=dto.emergencycontactphone,
            emergencycontactrelation=dto.emergencycontactrelation,
            notes=dto.notes,
            statecode=EmployeeStateCode.ACTIVE,
            statuscode=EmployeeStatusCode.PROBATION,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )
        employee.save()

        from apps.notifications.signals import record_assigned
        record_assigned.send(
            sender=Employee,
            entity_type='employee',
            entity_id=employee.employeeid,
            entity_name=employee.fullname,
            new_owner=employee.ownerid,
            actor=user,
        )

        return employee

    @staticmethod
    def get_employee_by_id(employee_id: UUID, user: SystemUser) -> Employee:
        """Get employee with ownership check."""
        try:
            employee = Employee.objects.select_related(
                'ownerid', 'createdby', 'modifiedby'
            ).get(employeeid=employee_id)
        except Employee.DoesNotExist:
            raise NotFound(f"Employee with ID {employee_id} not found")

        if user.role_name not in ADMIN_ROLES:
            if employee.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this employee")

        return employee

    @staticmethod
    @audit_action(action='update', entity='employee', record_arg='employee_id')
    def update_employee(employee_id: UUID, dto: UpdateEmployeeDto, user: SystemUser) -> Employee:
        """Update employee (partial update)."""
        employee = EmployeeService.get_employee_by_id(employee_id, user)

        update_fields = [
            'firstname', 'lastname', 'curp', 'rfc', 'nss',
            'emailaddress', 'phonenumber', 'dateofbirth',
            'position', 'department', 'salarytype', 'basesalary',
            'bankname', 'bankaccountnumber', 'clabenumber',
            'emergencycontactname', 'emergencycontactphone', 'emergencycontactrelation',
            'statuscode', 'notes',
        ]
        for field in update_fields:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(employee, field, value)

        if dto.ownerid:
            try:
                new_owner = SystemUser.objects.get(systemuserid=dto.ownerid)
                employee.ownerid = new_owner
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        employee.modifiedby = user
        employee.save()
        return employee

    @staticmethod
    @transaction.atomic
    @audit_action(action='terminate', entity='employee', record_arg='employee_id')
    def terminate_employee(employee_id: UUID, dto: TerminateEmployeeDto, user: SystemUser) -> Employee:
        """Terminate an employee."""
        employee = EmployeeService.get_employee_by_id(employee_id, user)

        if employee.statecode == EmployeeStateCode.TERMINATED:
            raise ValidationError("Employee is already terminated")

        if dto.statuscode not in [EmployeeStatusCode.VOLUNTARY_EXIT, EmployeeStatusCode.DISMISSED]:
            raise ValidationError("Termination status must be Voluntary Exit (5) or Dismissed (6)")

        employee.statecode = EmployeeStateCode.TERMINATED
        employee.statuscode = dto.statuscode
        employee.terminationdate = dto.terminationdate
        if dto.notes:
            employee.notes = f"{employee.notes or ''}\n[Termination] {dto.notes}".strip()
        employee.modifiedby = user
        employee.save()

        # Cancel active project assignments
        EmployeeProjectAssignment.objects.filter(
            employeeid=employee, statecode=AssignmentStateCode.ACTIVE
        ).update(statecode=AssignmentStateCode.CANCELED, enddate=dto.terminationdate)

        return employee

    @staticmethod
    @audit_action(action='delete', entity='employee', record_arg='employee_id')
    def delete_employee(employee_id: UUID, user: SystemUser) -> Employee:
        """Soft delete (terminate) employee."""
        employee = EmployeeService.get_employee_by_id(employee_id, user)
        employee.statecode = EmployeeStateCode.TERMINATED
        employee.statuscode = EmployeeStatusCode.DISMISSED
        employee.terminationdate = date.today()
        employee.modifiedby = user
        employee.save()
        return employee


# ============================================================================
# Assignment Service
# ============================================================================

class AssignmentService:
    """Service for EmployeeProjectAssignment entity."""

    @staticmethod
    def list_assignments(
        user: SystemUser,
        employeeid: Optional[UUID] = None,
        projectid: Optional[UUID] = None,
        statecode: Optional[int] = None,
    ) -> QuerySet[EmployeeProjectAssignment]:
        queryset = EmployeeProjectAssignment.objects.all()

        if employeeid:
            queryset = queryset.filter(employeeid=employeeid)
        if projectid:
            queryset = queryset.filter(projectid=projectid)
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)

        queryset = queryset.select_related('employeeid', 'projectid')
        return queryset

    @staticmethod
    @audit_action(action='create', entity='employeeprojectassignment')
    def create_assignment(dto: CreateAssignmentDto, user: SystemUser) -> EmployeeProjectAssignment:
        from apps.projects.models import ConstructionProject

        try:
            employee = Employee.objects.get(employeeid=dto.employeeid)
        except Employee.DoesNotExist:
            raise ValidationError(f"Employee with ID {dto.employeeid} not found")

        try:
            project = ConstructionProject.objects.get(projectid=dto.projectid)
        except ConstructionProject.DoesNotExist:
            raise ValidationError(f"Project with ID {dto.projectid} not found")

        if employee.statecode != EmployeeStateCode.ACTIVE:
            raise ValidationError("Cannot assign a non-active employee to a project")

        assignment = EmployeeProjectAssignment(
            employeeid=employee,
            projectid=project,
            role=dto.role,
            startdate=dto.startdate,
            enddate=dto.enddate,
            hoursperweek=dto.hoursperweek,
            isprimary=dto.isprimary,
            statecode=AssignmentStateCode.ACTIVE,
            createdby=user,
            modifiedby=user,
        )
        assignment.save()
        return assignment

    @staticmethod
    @audit_action(action='update', entity='employeeprojectassignment', record_arg='assignment_id')
    def update_assignment(assignment_id: UUID, dto: UpdateAssignmentDto, user: SystemUser) -> EmployeeProjectAssignment:
        try:
            assignment = EmployeeProjectAssignment.objects.select_related(
                'employeeid', 'projectid'
            ).get(assignmentid=assignment_id)
        except EmployeeProjectAssignment.DoesNotExist:
            raise NotFound(f"Assignment with ID {assignment_id} not found")

        for field in ['role', 'enddate', 'hoursperweek', 'isprimary', 'statecode']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(assignment, field, value)

        assignment.modifiedby = user
        assignment.save()
        return assignment


# ============================================================================
# Catalog Service (DeductionType + AdditionType)
# ============================================================================

class CatalogService:
    """Service for DeductionType and AdditionType catalogs."""

    # --- Deduction Types ---

    @staticmethod
    def list_deduction_types(statecode: Optional[int] = None) -> QuerySet[DeductionType]:
        queryset = DeductionType.objects.all()
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        return queryset

    @staticmethod
    def create_deduction_type(dto: CreateDeductionTypeDto, user: SystemUser) -> DeductionType:
        dt = DeductionType(
            code=dto.code.upper(),
            name=dto.name,
            description=dto.description,
            calculationtype=dto.calculationtype,
            defaultvalue=dto.defaultvalue,
            isstatutory=dto.isstatutory,
            createdby=user,
            modifiedby=user,
        )
        dt.save()
        return dt

    @staticmethod
    def update_deduction_type(dt_id: UUID, dto: UpdateDeductionTypeDto, user: SystemUser) -> DeductionType:
        try:
            dt = DeductionType.objects.get(deductiontypeid=dt_id)
        except DeductionType.DoesNotExist:
            raise NotFound(f"DeductionType with ID {dt_id} not found")

        for field in ['name', 'description', 'calculationtype', 'defaultvalue', 'isstatutory', 'statecode']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(dt, field, value)

        dt.modifiedby = user
        dt.save()
        return dt

    # --- Addition Types ---

    @staticmethod
    def list_addition_types(statecode: Optional[int] = None) -> QuerySet[AdditionType]:
        queryset = AdditionType.objects.all()
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        return queryset

    @staticmethod
    def create_addition_type(dto: CreateAdditionTypeDto, user: SystemUser) -> AdditionType:
        at = AdditionType(
            code=dto.code.upper(),
            name=dto.name,
            description=dto.description,
            calculationtype=dto.calculationtype,
            defaultvalue=dto.defaultvalue,
            istaxable=dto.istaxable,
            createdby=user,
            modifiedby=user,
        )
        at.save()
        return at

    @staticmethod
    def update_addition_type(at_id: UUID, dto: UpdateAdditionTypeDto, user: SystemUser) -> AdditionType:
        try:
            at = AdditionType.objects.get(additiontypeid=at_id)
        except AdditionType.DoesNotExist:
            raise NotFound(f"AdditionType with ID {at_id} not found")

        for field in ['name', 'description', 'calculationtype', 'defaultvalue', 'istaxable', 'statecode']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(at, field, value)

        at.modifiedby = user
        at.save()
        return at

    # --- Seed Defaults ---

    @staticmethod
    def seed_default_deductions(user: SystemUser) -> List[DeductionType]:
        """Create standard Mexican payroll deductions."""
        defaults = [
            {'code': 'ISR', 'name': 'Impuesto Sobre la Renta', 'calculationtype': CalculationTypeCode.PERCENTAGE, 'defaultvalue': Decimal('10.0000'), 'isstatutory': True},
            {'code': 'IMSS', 'name': 'Instituto Mexicano del Seguro Social', 'calculationtype': CalculationTypeCode.PERCENTAGE, 'defaultvalue': Decimal('2.7750'), 'isstatutory': True},
            {'code': 'INFONAVIT', 'name': 'Instituto del Fondo Nacional de la Vivienda', 'calculationtype': CalculationTypeCode.PERCENTAGE, 'defaultvalue': Decimal('5.0000'), 'isstatutory': True},
            {'code': 'SAR', 'name': 'Sistema de Ahorro para el Retiro', 'calculationtype': CalculationTypeCode.PERCENTAGE, 'defaultvalue': Decimal('2.0000'), 'isstatutory': True},
            {'code': 'LOAN', 'name': 'Préstamo Personal', 'calculationtype': CalculationTypeCode.FIXED_AMOUNT, 'defaultvalue': Decimal('0'), 'isstatutory': False},
            {'code': 'ADVANCE', 'name': 'Anticipo de Nómina', 'calculationtype': CalculationTypeCode.FIXED_AMOUNT, 'defaultvalue': Decimal('0'), 'isstatutory': False},
        ]
        created = []
        for d in defaults:
            obj, was_created = DeductionType.objects.get_or_create(
                code=d['code'],
                defaults={**d, 'createdby': user, 'modifiedby': user}
            )
            if was_created:
                created.append(obj)
        return created

    @staticmethod
    def seed_default_additions(user: SystemUser) -> List[AdditionType]:
        """Create standard construction payroll additions."""
        defaults = [
            {'code': 'OT', 'name': 'Horas Extra', 'calculationtype': CalculationTypeCode.HOURS_MULTIPLIER, 'defaultvalue': Decimal('2.0000'), 'istaxable': True},
            {'code': 'OT_TRIPLE', 'name': 'Horas Extra Triple', 'calculationtype': CalculationTypeCode.HOURS_MULTIPLIER, 'defaultvalue': Decimal('3.0000'), 'istaxable': True},
            {'code': 'BONUS', 'name': 'Bono de Productividad', 'calculationtype': CalculationTypeCode.FIXED_AMOUNT, 'defaultvalue': Decimal('0'), 'istaxable': True},
            {'code': 'HAZARD', 'name': 'Prima de Riesgo', 'calculationtype': CalculationTypeCode.PERCENTAGE, 'defaultvalue': Decimal('5.0000'), 'istaxable': False},
            {'code': 'TRANSPORT', 'name': 'Ayuda de Transporte', 'calculationtype': CalculationTypeCode.FIXED_AMOUNT, 'defaultvalue': Decimal('500.0000'), 'istaxable': False},
            {'code': 'FOOD', 'name': 'Vales de Despensa', 'calculationtype': CalculationTypeCode.FIXED_AMOUNT, 'defaultvalue': Decimal('1000.0000'), 'istaxable': False},
        ]
        created = []
        for a in defaults:
            obj, was_created = AdditionType.objects.get_or_create(
                code=a['code'],
                defaults={**a, 'createdby': user, 'modifiedby': user}
            )
            if was_created:
                created.append(obj)
        return created


# ============================================================================
# PayrollPeriod Service
# ============================================================================

class PayrollPeriodService:
    """Service for PayrollPeriod entity."""

    @staticmethod
    def list_periods(
        year: Optional[int] = None,
        periodtype: Optional[int] = None,
        statecode: Optional[int] = None,
    ) -> QuerySet[PayrollPeriod]:
        queryset = PayrollPeriod.objects.all()
        if year is not None:
            queryset = queryset.filter(year=year)
        if periodtype is not None:
            queryset = queryset.filter(periodtype=periodtype)
        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        return queryset

    @staticmethod
    def create_period(dto: CreatePayrollPeriodDto, user: SystemUser) -> PayrollPeriod:
        period = PayrollPeriod(
            periodnumber=dto.periodnumber,
            periodtype=dto.periodtype,
            startdate=dto.startdate,
            enddate=dto.enddate,
            year=dto.year,
            label=dto.label,
            statecode=PeriodStateCode.OPEN,
            createdby=user,
            modifiedby=user,
        )
        period.save()
        return period

    @staticmethod
    @transaction.atomic
    def generate_periods(dto: GeneratePeriodsDto, user: SystemUser) -> List[PayrollPeriod]:
        """Generate all periods for a given year and type."""
        year = dto.year
        ptype = dto.periodtype
        periods = []

        if ptype == PeriodTypeCode.WEEKLY:
            # Generate 52 weekly periods
            start = date(year, 1, 1)
            # Adjust to Monday
            while start.weekday() != 0:
                start += timedelta(days=1)
            num = 1
            while start.year == year or (start.year == year + 1 and num <= 52):
                end = start + timedelta(days=6)
                label = f'SEM-{year}-{num:02d}'
                period, created = PayrollPeriod.objects.get_or_create(
                    year=year, periodnumber=num, periodtype=ptype,
                    defaults={
                        'startdate': start, 'enddate': end,
                        'label': label, 'statecode': PeriodStateCode.OPEN,
                        'createdby': user, 'modifiedby': user,
                    }
                )
                if created:
                    periods.append(period)
                start = end + timedelta(days=1)
                num += 1
                if num > 52:
                    break

        elif ptype == PeriodTypeCode.BIWEEKLY:
            # 24 biweekly periods
            for num in range(1, 25):
                month = (num - 1) // 2 + 1
                half = (num - 1) % 2
                if half == 0:
                    s = date(year, month, 1)
                    e = date(year, month, 15)
                else:
                    s = date(year, month, 16)
                    # Last day of month
                    if month == 12:
                        e = date(year, 12, 31)
                    else:
                        e = date(year, month + 1, 1) - timedelta(days=1)
                label = f'QUIN-{year}-{num:02d}'
                period, created = PayrollPeriod.objects.get_or_create(
                    year=year, periodnumber=num, periodtype=ptype,
                    defaults={
                        'startdate': s, 'enddate': e,
                        'label': label, 'statecode': PeriodStateCode.OPEN,
                        'createdby': user, 'modifiedby': user,
                    }
                )
                if created:
                    periods.append(period)

        elif ptype == PeriodTypeCode.MONTHLY:
            # 12 monthly periods
            for num in range(1, 13):
                s = date(year, num, 1)
                if num == 12:
                    e = date(year, 12, 31)
                else:
                    e = date(year, num + 1, 1) - timedelta(days=1)
                label = f'MES-{year}-{num:02d}'
                period, created = PayrollPeriod.objects.get_or_create(
                    year=year, periodnumber=num, periodtype=ptype,
                    defaults={
                        'startdate': s, 'enddate': e,
                        'label': label, 'statecode': PeriodStateCode.OPEN,
                        'createdby': user, 'modifiedby': user,
                    }
                )
                if created:
                    periods.append(period)

        return periods


# ============================================================================
# PayrollRun Service
# ============================================================================

class PayrollRunService:
    """Service for PayrollRun entity with full workflow."""

    @staticmethod
    def _generate_run_number() -> str:
        """Generate next payroll run number: NOM-YYYY-NNN."""
        current_year = date.today().year
        prefix = f'NOM-{current_year}-'
        last = PayrollRun.objects.filter(
            runnumber__startswith=prefix
        ).order_by('-runnumber').first()

        if last:
            try:
                last_num = int(last.runnumber.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f'{prefix}{next_num:03d}'

    @staticmethod
    def list_runs(
        user: SystemUser,
        statecode: Optional[int] = None,
        payrollperiodid: Optional[UUID] = None,
        projectid: Optional[UUID] = None,
    ) -> QuerySet[PayrollRun]:
        queryset = PayrollRun.objects.all()
        queryset = filter_by_ownership(queryset, user, owner_field='ownerid')

        if statecode is not None:
            queryset = queryset.filter(statecode=statecode)
        if payrollperiodid:
            queryset = queryset.filter(payrollperiodid=payrollperiodid)
        if projectid:
            queryset = queryset.filter(projectid=projectid)

        queryset = queryset.select_related(
            'payrollperiodid', 'projectid', 'ownerid', 'approvedby'
        )
        return queryset

    @staticmethod
    def get_run_by_id(run_id: UUID, user: SystemUser) -> PayrollRun:
        try:
            run = PayrollRun.objects.select_related(
                'payrollperiodid', 'projectid', 'ownerid', 'approvedby',
                'createdby', 'modifiedby'
            ).get(payrollrunid=run_id)
        except PayrollRun.DoesNotExist:
            raise NotFound(f"PayrollRun with ID {run_id} not found")

        if user.role_name not in ADMIN_ROLES:
            if run.ownerid_id != user.systemuserid:
                raise PermissionDenied("You don't have access to this payroll run")
        return run

    @staticmethod
    @transaction.atomic
    @audit_action(action='create', entity='payrollrun')
    def create_run(dto: CreatePayrollRunDto, user: SystemUser) -> PayrollRun:
        """Create payroll run and generate entries for active employees."""
        try:
            period = PayrollPeriod.objects.get(payrollperiodid=dto.payrollperiodid)
        except PayrollPeriod.DoesNotExist:
            raise ValidationError(f"PayrollPeriod with ID {dto.payrollperiodid} not found")

        if period.statecode == PeriodStateCode.CLOSED:
            raise ValidationError("Cannot create a payroll run for a closed period")

        owner = user
        if dto.ownerid:
            try:
                owner = SystemUser.objects.get(systemuserid=dto.ownerid)
            except SystemUser.DoesNotExist:
                raise ValidationError(f"Owner with ID {dto.ownerid} not found")

        project = None
        if dto.projectid:
            from apps.projects.models import ConstructionProject
            try:
                project = ConstructionProject.objects.get(projectid=dto.projectid)
            except ConstructionProject.DoesNotExist:
                raise ValidationError(f"Project with ID {dto.projectid} not found")

        run = PayrollRun(
            payrollperiodid=period,
            runnumber=PayrollRunService._generate_run_number(),
            description=dto.description,
            projectid=project,
            statecode=PayrollRunStateCode.DRAFT,
            ownerid=owner,
            createdby=user,
            modifiedby=user,
        )
        run.save()

        # Get employees for this run
        employees = Employee.objects.filter(statecode=EmployeeStateCode.ACTIVE)
        if project:
            assigned_ids = EmployeeProjectAssignment.objects.filter(
                projectid=project, statecode=AssignmentStateCode.ACTIVE
            ).values_list('employeeid', flat=True)
            employees = employees.filter(employeeid__in=assigned_ids)

        # Create entries for each employee
        entries = []
        for emp in employees:
            entry = PayrollEntry(
                payrollrunid=run,
                employeeid=emp,
                basepay=emp.basesalary,
                createdby=user,
                modifiedby=user,
            )
            entries.append(entry)

        PayrollEntry.objects.bulk_create(entries)
        run.employeecount = len(entries)
        run.save(update_fields=['employeecount'])

        return run

    @staticmethod
    @transaction.atomic
    @audit_action(action='calculate', entity='payrollrun', record_arg='run_id')
    def calculate_payroll(run_id: UUID, user: SystemUser) -> PayrollRun:
        """Calculate payroll for all entries in a run."""
        run = PayrollRunService.get_run_by_id(run_id, user)

        if run.statecode not in [PayrollRunStateCode.DRAFT, PayrollRunStateCode.CALCULATED]:
            raise ValidationError(f"Cannot calculate payroll in state: {run.state_name}")

        # Get active deductions and additions
        deductions = list(DeductionType.objects.filter(statecode=0))
        additions = list(AdditionType.objects.filter(statecode=0))

        entries = PayrollEntry.objects.filter(payrollrunid=run).select_related('employeeid')

        for entry in entries:
            emp = entry.employeeid

            # Base pay is already set from employee salary
            base = entry.basepay

            # Apply additions
            entry_additions = []
            total_additions = Decimal('0')
            for at in additions:
                amount = Decimal('0')
                if at.calculationtype == CalculationTypeCode.FIXED_AMOUNT:
                    amount = at.defaultvalue
                elif at.calculationtype == CalculationTypeCode.PERCENTAGE:
                    amount = base * at.defaultvalue / Decimal('100')
                elif at.calculationtype == CalculationTypeCode.HOURS_MULTIPLIER:
                    if entry.overtimehours and entry.overtimehours > 0:
                        hourly_rate = base / Decimal('48') if emp.salarytype == SalaryTypeCode.WEEKLY else base / Decimal('8')
                        amount = entry.overtimehours * hourly_rate * at.defaultvalue
                    else:
                        continue

                if amount > 0:
                    entry_additions.append({
                        'additiontypeid': str(at.additiontypeid),
                        'code': at.code,
                        'name': at.name,
                        'amount': str(amount.quantize(Decimal('0.01'))),
                    })
                    total_additions += amount

            # Gross pay
            gross = base + total_additions
            entry.grosspay = gross.quantize(Decimal('0.01'))
            entry.totaladditions = total_additions.quantize(Decimal('0.01'))
            entry.additions = entry_additions

            # Apply deductions (statutory only by default)
            entry_deductions = []
            total_deductions = Decimal('0')
            for dt in deductions:
                if not dt.isstatutory:
                    continue
                amount = Decimal('0')
                if dt.calculationtype == CalculationTypeCode.FIXED_AMOUNT:
                    amount = dt.defaultvalue
                elif dt.calculationtype == CalculationTypeCode.PERCENTAGE:
                    amount = gross * dt.defaultvalue / Decimal('100')

                if amount > 0:
                    entry_deductions.append({
                        'deductiontypeid': str(dt.deductiontypeid),
                        'code': dt.code,
                        'name': dt.name,
                        'amount': str(amount.quantize(Decimal('0.01'))),
                    })
                    total_deductions += amount

            entry.totaldeductions = total_deductions.quantize(Decimal('0.01'))
            entry.deductions = entry_deductions

            # Net pay
            entry.netpay = (gross - total_deductions).quantize(Decimal('0.01'))
            entry.save()

        # Recalculate run totals
        PayrollRunService._recalculate_totals(run)
        run.statecode = PayrollRunStateCode.CALCULATED
        run.modifiedby = user
        run.save()
        return run

    @staticmethod
    def _recalculate_totals(run: PayrollRun):
        """Recalculate PayrollRun summary totals from entries."""
        totals = PayrollEntry.objects.filter(payrollrunid=run).aggregate(
            total_gross=Sum('grosspay'),
            total_deductions=Sum('totaldeductions'),
            total_additions=Sum('totaladditions'),
            total_net=Sum('netpay'),
        )
        run.totalgrosspay = totals['total_gross'] or Decimal('0')
        run.totaldeductions = totals['total_deductions'] or Decimal('0')
        run.totaladditions = totals['total_additions'] or Decimal('0')
        run.totalnetpay = totals['total_net'] or Decimal('0')
        run.employeecount = PayrollEntry.objects.filter(payrollrunid=run).count()

    @staticmethod
    @audit_action(action='submit', entity='payrollrun', record_arg='run_id')
    def submit_for_approval(run_id: UUID, user: SystemUser) -> PayrollRun:
        run = PayrollRunService.get_run_by_id(run_id, user)
        if run.statecode not in [PayrollRunStateCode.DRAFT, PayrollRunStateCode.CALCULATED]:
            raise ValidationError(f"Cannot submit payroll in state: {run.state_name}")
        if run.employeecount == 0:
            raise ValidationError("Cannot submit an empty payroll run")
        run.statecode = PayrollRunStateCode.PENDING_APPROVAL
        run.modifiedby = user
        run.save()
        return run

    @staticmethod
    @audit_action(action='approve', entity='payrollrun', record_arg='run_id')
    def approve_payroll(run_id: UUID, user: SystemUser) -> PayrollRun:
        run = PayrollRunService.get_run_by_id(run_id, user)
        if run.statecode != PayrollRunStateCode.PENDING_APPROVAL:
            raise ValidationError(f"Cannot approve payroll in state: {run.state_name}")
        run.statecode = PayrollRunStateCode.APPROVED
        run.approvedby = user
        run.approveddate = timezone.now()
        run.modifiedby = user
        run.save()
        return run

    @staticmethod
    @audit_action(action='reject', entity='payrollrun', record_arg='run_id')
    def reject_payroll(run_id: UUID, dto: RejectPayrollDto, user: SystemUser) -> PayrollRun:
        run = PayrollRunService.get_run_by_id(run_id, user)
        if run.statecode != PayrollRunStateCode.PENDING_APPROVAL:
            raise ValidationError(f"Cannot reject payroll in state: {run.state_name}")
        run.statecode = PayrollRunStateCode.REJECTED
        if dto.reason:
            run.description = f"{run.description or ''}\n[Rejected] {dto.reason}".strip()
        run.modifiedby = user
        run.save()
        return run

    @staticmethod
    @audit_action(action='mark_paid', entity='payrollrun', record_arg='run_id')
    def mark_as_paid(run_id: UUID, user: SystemUser) -> PayrollRun:
        run = PayrollRunService.get_run_by_id(run_id, user)
        if run.statecode != PayrollRunStateCode.APPROVED:
            raise ValidationError(f"Cannot mark as paid in state: {run.state_name}")
        run.statecode = PayrollRunStateCode.PAID
        run.paiddate = date.today()
        run.modifiedby = user
        run.save()

        # Mark all entries as paid
        PayrollEntry.objects.filter(payrollrunid=run).update(
            paymentstatus=PaymentStatusCode.PAID
        )
        return run

    @staticmethod
    def list_entries(
        run_id: UUID,
        user: SystemUser,
    ) -> QuerySet[PayrollEntry]:
        run = PayrollRunService.get_run_by_id(run_id, user)
        return PayrollEntry.objects.filter(
            payrollrunid=run
        ).select_related('employeeid')

    @staticmethod
    def update_entry(entry_id: UUID, dto: UpdatePayrollEntryDto, user: SystemUser) -> PayrollEntry:
        try:
            entry = PayrollEntry.objects.select_related(
                'payrollrunid', 'employeeid'
            ).get(payrollentryid=entry_id)
        except PayrollEntry.DoesNotExist:
            raise NotFound(f"PayrollEntry with ID {entry_id} not found")

        if entry.payrollrunid.statecode not in [PayrollRunStateCode.DRAFT, PayrollRunStateCode.CALCULATED]:
            raise ValidationError("Cannot modify entries in a submitted/approved payroll run")

        for field in ['basepay', 'regularhours', 'overtimehours', 'notes']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(entry, field, value)

        entry.modifiedby = user
        entry.save()
        return entry


# ============================================================================
# Attendance Service
# ============================================================================

class AttendanceService:
    """Service for AttendanceRecord entity."""

    @staticmethod
    def list_attendance(
        user: SystemUser,
        employeeid: Optional[UUID] = None,
        projectid: Optional[UUID] = None,
        startdate: Optional[date] = None,
        enddate: Optional[date] = None,
        attendancetype: Optional[int] = None,
    ) -> QuerySet[AttendanceRecord]:
        queryset = AttendanceRecord.objects.all()

        if employeeid:
            queryset = queryset.filter(employeeid=employeeid)
        if projectid:
            queryset = queryset.filter(projectid=projectid)
        if startdate:
            queryset = queryset.filter(attendancedate__gte=startdate)
        if enddate:
            queryset = queryset.filter(attendancedate__lte=enddate)
        if attendancetype is not None:
            queryset = queryset.filter(attendancetype=attendancetype)

        queryset = queryset.select_related('employeeid', 'projectid')
        return queryset

    @staticmethod
    @audit_action(action='create', entity='attendancerecord')
    def create_attendance(dto: CreateAttendanceDto, user: SystemUser) -> AttendanceRecord:
        try:
            employee = Employee.objects.get(employeeid=dto.employeeid)
        except Employee.DoesNotExist:
            raise ValidationError(f"Employee with ID {dto.employeeid} not found")

        project = None
        if dto.projectid:
            from apps.projects.models import ConstructionProject
            try:
                project = ConstructionProject.objects.get(projectid=dto.projectid)
            except ConstructionProject.DoesNotExist:
                raise ValidationError(f"Project with ID {dto.projectid} not found")

        record = AttendanceRecord(
            employeeid=employee,
            projectid=project,
            attendancedate=dto.attendancedate,
            checkintime=dto.checkintime,
            checkouttime=dto.checkouttime,
            regularhoursworked=dto.regularhoursworked,
            overtimehoursworked=dto.overtimehoursworked,
            attendancetype=dto.attendancetype,
            notes=dto.notes,
            createdby=user,
            modifiedby=user,
        )
        record.save()
        return record

    @staticmethod
    def update_attendance(record_id: UUID, dto: UpdateAttendanceDto, user: SystemUser) -> AttendanceRecord:
        try:
            record = AttendanceRecord.objects.select_related(
                'employeeid', 'projectid'
            ).get(attendanceid=record_id)
        except AttendanceRecord.DoesNotExist:
            raise NotFound(f"AttendanceRecord with ID {record_id} not found")

        for field in ['checkintime', 'checkouttime', 'regularhoursworked', 'overtimehoursworked', 'attendancetype', 'notes']:
            value = getattr(dto, field, None)
            if value is not None:
                setattr(record, field, value)

        if dto.projectid is not None:
            from apps.projects.models import ConstructionProject
            try:
                record.projectid = ConstructionProject.objects.get(projectid=dto.projectid)
            except ConstructionProject.DoesNotExist:
                raise ValidationError(f"Project with ID {dto.projectid} not found")

        record.modifiedby = user
        record.save()
        return record

    @staticmethod
    @transaction.atomic
    def bulk_create_attendance(entries: list, user: SystemUser) -> List[AttendanceRecord]:
        """Create attendance records for multiple employees at once."""
        records = []
        for dto in entries:
            try:
                record = AttendanceService.create_attendance(dto, user)
                records.append(record)
            except (ValidationError, Exception):
                continue
        return records

    @staticmethod
    def delete_attendance(record_id: UUID, user: SystemUser) -> None:
        try:
            record = AttendanceRecord.objects.get(attendanceid=record_id)
        except AttendanceRecord.DoesNotExist:
            raise NotFound(f"AttendanceRecord with ID {record_id} not found")
        record.delete()

    @staticmethod
    def get_attendance_summary(
        employeeid: UUID,
        startdate: date,
        enddate: date,
    ) -> dict:
        """Get attendance summary for an employee in a date range."""
        records = AttendanceRecord.objects.filter(
            employeeid=employeeid,
            attendancedate__gte=startdate,
            attendancedate__lte=enddate,
        )
        totals = records.aggregate(
            total_regular=Sum('regularhoursworked'),
            total_overtime=Sum('overtimehoursworked'),
        )
        present_days = records.filter(attendancetype=AttendanceTypeCode.PRESENT).count()
        absent_days = records.filter(attendancetype=AttendanceTypeCode.ABSENT).count()

        return {
            'employeeid': str(employeeid),
            'startdate': str(startdate),
            'enddate': str(enddate),
            'total_regular_hours': float(totals['total_regular'] or 0),
            'total_overtime_hours': float(totals['total_overtime'] or 0),
            'present_days': present_days,
            'absent_days': absent_days,
            'total_records': records.count(),
        }
