"""Audit del estado tras fase 4: indirectos prorrateados, cascada completa."""
from decimal import Decimal
from apps.proyeccion.models import (
    EstimationProject, BudgetConcept, IndirectCostDetail,
)
from apps.proyeccion.services import IndirectCostDetailService

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')

# 1) Total indirect
total_indirect = IndirectCostDetailService.get_total(project.estimationprojectid, None)
print(f'Total indirecto en BD: ${total_indirect:,.2f}')
print(f'Esperado del Excel:    $3,331,744.00')
print()

# 2) Concepts con direct cost > 0
concepts = BudgetConcept.objects.filter(projectid=project, directunitcost__gt=0).order_by('subfamilyid__familyid__sortorder', 'subfamilyid__sortorder', 'sequencenumber')

print(f'=== Cascada en {concepts.count()} conceptos con direct cost > 0 ===')
sum_direct_total = Decimal('0')
sum_indirect_share = Decimal('0')
sum_total = Decimal('0')

for c in concepts:
    direct_total = c.directunitcost * c.quantity
    indirect_share = c.indirectunitcost * c.quantity
    sum_direct_total += direct_total
    sum_indirect_share += indirect_share
    sum_total += c.totalamount
    print(f'  {c.code:6s}  '
          f'CD=${c.directunitcost:>10,.4f}  '
          f'CI=${c.indirectunitcost:>10,.4f}  '
          f'U=${c.utilityunitcost:>10,.4f}  '
          f'PU=${c.unitprice:>10,.4f}  '
          f'qty={c.quantity:>10,.2f}  '
          f'imp=${c.totalamount:>14,.2f}')

print()
print(f'Suma direct (qty x direct):   ${sum_direct_total:>14,.2f}')
print(f'Suma indirect (qty x indir):  ${sum_indirect_share:>14,.2f}  (deberia = $3,331,744)')
print(f'Suma totalamount (venta):     ${sum_total:>14,.2f}')

# 3) Compare with Excel "Venta" = $24,044,602.34 (Hoja Cierre R48)
print()
print('=== Comparacion con Excel ===')
print(f'  CD Excel R40:           $17,576,605.87')
print(f'  CD BD:                  ${sum_direct_total:>14,.2f}')
print(f'  CI Excel R42:           $ 3,331,744.00')
print(f'  CI BD:                  ${sum_indirect_share:>14,.2f}')
print(f'  Venta neta Excel R48:   $24,044,602.34')
print(f'  Venta neta BD (sum PU x qty): ${sum_total:>14,.2f}')
