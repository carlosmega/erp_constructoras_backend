"""Audit fase 5: SupplyCatalogItem creados y reproduccion de la Explosion."""
from decimal import Decimal
from apps.proyeccion.models import (
    EstimationProject, UnitCostBreakdown, SupplyCatalogItem,
)
from apps.proyeccion.services import SupplyExplosionService

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')

# 1) Cobertura de linkeo
total_bds = UnitCostBreakdown.objects.filter(conceptid__projectid=project).count()
linked = UnitCostBreakdown.objects.filter(
    conceptid__projectid=project, supplyid__isnull=False,
).count()
unlinked = total_bds - linked
unlinked_by_cat = UnitCostBreakdown.objects.filter(
    conceptid__projectid=project, supplyid__isnull=True,
).values('categorycode').distinct()

print(f'Total breakdowns:        {total_bds}')
print(f'Vinculados a supply:     {linked}')
print(f'Sin vincular:            {unlinked}')
print(f'  Categorias sin link:   {[r["categorycode"] for r in unlinked_by_cat]}')
print(f'  (esperado: 6=HM, 7=EPP)')
print()

# 2) Ejecutar el servicio de Explosion consolidada
explosion = SupplyExplosionService.generate_consolidated(
    project.estimationprojectid, None,
)
print(f'=== SupplyExplosionService.generate_consolidated ===')
print(f'Insumos en explosion: {len(explosion)}')
print()

# Total por tipo
from collections import defaultdict
by_type = defaultdict(lambda: Decimal('0'))
for item in explosion:
    by_type[item['supplytype']] += Decimal(str(item['totalamount']))

type_labels = {0: 'MATERIAL', 1: 'LABOR', 2: 'MACHINERY', 3: 'SUBCONTRACT', 4: 'HAULING'}
print('Total por tipo (BD):')
total_explosion = Decimal('0')
for st in sorted(by_type.keys()):
    label = type_labels.get(st, f'type{st}')
    print(f'  {st} {label:12s}  ${by_type[st]:>14,.2f}')
    total_explosion += by_type[st]
print(f'  TOTAL                ${total_explosion:>14,.2f}')

print()
print('Comparacion contra Excel "Explosion de Insumos":')
print(f'  Excel total (sin HM+EPP): $16,520,067 (5,032,840 + 8,883,622 + 1,474,033 + 465,478 + 664,094)')
print(f'  BD total (consolidado):   ${total_explosion:>14,.2f}')

# 3) Top 10 insumos por importe
print()
print('Top 10 insumos por importe (BD consolidada):')
sorted_items = sorted(explosion, key=lambda x: -Decimal(str(x['totalamount'])))[:10]
for item in sorted_items:
    print(f"  {item['supplycode']:10s}  {item['description'][:45]:45s}  ${item['totalamount']:>14,.2f}")
