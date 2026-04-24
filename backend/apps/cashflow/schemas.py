"""Django Ninja DTOs for cashflow module."""
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID
from ninja import Schema
from pydantic import Field


# -------------------------------------------------------------------
# Billing rules
# -------------------------------------------------------------------

class BillingRuleDto(Schema):
    ruleid: Optional[UUID] = None
    sequence: int = Field(ge=1, le=10)
    percent: Decimal = Field(ge=0, le=1, decimal_places=4)
    lagperiods: int = Field(ge=0, le=120)


class ReplaceBillingRulesDto(Schema):
    rules: list[BillingRuleDto]


# -------------------------------------------------------------------
# Financial settings
# -------------------------------------------------------------------

class FinancialSettingsDto(Schema):
    settingsid: UUID
    projectid: UUID
    imssretentionrate: Decimal
    otherretentionrate: Decimal
    retentionreturnperiod: Optional[int] = None
    advanceamortizationrate: Decimal
    anticipoentryperiod: int
    transversalcost: Decimal
    transversalwithdrawalperiod: int
    utilitycost: Decimal
    utilitywithdrawalperiod: int
    financecostrate: Decimal


class UpdateFinancialSettingsDto(Schema):
    imssretentionrate: Optional[Decimal] = None
    otherretentionrate: Optional[Decimal] = None
    retentionreturnperiod: Optional[int] = None
    advanceamortizationrate: Optional[Decimal] = None
    anticipoentryperiod: Optional[int] = None
    transversalcost: Optional[Decimal] = None
    transversalwithdrawalperiod: Optional[int] = None
    utilitycost: Optional[Decimal] = None
    utilitywithdrawalperiod: Optional[int] = None
    financecostrate: Optional[Decimal] = None


# -------------------------------------------------------------------
# PNT report
# -------------------------------------------------------------------

class PNTPeriodDto(Schema):
    label: str
    startdate: date
    enddate: date


class PNTRowDto(Schema):
    code: str
    label: str
    section: Literal['RESULTADO', 'COBROS', 'PAGOS', 'CAJA']
    values: list[Decimal]
    emphasis: bool = False


class PNTStatsDto(Schema):
    pnt_min: Decimal
    pnt_max: Decimal
    pnt_avg: Decimal
    total_costo_financiero: Decimal
    cobros_fuera_horizonte: Decimal
    pagos_fuera_horizonte: Decimal
    codes_sin_precio: list[str]


class PNTReportDto(Schema):
    projectid: UUID
    granularity: Literal['period', 'month']
    periods: list[PNTPeriodDto]
    rows: list[PNTRowDto]
    stats: PNTStatsDto
    generated_at: datetime
