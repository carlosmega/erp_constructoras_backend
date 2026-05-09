"""Reset concepts/subfamilies/families for EST-2026-009 to allow re-import.

Borra en cascada: ConceptFamily → ConceptSubfamily → BudgetConcept → UnitCostBreakdown.
"""
from apps.proyeccion.models import (
    EstimationProject, ConceptFamily, ConceptSubfamily, BudgetConcept,
    UnitCostBreakdown,
)

project = EstimationProject.objects.get(estimationnumber='EST-2026-009')
n_breakdown = UnitCostBreakdown.objects.filter(conceptid__projectid=project).count()
n_concepts = BudgetConcept.objects.filter(projectid=project).count()
n_sub = ConceptSubfamily.objects.filter(projectid=project).count()
n_fam = ConceptFamily.objects.filter(projectid=project).count()
print(f'Antes:   {n_fam} fam, {n_sub} sub, {n_concepts} conc, {n_breakdown} breakdowns')
ConceptFamily.objects.filter(projectid=project).delete()
print('Borrado completo (cascade)')
print(f'Despues: '
      f'{ConceptFamily.objects.filter(projectid=project).count()} fam, '
      f'{ConceptSubfamily.objects.filter(projectid=project).count()} sub, '
      f'{BudgetConcept.objects.filter(projectid=project).count()} conc, '
      f'{UnitCostBreakdown.objects.filter(conceptid__projectid=project).count()} breakdowns')
