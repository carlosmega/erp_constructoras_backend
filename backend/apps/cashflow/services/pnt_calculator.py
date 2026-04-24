"""
PNTCalculator — derive Posición Neta de Tesorería from budget + financial settings.

Produces a PNTReportDto with ~22 rows × N periods.
"""
from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from dataclasses import dataclass

from django.utils import timezone

from apps.projects.models import ConstructionProject
from apps.budgets.models import (
    ImputationPeriod, ImputationCodeBudget, CostTypeCode,
)
from apps.cashflow.models import ProjectBillingRule
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

        # --- Cobros ---
        cobro_facturacion, cobros_fuera_horizonte = self._compute_cobro_facturacion(produccion)
        anticipo_concedido = self._compute_anticipo_concedido()
        anticipo_amortizado = [(-self.settings.advanceamortizationrate) * cf for cf in cobro_facturacion]
        retencion_imss = [(-self.settings.imssretentionrate) * cf for cf in cobro_facturacion]
        otras_retencion = [(-self.settings.otherretentionrate) * cf for cf in cobro_facturacion]
        devolucion = self._compute_devolucion_retenciones(retencion_imss, otras_retencion)
        saldo_anticipo = self._compute_saldo_anticipo(anticipo_amortizado)

        cobro_total = [
            anticipo_concedido[i] + cobro_facturacion[i] + anticipo_amortizado[i]
            + retencion_imss[i] + otras_retencion[i] + devolucion[i] + saldo_anticipo[i]
            for i in range(self.N)
        ]

        rows.extend([
            _Row('COBRO_TOTAL', 'Cobro Total sin IVA', 'COBROS', cobro_total, emphasis=True),
            _Row('COBRO_FACTURACION', 'Cobro Facturación', 'COBROS', cobro_facturacion),
            _Row('ANTICIPO_CONCEDIDO', 'Anticipo Concedido', 'COBROS', anticipo_concedido),
            _Row('ANTICIPO_AMORT', 'Anticipo Amortizado', 'COBROS', anticipo_amortizado),
            _Row('RET_IMSS', 'Retenciones IMSS', 'COBROS', retencion_imss),
            _Row('OTRAS_RET', 'Otras Retenciones', 'COBROS', otras_retencion),
            _Row('DEVOLUCION', 'Devolución Retenciones', 'COBROS', devolucion),
            _Row('SALDO_ANTICIPO', 'Saldo Anticipo', 'COBROS', saldo_anticipo),
        ])

        stats = {
            'pnt_min': ZERO, 'pnt_max': ZERO, 'pnt_avg': ZERO,
            'total_costo_financiero': ZERO,
            'cobros_fuera_horizonte': cobros_fuera_horizonte,
            'pagos_fuera_horizonte': ZERO,
            'codes_sin_precio': sorted(codes_sin_precio),
        }
        return _Report(
            projectid=self.project.projectid,
            granularity=granularity,
            periods=[{'label': p.label, 'startdate': p.startdate, 'enddate': p.enddate} for p in self.periods],
            rows=rows,
            stats=stats,
            generated_at=timezone.now(),
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

    def _compute_cobro_facturacion(self, produccion: list[Decimal]) -> tuple[list[Decimal], Decimal]:
        out = [ZERO] * self.N
        fuera = ZERO
        for i in range(self.N):
            if produccion[i] == 0:
                continue
            for rule in self.billing_rules:
                target = i + rule.lagperiods
                amount = produccion[i] * rule.percent
                if 0 <= target < self.N:
                    out[target] += amount
                else:
                    fuera += amount
        return out, fuera

    def _compute_anticipo_concedido(self) -> list[Decimal]:
        out = [ZERO] * self.N
        p = (self.settings.anticipoentryperiod or 1) - 1
        if 0 <= p < self.N and self.project.advancepayment_notax:
            out[p] = self.project.advancepayment_notax
        return out

    def _compute_devolucion_retenciones(self, imss: list[Decimal], otras: list[Decimal]) -> list[Decimal]:
        out = [ZERO] * self.N
        if self.settings.retentionreturnperiod is None:
            return out
        p = self.settings.retentionreturnperiod - 1
        if 0 <= p < self.N:
            out[p] = -sum(imss) - sum(otras)
        return out

    def _compute_saldo_anticipo(self, anticipo_amortizado: list[Decimal]) -> list[Decimal]:
        out = []
        acc = ZERO
        for x in anticipo_amortizado:
            acc += x
            out.append(acc)
        return out


@dataclass
class _InlineRule:
    sequence: int
    percent: Decimal
    lagperiods: int
