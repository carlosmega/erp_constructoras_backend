"""Corporate module API schemas."""

from ninja import ModelSchema, Schema
from typing import Optional, List
from uuid import UUID
from decimal import Decimal
from datetime import date, datetime

from apps.corporate.models import (
    CorporateBudget,
    CorporateBudgetVersion,
    CorporateBudgetLine,
    CorporateExpense,
    CorporateAllocation,
    CorporateAllocationLine,
    WhatIfSimulation,
)


# =============================================================================
# Budget Schemas
# =============================================================================

class CorporateBudgetLineSchema(ModelSchema):
    """Full budget line response."""
    monthlypromedio: Decimal = 0

    class Meta:
        model = CorporateBudgetLine
        fields = '__all__'

    @staticmethod
    def resolve_monthlypromedio(obj):
        return obj.monthlypromedio


class CorporateBudgetVersionSchema(ModelSchema):
    """Full budget version response with nested lines."""
    lines: List[CorporateBudgetLineSchema] = []

    class Meta:
        model = CorporateBudgetVersion
        fields = '__all__'

    @staticmethod
    def resolve_lines(obj):
        if hasattr(obj, 'lines'):
            return list(obj.lines.all())
        return []


class CorporateBudgetSchema(ModelSchema):
    """Full corporate budget response."""
    approvedbyname: Optional[str] = None
    ownername: Optional[str] = None
    activeversion: Optional[CorporateBudgetVersionSchema] = None
    versioncount: int = 0

    class Meta:
        model = CorporateBudget
        fields = '__all__'

    @staticmethod
    def resolve_approvedbyname(obj):
        return obj.approvedby.fullname if obj.approvedby else None

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_activeversion(obj):
        if hasattr(obj, '_active_version'):
            return obj._active_version
        try:
            return obj.versions.filter(statecode=0).first()
        except Exception:
            return None

    @staticmethod
    def resolve_versioncount(obj):
        try:
            return obj.versions.count()
        except Exception:
            return 0


class CorporateBudgetListSchema(ModelSchema):
    """Lightweight budget for list views."""
    ownername: Optional[str] = None
    versioncount: int = 0

    class Meta:
        model = CorporateBudget
        fields = [
            'corporatebudgetid', 'fiscalyear', 'periodtype', 'quarter', 'name', 'currency',
            'totalbudget', 'monthlypromedio', 'statecode',
            'approveddate', 'createdon', 'modifiedon',
        ]

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None

    @staticmethod
    def resolve_versioncount(obj):
        try:
            return obj.versions.count()
        except Exception:
            return 0


# Budget DTOs
class CreateCorporateBudgetDto(Schema):
    fiscalyear: int
    name: str
    description: Optional[str] = None
    currency: str = 'MXN'
    periodtype: int = 0  # 0=Annual, 1=Q1, 2=Q2, 3=Q3, 4=Q4
    quarter: Optional[int] = None


class UpdateCorporateBudgetDto(Schema):
    name: Optional[str] = None
    description: Optional[str] = None


class CreateBudgetVersionDto(Schema):
    label: str
    notes: Optional[str] = None


class UpdateBudgetLineDto(Schema):
    jan: Optional[Decimal] = None
    feb: Optional[Decimal] = None
    mar: Optional[Decimal] = None
    apr: Optional[Decimal] = None
    may: Optional[Decimal] = None
    jun: Optional[Decimal] = None
    jul: Optional[Decimal] = None
    aug: Optional[Decimal] = None
    sep: Optional[Decimal] = None
    oct: Optional[Decimal] = None
    nov: Optional[Decimal] = None
    dec: Optional[Decimal] = None
    notes: Optional[str] = None


class BulkUpdateBudgetLinesDto(Schema):
    lines: List[dict]  # List of {budgetlineid: str, ...month fields}


# =============================================================================
# Expense Schemas
# =============================================================================

class CorporateExpenseSchema(ModelSchema):
    """Full expense response with semaphore."""
    semaphore: str = 'green'

    class Meta:
        model = CorporateExpense
        fields = '__all__'

    @staticmethod
    def resolve_semaphore(obj):
        if obj.budgetedamount and obj.budgetedamount > 0:
            pct = abs(float(obj.variancepercent))
            if pct > 20:
                return 'red'
            elif pct > 10:
                return 'yellow'
        return 'green'


class RecordExpenseDto(Schema):
    categorycode: str
    year: int
    month: int
    actualamount: Decimal
    notes: Optional[str] = None


class BulkRecordExpenseDto(Schema):
    expenses: List[RecordExpenseDto]


class BudgetVsActualMonthSchema(Schema):
    month: int
    budgeted: Decimal
    actual: Decimal
    variance: Decimal
    variancepercent: Decimal
    semaphore: str


class BudgetVsActualRowSchema(Schema):
    categorycode: str
    categoryname: str
    months: List[BudgetVsActualMonthSchema]
    annualbudgeted: Decimal
    annualactual: Decimal
    annualvariance: Decimal
    annualvariancepercent: Decimal
    annualsemaphore: str


class BudgetVsActualSummarySchema(Schema):
    rows: List[BudgetVsActualRowSchema]
    totalbudgeted: Decimal
    totalactual: Decimal
    totalvariance: Decimal
    totalvariancepercent: Decimal
    totalsemaphore: str
    ytdbudgeted: Decimal
    ytdactual: Decimal
    ytdvariance: Decimal
    projectedannual: Decimal


# =============================================================================
# Allocation Schemas (stubs for Agent D to complete)
# =============================================================================

class CorporateAllocationLineSchema(ModelSchema):
    """Full allocation line response."""
    projectname: Optional[str] = None
    projectnumber: Optional[str] = None

    class Meta:
        model = CorporateAllocationLine
        fields = '__all__'

    @staticmethod
    def resolve_projectname(obj):
        return obj.projectid.name if obj.projectid else None

    @staticmethod
    def resolve_projectnumber(obj):
        return obj.projectid.projectnumber if obj.projectid else None


class CorporateAllocationSchema(ModelSchema):
    """Full allocation response with lines."""
    prorationmethodname: Optional[str] = None
    lines: List[CorporateAllocationLineSchema] = []

    class Meta:
        model = CorporateAllocation
        fields = '__all__'

    @staticmethod
    def resolve_prorationmethodname(obj):
        return obj.get_prorationmethod_display()

    @staticmethod
    def resolve_lines(obj):
        if hasattr(obj, 'lines'):
            return list(obj.lines.select_related('projectid').all())
        return []


class CalculateAllocationDto(Schema):
    year: int
    month: int
    prorationmethod: int
    manualweights: Optional[dict] = None  # {project_id_str: percent}


class ApplyAllocationDto(Schema):
    confirm: bool = True


# =============================================================================
# Portfolio Schemas (stubs for Agent D to complete)
# =============================================================================

class PortfolioProjectSchema(Schema):
    projectid: str
    projectnumber: str
    name: str
    statecode: int
    startdate: Optional[str] = None
    contractenddate: Optional[str] = None
    durationmonths: int = 0
    contractamount: Decimal = 0
    directcosts: Decimal = 0
    indirectcostscampo: Decimal = 0
    corporateoverhead: Decimal = 0
    marginbeforeoverhead: Decimal = 0
    marginafteroverhead: Decimal = 0
    marginpercent: Decimal = 0


class PortfolioSummarySchema(Schema):
    projects: List[PortfolioProjectSchema]
    totalcontractamount: Decimal = 0
    totaldirectcosts: Decimal = 0
    totalindirectcostscampo: Decimal = 0
    totalcorporateoverhead: Decimal = 0
    totalmargin: Decimal = 0
    totalmarginpercent: Decimal = 0
    corporatebudgetannual: Decimal = 0
    unallocatedoverhead: Decimal = 0


class MonthCoverageSchema(Schema):
    month: int
    year: int
    label: str
    activeprojects: int
    coveragepercent: Decimal
    overheadbudgeted: Decimal
    overheadallocated: Decimal


class CapacityBreakevenSchema(Schema):
    corporatebudgetannual: Decimal = 0
    totalcontractedcd: Decimal = 0
    estimatedcapacity: Decimal = 0
    breakevenpointcd: Decimal = 0
    currentcoveragepercent: Decimal = 0
    availablecapacity: Decimal = 0
    idlecapacitypercent: Decimal = 0
    activeprojectcount: int = 0
    monthscoverage: List[MonthCoverageSchema] = []


class TimelineProjectSchema(Schema):
    projectid: str
    projectnumber: str
    name: str
    startdate: str
    contractenddate: str
    allocatedoverhead: Decimal = 0


class TimelineMonthSchema(Schema):
    month: int
    year: int
    label: str
    projects: List[TimelineProjectSchema] = []
    overheadbudgeted: Decimal = 0
    overheadallocated: Decimal = 0
    coveragepercent: Decimal = 0


class TimelineDataSchema(Schema):
    months: List[TimelineMonthSchema] = []
    projects: List[TimelineProjectSchema] = []


# =============================================================================
# Simulation Schemas (stubs for Agent D to complete)
# =============================================================================

class WhatIfSimulationSchema(ModelSchema):
    """Full simulation response."""
    ownername: Optional[str] = None

    class Meta:
        model = WhatIfSimulation
        fields = '__all__'

    @staticmethod
    def resolve_ownername(obj):
        return obj.ownerid.fullname if obj.ownerid else None


class CreateSimulationDto(Schema):
    name: str
    description: Optional[str] = None
    fiscalyear: int
    corporatebudgetid: Optional[UUID] = None
    parameters: dict = {}


class SimulationResultSchema(Schema):
    currentscenario: dict = {}
    newscenario: dict = {}
