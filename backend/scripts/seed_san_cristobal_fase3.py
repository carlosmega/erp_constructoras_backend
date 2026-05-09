"""Fase 3 — Importar Desglose de Costo Directo Unitario (CDU) a EST-2026-009.

Lee la hoja 'Desglose de C.D.U.' del Excel y crea filas UnitCostBreakdown por
cada BudgetConcept, descomponiendo el costo directo en 7 categorías.

Estructura del Excel:
  - Bloques de 43 filas, uno por concepto, comenzando en la fila 11.
  - Total: 501 bloques (códigos A1-A100, B1-B100, ..., E1-E100). 118 reales,
    el resto son slots placeholder con D='-'.
  - Layout dentro de un bloque (offsets relativos al header del bloque):
       +0   header: C=código, D=descripción, E=unidad, J=cantidad, K=importe
       +1   "MATERIALES"   (header de sección)
       +2..+11   10 slots de materiales
       +12  "ACARREOS"
       +13..+16  4 slots de acarreos
       +17  "MAQUINARIA"
       +18..+23  6 slots de maquinaria
       +24  "MANO DE OBRA"
       +25..+31  7 slots de mano de obra
       +32  "SUBCONTRATOS"
       +33..+37  5 slots de subcontratos
       +38  "HERRAMIENTA MENOR"  (línea única, % de M.O.)
       +39  "EPP"                (línea única, % de M.O.)
       +40  (vacío)
       +41  "TOTAL" (col F = "TOTAL", col I = total)
       +42  (vacío)
  - Columnas de detalle: D=descripción, E=unidad, F=cantidad, G=costo unitario,
    H=rendimiento, I=importe (= F × G × H, salvo H.M./EPP que son F × subtotal).
"""
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    BudgetConcept,
    UnitCostBreakdown,
    BreakdownCategoryCode,
)
from apps.proyeccion.services import ConceptCatalogService
from apps.users.models import SystemUser

EXCEL_PATH = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
SHEET_INDEX = 3  # 'Desglose de C.D.U.'
ESTIMATION_NUMBER = 'EST-2026-009'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# Layout de un bloque CDU (offsets relativos al row del header).
# (categorycode, header_offset, first_detail_offset, last_detail_offset)
CATEGORY_RANGES = [
    (BreakdownCategoryCode.MATERIALS,    1,   2, 11),
    (BreakdownCategoryCode.HAULING,      12, 13, 16),
    (BreakdownCategoryCode.MACHINERY,    17, 18, 23),
    (BreakdownCategoryCode.LABOR,        24, 25, 31),
    (BreakdownCategoryCode.SUBCONTRACTS, 32, 33, 37),
    (BreakdownCategoryCode.MINOR_TOOLS,  38, 38, 38),  # single line
    (BreakdownCategoryCode.PPE,          39, 39, 39),  # single line
]
BLOCK_SIZE = 43
FIRST_BLOCK_ROW = 11


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


def parse_breakdown_for_block(rows: dict, block_row: int) -> list[dict]:
    """Parse all 7 categories for a single concept block.

    Returns list of breakdown dicts, only including lines with non-zero amount.
    """
    breakdowns = []
    for category, _hdr_off, first_off, last_off in CATEGORY_RANGES:
        line_no = 0
        for off in range(first_off, last_off + 1):
            row = rows.get(block_row + off, {})
            description = (row.get('D') or '').strip()
            unit = (row.get('E') or '').strip()
            amount = to_decimal(row.get('I', '0'))

            # Skip empty slots: no description AND amount = 0
            if not description and amount == 0:
                continue

            # Even if amount = 0, a line with description (e.g., a structural
            # filler) is unusual — skip to keep the breakdown clean.
            if amount == 0:
                continue

            line_no += 1
            breakdowns.append({
                'categorycode': int(category),
                'linenumber': line_no,
                'description': description[:500],
                'unit': unit[:20],
                'quantity': to_decimal(row.get('F', '0')),
                'unitprice': to_decimal(row.get('G', '0')),
                'yieldvalue': to_decimal(row.get('H', '1')) or Decimal('1'),
                'amount': amount,
            })
    return breakdowns


def import_breakdowns(project: EstimationProject, rows: dict, user) -> dict:
    """Walk CDU blocks and create UnitCostBreakdown rows for matching concepts.

    Tras importar los breakdowns de cada concepto, llama a
    ConceptCatalogService.recalculate_concept para derivar directunitcost
    desde la suma de breakdowns (y cascadea utility/unitprice/totalamount
    con el indirectunitcost actual — que será 0 hasta fase 4).
    """
    db_concepts = {
        c.code: c for c in BudgetConcept.objects.filter(projectid=project)
    }
    print(f'Conceptos en DB: {len(db_concepts)}')

    stats = {
        'blocks_seen': 0,
        'blocks_skipped_no_match': 0,
        'concepts_imported': 0,
        'concepts_no_detail': 0,
        'breakdown_lines': 0,
        'concepts_recalculated': 0,
    }

    with transaction.atomic():
        block_row = FIRST_BLOCK_ROW
        recalculated_concept_ids = []
        while block_row in rows:
            stats['blocks_seen'] += 1
            row = rows[block_row]
            code = (row.get('C') or '').strip()
            desc = (row.get('D') or '').strip()

            if not code or desc == '-':
                block_row += BLOCK_SIZE
                continue

            concept = db_concepts.get(code)
            if concept is None:
                stats['blocks_skipped_no_match'] += 1
                block_row += BLOCK_SIZE
                continue

            breakdowns = parse_breakdown_for_block(rows, block_row)
            if not breakdowns:
                stats['concepts_no_detail'] += 1
                block_row += BLOCK_SIZE
                continue

            UnitCostBreakdown.objects.bulk_create([
                UnitCostBreakdown(conceptid=concept, **bd)
                for bd in breakdowns
            ])
            stats['concepts_imported'] += 1
            stats['breakdown_lines'] += len(breakdowns)
            recalculated_concept_ids.append(concept.conceptid)

            block_row += BLOCK_SIZE

        # Re-derivar directunitcost (y cascada) desde el detalle CDU.
        # utilityunitcost/unitprice/totalamount quedarán correctos para el
        # estado actual (indirectunitcost = 0); fase 4 los recalculará al
        # importar IndirectCostDetail y llamar prorate_to_concepts.
        for cid in recalculated_concept_ids:
            ConceptCatalogService.recalculate_concept(cid, user)
            stats['concepts_recalculated'] += 1

    return stats


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    if UnitCostBreakdown.objects.filter(conceptid__projectid=project).exists():
        print(f'Proyeccion {ESTIMATION_NUMBER} ya tiene UnitCostBreakdown.')
        print('Para reimportar, borra primero:')
        print(f'  UnitCostBreakdown.objects.filter(conceptid__projectid=project).delete()')
        return

    rows = read_sheet(EXCEL_PATH, SHEET_INDEX)
    stats = import_breakdowns(project, rows, user)

    print()
    print('=== Importacion fase 3 completada ===')
    print(f'  Bloques CDU vistos:               {stats["blocks_seen"]}')
    print(f'  Bloques sin match en DB (skip):   {stats["blocks_skipped_no_match"]}')
    print(f'  Conceptos sin detalle (todo 0):   {stats["concepts_no_detail"]}')
    print(f'  Conceptos con desglose importado: {stats["concepts_imported"]}')
    print(f'  Lineas de desglose totales:       {stats["breakdown_lines"]}')
    print(f'  Conceptos recalculados (cascada): {stats["concepts_recalculated"]}')


if __name__ == '__main__':
    run()
