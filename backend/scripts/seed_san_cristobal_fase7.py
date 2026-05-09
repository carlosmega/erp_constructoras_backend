"""Fase 7 — Distribucion Temporal: generar ProjectionPeriod del proyecto.

La hoja `Dist. Temporal` del Excel es una matriz subfamilia x periodo (90 cols).
Granularidad incompatible con CostDistribution (1 fila por linea-de-costo x periodo).
Ademas en este Excel piloto la matriz esta VACIA (analogo a Plan de Obra).

Por lo tanto fase 7 hace solo lo que SI tiene sentido:
  1. Generar ProjectionPeriod via PeriodService.regenerate_projection_periods.
     (Derivado de project.estimatedstartdate + estimatedenddate + periodtype).
  2. NO importar CostDistribution.
  3. Reportar al usuario que puede usar `CostDistributionService.autofill`
     o llenar manualmente desde la UI.

Cuando aparezca un Excel con distribucion poblada:
  - El parser debera leer 2 secciones (Facturacion + Costos por subfamilia).
  - Convertir importe-por-subfamilia a fracciones-por-linea (proporcional al peso de cada linea
    en su subfamilia) — esto NO es trivial y requiere logica de auto-distribution
    similar a CostDistributionService.autofill(strategy='proportional_workplan').
"""
from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    ProjectionPeriod,
    CostDistribution,
)
from apps.proyeccion.services import PeriodService

ESTIMATION_NUMBER = 'EST-2026-009'


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)

    # Idempotencia: si ya hay periodos, mostrar y salir
    existing = ProjectionPeriod.objects.filter(projectid=project).count()
    if existing > 0:
        print(f'Proyeccion {ESTIMATION_NUMBER} ya tiene {existing} ProjectionPeriod.')
        for p in ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'):
            print(f'  P{p.periodnumber:02d}  {p.periodlabel:15s}  {p.startdate} a {p.enddate}')
        print()
        print('Para regenerar (DESTRUCTIVO si hay edits manuales en CostDistribution):')
        print('  PeriodService.regenerate_projection_periods(project, confirm=True)')
        return

    # Verificar fechas
    if not project.estimatedstartdate or not project.estimatedenddate:
        print('ERROR: el proyecto no tiene estimatedstartdate o estimatedenddate.')
        print(f'  estimatedstartdate: {project.estimatedstartdate}')
        print(f'  estimatedenddate:   {project.estimatedenddate}')
        print('  durationmonths:     {project.durationmonths}')
        print('  periodtype:         {project.periodtype}')
        return

    # Generar periodos
    print(f'Generando ProjectionPeriod para {ESTIMATION_NUMBER}:')
    print(f'  start = {project.estimatedstartdate}')
    print(f'  end   = {project.estimatedenddate}')
    print(f'  type  = {project.periodtype} ({"Semanal" if project.periodtype == 0 else "Quincenal"})')
    print()

    PeriodService.regenerate_projection_periods(project, confirm=False)

    periods = list(ProjectionPeriod.objects.filter(projectid=project).order_by('periodnumber'))
    print(f'Generados {len(periods)} periodos:')
    for p in periods:
        print(f'  P{p.periodnumber:02d}  {p.periodlabel:15s}  {p.startdate} a {p.enddate}')

    # Verificar si hay CostDistribution poblada
    cd_count = CostDistribution.objects.filter(projectid=project).count()
    print()
    print(f'CostDistribution rows: {cd_count}')

    print()
    print('=' * 60)
    print('  AVISO: La hoja "Dist. Temporal" del Excel esta VACIA.')
    print('  La distribucion de costos por periodo NO se importo.')
    print('  Opciones para llenarla:')
    print('    1. Editar manualmente en la UI (tab Distribucion Temporal).')
    print('    2. Auto-distribuir via service:')
    print('       CostDistributionService.autofill(')
    print('           project, strategy="proportional_workplan", scope="all",')
    print('           only_empty=True, user=user,')
    print('       )')
    print('       (requiere WorkPlanEntry poblado — que tambien esta vacio en este Excel)')
    print('    3. Auto-distribuir uniforme:')
    print('       CostDistributionService.autofill(')
    print('           project, strategy="uniform", scope="all",')
    print('           only_empty=True, user=user,')
    print('       )')
    print('=' * 60)


if __name__ == '__main__':
    run()
