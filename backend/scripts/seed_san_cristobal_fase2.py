"""Fase 2 — Importar conceptos del Excel a la proyección 'ENTRONQUE SAN CRISTOBAL'.

Lee la hoja 'E7 Fase Estudio' del Excel y crea ConceptFamily, ConceptSubfamily
y BudgetConcept para la proyección EST-2026-009.

Estructura del Excel:
  - Header en filas 1-5
  - Fila 6: total del proyecto (skip)
  - Fila familia: columna C = letra (A,B,C,D,E), columna E = "01. NOMBRE"
  - Fila subfamilia: columna E = nombre en MAYÚSCULAS, sin D, F, G
  - Fila concepto: columna D = código (A1, A21, B1-A...), E = descripción, F = unidad
    - Cantidad (G) puede ser 0: variantes no usadas en este estudio pero presentes en catálogo.
  - Fila SECCIÓN/HEADER intra-subfamilia: columna D + E (descripción), pero SIN F ni G.
    Ejemplos: A22 "Formación y compactación, por unidad de obra terminada (...):",
              A23 "De Terraplenes adicionados con sus cuñas de sobre ancho.",
              A28 "De Terraplenes de relleno para formar la subrasante...".
    Estos NO se importan (son texto organizativo, no partidas facturables).
  - Slots vacíos: D con código (ej. "A5") pero E, F, G vacíos. NO importar.
  - Subfamilias sin conceptos reales (ej. "SUBFAMILIA 03") se ignoran
"""
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    ConceptFamily,
    ConceptSubfamily,
    BudgetConcept,
)
from apps.users.models import SystemUser

EXCEL_PATH = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
SHEET_INDEX = 2  # 'E7 Fase Estudio'
ESTIMATION_NUMBER = 'EST-2026-009'

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def to_decimal(s, default='0'):
    try:
        return Decimal(str(s).strip()) if str(s).strip() else Decimal(default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def is_num(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def read_sheet(xlsx_path: Path, sheet_index: int) -> dict:
    """Read sheet → {row_number: {col_letter: value}}."""
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


def parse_concepts_sheet(rows: dict) -> list[dict]:
    """Walk the sheet rows and produce a flat tree:
    [
      {kind: 'family',    code: '01', name: '01. TERRACERIAS', sortorder: 1},
      {kind: 'subfamily', name: 'CORTES'},
      {kind: 'concept',   code: 'A1', description: '...', unit: 'm3', quantity, ...},
      ...
    ]
    """
    result = []
    family_seq = 0

    for r in sorted(rows.keys()):
        if r < 7:  # skip headers and project total row
            continue
        rr = rows[r]
        c = (rr.get('C') or '').strip()
        d = (rr.get('D') or '').strip()
        e = (rr.get('E') or '').strip()
        f = (rr.get('F') or '').strip()
        g = (rr.get('G') or '').strip()

        # Family: column C is single letter + column E has the family label
        if c and len(c) <= 2 and c.isalpha() and e:
            family_seq += 1
            # Extract numeric prefix "01" from "01. TERRACERIAS"
            parts = e.split('.', 1)
            code = parts[0].strip() if parts and parts[0].strip().isdigit() else c
            result.append({
                'kind': 'family',
                'code': code,
                'name': e,
                'sortorder': family_seq,
            })
            continue

        # Concept: D has code AND E has description AND F has unit.
        # Quantity (G) puede ser 0: variantes no usadas en este estudio pero
        # presentes en el catálogo de partidas. Filas con D+E pero sin F son
        # encabezados de sección intra-subfamilia (ej. A22, A23, A28) — skip.
        #
        # Nota: NO importamos los campos calculados (directunitcost,
        # indirectunitcost, utilityunitcost, unitprice, totalamount).
        # Esos se derivan de las hojas CDU (fase 3) y Costo Indirecto (fase 4)
        # vía BudgetConceptService.recalculate_concept y prorate_to_concepts.
        if d and e and f:
            result.append({
                'kind': 'concept',
                'code': d,
                'description': e,
                'unit': f,
                'quantity': to_decimal(g),
                'clientunitprice': to_decimal(rr.get('R', '0')),  # P.U. CONOCIDO (input del cliente)
            })
            continue

        # Subfamily: D empty, E has UPPERCASE name, F empty, G empty
        if (not d) and e and (not f) and (not g) and e.isupper():
            result.append({
                'kind': 'subfamily',
                'name': e,
            })
            continue

    return result


def import_concepts(project: EstimationProject, parsed: list[dict], user) -> dict:
    """Materialize parsed nodes into ConceptFamily/Subfamily/BudgetConcept rows.

    Empty subfamilies (no concepts under them) are skipped.
    Concept codes from the Excel are preserved (e.g., A1, A21, B1-A).
    """
    created = {'families': 0, 'subfamilies': 0, 'concepts': 0, 'skipped_subfamilies': 0}

    current_family = None
    current_subfamily = None
    pending_subfamily = None  # name + sortorder, materialized only when first concept arrives
    subfamily_seq_in_family = 0
    concept_seq_in_subfamily = 0

    with transaction.atomic():
        for node in parsed:
            if node['kind'] == 'family':
                current_family = ConceptFamily.objects.create(
                    projectid=project,
                    name=node['name'],
                    code=node['code'],
                    sortorder=node['sortorder'] * 10,
                    createdby=user,
                    modifiedby=user,
                )
                created['families'] += 1
                current_subfamily = None
                pending_subfamily = None
                subfamily_seq_in_family = 0

            elif node['kind'] == 'subfamily':
                if pending_subfamily is not None and current_subfamily is None:
                    created['skipped_subfamilies'] += 1
                subfamily_seq_in_family += 1
                pending_subfamily = {
                    'name': node['name'],
                    'sortorder': subfamily_seq_in_family,
                }
                current_subfamily = None
                concept_seq_in_subfamily = 0

            elif node['kind'] == 'concept':
                if current_family is None:
                    raise RuntimeError(f"Concept {node['code']} sin familia")

                # Lazy-create subfamily once we know it has at least one real concept
                if current_subfamily is None:
                    if pending_subfamily is None:
                        # Concept without preceding subfamily — fall back to default
                        pending_subfamily = {'name': 'GENERAL', 'sortorder': 99}
                    sf_code = f"{current_family.code}.{pending_subfamily['sortorder']:02d}"
                    current_subfamily = ConceptSubfamily.objects.create(
                        projectid=project,
                        familyid=current_family,
                        name=pending_subfamily['name'],
                        code=sf_code,
                        sortorder=pending_subfamily['sortorder'] * 10,
                        createdby=user,
                        modifiedby=user,
                    )
                    created['subfamilies'] += 1
                    concept_seq_in_subfamily = 0

                concept_seq_in_subfamily += 1
                BudgetConcept.objects.create(
                    projectid=project,
                    subfamilyid=current_subfamily,
                    code=node['code'],
                    sequencenumber=concept_seq_in_subfamily,
                    description=node['description'][:500],
                    unit=node['unit'][:20],
                    quantity=node['quantity'],
                    clientunitprice=(
                        node['clientunitprice']
                        if node['clientunitprice'] > 0 else None
                    ),
                    breakdownmethod=0,
                    isprintable=True,
                    # Campos calculados intencionalmente NO seteados aquí:
                    # directunitcost ← derivado de UnitCostBreakdown (fase 3)
                    # indirectunitcost ← derivado de IndirectCostDetail vía prorate (fase 4)
                    # utilityunitcost, unitprice, totalamount ← cascada en prorate_to_concepts
                    createdby=user,
                    modifiedby=user,
                )
                created['concepts'] += 1

        # Final pending subfamily that never got a concept
        if pending_subfamily is not None and current_subfamily is None:
            created['skipped_subfamilies'] += 1

    return created


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    # Idempotency: bail out if the project already has concepts
    if BudgetConcept.objects.filter(projectid=project).exists():
        print(f"Proyeccion {ESTIMATION_NUMBER} ya tiene conceptos. Abortando.")
        print("Si querés reimportar, borra primero las familias:")
        print(f"  ConceptFamily.objects.filter(projectid='{project.estimationprojectid}').delete()")
        return

    rows = read_sheet(EXCEL_PATH, SHEET_INDEX)
    parsed = parse_concepts_sheet(rows)

    families = sum(1 for n in parsed if n['kind'] == 'family')
    subfamilies = sum(1 for n in parsed if n['kind'] == 'subfamily')
    concepts = sum(1 for n in parsed if n['kind'] == 'concept')
    print(f"Parseado: {families} familias, {subfamilies} subfamilias, {concepts} conceptos")

    stats = import_concepts(project, parsed, user)

    print()
    print("=== Importación fase 2 completada ===")
    print(f"  Proyeccion:              {project.estimationnumber} - {project.name}")
    print(f"  Familias creadas:        {stats['families']}")
    print(f"  Subfamilias creadas:     {stats['subfamilies']}")
    print(f"  Subfamilias vacias (skip): {stats['skipped_subfamilies']}")
    print(f"  Conceptos creados:       {stats['concepts']}")
    print()

    # Resumen por familia
    print("Resumen por familia:")
    for fam in ConceptFamily.objects.filter(projectid=project).order_by('sortorder'):
        c_count = BudgetConcept.objects.filter(
            projectid=project, subfamilyid__familyid=fam
        ).count()
        sf_count = ConceptSubfamily.objects.filter(
            projectid=project, familyid=fam
        ).count()
        total = sum(
            (c.totalamount for c in BudgetConcept.objects.filter(
                projectid=project, subfamilyid__familyid=fam
            )),
            Decimal('0'),
        )
        print(f"  [{fam.code}] {fam.name[:40]:40s}  {sf_count} sf, {c_count:3d} conc, ${total:>15,.2f}")


if __name__ == '__main__':
    run()
