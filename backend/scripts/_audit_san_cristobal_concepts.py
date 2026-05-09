"""Audit detallado de conceptos importados en EST-2026-009."""
from decimal import Decimal
from apps.proyeccion.models import (
    EstimationProject, ConceptFamily, ConceptSubfamily, BudgetConcept,
)

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')

for fam in ConceptFamily.objects.filter(projectid=project).order_by('sortorder'):
    print()
    print(f'=== FAMILIA [{fam.code}] {fam.name} ===')
    for sf in ConceptSubfamily.objects.filter(
        projectid=project, familyid=fam,
    ).order_by('sortorder'):
        concepts = list(BudgetConcept.objects.filter(
            projectid=project, subfamilyid=sf,
        ).order_by('sequencenumber'))
        sf_total = sum((c.totalamount for c in concepts), Decimal('0'))
        print(f'  Subfamilia [{sf.code}] {sf.name}  ({len(concepts)} conc, ${sf_total:,.2f})')
        for c in concepts:
            zero = '  (qty=0)' if c.quantity == 0 else ''
            print(f'    {c.code:6s}  {c.unit:6s}  qty={c.quantity:>15,.4f}  P.U.=${c.unitprice:>12,.4f}  imp=${c.totalamount:>14,.2f}{zero}')
            print(f'           {c.description[:90]}')
