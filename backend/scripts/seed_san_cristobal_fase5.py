"""Fase 5 — Catalogo de Insumos: derivar SupplyCatalogItem desde UnitCostBreakdown
y vincular cada breakdown a su catalog item.

A diferencia de las fases 1-4, NO leemos el Excel "Explosion de Insumos" — esa
hoja es un derivado calculado por el Excel desde la hoja CDU. El servicio
`SupplyExplosionService.generate_consolidated` reproduce ese reporte
dinamicamente desde UnitCostBreakdown una vez que cada linea apunta a su
SupplyCatalogItem via `supplyid`.

Estrategia:
  1. Iterar UnitCostBreakdown del proyecto.
  2. Dedupe por clave natural: (description.strip().upper(), unit.strip().upper(),
     categorycode → supplytype).
  3. Para cada insumo unico: get_or_create SupplyCatalogItem (catalogo global,
     compartido entre proyectos). Codigo autogenerado por prefijo de tipo.
  4. Bulk-update UnitCostBreakdown.supplyid.

Categorias 6 (HERRAMIENTA MENOR) y 7 (EPP) se SKIPpean — no son insumos reales,
son porcentajes calculados sobre M.O.

Mapeo BreakdownCategoryCode → SupplyTypeCode:
  1 MATERIALS    → 0 MATERIAL    (prefix MAT)
  2 HAULING      → 4 HAULING     (prefix ACA)
  3 MACHINERY    → 2 MACHINERY   (prefix EQ)
  4 LABOR        → 1 LABOR       (prefix MO)
  5 SUBCONTRACTS → 3 SUBCONTRACT (prefix SUB)
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    UnitCostBreakdown,
    SupplyCatalogItem,
    BreakdownCategoryCode,
    SupplyTypeCode,
)
from apps.users.models import SystemUser

ESTIMATION_NUMBER = 'EST-2026-009'

# Categoria del breakdown -> tipo del insumo
CATEGORY_TO_SUPPLYTYPE = {
    int(BreakdownCategoryCode.MATERIALS):    int(SupplyTypeCode.MATERIAL),
    int(BreakdownCategoryCode.HAULING):      int(SupplyTypeCode.HAULING),
    int(BreakdownCategoryCode.MACHINERY):    int(SupplyTypeCode.MACHINERY),
    int(BreakdownCategoryCode.LABOR):        int(SupplyTypeCode.LABOR),
    int(BreakdownCategoryCode.SUBCONTRACTS): int(SupplyTypeCode.SUBCONTRACT),
    # 6 MINOR_TOOLS y 7 PPE NO mapean — se skipean
}

# Tipo de insumo -> prefijo de codigo (alineado con catalogo existente)
SUPPLYTYPE_TO_PREFIX = {
    int(SupplyTypeCode.MATERIAL):    'MAT',
    int(SupplyTypeCode.LABOR):       'MO',
    int(SupplyTypeCode.MACHINERY):   'EQ',
    int(SupplyTypeCode.SUBCONTRACT): 'SUB',
    int(SupplyTypeCode.HAULING):     'ACA',
}


def next_code_for_type(supplytype: int) -> str:
    """Generar siguiente codigo libre para un tipo (ej. MAT-0041)."""
    prefix = SUPPLYTYPE_TO_PREFIX[supplytype]
    existing = SupplyCatalogItem.objects.filter(
        code__startswith=f'{prefix}-'
    ).values_list('code', flat=True)
    max_n = 0
    for code in existing:
        try:
            n = int(code.split('-', 1)[1])
            max_n = max(max_n, n)
        except (IndexError, ValueError):
            continue
    return f'{prefix}-{max_n + 1:04d}'


def import_supplies(project: EstimationProject, user) -> dict:
    """Crear SupplyCatalogItem para cada insumo unico y vincular breakdowns."""
    bds = list(UnitCostBreakdown.objects.filter(
        conceptid__projectid=project,
        statecode=0,
    ))

    # Group por clave natural
    groups = defaultdict(list)
    skipped_hm_epp = 0
    for bd in bds:
        if bd.categorycode not in CATEGORY_TO_SUPPLYTYPE:
            skipped_hm_epp += 1
            continue
        supplytype = CATEGORY_TO_SUPPLYTYPE[bd.categorycode]
        key = (bd.description.strip().upper(), bd.unit.strip().upper(), supplytype)
        groups[key].append(bd)

    stats = {
        'unique_supplies': len(groups),
        'created': 0,
        'reused': 0,
        'breakdowns_total': len(bds),
        'breakdowns_linked': 0,
        'breakdowns_skipped_hm_epp': skipped_hm_epp,
        'by_type': defaultdict(lambda: {'created': 0, 'reused': 0}),
    }

    with transaction.atomic():
        breakdowns_to_update = []
        for (desc_key, unit_key, supplytype), bd_list in groups.items():
            # Tomar description/unit/precio del primer breakdown (representante)
            sample = bd_list[0]

            # Buscar existente por (description, unit, supplytype) case-insensitive
            existing = SupplyCatalogItem.objects.filter(
                description__iexact=sample.description.strip(),
                unit__iexact=sample.unit.strip(),
                supplytype=supplytype,
                statecode=0,
            ).first()

            if existing is None:
                code = next_code_for_type(supplytype)
                item = SupplyCatalogItem.objects.create(
                    code=code,
                    description=sample.description.strip(),
                    unit=sample.unit.strip(),
                    supplytype=supplytype,
                    referenceprice=sample.unitprice or Decimal('0'),
                    geographiczone='',
                    createdby=user,
                    modifiedby=user,
                )
                stats['created'] += 1
                stats['by_type'][supplytype]['created'] += 1
            else:
                item = existing
                stats['reused'] += 1
                stats['by_type'][supplytype]['reused'] += 1

            # Linkear todas las breakdowns que matchean
            for bd in bd_list:
                bd.supplyid = item
                breakdowns_to_update.append(bd)

        # Bulk update supplyid
        if breakdowns_to_update:
            UnitCostBreakdown.objects.bulk_update(
                breakdowns_to_update, ['supplyid']
            )
            stats['breakdowns_linked'] = len(breakdowns_to_update)

    return stats


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    # Idempotencia: verificar si ya hay supplies linkeados
    already_linked = UnitCostBreakdown.objects.filter(
        conceptid__projectid=project,
        supplyid__isnull=False,
    ).count()
    if already_linked > 0:
        print(f'Proyeccion {ESTIMATION_NUMBER} ya tiene {already_linked} breakdowns con supply linkeado.')
        print('Para reimportar, primero corre:')
        print('  UnitCostBreakdown.objects.filter(')
        print('      conceptid__projectid=project, supplyid__isnull=False,')
        print('  ).update(supplyid=None)')
        return

    stats = import_supplies(project, user)

    print('=== Importacion fase 5 completada ===')
    print(f'  Insumos unicos detectados:      {stats["unique_supplies"]}')
    print(f'  SupplyCatalogItem creados:      {stats["created"]}')
    print(f'  SupplyCatalogItem reusados:     {stats["reused"]}')
    print(f'  Breakdowns vinculados:          {stats["breakdowns_linked"]}')
    print(f'  Breakdowns HM/EPP skipped:      {stats["breakdowns_skipped_hm_epp"]}')
    print()
    type_labels = {0: 'MATERIAL', 1: 'LABOR', 2: 'MACHINERY', 3: 'SUBCONTRACT', 4: 'HAULING'}
    print('  Detalle por tipo:')
    for st, counts in sorted(stats['by_type'].items()):
        label = type_labels.get(st, f'type{st}')
        print(f'    {st} {label:12s}  creados: {counts["created"]:3d}  reusados: {counts["reused"]:3d}')


if __name__ == '__main__':
    run()
