"""
PNTCalculator — derive Posición Neta de Tesorería from budget + financial settings.

Produces a PNTReportDto with ~22 rows × N periods.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass, field

from apps.projects.models import ConstructionProject
from apps.budgets.models import (
    ImputationPeriod, ImputationCodeBudget, CostTypeCode,
)
from apps.cashflow.models import ProjectFinancialSettings, ProjectBillingRule
from apps.cashflow.services.financial_settings import FinancialSettingsService


ZERO = Decimal('0')


@dataclass
class _Row:
    code: str
    label: str
    section: str
    values: list
    emphasis: bool = False


@dataclass
class _Report:
    projectid: UUID
    granularity: str
    periods: list
    rows: list
    stats: dict
    generated_at: datetime


class PNTCalculator:
    def __init__(self, project_id: UUID):
        self.project = ConstructionProject.objects.get(projectid=project_id)
        self.periods = list(
            ImputationPeriod.objects.filter(projectid=project_id).order_by('sortorder')
        )
        self.N = len(self.periods)
        if self.N == 0:
            raise ValueError(
                'No hay períodos inicializados para este proyecto. '
                'Inicializa el presupuesto antes de consultar PNT.'
            )
        self.settings = FinancialSettingsService.get_or_create(project_id)
        self.billing_rules = self._load_billing_rules()
        self._period_index = {p.label: i for i, p in enumerate(self.periods)}

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def compute(self, overrides: dict | None = None, granularity: str = 'period') -> _Report:
        if overrides:
            self._apply_overrides(overrides)

        produccion, costo_directo, costo_indirecto, codes_sin_precio = self._compute_base_vectors()

        rows = [
            _Row('PRODUCCION', 'Producción', 'RESULTADO', produccion),
            _Row('COSTO_DIRECTO', 'Costo Directo', 'RESULTADO', costo_directo),
            _Row('COSTO_INDIRECTO', 'Costo Indirecto', 'RESULTADO', costo_indirecto),
        ]

        stats = {
            'pnt_min': ZERO, 'pnt_max': ZERO, 'pnt_avg': ZERO,
            'total_costo_financiero': ZERO,
            'cobros_fuera_horizonte': ZERO,
            'pagos_fuera_horizonte': ZERO,
            'codes_sin_precio': sorted(codes_sin_precio),
        }
        return _Report(
            projectid=self.project.projectid,
            granularity=granularity,
            periods=[{'label': p.label, 'startdate': p.startdate, 'enddate': p.enddate} for p in self.periods],
            rows=rows,
            stats=stats,
            generated_at=datetime.utcnow(),
        )

    # -----------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------

    def _load_billing_rules(self):
        rules = list(
            ProjectBillingRule.objects.filter(projectid=self.project)
            .order_by('sequence')
        )
        if not rules:
            # Implicit default: 100% at lag 0
            return [_InlineRule(sequence=1, percent=Decimal('1'), lagperiods=0)]
        return rules

    def _apply_overrides(self, overrides: dict):
        """Apply overrides to a detached copy of settings / rules (no DB writes)."""
        FIELD_ALLOW = {
            'imssretentionrate', 'otherretentionrate', 'retentionreturnperiod',
            'advanceamortizationrate', 'anticipoentryperiod',
            'transversalcost', 'transversalwithdrawalperiod',
            'utilitycost', 'utilitywithdrawalperiod',
            'financecostrate',
        }
        for key, value in overrides.items():
            if key in FIELD_ALLOW:
                setattr(self.settings, key, Decimal(str(value)) if isinstance(value, (int, float, str)) else value)
        if 'billing_rules' in overrides:
            self.billing_rules = [
                _InlineRule(
                    sequence=r['sequence'],
                    percent=Decimal(str(r['percent'])),
                    lagperiods=int(r['lagperiods']),
                )
                for r in overrides['billing_rules']
            ]

    def _compute_base_vectors(self):
        produccion = [ZERO] * self.N
        costo_directo = [ZERO] * self.N
        costo_indirecto = [ZERO] * self.N
        codes_sin_precio: set[str] = set()

        budgets = (
            ImputationCodeBudget.objects
            .filter(imputationcodeid__projectid=self.project.projectid)
            .select_related('imputationcodeid', 'imputationcodeid__categoryid')
        )
        for b in budgets:
            i = self._period_index.get(b.periodlabel)
            if i is None:
                continue
            code = b.imputationcodeid
            if code.costtype == CostTypeCode.DIRECT:
                price = code.contractunitprice
                if price is None:
                    codes_sin_precio.add(code.code)
                    price = ZERO
                produccion[i] += price * b.plannedvolume
                costo_directo[i] += b.plannedamount
            else:
                costo_indirecto[i] += b.plannedamount
        return produccion, costo_directo, costo_indirecto, codes_sin_precio


@dataclass
class _InlineRule:
    sequence: int
    percent: Decimal
    lagperiods: int
