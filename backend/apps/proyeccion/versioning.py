"""Versionamiento de estudios: snapshots JSONB inmutables del grafo completo.

Spec: docs/superpowers/specs/2026-06-12-versionamiento-estudios-design.md (monorepo raíz).
Separado de services.py a propósito (ese archivo ya supera las 10k líneas).
"""
import json
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


class EstimationVersionService:
    """Crear, listar y restaurar versiones de un estudio."""

    @staticmethod
    def _summary_from_snapshot(snap: dict) -> dict:
        """Resumen congelado calculado del MISMO snapshot (sin queries extra),
        garantizando que totales y snapshot sean consistentes entre sí.

        En el snapshot los Decimal vienen como string, los bool como bool
        nativo y los nulls como None.
        """
        chosen = next((a for a in snap['alternatives'] if a.get('ischosen')), None)
        sale = Decimal(chosen['salepricenet'] or '0') if chosen else Decimal('0')
        direct = Decimal('0')
        count = 0
        # El resumen solo cuenta filas ACTIVAS (statecode=0); el snapshot sí
        # incluye las soft-deleted por fidelidad de restauración.
        for c in snap['concepts']:
            if c['statecode'] != 0:
                continue
            direct += Decimal(c['directunitcost'] or '0') * Decimal(c['quantity'] or '0')
            count += 1
        indirect = sum(
            (Decimal(i['amount'] or '0')
             for i in snap['indirects'] if i['statecode'] == 0),
            Decimal('0'),
        )
        return {
            'saleamount': sale, 'directtotal': direct, 'indirecttotal': indirect,
            'margintotal': sale - direct - indirect, 'conceptcount': count,
        }

    @staticmethod
    @transaction.atomic
    def create_version(project, *, user, note: str = '', isauto: bool = False) -> EstimationVersion:
        # Lock del proyecto para serializar la asignación del número.
        project = EstimationProject.objects.select_for_update().get(pk=project.pk)
        nxt = (EstimationVersion.objects.filter(projectid=project)
               .aggregate(m=Max('versionnumber'))['m'] or 0) + 1
        snap = dump_graph(project)
        version = EstimationVersion.objects.create(
            projectid=project, versionnumber=nxt, note=note[:500], isauto=isauto,
            schema_version=SCHEMA_VERSION, snapshot=snap,
            createdby=user, modifiedby=user,
            **EstimationVersionService._summary_from_snapshot(snap),
        )
        log_action(
            action='create', entity='estimationversion', record_id=version.versionid,
            user=user, record_name=f'v{nxt}',
            message=f'Versión {nxt} de {project.estimationnumber}: {note}'.strip(),
        )
        return version

    @staticmethod
    def _coerce(model, data: dict) -> dict:
        """Convierte el dict del snapshot a kwargs del modelo vigente.
        Ignora attnames que ya no existen (forward-compat tras renames con adapter)."""
        valid = {f.attname: f for f in model._meta.concrete_fields}
        out = {}
        for attname, raw in data.items():
            f = valid.get(attname)
            if f is None:
                continue
            if raw is None:
                out[attname] = None
            else:
                out[attname] = f.to_python(raw)
        return out

    @staticmethod
    @transaction.atomic
    def restore_version(project, versionnumber: int, *, user) -> dict:
        project = EstimationProject.objects.select_for_update().get(pk=project.pk)
        if project.generatedprojectid_id:
            raise ValueError(
                "El estudio ya fue convertido a proyecto de obra; no se puede restaurar."
            )
        version = EstimationVersion.objects.get(projectid=project, versionnumber=versionnumber)

        snap = json.loads(json.dumps(version.snapshot))  # deep copy: los ADAPTERS pueden mutar sin tocar el original
        snap_ver = version.schema_version  # use model field, not snapshot JSON
        if snap_ver > SCHEMA_VERSION:
            raise ValueError(
                f"El snapshot tiene schema {snap_ver}, mayor al soportado ({SCHEMA_VERSION})."
            )
        while snap_ver < SCHEMA_VERSION:
            if snap_ver not in ADAPTERS:
                raise ValueError(
                    f"No existe adaptador para migrar schema {snap_ver} -> {snap_ver + 1}."
                )
            snap = ADAPTERS[snap_ver](snap)
            snap_ver += 1

        # 1) Respaldo automático del estado vigente.
        backup = EstimationVersionService.create_version(
            project, user=user, isauto=True,
            note=f"Respaldo antes de restaurar v{versionnumber}",
        )

        # 2) Borrar el grafo vigente (hijo -> padre) + presencia efímera.
        DistributionPresence.objects.filter(projectid=project).delete()
        for key, model, qs_fn in reversed(GRAPH_SPEC):
            qs_fn(project).delete()

        # 3) Recrear desde el snapshot (padre -> hijo) con los UUIDs originales.
        existing_supplies = set(SupplyCatalogItem.objects.values_list('supplyid', flat=True))
        for key, model, _qs_fn in GRAPH_SPEC:
            rows = []
            for data in snap.get(key, []):
                kwargs = EstimationVersionService._coerce(model, data)
                # Insumo de catálogo borrado después del snapshot: soltar la liga.
                if model is UnitCostBreakdown and kwargs.get('supplyid_id') is not None:
                    if kwargs['supplyid_id'] not in existing_supplies:
                        kwargs['supplyid_id'] = None
                rows.append(model(**kwargs))
            model.objects.bulk_create(rows)
            # Fidelidad de timestamps: auto_now/auto_now_add pisan los valores al
            # insertar; restaurarlos con update() (que no dispara auto_now).
            # Deuda conocida (docs/deuda/011): O(N) UPDATEs por fila — aceptable
            # porque restaurar es infrecuente, pero en estudios grandes suma ~1-2s.
            ts_fields = {f.attname for f in model._meta.concrete_fields} & {'createdon', 'modifiedon'}
            if ts_fields:
                for data in snap.get(key, []):
                    pk_field = model._meta.pk.attname
                    updates = {t: data[t] for t in ts_fields if data.get(t)}
                    if updates:
                        model.objects.filter(pk=data[pk_field]).update(**updates)

        # 4) Campos propios del proyecto (sin tocar PK ni FKs estructurales).
        proj_kwargs = EstimationVersionService._coerce(EstimationProject, snap['project'])
        # generatedprojectid_id: el guard de arriba garantiza que es None; no
        # restaurarlo desde el snapshot (podría re-ligar a un proyecto borrado).
        skip = {'estimationprojectid', 'createdon', 'createdby_id', 'generatedprojectid_id'}
        for attname, val in proj_kwargs.items():
            if attname not in skip:
                setattr(project, attname, val)
        project.modifiedby = user
        project.save()

        log_action(
            action='update', entity='estimationversion', record_id=version.versionid,
            user=user, record_name=f'v{versionnumber}',
            message=f'Estudio {project.estimationnumber} restaurado a v{versionnumber} '
                    f'(respaldo: v{backup.versionnumber})',
        )
        return {'restored': versionnumber, 'backup_versionnumber': backup.versionnumber}
