"""Verifica el estado tras fases 2+3: derivados deben venir del detalle CDU."""
from decimal import Decimal
from apps.proyeccion.models import (
    EstimationProject, BudgetConcept, UnitCostBreakdown,
)

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')
profit = project.profitpercent

print(f'Proyecto: {project.estimationnumber} ({project.name})')
print(f'profitpercent: {profit}%')
print()
print('=== Conceptos con desglose CDU (estado tras fase 3, sin fase 4) ===')
print('Esperado: directunitcost = SUM(breakdowns), indirectunitcost = 0,')
print('          utility = direct * profit / 100, unitprice = direct + utility,')
print('          totalamount = unitprice * quantity')
print()

concepts = BudgetConcept.objects.filter(
    projectid=project, breakdowns__isnull=False,
).distinct().order_by('subfamilyid__familyid__sortorder', 'subfamilyid__sortorder', 'sequencenumber')

errors = 0
for c in concepts:
    bd_sum = UnitCostBreakdown.objects.filter(conceptid=c).values('amount')
    direct_from_detail = sum((Decimal(str(b['amount'])) for b in bd_sum), Decimal('0'))

    expected_utility = (c.directunitcost + c.indirectunitcost) * profit / Decimal('100')
    expected_unitprice = c.directunitcost + c.indirectunitcost + c.utilityunitcost
    expected_total = c.unitprice * c.quantity

    # Tolerancia: 0.01 absoluto o 0.01% relativo (lo que sea mayor) para
    # absorber redondeos de cascada (campos almacenan 2-4 decimales).
    def tol(expected):
        return max(Decimal('0.01'), abs(expected) * Decimal('0.0001'))
    direct_ok = abs(c.directunitcost - direct_from_detail) <= tol(direct_from_detail)
    indirect_ok = c.indirectunitcost == 0
    utility_ok = abs(c.utilityunitcost - expected_utility) <= tol(expected_utility)
    unitprice_ok = abs(c.unitprice - expected_unitprice) <= tol(expected_unitprice)
    total_ok = abs(c.totalamount - expected_total) <= tol(expected_total)

    all_ok = direct_ok and indirect_ok and utility_ok and unitprice_ok and total_ok
    if not all_ok:
        errors += 1

    flag = 'OK' if all_ok else 'ERR'
    print(f'  [{flag}] {c.code:6s}  '
          f'CD=${c.directunitcost:>10,.4f}  '
          f'CI=${c.indirectunitcost:>8,.4f}  '
          f'U=${c.utilityunitcost:>9,.4f}  '
          f'PU=${c.unitprice:>10,.4f}  '
          f'qty={c.quantity:>10,.2f}  '
          f'total=${c.totalamount:>14,.2f}')

print()
print(f'Conceptos con desglose: {len(concepts)}')
print(f'Errores: {errors}')

# Conceptos sin desglose: deben tener todos los campos en 0
no_bd = BudgetConcept.objects.filter(projectid=project, breakdowns__isnull=True).distinct()
print()
print(f'=== Conceptos sin desglose CDU: {no_bd.count()} ===')
print('Esperado: todos los costos derivados en 0.')
non_zero = no_bd.exclude(
    directunitcost=0, indirectunitcost=0, utilityunitcost=0,
    unitprice=0, totalamount=0,
)
print(f'Conceptos con algún derivado != 0: {non_zero.count()} (debe ser 0)')
