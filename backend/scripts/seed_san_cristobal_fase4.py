"""Fase 4 — Importar Costos Indirectos (C1-C8) a EST-2026-009.

Lee la hoja 'Costo Indirecto' del Excel y crea filas IndirectCostDetail.
Después llama IndirectCostDetailService.prorate_to_concepts para que cada
BudgetConcept reciba su indirectunitcost proporcional al direct cost,
y cascadea utility/unitprice/totalamount.

Estructura de la hoja:
  - Headers: filas 1-8. R8 = nombres de columna.
  - R9: total general del proyecto ($3,331,744)
  - Filas categoria (R11=C1, R52=C2, R63=C3, R71=C4, R82=C5, R91=C6, R116=C7, R132=C8):
      C='Cn', D=nombre categoria, I=total categoria
  - Filas sub-area (solo en C1): D='PERSONAL OFICINA CENTRAL'/'OFICINA TECNICA'/etc.
      Sin B/C/F/G/H/I — puro texto organizativo.
  - Filas detalle: B=#, A=imputationcode (AC1/AC4/AC6, opcional),
      D=area/role, E=descripcion, F=monthlycost, G=units, H=months, I=amount.

Filtros:
  - Skip lineas con I=0 (ranura definida pero no usada).
  - Skip filas sub-area (solo D, sin B/F/I).
  - Skip categoria C5 entera si total=0 (toda implantacion no aplica).

Mapeo a IndirectCostDetail:
  - categorycode = 'C1'..'C8'
  - linenumber = secuencial dentro de categoria
  - imputationcode = columna A (asset/amortizacion code)
  - area = nombre del sub-area actual (track al recorrer)
  - description = columna E (o D si E vacia)
  - monthlycost, units, months, amount = F, G, H, I
"""
import re
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    IndirectCostDetail,
)
from apps.proyeccion.services import IndirectCostDetailService
from apps.users.models import SystemUser

EXCEL_PATH = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
SHEET_INDEX = 4  # 'Costo Indirecto'
ESTIMATION_NUMBER = 'EST-2026-009'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

CATEGORY_RE = re.compile(r'^C[1-8]$')


def to_decimal(s, default='0'):
    try:
        return Decimal(str(s).strip()) if str(s).strip() else Decimal(default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


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


def parse_indirect_sheet(rows: dict) -> list[dict]:
    """Walk the sheet rows and produce a flat list of indirect cost detail nodes.

    Returns dicts with keys:
      categorycode, linenumber, imputationcode, area, description,
      monthlycost, units, months, amount.
    """
    result = []
    current_category = None         # 'C1'..'C8'
    current_category_name = None
    current_area = None             # sub-area within category (PERSONAL OFICINA CENTRAL, etc.)
    line_no = 0

    # Detail rows start at row 11 (after headers + project total)
    for r in sorted(rows.keys()):
        if r < 11:
            continue
        rr = rows[r]
        a = (rr.get('A') or '').strip()
        b = (rr.get('B') or '').strip()
        c = (rr.get('C') or '').strip()
        d = (rr.get('D') or '').strip()
        e = (rr.get('E') or '').strip()
        f = (rr.get('F') or '').strip()
        g = (rr.get('G') or '').strip()
        h = (rr.get('H') or '').strip()
        i = (rr.get('I') or '').strip()

        # Category header row: C='C1'..'C8'
        if c and CATEGORY_RE.match(c):
            current_category = c
            current_category_name = d
            current_area = None
            line_no = 0
            continue

        if current_category is None:
            continue

        # Detail line: B + F (line# + monthly cost). Skip if amount = 0.
        if b and f:
            amount = to_decimal(i)
            if amount == 0:
                # Defined slot but not used in this study — skip
                continue
            line_no += 1
            result.append({
                'categorycode': current_category,
                'linenumber': line_no,
                'imputationcode': a[:10],
                'area': (current_area or current_category_name or '')[:100],
                'description': (e or d)[:500],
                'monthlycost': to_decimal(f),
                'units': to_decimal(g, '1') or Decimal('1'),
                'months': to_decimal(h, '1') or Decimal('1'),
                'amount': amount,
            })
            continue

        # Sub-area header: D set, no B/C/F/I
        if d and not b and not f and not i:
            current_area = d
            continue

    return result


def import_indirects(project: EstimationProject, parsed: list[dict], user) -> dict:
    """Bulk-create IndirectCostDetail rows; then prorate to concepts."""
    stats = {
        'lines_created': 0,
        'by_category': {},
        'total_indirect': Decimal('0'),
        'concepts_updated': 0,
    }

    with transaction.atomic():
        objs = []
        for node in parsed:
            objs.append(IndirectCostDetail(
                projectid=project,
                createdby=user,
                modifiedby=user,
                **node,
            ))
            stats['by_category'].setdefault(node['categorycode'], 0)
            stats['by_category'][node['categorycode']] += 1
            stats['total_indirect'] += node['amount']

        IndirectCostDetail.objects.bulk_create(objs)
        stats['lines_created'] = len(objs)

        # Cascada: derivar indirectunitcost por concepto + utility/unitprice/totalamount.
        updated = IndirectCostDetailService.prorate_to_concepts(
            project.estimationprojectid, user,
        )
        stats['concepts_updated'] = len(updated)

    return stats


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    if IndirectCostDetail.objects.filter(projectid=project).exists():
        print(f'Proyeccion {ESTIMATION_NUMBER} ya tiene IndirectCostDetail.')
        print('Para reimportar, borra primero:')
        print(f'  IndirectCostDetail.objects.filter(projectid=project).delete()')
        return

    rows = read_sheet(EXCEL_PATH, SHEET_INDEX)
    parsed = parse_indirect_sheet(rows)

    print(f'Parseadas {len(parsed)} lineas de detalle indirecto')
    stats = import_indirects(project, parsed, user)

    print()
    print('=== Importacion fase 4 completada ===')
    print(f'  Lineas IndirectCostDetail creadas: {stats["lines_created"]}')
    print(f'  Total indirecto importado:         ${stats["total_indirect"]:,.2f}')
    print(f'  Conceptos actualizados (prorate):  {stats["concepts_updated"]}')
    print()
    print('Detalle por categoria:')
    for cat in sorted(stats['by_category'].keys()):
        cat_total = sum(
            (Decimal(str(n['amount'])) for n in parsed if n['categorycode'] == cat),
            Decimal('0'),
        )
        print(f'  {cat}: {stats["by_category"][cat]:3d} lineas  ${cat_total:>14,.2f}')


if __name__ == '__main__':
    run()
