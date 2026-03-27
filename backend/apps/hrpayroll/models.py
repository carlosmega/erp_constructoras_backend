"""
HR & Payroll entity models.
Manages employees, payroll runs, attendance, and deduction/addition catalogs
for construction company workforce.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator
from core.models import AuditMixin


# ============================================================================
# Enum Definitions
# ============================================================================

class EmployeeStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    ON_LEAVE = 1, 'On Leave'
    TERMINATED = 2, 'Terminated'


class EmployeeStatusCode(models.IntegerChoices):
    PROBATION = 0, 'Probation'
    CONFIRMED = 1, 'Confirmed'
    ON_VACATION = 2, 'On Vacation'
    SICK_LEAVE = 3, 'Sick Leave'
    SUSPENDED = 4, 'Suspended'
    VOLUNTARY_EXIT = 5, 'Voluntary Exit'
    DISMISSED = 6, 'Dismissed'


class SalaryTypeCode(models.IntegerChoices):
    HOURLY = 0, 'Hourly'
    WEEKLY = 1, 'Weekly'
    BIWEEKLY = 2, 'Biweekly'
    MONTHLY = 3, 'Monthly'


class AssignmentStateCode(models.IntegerChoices):
    ACTIVE = 0, 'Active'
    COMPLETED = 1, 'Completed'
    CANCELED = 2, 'Canceled'


class CalculationTypeCode(models.IntegerChoices):
    FIXED_AMOUNT = 0, 'Fixed Amount'
    PERCENTAGE = 1, 'Percentage'
    HOURS_MULTIPLIER = 2, 'Hours Multiplier'


class PeriodTypeCode(models.IntegerChoices):
    WEEKLY = 0, 'Weekly'
    BIWEEKLY = 1, 'Biweekly'
    MONTHLY = 2, 'Monthly'


class PeriodStateCode(models.IntegerChoices):
    OPEN = 0, 'Open'
    PROCESSING = 1, 'Processing'
    CLOSED = 2, 'Closed'


class PayrollRunStateCode(models.IntegerChoices):
    DRAFT = 0, 'Draft'
    CALCULATED = 1, 'Calculated'
    PENDING_APPROVAL = 2, 'Pending Approval'
    APPROVED = 3, 'Approved'
    PAID = 4, 'Paid'
    REJECTED = 5, 'Rejected'


class PaymentStatusCode(models.IntegerChoices):
    PENDING = 0, 'Pending'
    PAID = 1, 'Paid'
    FAILED = 2, 'Failed'


class AttendanceTypeCode(models.IntegerChoices):
    PRESENT = 0, 'Present'
    ABSENT = 1, 'Absent'
    HALF_DAY = 2, 'Half Day'
    HOLIDAY = 3, 'Holiday'
    REST_DAY = 4, 'Rest Day'


# ============================================================================
# Employee Model
# ============================================================================

class Employee(AuditMixin):
    """Employee entity for construction workforce management."""

    employeeid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='employeeid'
    )

    # Auto-generated number
    employeenumber = models.CharField(
        max_length=20,
        unique=True,
        db_column='employeenumber',
        help_text='Auto-generated: EMP-YYYY-NNN'
    )

    # Personal information
    firstname = models.CharField(max_length=100, db_column='firstname')
    lastname = models.CharField(max_length=100, db_column='lastname')
    fullname = models.CharField(max_length=200, db_column='fullname', blank=True)
    curp = models.CharField(max_length=18, db_column='curp', blank=True, null=True, unique=True)
    rfc = models.CharField(max_length=13, db_column='rfc', blank=True, null=True)
    nss = models.CharField(max_length=11, db_column='nss', blank=True, null=True, help_text='Social security number')
    emailaddress = models.EmailField(db_column='emailaddress', blank=True, null=True)
    phonenumber = models.CharField(max_length=20, db_column='phonenumber', blank=True, null=True)
    dateofbirth = models.DateField(db_column='dateofbirth', blank=True, null=True)

    # Employment information
    hiredate = models.DateField(db_column='hiredate')
    terminationdate = models.DateField(db_column='terminationdate', blank=True, null=True)
    position = models.CharField(max_length=100, db_column='position')
    department = models.CharField(max_length=100, db_column='department')

    # Salary
    salarytype = models.IntegerField(
        choices=SalaryTypeCode.choices,
        default=SalaryTypeCode.WEEKLY,
        db_column='salarytype'
    )
    basesalary = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        db_column='basesalary'
    )

    # Bank information
    bankname = models.CharField(max_length=100, db_column='bankname', blank=True, null=True)
    bankaccountnumber = models.CharField(max_length=20, db_column='bankaccountnumber', blank=True, null=True)
    clabenumber = models.CharField(max_length=18, db_column='clabenumber', blank=True, null=True)

    # Emergency contact
    emergencycontactname = models.CharField(max_length=200, db_column='emergencycontactname', blank=True, null=True)
    emergencycontactphone = models.CharField(max_length=20, db_column='emergencycontactphone', blank=True, null=True)
    emergencycontactrelation = models.CharField(max_length=50, db_column='emergencycontactrelation', blank=True, null=True)

    # State management
    statecode = models.IntegerField(
        choices=EmployeeStateCode.choices,
        default=EmployeeStateCode.ACTIVE,
        db_column='statecode'
    )
    statuscode = models.IntegerField(
        choices=EmployeeStatusCode.choices,
        default=EmployeeStatusCode.PROBATION,
        db_column='statuscode'
    )

    notes = models.TextField(db_column='notes', blank=True, null=True)

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_employees'
    )

    class Meta:
        db_table = 'employee'
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['employeenumber']),
            models.Index(fields=['lastname', 'firstname']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return f'{self.fullname} ({self.employeenumber})'

    def save(self, *args, **kwargs):
        self.fullname = f'{self.firstname} {self.lastname}'.strip()
        super().save(*args, **kwargs)

    @property
    def state_name(self):
        return EmployeeStateCode(self.statecode).label

    @property
    def status_name(self):
        return EmployeeStatusCode(self.statuscode).label

    @property
    def salary_type_name(self):
        return SalaryTypeCode(self.salarytype).label


# ============================================================================
# EmployeeProjectAssignment Model
# ============================================================================

class EmployeeProjectAssignment(AuditMixin):
    """Links employees to construction projects with role and schedule."""

    assignmentid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='assignmentid'
    )

    employeeid = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column='employeeid',
        related_name='assignments'
    )
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.PROTECT,
        db_column='projectid',
        related_name='employee_assignments'
    )

    role = models.CharField(max_length=100, db_column='role')
    startdate = models.DateField(db_column='startdate')
    enddate = models.DateField(db_column='enddate', blank=True, null=True)
    hoursperweek = models.DecimalField(
        max_digits=5, decimal_places=2,
        db_column='hoursperweek', blank=True, null=True
    )
    isprimary = models.BooleanField(default=False, db_column='isprimary')

    statecode = models.IntegerField(
        choices=AssignmentStateCode.choices,
        default=AssignmentStateCode.ACTIVE,
        db_column='statecode'
    )

    class Meta:
        db_table = 'employeeprojectassignment'
        verbose_name = 'Employee Project Assignment'
        verbose_name_plural = 'Employee Project Assignments'
        ordering = ['-startdate']
        constraints = [
            models.UniqueConstraint(
                fields=['employeeid', 'projectid'],
                condition=models.Q(statecode=0),
                name='unique_active_employee_project'
            )
        ]

    def __str__(self):
        return f'{self.employeeid} → {self.projectid} ({self.role})'


# ============================================================================
# DeductionType Model (Catalog)
# ============================================================================

class DeductionType(AuditMixin):
    """Catalog of payroll deduction types (ISR, IMSS, INFONAVIT, loans)."""

    deductiontypeid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='deductiontypeid'
    )

    code = models.CharField(max_length=20, unique=True, db_column='code')
    name = models.CharField(max_length=100, db_column='name')
    description = models.TextField(db_column='description', blank=True, null=True)
    calculationtype = models.IntegerField(
        choices=CalculationTypeCode.choices,
        default=CalculationTypeCode.FIXED_AMOUNT,
        db_column='calculationtype'
    )
    defaultvalue = models.DecimalField(
        max_digits=12, decimal_places=4,
        default=0,
        db_column='defaultvalue'
    )
    isstatutory = models.BooleanField(default=False, db_column='isstatutory')

    statecode = models.IntegerField(
        choices=models.IntegerChoices('CatalogStateCode', 'ACTIVE INACTIVE').choices,
        default=0,
        db_column='statecode'
    )

    class Meta:
        db_table = 'deductiontype'
        verbose_name = 'Deduction Type'
        verbose_name_plural = 'Deduction Types'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


# ============================================================================
# AdditionType Model (Catalog)
# ============================================================================

class AdditionType(AuditMixin):
    """Catalog of payroll addition types (overtime, bonuses, hazard pay)."""

    additiontypeid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='additiontypeid'
    )

    code = models.CharField(max_length=20, unique=True, db_column='code')
    name = models.CharField(max_length=100, db_column='name')
    description = models.TextField(db_column='description', blank=True, null=True)
    calculationtype = models.IntegerField(
        choices=CalculationTypeCode.choices,
        default=CalculationTypeCode.FIXED_AMOUNT,
        db_column='calculationtype'
    )
    defaultvalue = models.DecimalField(
        max_digits=12, decimal_places=4,
        default=0,
        db_column='defaultvalue'
    )
    istaxable = models.BooleanField(default=True, db_column='istaxable')

    statecode = models.IntegerField(
        choices=models.IntegerChoices('CatalogStateCode', 'ACTIVE INACTIVE').choices,
        default=0,
        db_column='statecode'
    )

    class Meta:
        db_table = 'additiontype'
        verbose_name = 'Addition Type'
        verbose_name_plural = 'Addition Types'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


# ============================================================================
# PayrollPeriod Model
# ============================================================================

class PayrollPeriod(AuditMixin):
    """Payroll period definition (weekly, biweekly, monthly)."""

    payrollperiodid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='payrollperiodid'
    )

    periodnumber = models.IntegerField(db_column='periodnumber')
    periodtype = models.IntegerField(
        choices=PeriodTypeCode.choices,
        default=PeriodTypeCode.WEEKLY,
        db_column='periodtype'
    )
    startdate = models.DateField(db_column='startdate')
    enddate = models.DateField(db_column='enddate')
    year = models.IntegerField(db_column='year')
    label = models.CharField(max_length=50, db_column='label')

    statecode = models.IntegerField(
        choices=PeriodStateCode.choices,
        default=PeriodStateCode.OPEN,
        db_column='statecode'
    )

    class Meta:
        db_table = 'payrollperiod'
        verbose_name = 'Payroll Period'
        verbose_name_plural = 'Payroll Periods'
        ordering = ['-year', '-periodnumber']
        constraints = [
            models.UniqueConstraint(
                fields=['year', 'periodnumber', 'periodtype'],
                name='unique_payroll_period'
            )
        ]

    def __str__(self):
        return self.label

    @property
    def period_type_name(self):
        return PeriodTypeCode(self.periodtype).label


# ============================================================================
# PayrollRun Model
# ============================================================================

class PayrollRun(AuditMixin):
    """Payroll run (corrida de nómina) with approval workflow."""

    payrollrunid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='payrollrunid'
    )

    payrollperiodid = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.PROTECT,
        db_column='payrollperiodid',
        related_name='runs'
    )

    runnumber = models.CharField(
        max_length=20,
        unique=True,
        db_column='runnumber',
        help_text='Auto-generated: NOM-YYYY-NNN'
    )
    description = models.CharField(max_length=200, db_column='description', blank=True, null=True)

    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.PROTECT,
        db_column='projectid',
        related_name='payroll_runs',
        blank=True, null=True,
        help_text='Optional: payroll run for a specific project'
    )

    # Computed totals
    totalgrosspay = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='totalgrosspay')
    totaldeductions = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='totaldeductions')
    totaladditions = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='totaladditions')
    totalnetpay = models.DecimalField(max_digits=14, decimal_places=2, default=0, db_column='totalnetpay')
    employeecount = models.IntegerField(default=0, db_column='employeecount')

    # State management
    statecode = models.IntegerField(
        choices=PayrollRunStateCode.choices,
        default=PayrollRunStateCode.DRAFT,
        db_column='statecode'
    )

    # Approval
    approvedby = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.SET_NULL,
        db_column='approvedby',
        related_name='approved_payroll_runs',
        blank=True, null=True
    )
    approveddate = models.DateTimeField(db_column='approveddate', blank=True, null=True)
    paiddate = models.DateField(db_column='paiddate', blank=True, null=True)

    # Ownership
    ownerid = models.ForeignKey(
        'users.SystemUser',
        on_delete=models.PROTECT,
        db_column='ownerid',
        related_name='owned_payroll_runs'
    )

    class Meta:
        db_table = 'payrollrun'
        verbose_name = 'Payroll Run'
        verbose_name_plural = 'Payroll Runs'
        ordering = ['-createdon']
        indexes = [
            models.Index(fields=['statecode', 'ownerid']),
            models.Index(fields=['payrollperiodid']),
            models.Index(fields=['runnumber']),
        ]

    def __str__(self):
        return f'{self.runnumber} - {self.payrollperiodid.label}'

    @property
    def state_name(self):
        return PayrollRunStateCode(self.statecode).label


# ============================================================================
# PayrollEntry Model
# ============================================================================

class PayrollEntry(AuditMixin):
    """Individual employee payroll entry within a payroll run."""

    payrollentryid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='payrollentryid'
    )

    payrollrunid = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        db_column='payrollrunid',
        related_name='entries'
    )
    employeeid = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        db_column='employeeid',
        related_name='payroll_entries'
    )

    # Pay calculation
    basepay = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='basepay')
    regularhours = models.DecimalField(max_digits=6, decimal_places=2, db_column='regularhours', blank=True, null=True)
    overtimehours = models.DecimalField(max_digits=6, decimal_places=2, default=0, db_column='overtimehours')

    # Totals
    grosspay = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='grosspay')
    totaldeductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='totaldeductions')
    totaladditions = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='totaladditions')
    netpay = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='netpay')

    # Deduction/addition detail (snapshot from catalogs)
    deductions = models.JSONField(default=list, db_column='deductions', help_text='Snapshot of applied deductions')
    additions = models.JSONField(default=list, db_column='additions', help_text='Snapshot of applied additions')

    # Payment tracking
    paymentstatus = models.IntegerField(
        choices=PaymentStatusCode.choices,
        default=PaymentStatusCode.PENDING,
        db_column='paymentstatus'
    )

    notes = models.TextField(db_column='notes', blank=True, null=True)

    class Meta:
        db_table = 'payrollentry'
        verbose_name = 'Payroll Entry'
        verbose_name_plural = 'Payroll Entries'
        ordering = ['employeeid__lastname']
        constraints = [
            models.UniqueConstraint(
                fields=['payrollrunid', 'employeeid'],
                name='unique_payroll_entry_per_run'
            )
        ]

    def __str__(self):
        return f'{self.employeeid.fullname} - {self.payrollrunid.runnumber}'

    @property
    def payment_status_name(self):
        return PaymentStatusCode(self.paymentstatus).label


# ============================================================================
# AttendanceRecord Model
# ============================================================================

class AttendanceRecord(AuditMixin):
    """Daily attendance record per employee, optionally linked to a project."""

    attendanceid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column='attendanceid'
    )

    employeeid = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column='employeeid',
        related_name='attendance_records'
    )
    projectid = models.ForeignKey(
        'projects.ConstructionProject',
        on_delete=models.PROTECT,
        db_column='projectid',
        related_name='attendance_records',
        blank=True, null=True
    )

    attendancedate = models.DateField(db_column='attendancedate')
    checkintime = models.TimeField(db_column='checkintime', blank=True, null=True)
    checkouttime = models.TimeField(db_column='checkouttime', blank=True, null=True)
    regularhoursworked = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0,
        db_column='regularhoursworked'
    )
    overtimehoursworked = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=0,
        db_column='overtimehoursworked'
    )

    attendancetype = models.IntegerField(
        choices=AttendanceTypeCode.choices,
        default=AttendanceTypeCode.PRESENT,
        db_column='attendancetype'
    )

    notes = models.TextField(db_column='notes', blank=True, null=True)

    class Meta:
        db_table = 'attendancerecord'
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        ordering = ['-attendancedate']
        constraints = [
            models.UniqueConstraint(
                fields=['employeeid', 'attendancedate'],
                name='unique_attendance_per_day'
            )
        ]
        indexes = [
            models.Index(fields=['attendancedate', 'projectid']),
            models.Index(fields=['employeeid', 'attendancedate']),
        ]

    def __str__(self):
        return f'{self.employeeid.fullname} - {self.attendancedate}'

    @property
    def attendance_type_name(self):
        return AttendanceTypeCode(self.attendancetype).label
