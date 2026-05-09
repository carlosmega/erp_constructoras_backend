"""Audit del desglose CDU importado para EST-2026-009."""
from decimal import Decimal
from collections import Counter
from apps.proyeccion.models import (
    EstimationProject, BudgetConcept, UnitCostBreakdown, BreakdownCategoryCode,
)

CATEGORY_LABELS = {
    1: 'MATERIALES',
    2: 'ACARREOS',
    3: 'MAQUINARIA',
    4: 'MANO DE OBRA',
    5: 'SUBCONTRATOS',
    6: 'HERRAM. MENOR',
    7: 'EPP',
}

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')

# Cuenta por categoría
by_cat = Counter()
total_amount = Decimal('0')
for bd in UnitCostBreakdown.objects.filter(conceptid__projectid=project):
    by_cat[bd.categorycode] += 1
    total_amount += bd.amount

print('=== Resumen por categoria ===')
for code, label in CATEGORY_LABELS.items():
    count = by_cat.get(code, 0)
    print(f'  {code}  {label:20s}  {count:3d} lineas')
print(f'  TOTAL                       {sum(by_cat.values()):3d} lineas')

# Detalle por concepto con desglose
print()
print('=== Conceptos con desglose ===')
concepts_with_bd = BudgetConcept.objects.filter(
    projectid=project,
    breakdowns__isnull=False,
).distinct().order_by('subfamilyid__familyid__sortorder', 'subfamilyid__sortorder', 'sequencenumber')

for c in concepts_with_bd:
    bds = list(UnitCostBreakdown.objects.filter(conceptid=c))
    total = sum((bd.amount for bd in bds), Decimal('0'))
    n_by_cat = Counter(bd.categorycode for bd in bds)
    cat_summary = '+'.join(
        f'{CATEGORY_LABELS[code][:3]}:{cnt}'
        for code, cnt in sorted(n_by_cat.items())
    )
    diff_marker = '' if abs(total - c.directunitcost) < Decimal('0.01') else f'  ⚠ diff=${abs(total - c.directunitcost):.4f}'
    print(f'  {c.code:6s}  {len(bds):2d} lineas  CDU=${total:>10,.4f}  CD=${c.directunitcost:>10,.4f}  [{cat_summary}]{diff_marker}')

# Detalle del primer concepto (A1) para ver una muestra
print()
print('=== Detalle CDU concepto A1 (Despalmes) ===')
c = BudgetConcept.objects.get(projectid=project, code='A1')
print(f'Concepto: {c.code} - {c.description[:60]}')
print(f'Costo directo: ${c.directunitcost:,.4f}/{c.unit}')
print()
for bd in UnitCostBreakdown.objects.filter(conceptid=c).order_by('categorycode', 'linenumber'):
    print(f'  [{bd.categorycode}] {CATEGORY_LABELS[bd.categorycode]:15s} L{bd.linenumber}: '
          f'{bd.description[:35]:35s}  {bd.unit:5s}  '
          f'qty={bd.quantity:>10.6f}  P.U.=${bd.unitprice:>9,.2f}  '
          f'rdto={bd.yieldvalue:>10.6f}  imp=${bd.amount:>10,.4f}')
