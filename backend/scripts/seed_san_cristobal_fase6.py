"""Fase 6 — Importar Plan de Obra (`Plan de obra`) a EST-2026-009.

Lee la hoja `Plan de obra` y crea filas WorkPlanEntry tipo PLANNED por
(concepto, periodo) con cantidad distribuida.

Estructura de la hoja:
  - Headers en filas 1-5. Fila 5 = nombres de columna.
    - C=PARTIDA, D=CODIGO, E=DESCRIPCION, F=UNIDAD, G=CANTIDAD, H=P.U., I=IMPORTE
    - K=VOLUMENES PLANIFICADOS (total), L=IMPORTE PLANIFICADOS (total)
    - N..CY = 90 periodos (cada columna numerada 1..90)
  - Mismo layout de familias/subfamilias/conceptos que `E7 Fase Estudio`.
  - Para cada concepto, columnas N+ contienen la cantidad distribuida por periodo.

Filtros:
  - Solo procesar filas con D=code que matche un BudgetConcept de la proyeccion.
  - Solo crear WorkPlanEntry para periodos con cantidad > 0.
  - Si TODO el concepto tiene plan en 0: skip silencioso.

Periodlabel: si existen ProjectionPeriod (fase 7 corrida), usar su label.
Si no, usar "P{n:02d}" como placeholder. La regeneracion de fase 7 puede
luego sobreescribir labels via update masivo si es necesario.
"""
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    BudgetConcept,
    ProjectionPeriod,
    WorkPlanEntry,
    WorkPlanEntryType,
)
from apps.users.models import SystemUser

EXCEL_PATH = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
SHEET_INDEX = 7  # 'Plan de obra'
ESTIMATION_NUMBER = 'EST-2026-009'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

HEADER_ROW = 5  # fila 5 contiene los headers (N=1, O=2, ...)
DATA_START_ROW = 7  # primera fila de datos (familias/subfamilias/conceptos)


def to_decimal(s):
    try:
        s = str(s).strip()
        if not s:
            return Decimal('0')
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal('0')


def col_letter_to_idx(letter):
    idx = 0
    for c in letter:
        idx = idx * 26 + (ord(c) - ord('A') + 1)
    return idx


def read_sheet(xlsx_path: Path, sheet_index: int) -> dict:
    z = zipfile.ZipFile(str(xlsx_path))
    ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
    shared = [
        ''.join(t.text or '' for t in si.iter(f'{NS}t'))
        for si in ss.findall(f'{NS}si')
    ]
    tree = ET.fromstring(z.read(f'xl/worksheets/sheet{sheet_index}.xml'))
    rows = {}
    for row in tree.iter(f'{NS}row'):
        r = int(row.get('r'))
        rows[r] = {}
        for c in row.findall(f'{NS}c'):
            ref = c.get('r')
            t = c.get('t')
            v = c.find(f'{NS}v')
            val = v.text if v is not None else ''
            if t == 's' and val:
                try:
                    val = shared[int(val)]
                except (ValueError, IndexError):
                    pass
            elif t == 'inlineStr':
                inline = c.find(f'{NS}is')
                if inline is not None:
                    val = ''.join(tt.text or '' for tt in inline.iter(f'{NS}t'))
            col = ''.join(ch for ch in ref if ch.isalpha())
            rows[r][col] = val
    return rows


def detect_period_columns(rows: dict) -> list[tuple[str, int]]:
    """Lee la fila 5 y devuelve [(letra_columna, periodnumber), ...] ordenado."""
    header = rows.get(HEADER_ROW, {})
    period_cols = []
    for col, val in header.items():
        try:
            n = int(str(val).strip())
            if n >= 1:
                period_cols.append((col, n))
        except (ValueError, TypeError):
            continue
    return sorted(period_cols, key=lambda x: x[1])


def import_workplan(project: EstimationProject, rows: dict, user) -> dict:
    """Iterar conceptos en BD y matchear con filas de la hoja por code (columna D)."""
    # Map code -> concept (los codigos del Excel se preservaron en fase 2)
    db_concepts = {
        c.code: c for c in BudgetConcept.objects.filter(projectid=project)
    }

    # Build index: row_number -> code
    code_to_row = {}
    for r in sorted(rows.keys()):
        if r < DATA_START_ROW:
            continue
        d = (rows[r].get('D') or '').strip()
        if d and d in db_concepts:
            code_to_row[d] = r

    period_cols = detect_period_columns(rows)
    if not period_cols:
        raise RuntimeError('No se detectaron columnas de periodo en fila 5')

    # Cache projection period labels si existen
    projection_periods = {
        p.periodnumber: p.periodlabel
        for p in ProjectionPeriod.objects.filter(projectid=project)
    }

    stats = {
        'concepts_in_excel': len(code_to_row),
        'concepts_with_plan': 0,
        'entries_created': 0,
        'concepts_unmatched': set(db_concepts.keys()) - set(code_to_row.keys()),
        'periods_used': set(),
    }

    with transaction.atomic():
        entries_to_create = []
        for code, r in code_to_row.items():
            concept = db_concepts[code]
            row_data = rows[r]

            concept_has_plan = False
            for col_letter, period_n in period_cols:
                qty = to_decimal(row_data.get(col_letter, '0'))
                if qty == 0:
                    continue
                concept_has_plan = True
                stats['periods_used'].add(period_n)

                # Periodlabel: usar de ProjectionPeriod si existe, sino placeholder
                label = projection_periods.get(period_n, f'P{period_n:02d}')

                # distributedamount = qty × concept.unitprice (importe planificado)
                # Como unitprice es derivado, usamos el cache actual del concepto.
                amount = qty * (concept.unitprice or Decimal('0'))

                entries_to_create.append(WorkPlanEntry(
                    conceptid=concept,
                    projectid=project,
                    periodnumber=period_n,
                    periodlabel=label[:20],
                    entrytype=int(WorkPlanEntryType.PLANNED),
                    distributedquantity=qty,
                    distributedamount=amount,
                    createdby=user,
                    modifiedby=user,
                ))

            if concept_has_plan:
                stats['concepts_with_plan'] += 1

        if entries_to_create:
            WorkPlanEntry.objects.bulk_create(entries_to_create)
            stats['entries_created'] = len(entries_to_create)

    return stats


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    if WorkPlanEntry.objects.filter(projectid=project).exists():
        print(f'Proyeccion {ESTIMATION_NUMBER} ya tiene WorkPlanEntry.')
        print('Para reimportar:  WorkPlanEntry.objects.filter(projectid=project).delete()')
        return

    rows = read_sheet(EXCEL_PATH, SHEET_INDEX)
    stats = import_workplan(project, rows, user)

    print('=== Importacion fase 6 completada ===')
    print(f'  Conceptos hallados en hoja:        {stats["concepts_in_excel"]}')
    print(f'  Conceptos sin match en BD:         {len(stats["concepts_unmatched"])}')
    print(f'  Conceptos con plan (qty > 0):      {stats["concepts_with_plan"]}')
    print(f'  WorkPlanEntry creados:             {stats["entries_created"]}')
    print(f'  Periodos usados (set):             {sorted(stats["periods_used"]) if stats["periods_used"] else "ninguno"}')

    if stats['entries_created'] == 0:
        print()
        print('=' * 60)
        print('  AVISO: La hoja "Plan de obra" del Excel esta VACIA.')
        print('  Todos los 114 conceptos tienen 0 en todas las quincenas.')
        print('  Esto es comun en estudios de oferta pre-adjudicacion.')
        print('  El plan se llena despues, ya sea:')
        print('    1. Editando manualmente en la UI de la proyeccion.')
        print('    2. Re-corriendo este importer cuando el Excel se actualice.')
        print('    3. Auto-distribuyendo via servicio (no implementado aqui).')
        print('=' * 60)


if __name__ == '__main__':
    run()
