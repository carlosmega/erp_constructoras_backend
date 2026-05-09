"""Cuenta insumos unicos en UnitCostBreakdown para EST-2026-009 vs Excel Explosion."""
from collections import Counter
from apps.proyeccion.models import (
    EstimationProject, UnitCostBreakdown, BreakdownCategoryCode,
)

CATEGORY_LABELS = {
    1: 'MATERIALES', 2: 'ACARREOS', 3: 'MAQUINARIA',
    4: 'MANO DE OBRA', 5: 'SUBCONTRATOS', 6: 'HM', 7: 'EPP',
}

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')

bds = UnitCostBreakdown.objects.filter(conceptid__projectid=project)

# Group unique by (description.upper(), unit.upper(), categorycode)
unique_keys = Counter()
for bd in bds:
    key = (bd.description.strip().upper(), bd.unit.strip().upper(), bd.categorycode)
    unique_keys[key] += 1

# By category
by_cat = Counter()
for (desc, unit, cat), n in unique_keys.items():
    by_cat[cat] += 1

print(f'Total UnitCostBreakdown rows: {bds.count()}')
print(f'Unique (description, unit, category): {len(unique_keys)}')
print()
print('=== Por categoria ===')
for cat in sorted(by_cat.keys()):
    label = CATEGORY_LABELS.get(cat, f'cat{cat}')
    print(f'  {cat}  {label:15s}  {by_cat[cat]:3d} unicos')

# Excluyendo HM/EPP (no son insumos reales)
real = sum(n for cat, n in by_cat.items() if cat not in (6, 7))
print(f'\n  Insumos reales (sin HM/EPP):  {real}')
print(f'  Excel "Explosion de Insumos": 47')
