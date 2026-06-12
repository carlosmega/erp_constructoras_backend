"""Versionamiento de estudios: snapshots JSONB inmutables del grafo completo.

Spec: docs/superpowers/specs/2026-06-12-versionamiento-estudios-design.md (monorepo raíz).
Separado de services.py a propósito (ese archivo ya supera las 10k líneas).
"""
import uuid as _uuid
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from apps.audit.services import log_action
from apps.proyeccion.models import (
    EstimationProject, ConceptFamily, ConceptSubfamily, BudgetConcept,
    UnitCostBreakdown, IndirectCostDetail, OfferAlternative,
    AlternativeCostAdjustment, EstimationFinancialSettings, EstimationBillingRule,
    WorkPlanEntry, ProjectionPeriod, CostDistribution, DistributionPresence,
    SupplyCatalogItem, EstimationVersion,
)

SCHEMA_VERSION = 1

# Adaptadores snapshot viejo -> siguiente schema_version. Se aplican en cadena
# al restaurar. Ej. futuro: {1: _adapt_v1_to_v2}
ADAPTERS: dict[int, Callable[[dict], dict]] = {}

# Grafo del estudio en orden padre -> hijo. El restore borra en orden inverso
# y recrea en este orden. Catálogos globales (SupplyCatalogItem, templates,
# price catalog) NO forman parte del snapshot. DistributionPresence es efímero.
GRAPH_SPEC = [
    ('families', ConceptFamily, lambda p: ConceptFamily.objects.filter(projectid=p)),
    ('subfamilies', ConceptSubfamily, lambda p: ConceptSubfamily.objects.filter(projectid=p)),
    ('concepts', BudgetConcept, lambda p: BudgetConcept.objects.filter(projectid=p)),
    ('breakdowns', UnitCostBreakdown, lambda p: UnitCostBreakdown.objects.filter(conceptid__projectid=p)),
    ('indirects', IndirectCostDetail, lambda p: IndirectCostDetail.objects.filter(projectid=p)),
    ('alternatives', OfferAlternative, lambda p: OfferAlternative.objects.filter(projectid=p)),
    ('alternative_adjustments', AlternativeCostAdjustment,
     lambda p: AlternativeCostAdjustment.objects.filter(alternativeid__projectid=p)),
    ('financial_settings', EstimationFinancialSettings,
     lambda p: EstimationFinancialSettings.objects.filter(projectid=p)),
    ('billing_rules', EstimationBillingRule, lambda p: EstimationBillingRule.objects.filter(projectid=p)),
    ('projection_periods', ProjectionPeriod, lambda p: ProjectionPeriod.objects.filter(projectid=p)),
    ('workplan_entries', WorkPlanEntry, lambda p: WorkPlanEntry.objects.filter(projectid=p)),
    ('cost_distributions', CostDistribution, lambda p: CostDistribution.objects.filter(projectid=p)),
]


def _jsonable(value):
    if value is None or isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, _uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, dict)):
        return value  # JSONField nativo: ya es JSON-serializable
    return str(value)


def _dump_instance(obj) -> dict:
    return {f.attname: _jsonable(getattr(obj, f.attname)) for f in obj._meta.concrete_fields}


def dump_graph(project: EstimationProject) -> dict:
    """Serializa el grafo completo del estudio (UUIDs preservados, JSON-safe)."""
    snap = {
        'schema_version': SCHEMA_VERSION,
        'project': _dump_instance(project),
    }
    for key, _model, qs_fn in GRAPH_SPEC:
        snap[key] = [_dump_instance(o) for o in qs_fn(project)]
    return snap
