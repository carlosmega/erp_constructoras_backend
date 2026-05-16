"""Import a Dimovere "Estudio de Oferta" Excel into the ERP backend.

Consolidates the 8-phase pipeline from seed_san_cristobal_fase{1..8}.py into
a single parametrized script with dry-run safety.

Usage:
    python scripts/import_estudio_excel.py \\
        --xlsx <path> \\
        --owner-email <email> \\
        [--account-id <uuid>] \\
        [--phases 1-8] \\
        [--commit]

Without --commit, the script runs in dry-run mode: all phases execute within
a transaction that is rolled back at the end. Use this to validate parity
before persisting.

See docs/superpowers/specs/2026-05-15-import-estudio-prod-deploy-design.md
for the deployment workflow (backup -> staging -> dry-run -> prod).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

# ---------------------------------------------------------------------------
# Django bootstrap (must happen before any apps.* import)
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm.settings')
import django  # noqa: E402
django.setup()

from dateutil.relativedelta import relativedelta  # noqa: E402
from django.db import transaction  # noqa: E402

from apps.accounts.models import Account  # noqa: E402
from apps.proyeccion.models import (  # noqa: E402
    BreakdownCategoryCode,
    BudgetConcept,
    ConceptFamily,
    ConceptSubfamily,
    CostDistribution,
    EstimationBillingRule,
    EstimationFinancialSettings,
    EstimationProject,
    IndirectCostDetail,
    ProjectionPeriod,
    SupplyCatalogItem,
    SupplyTypeCode,
    UnitCostBreakdown,
    WorkPlanEntry,
    WorkPlanEntryType,
)
from apps.proyeccion.services import (  # noqa: E402
    ConceptCatalogService,
    EstimationProjectService,
    IndirectCostDetailService,
    PeriodService,
)
from apps.users.models import SystemUser  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
EXCEL_EPOCH = date(1899, 12, 30)
PARITY_TOLERANCE_ABS = Decimal('50.00')  # ±$50 absolute (Decimal accumulation drift)
PARITY_TOLERANCE_REL = Decimal('0.0001')  # 0.01% relative, whichever is greater

# Expected sheet names (Dimovere template). Order matters; index = position in workbook.
EXPECTED_SHEETS = [
    'Hoja Cierre Estudio',   # 1
    'E7 Fase Estudio',       # 2
    'Desglose de C.D.U.',    # 3
    'Costo Indirecto',       # 4
    'Aux. Exp de Ins',       # 5 (hidden — ignored)
    'Explosión de Insumos',  # 6 (derived — ignored)
    'Plan de obra',          # 7
    'Dist. Temporal',        # 8 (matrix ignored, only generates periods)
    'PNT',                   # 9
    'Proforma',              # 10 (derived — ignored)
    'Rdtos Medios propios',  # 11 (reference — ignored)
]

# Enum mappings (Excel label → BD value)
PROJECT_TYPE_MAP = {
    'PÚBLICO': 0, 'PUBLICO': 0,
    'PRIVADO': 1,
}
BIDDING_TYPE_MAP = {
    'LICITACIÓN PÚBLICA': 0, 'LICITACION PUBLICA': 0,
    'INVITACIÓN A 3': 1, 'INVITACION A 3': 1,
    'INVITACIÓN RESTRINGIDA': 1, 'INVITACION RESTRINGIDA': 1,
    'ADJUDICACIÓN DIRECTA': 2, 'ADJUDICACION DIRECTA': 2,
}
PERIOD_TYPE_MAP = {
    'SEMANAL': 0,
    'QUINCENAL': 1,
    'MENSUAL': 1,  # fallback: model only supports semanal/quincenal
}

# CDU layout: 7 categories per concept block, fixed offsets from block header.
CATEGORY_RANGES = [
    (BreakdownCategoryCode.MATERIALS,    1,   2, 11),
    (BreakdownCategoryCode.HAULING,      12, 13, 16),
    (BreakdownCategoryCode.MACHINERY,    17, 18, 23),
    (BreakdownCategoryCode.LABOR,        24, 25, 31),
    (BreakdownCategoryCode.SUBCONTRACTS, 32, 33, 37),
    (BreakdownCategoryCode.MINOR_TOOLS,  38, 38, 38),
    (BreakdownCategoryCode.PPE,          39, 39, 39),
]
CDU_BLOCK_SIZE = 43
CDU_FIRST_BLOCK_ROW = 11

# Indirect category regex (column C in 'Costo Indirecto' sheet)
INDIRECT_CATEGORY_RE = re.compile(r'^C[1-8]$')

# Fase 5: breakdown category → supply type → code prefix
CATEGORY_TO_SUPPLYTYPE = {
    int(BreakdownCategoryCode.MATERIALS):    int(SupplyTypeCode.MATERIAL),
    int(BreakdownCategoryCode.HAULING):      int(SupplyTypeCode.HAULING),
    int(BreakdownCategoryCode.MACHINERY):    int(SupplyTypeCode.MACHINERY),
    int(BreakdownCategoryCode.LABOR):        int(SupplyTypeCode.LABOR),
    int(BreakdownCategoryCode.SUBCONTRACTS): int(SupplyTypeCode.SUBCONTRACT),
    # MINOR_TOOLS (6) and PPE (7) intentionally not mapped — skipped.
}
SUPPLYTYPE_TO_PREFIX = {
    int(SupplyTypeCode.MATERIAL):    'MAT',
    int(SupplyTypeCode.LABOR):       'MO',
    int(SupplyTypeCode.MACHINERY):   'EQ',
    int(SupplyTypeCode.SUBCONTRACT): 'SUB',
    int(SupplyTypeCode.HAULING):     'ACA',
}

# Fase 6: workplan sheet layout
WORKPLAN_HEADER_ROW = 5
WORKPLAN_DATA_START_ROW = 7


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def to_decimal(s, default='0') -> Decimal:
    try:
        s = str(s).strip()
        return Decimal(s) if s else Decimal(default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def to_int(s, default=0) -> int:
    try:
        return int(float(str(s).strip())) if str(s).strip() else default
    except (ValueError, TypeError):
        return default


def normalize_label(s: str) -> str:
    """Upper + sin acentos para matching robusto contra labels del Excel."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').upper()


def excel_serial_to_date(serial) -> Optional[date]:
    n = to_int(serial)
    if n <= 0:
        return None
    return EXCEL_EPOCH + timedelta(days=n)


def list_sheets(xlsx_path: Path) -> list[str]:
    """Lista nombres de hojas vía xl/workbook.xml (no requiere openpyxl)."""
    with zipfile.ZipFile(str(xlsx_path)) as z:
        with z.open('xl/workbook.xml') as f:
            content = f.read().decode('utf-8')
    return re.findall(r'<sheet name="([^"]+)"', content)


def read_sheet(xlsx_path: Path, sheet_index: int) -> dict:
    """Read sheet → {row_number: {col_letter: value}}.

    sheet_index is 1-based (sheet1.xml = first sheet).
    """
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


def detect_columns(
    rows: dict,
    header_row: int,
    field_to_keywords: dict[str, list[str]],
) -> dict[str, str]:
    """Inspect header_row and map each field to its column letter.

    field_to_keywords: e.g. {'code': ['CODIGO', 'CÓDIGO'], 'unit': ['UNIDAD']}.
    Match is case- and accent-insensitive substring on the header text.
    Returns: {'code': 'E', 'unit': 'G', ...}. Missing fields are absent from result.
    """
    header = rows.get(header_row, {})
    found = {}
    for col, val in header.items():
        if not val:
            continue
        norm = normalize_label(str(val).strip())
        for field, keywords in field_to_keywords.items():
            if field in found:
                continue
            for kw in keywords:
                if normalize_label(kw) in norm:
                    found[field] = col
                    break
    return found


def banner(text: str, char: str = '=') -> None:
    line = char * 70
    print()
    print(line)
    print(f'  {text}')
    print(line)


# ---------------------------------------------------------------------------
# ImportContext
# ---------------------------------------------------------------------------
@dataclass
class ImportContext:
    """State carried between phases within a single import run."""
    xlsx_path: Path
    user: SystemUser
    account_id_override: Optional[UUID] = None

    # Fase 1 overrides for Excels with missing cells (typical en estudios INTERNOS)
    client_name_override: Optional[str] = None
    presentation_date_override: Optional[date] = None
    start_date_override: Optional[date] = None
    bidding_type_override: Optional[int] = None
    project_type_override: Optional[int] = None
    period_type_override: Optional[int] = None

    # Populated by fase 1
    account: Optional[Account] = None
    project: Optional[EstimationProject] = None
    excel_totals: dict = field(default_factory=dict)

    # Per-phase summary (for final report)
    phase_stats: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fase 1 — Datos Generales (Hoja Cierre Estudio)
# ---------------------------------------------------------------------------
def run_fase_1(ctx: ImportContext) -> dict:
    """Parse 'Hoja Cierre Estudio' → create Account (or reuse) + EstimationProject."""
    rows = read_sheet(ctx.xlsx_path, 1)

    def cell(ref: str) -> str:
        col = ''.join(ch for ch in ref if ch.isalpha())
        row_n = int(''.join(ch for ch in ref if ch.isdigit()))
        return (rows.get(row_n, {}).get(col) or '').strip()

    # ---- Datos del proyecto ----
    project_name = cell('A7').strip()
    if not project_name:
        raise RuntimeError("Fase 1: A7 (PROYECTO) vacío. ¿Plantilla correcta?")

    # Client: override CLI > Excel I7. Required.
    client_name = ctx.client_name_override or cell('I7').strip()
    if not client_name:
        raise RuntimeError(
            "Fase 1: I7 (CLIENTE) vacío y sin --client-name. "
            "Para estudios INTERNOS pasar --client-name explícito."
        )

    country_code = cell('B9').strip() or 'MX'
    country = 'México' if country_code.upper() in ('MX', 'MÉXICO', 'MEXICO') else country_code

    # Dates: override CLI > Excel serial. Start is required.
    presentation = ctx.presentation_date_override or excel_serial_to_date(cell('C9'))
    start = ctx.start_date_override or excel_serial_to_date(cell('E9'))
    duration_months = to_int(cell('R8'))
    if not start or duration_months <= 0:
        raise RuntimeError(
            f"Fase 1: faltan fechas. start={start}, durationmonths={duration_months}. "
            "Pasar --start-date YYYY-MM-DD para overridear."
        )
    end = start + relativedelta(months=duration_months)

    # Enums: override CLI > Excel label > default.
    if ctx.bidding_type_override is not None:
        bidding_type = ctx.bidding_type_override
    else:
        bidding_label = normalize_label(cell('G9'))
        bidding_type = BIDDING_TYPE_MAP.get(bidding_label, 2)  # default: ADJ. DIRECTA

    if ctx.project_type_override is not None:
        project_type = ctx.project_type_override
    else:
        project_label = normalize_label(cell('E12'))
        project_type = PROJECT_TYPE_MAP.get(project_label, 0)

    if ctx.period_type_override is not None:
        period_type = ctx.period_type_override
    else:
        period_label = normalize_label(cell('I12'))
        period_type = PERIOD_TYPE_MAP.get(period_label, 1)
        if period_label == 'MENSUAL':
            print(f"  AVISO: PAGOS Y FINANCIAMIENTO='MENSUAL' mapeado a Quincenal "
                  f"(modelo no soporta MONTHLY). Tech-debt registrada.")

    exchange_rate = to_decimal(cell('B15'), '20.0000')
    profit_pct = to_decimal(cell('D44'))
    # D44 viene como decimal (0.15). Convertir a porcentaje (15.00).
    if profit_pct < 1:
        profit_pct = profit_pct * 100
    contract_amount = to_decimal(cell('G57'))

    # Totales del Excel para auditoría posterior
    ctx.excel_totals = {
        'direct': to_decimal(cell('G40')),
        'indirect': to_decimal(cell('G42')),
        'construction': to_decimal(cell('G46')),
        'sale_net': to_decimal(cell('G48')),
        'contract': contract_amount,
    }

    # ---- Account ----
    if ctx.account_id_override is not None:
        ctx.account = Account.objects.get(accountid=ctx.account_id_override)
        account_action = 'reused (override)'
    else:
        ctx.account, created = Account.objects.get_or_create(
            name=client_name,
            defaults={
                'address1_country': country,
                'customertypecode': 3,
                'creditonhold': False,
                'statecode': 0,
                'statuscode': 1,
                'ownerid': ctx.user,
                'createdby': ctx.user,
                'modifiedby': ctx.user,
            },
        )
        account_action = 'created' if created else 'reused (by name)'

    # ---- EstimationProject ----
    description = (
        f"Estudio de oferta para construcción de {project_name}. "
        f"Cliente: {client_name}. "
        f"{cell('G9') or 'Adjudicación directa'}, periodo de ejecución {duration_months} meses, "
        f"pago {cell('I12') or 'mensual'}."
    )
    dto = SimpleNamespace(
        name=project_name,
        description=description,
        accountid=ctx.account.accountid,
        opportunityid=None,
        presentationdate=presentation or start,
        estimatedstartdate=start,
        estimatedenddate=end,
        durationmonths=duration_months,
        projecttype=project_type,
        biddingtype=bidding_type,
        periodtype=period_type,
        estimatedcontractamount=contract_amount,
        exchangerate_mxn_usd=exchange_rate,
        profitpercent=profit_pct,
    )
    ctx.project = EstimationProjectService.create_project(dto, ctx.user)
    ctx.project.profitpercent = profit_pct
    ctx.project.save(update_fields=['profitpercent'])

    stats = {
        'account_action': account_action,
        'account_id': str(ctx.account.accountid),
        'account_name': ctx.account.name,
        'project_id': str(ctx.project.estimationprojectid),
        'project_number': ctx.project.estimationnumber,
        'project_name': ctx.project.name,
        'profit_percent': float(profit_pct),
        'contract_amount': float(contract_amount),
    }
    print(f"  Account {account_action}: {ctx.account.name}")
    print(f"  EstimationProject creado: {ctx.project.estimationnumber} ({ctx.project.name})")
    print(f"  Fechas: {start} -> {end} ({duration_months} meses, periodtype={period_type})")
    print(f"  Contrato: ${contract_amount:,.2f}  Utilidad: {profit_pct}%")
    return stats


# ---------------------------------------------------------------------------
# Fase 2 — Conceptos (E7 Fase Estudio)
# ---------------------------------------------------------------------------
CONCEPTS_HEADER_KEYWORDS = {
    'partida': ['PARTIDA'],
    'code': ['CODIGO', 'CÓDIGO'],
    'description': ['DESCRIPCION', 'DESCRIPCIÓN'],
    'unit': ['UNIDAD'],
    'quantity': ['CANTIDAD'],
    'pu_known': ['P.U. ', 'P.U.'],  # cliente unit price (último P.U.)
}


def _parse_concepts_sheet(rows: dict) -> list[dict]:
    """Parse 'E7 Fase Estudio' with dynamic column detection.

    Excel piloto (#1): partida=C, code=D, description=E, unit=F, quantity=G
    Excel V10 (#2):   partida=D, code=E, description=F, unit=G, quantity=H
    """
    cols = detect_columns(rows, 5, CONCEPTS_HEADER_KEYWORDS)
    required = ['partida', 'code', 'description', 'unit', 'quantity']
    missing = [k for k in required if k not in cols]
    if missing:
        raise RuntimeError(
            f"Fase 2: no se detectaron columnas {missing} en fila 5 de E7 Fase Estudio. "
            f"Detectado: {cols}"
        )
    col_partida = cols['partida']
    col_code = cols['code']
    col_desc = cols['description']
    col_unit = cols['unit']
    col_qty = cols['quantity']
    col_pu = cols.get('pu_known', 'S')  # fallback al último P.U. ubicación típica

    result = []
    family_seq = 0
    for r in sorted(rows.keys()):
        if r < 7:
            continue
        rr = rows[r]
        partida = (rr.get(col_partida) or '').strip()
        code = (rr.get(col_code) or '').strip()
        desc = (rr.get(col_desc) or '').strip()
        unit = (rr.get(col_unit) or '').strip()
        qty = (rr.get(col_qty) or '').strip()

        # Family: partida column has single letter + description has family label
        if partida and len(partida) <= 2 and partida.isalpha() and desc:
            family_seq += 1
            parts = desc.split('.', 1)
            fam_code = parts[0].strip() if parts and parts[0].strip().isdigit() else partida
            result.append({'kind': 'family', 'code': fam_code, 'name': desc, 'sortorder': family_seq})
            continue

        # Concept: code + description + unit. Quantity may be 0.
        if code and desc and unit:
            result.append({
                'kind': 'concept',
                'code': code,
                'description': desc,
                'unit': unit,
                'quantity': to_decimal(qty),
                'clientunitprice': to_decimal(rr.get(col_pu, '0')),
            })
            continue

        # Subfamily: only description in UPPERCASE, no code/unit/qty
        if (not code) and desc and (not unit) and (not qty) and desc.isupper():
            result.append({'kind': 'subfamily', 'name': desc})
            continue
    return result


def run_fase_2(ctx: ImportContext) -> dict:
    """Parse 'E7 Fase Estudio' → ConceptFamily + ConceptSubfamily + BudgetConcept."""
    if BudgetConcept.objects.filter(projectid=ctx.project).exists():
        raise RuntimeError(
            f"Proyecto {ctx.project.estimationnumber} ya tiene conceptos. "
            "Borrar familias antes de re-importar."
        )

    rows = read_sheet(ctx.xlsx_path, 2)
    parsed = _parse_concepts_sheet(rows)

    stats = {'families': 0, 'subfamilies': 0, 'concepts': 0, 'skipped_subfamilies': 0}
    current_family = None
    current_subfamily = None
    pending_subfamily = None
    subfamily_seq = 0
    concept_seq = 0

    for node in parsed:
        if node['kind'] == 'family':
            current_family = ConceptFamily.objects.create(
                projectid=ctx.project,
                name=node['name'],
                code=node['code'],
                sortorder=node['sortorder'] * 10,
                createdby=ctx.user,
                modifiedby=ctx.user,
            )
            stats['families'] += 1
            current_subfamily = None
            pending_subfamily = None
            subfamily_seq = 0

        elif node['kind'] == 'subfamily':
            if pending_subfamily is not None and current_subfamily is None:
                stats['skipped_subfamilies'] += 1
            subfamily_seq += 1
            pending_subfamily = {'name': node['name'], 'sortorder': subfamily_seq}
            current_subfamily = None
            concept_seq = 0

        elif node['kind'] == 'concept':
            if current_family is None:
                raise RuntimeError(f"Concept {node['code']} sin familia precedente")
            if current_subfamily is None:
                if pending_subfamily is None:
                    pending_subfamily = {'name': 'GENERAL', 'sortorder': 99}
                sf_code = f"{current_family.code}.{pending_subfamily['sortorder']:02d}"
                current_subfamily = ConceptSubfamily.objects.create(
                    projectid=ctx.project,
                    familyid=current_family,
                    name=pending_subfamily['name'],
                    code=sf_code,
                    sortorder=pending_subfamily['sortorder'] * 10,
                    createdby=ctx.user,
                    modifiedby=ctx.user,
                )
                stats['subfamilies'] += 1
                concept_seq = 0
            concept_seq += 1
            BudgetConcept.objects.create(
                projectid=ctx.project,
                subfamilyid=current_subfamily,
                code=node['code'],
                sequencenumber=concept_seq,
                description=node['description'][:500],
                unit=node['unit'][:20],
                quantity=node['quantity'],
                clientunitprice=node['clientunitprice'] if node['clientunitprice'] > 0 else None,
                breakdownmethod=0,
                isprintable=True,
                createdby=ctx.user,
                modifiedby=ctx.user,
            )
            stats['concepts'] += 1

    if pending_subfamily is not None and current_subfamily is None:
        stats['skipped_subfamilies'] += 1

    print(f"  Familias: {stats['families']}, Subfamilias: {stats['subfamilies']} "
          f"(skip vacías: {stats['skipped_subfamilies']}), Conceptos: {stats['concepts']}")
    return stats


# ---------------------------------------------------------------------------
# Fase 3 — Desglose CDU
# ---------------------------------------------------------------------------
CDU_HEADER_KEYWORDS = {
    'code': ['CODIGO', 'CÓDIGO'],
    'description': ['CONCEPTO', 'DESCRIPCION', 'DESCRIPCIÓN'],
    'unit': ['UNIDAD'],
    'quantity': ['CANTIDAD'],
    'unitprice': ['COSTO'],
    'yieldvalue': ['RENDIMIENTO'],
    'amount': ['IMPORTE'],
}

# Mapping de nombres de sección dentro de un bloque CDU → categoría BD.
# Usado para parser dinámico que no depende de offsets fijos.
SECTION_LABEL_TO_CATEGORY = {
    'MATERIALES': BreakdownCategoryCode.MATERIALS,
    'ACARREOS': BreakdownCategoryCode.HAULING,
    'MAQUINARIA': BreakdownCategoryCode.MACHINERY,
    'MANO DE OBRA': BreakdownCategoryCode.LABOR,
    'SUBCONTRATOS': BreakdownCategoryCode.SUBCONTRACTS,
    'HERRAMIENTA MENOR': BreakdownCategoryCode.MINOR_TOOLS,
    'EPP': BreakdownCategoryCode.PPE,
}


def _detect_cdu_header_row(rows: dict) -> int:
    """Find header row (looks for 'CODIGO' + 'IMPORTE' in same row, typically 9 or 10)."""
    for r in sorted(rows.keys()):
        if r > 12:
            break
        cols = detect_columns(rows, r, CDU_HEADER_KEYWORDS)
        if 'code' in cols and 'amount' in cols and 'unit' in cols:
            return r
    raise RuntimeError("Fase 3: no se encontró fila de headers (CODIGO + IMPORTE + UNIDAD)")


def _detect_cdu_block_size(rows: dict, code_col: str, first_block_row: int) -> int:
    """Detect block size by finding distance between first 2 concept headers."""
    found_rows = []
    for r in sorted(rows.keys()):
        if r < first_block_row:
            continue
        code = (rows[r].get(code_col) or '').strip()
        if code and code != '-' and len(code) >= 2:
            # Skip section headers (single word in caps without dash/digit)
            norm = normalize_label(code)
            if norm in (normalize_label(k) for k in SECTION_LABEL_TO_CATEGORY):
                continue
            found_rows.append(r)
            if len(found_rows) >= 2:
                return found_rows[1] - found_rows[0]
    return 43  # fallback al layout v1


def _parse_cdu_block(rows: dict, block_row: int, block_size: int, cols: dict[str, str]) -> list[dict]:
    """Walk a block looking for section labels in the description column.

    Robust to layout changes: doesn't depend on fixed offsets per category.
    """
    breakdowns = []
    col_desc = cols['description']
    col_unit = cols['unit']
    col_qty = cols['quantity']
    col_price = cols['unitprice']
    col_yield = cols['yieldvalue']
    col_amount = cols['amount']

    section_norm = {normalize_label(k): v for k, v in SECTION_LABEL_TO_CATEGORY.items()}
    # HM y EPP son secciones de una sola línea: el row con la etiqueta ES el dato.
    SINGLE_LINE_CATEGORIES = {
        int(BreakdownCategoryCode.MINOR_TOOLS),
        int(BreakdownCategoryCode.PPE),
    }
    current_category = None
    line_no = 0

    # Skip offset 0 (concept header); walk through rest of block
    for off in range(1, block_size):
        row = rows.get(block_row + off, {})
        desc = (row.get(col_desc) or '').strip()
        norm_desc = normalize_label(desc)

        # Section header?
        if norm_desc in section_norm:
            cat = int(section_norm[norm_desc])
            if cat in SINGLE_LINE_CATEGORIES:
                # HM/EPP: el header ES el dato. Capturar la fila aquí mismo.
                amount = to_decimal(row.get(col_amount, '0'))
                if amount > 0:
                    breakdowns.append({
                        'categorycode': cat,
                        'linenumber': 1,
                        'description': desc[:500],
                        'unit': (row.get(col_unit) or '').strip()[:20],
                        'quantity': to_decimal(row.get(col_qty, '0')),
                        'unitprice': to_decimal(row.get(col_price, '0')),
                        'yieldvalue': to_decimal(row.get(col_yield, '1')) or Decimal('1'),
                        'amount': amount,
                    })
                # No setear current_category — siguientes filas (TOTAL, etc.) no aplican.
                current_category = None
            else:
                # Sección normal: switch + skip; siguientes filas son detalle.
                current_category = section_norm[norm_desc]
                line_no = 0
            continue

        if current_category is None:
            continue

        amount = to_decimal(row.get(col_amount, '0'))
        if amount == 0:
            continue

        line_no += 1
        breakdowns.append({
            'categorycode': int(current_category),
            'linenumber': line_no,
            'description': desc[:500],
            'unit': (row.get(col_unit) or '').strip()[:20],
            'quantity': to_decimal(row.get(col_qty, '0')),
            'unitprice': to_decimal(row.get(col_price, '0')),
            'yieldvalue': to_decimal(row.get(col_yield, '1')) or Decimal('1'),
            'amount': amount,
        })
    return breakdowns


def run_fase_3(ctx: ImportContext) -> dict:
    """Parse 'Desglose de C.D.U.' -> UnitCostBreakdown + cascade recalculate_concept."""
    if UnitCostBreakdown.objects.filter(conceptid__projectid=ctx.project).exists():
        raise RuntimeError(f"Proyecto {ctx.project.estimationnumber} ya tiene UnitCostBreakdown.")

    rows = read_sheet(ctx.xlsx_path, 3)
    header_row = _detect_cdu_header_row(rows)
    cols = detect_columns(rows, header_row, CDU_HEADER_KEYWORDS)
    print(f"  CDU columns detectadas (fila {header_row}): {cols}")
    first_block_row = header_row + 2  # skip header + 1 separator row
    col_block_code = cols['code']  # column with concept code at block header
    block_size = _detect_cdu_block_size(rows, col_block_code, first_block_row)
    print(f"  CDU block size detectado: {block_size} filas")
    db_concepts = {c.code: c for c in BudgetConcept.objects.filter(projectid=ctx.project)}

    stats = {
        'blocks_seen': 0,
        'blocks_skipped_no_match': 0,
        'concepts_imported': 0,
        'concepts_no_detail': 0,
        'breakdown_lines': 0,
        'concepts_recalculated': 0,
    }
    recalculated_ids = []
    block_row = first_block_row

    while block_row in rows:
        stats['blocks_seen'] += 1
        row = rows[block_row]
        code = (row.get(col_block_code) or '').strip()

        if not code or code == '-':
            block_row += block_size
            continue

        concept = db_concepts.get(code)
        if concept is None:
            stats['blocks_skipped_no_match'] += 1
            block_row += block_size
            continue

        breakdowns = _parse_cdu_block(rows, block_row, block_size, cols)
        if not breakdowns:
            stats['concepts_no_detail'] += 1
            block_row += block_size
            continue

        UnitCostBreakdown.objects.bulk_create([
            UnitCostBreakdown(conceptid=concept, **bd) for bd in breakdowns
        ])
        stats['concepts_imported'] += 1
        stats['breakdown_lines'] += len(breakdowns)
        recalculated_ids.append(concept.conceptid)
        block_row += block_size

    for cid in recalculated_ids:
        ConceptCatalogService.recalculate_concept(cid, ctx.user)
        stats['concepts_recalculated'] += 1

    print(f"  Bloques vistos: {stats['blocks_seen']}, "
          f"conceptos con CDU: {stats['concepts_imported']}, "
          f"líneas: {stats['breakdown_lines']}, "
          f"recalculados: {stats['concepts_recalculated']}")
    return stats


# ---------------------------------------------------------------------------
# Fase 4 — Costos Indirectos
# ---------------------------------------------------------------------------
INDIRECT_HEADER_KEYWORDS = {
    'line': ['NO.', 'NUMERO', 'NÚMERO'],
    'imputation': ['C. IMP', 'C.IMP', 'IMPUTAC'],
    'area': ['AREA', 'ÁREA'],
    'description': ['DESCRIPCION', 'DESCRIPCIÓN'],
    'monthly': ['COSTO MENSUAL', 'MENSUAL'],
    'units': ['UNIDADES'],
    'months': ['MESES'],
    'amount': ['IMPORTE'],
}


def _detect_indirect_header_row(rows: dict) -> int:
    """Find header row (looks for 'Importe' + 'Costo mensual' + 'Meses')."""
    for r in sorted(rows.keys()):
        if r > 12:
            break
        cols = detect_columns(rows, r, INDIRECT_HEADER_KEYWORDS)
        if 'amount' in cols and 'monthly' in cols and 'months' in cols:
            return r
    raise RuntimeError("Fase 4: no se encontró fila de headers (Importe + Costo mensual + Meses)")


def _parse_indirect_sheet(rows: dict) -> list[dict]:
    """Parse 'Costo Indirecto' with dynamic column detection.

    Excel V10 layout: B=No., C=C.Imp. (también categoría 'Cn'), D=Area,
    E=Descripcion, F=Costo mensual, G=Unidades, H=Meses, I=Importe Total.
    """
    header_row = _detect_indirect_header_row(rows)
    cols = detect_columns(rows, header_row, INDIRECT_HEADER_KEYWORDS)
    print(f"  Indirect columns detectadas (fila {header_row}): {cols}")

    col_line = cols.get('line', 'B')
    col_imp = cols.get('imputation', 'C')
    col_area = cols.get('area', 'D')
    col_desc = cols.get('description', 'E')
    col_monthly = cols['monthly']
    col_units = cols.get('units', 'G')
    col_months = cols.get('months', 'H')
    col_amount = cols['amount']

    result = []
    current_category = None
    current_category_name = None
    current_area = None
    line_no = 0
    data_start = header_row + 2  # skip header + 1 separator

    for r in sorted(rows.keys()):
        if r < data_start:
            continue
        rr = rows[r]
        line = (rr.get(col_line) or '').strip()
        imp = (rr.get(col_imp) or '').strip()
        area = (rr.get(col_area) or '').strip()
        desc = (rr.get(col_desc) or '').strip()
        monthly = (rr.get(col_monthly) or '').strip()
        amount = (rr.get(col_amount) or '').strip()

        # Category header: imputation column matches C1-C8 regex (vs detail rows have AC1/AC4)
        if imp and INDIRECT_CATEGORY_RE.match(imp):
            current_category = imp
            current_category_name = area
            current_area = None
            line_no = 0
            continue

        if current_category is None:
            continue

        # Detail line: line# + monthly. Skip amount=0.
        if line and monthly:
            amount_val = to_decimal(amount)
            if amount_val == 0:
                continue
            line_no += 1
            result.append({
                'categorycode': current_category,
                'linenumber': line_no,
                'imputationcode': imp[:10],
                'area': (current_area or current_category_name or '')[:100],
                'description': (desc or area)[:500],
                'monthlycost': to_decimal(monthly),
                'units': to_decimal(rr.get(col_units, '1'), '1') or Decimal('1'),
                'months': to_decimal(rr.get(col_months, '1'), '1') or Decimal('1'),
                'amount': amount_val,
            })
            continue

        # Sub-area header: area set, no line# / monthly / amount
        if area and not line and not monthly and not amount:
            current_area = area
            continue
    return result


def run_fase_4(ctx: ImportContext) -> dict:
    """Parse 'Costo Indirecto' → IndirectCostDetail + cascade prorate_to_concepts."""
    if IndirectCostDetail.objects.filter(projectid=ctx.project).exists():
        raise RuntimeError(f"Proyecto {ctx.project.estimationnumber} ya tiene IndirectCostDetail.")

    rows = read_sheet(ctx.xlsx_path, 4)
    parsed = _parse_indirect_sheet(rows)

    stats = {
        'lines_created': 0,
        'by_category': {},
        'total_indirect': Decimal('0'),
        'concepts_updated': 0,
    }
    objs = []
    for node in parsed:
        objs.append(IndirectCostDetail(
            projectid=ctx.project,
            createdby=ctx.user,
            modifiedby=ctx.user,
            **node,
        ))
        stats['by_category'].setdefault(node['categorycode'], 0)
        stats['by_category'][node['categorycode']] += 1
        stats['total_indirect'] += node['amount']

    IndirectCostDetail.objects.bulk_create(objs)
    stats['lines_created'] = len(objs)

    updated = IndirectCostDetailService.prorate_to_concepts(
        ctx.project.estimationprojectid, ctx.user,
    )
    stats['concepts_updated'] = len(updated)

    print(f"  Líneas: {stats['lines_created']}, "
          f"total ${stats['total_indirect']:,.2f}, "
          f"conceptos actualizados: {stats['concepts_updated']}")
    return stats


# ---------------------------------------------------------------------------
# Fase 5 — Catálogo de Insumos (derived from UnitCostBreakdown)
# ---------------------------------------------------------------------------
def _next_supply_code(supplytype: int) -> str:
    prefix = SUPPLYTYPE_TO_PREFIX[supplytype]
    existing = SupplyCatalogItem.objects.filter(
        code__startswith=f'{prefix}-'
    ).values_list('code', flat=True)
    max_n = 0
    for code in existing:
        try:
            n = int(code.split('-', 1)[1])
            max_n = max(max_n, n)
        except (IndexError, ValueError):
            continue
    return f'{prefix}-{max_n + 1:04d}'


def run_fase_5(ctx: ImportContext) -> dict:
    """Derive SupplyCatalogItem from UnitCostBreakdown, link via supplyid.

    Catalog is GLOBAL — dedupe by (description, unit, supplytype) for reuse.
    """
    already_linked = UnitCostBreakdown.objects.filter(
        conceptid__projectid=ctx.project,
        supplyid__isnull=False,
    ).count()
    if already_linked > 0:
        raise RuntimeError(
            f"Proyecto ya tiene {already_linked} breakdowns con supply linkeado."
        )

    bds = list(UnitCostBreakdown.objects.filter(
        conceptid__projectid=ctx.project,
        statecode=0,
    ))
    groups = defaultdict(list)
    skipped_hm_epp = 0
    for bd in bds:
        if bd.categorycode not in CATEGORY_TO_SUPPLYTYPE:
            skipped_hm_epp += 1
            continue
        supplytype = CATEGORY_TO_SUPPLYTYPE[bd.categorycode]
        key = (bd.description.strip().upper(), bd.unit.strip().upper(), supplytype)
        groups[key].append(bd)

    stats = {
        'unique_supplies': len(groups),
        'created': 0,
        'reused': 0,
        'breakdowns_total': len(bds),
        'breakdowns_linked': 0,
        'breakdowns_skipped_hm_epp': skipped_hm_epp,
    }

    breakdowns_to_update = []
    for (_desc, _unit, supplytype), bd_list in groups.items():
        sample = bd_list[0]
        existing = SupplyCatalogItem.objects.filter(
            description__iexact=sample.description.strip(),
            unit__iexact=sample.unit.strip(),
            supplytype=supplytype,
            statecode=0,
        ).first()
        if existing is None:
            item = SupplyCatalogItem.objects.create(
                code=_next_supply_code(supplytype),
                description=sample.description.strip(),
                unit=sample.unit.strip(),
                supplytype=supplytype,
                referenceprice=sample.unitprice or Decimal('0'),
                geographiczone='',
                createdby=ctx.user,
                modifiedby=ctx.user,
            )
            stats['created'] += 1
        else:
            item = existing
            stats['reused'] += 1
        for bd in bd_list:
            bd.supplyid = item
            breakdowns_to_update.append(bd)

    if breakdowns_to_update:
        UnitCostBreakdown.objects.bulk_update(breakdowns_to_update, ['supplyid'])
        stats['breakdowns_linked'] = len(breakdowns_to_update)

    print(f"  Insumos únicos: {stats['unique_supplies']}, "
          f"creados: {stats['created']}, reusados: {stats['reused']}, "
          f"links: {stats['breakdowns_linked']}")
    return stats


# ---------------------------------------------------------------------------
# Fase 6 — Plan de Obra
# ---------------------------------------------------------------------------
WORKPLAN_HEADER_KEYWORDS = {
    'code': ['CODIGO', 'CÓDIGO'],
}


def _detect_period_columns(rows: dict) -> list[tuple[str, int]]:
    header = rows.get(WORKPLAN_HEADER_ROW, {})
    period_cols = []
    for col, val in header.items():
        try:
            n = int(str(val).strip())
            if n >= 1:
                period_cols.append((col, n))
        except (ValueError, TypeError):
            continue
    return sorted(period_cols, key=lambda x: x[1])


def run_fase_6(ctx: ImportContext) -> dict:
    """Parse 'Plan de obra' -> WorkPlanEntry (PLANNED). Handles empty plan gracefully."""
    if WorkPlanEntry.objects.filter(projectid=ctx.project).exists():
        raise RuntimeError(f"Proyecto {ctx.project.estimationnumber} ya tiene WorkPlanEntry.")

    rows = read_sheet(ctx.xlsx_path, 7)
    cols = detect_columns(rows, WORKPLAN_HEADER_ROW, WORKPLAN_HEADER_KEYWORDS)
    if 'code' not in cols:
        raise RuntimeError(f"Fase 6: no se detectó columna CODIGO en fila {WORKPLAN_HEADER_ROW}")
    col_code = cols['code']
    print(f"  Plan de Obra: code en columna {col_code}")

    db_concepts = {c.code: c for c in BudgetConcept.objects.filter(projectid=ctx.project)}
    code_to_row = {}
    for r in sorted(rows.keys()):
        if r < WORKPLAN_DATA_START_ROW:
            continue
        code = (rows[r].get(col_code) or '').strip()
        if code and code in db_concepts:
            code_to_row[code] = r

    period_cols = _detect_period_columns(rows)
    if not period_cols:
        raise RuntimeError('Fase 6: no se detectaron columnas de periodo en fila 5')

    projection_periods = {
        p.periodnumber: p.periodlabel
        for p in ProjectionPeriod.objects.filter(projectid=ctx.project)
    }

    stats = {
        'concepts_in_excel': len(code_to_row),
        'concepts_with_plan': 0,
        'entries_created': 0,
        'periods_used': set(),
        'plan_is_empty': False,
    }
    entries = []
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
            label = projection_periods.get(period_n, f'P{period_n:02d}')
            amount = qty * (concept.unitprice or Decimal('0'))
            entries.append(WorkPlanEntry(
                conceptid=concept,
                projectid=ctx.project,
                periodnumber=period_n,
                periodlabel=label[:20],
                entrytype=int(WorkPlanEntryType.PLANNED),
                distributedquantity=qty,
                distributedamount=amount,
                createdby=ctx.user,
                modifiedby=ctx.user,
            ))
        if concept_has_plan:
            stats['concepts_with_plan'] += 1

    if entries:
        WorkPlanEntry.objects.bulk_create(entries)
        stats['entries_created'] = len(entries)
    else:
        stats['plan_is_empty'] = True

    stats['periods_used'] = sorted(stats['periods_used'])
    if stats['plan_is_empty']:
        print("  AVISO: hoja 'Plan de obra' vacía (todos los conceptos en 0). "
              "Común pre-adjudicación.")
    else:
        print(f"  Conceptos con plan: {stats['concepts_with_plan']}, "
              f"entries: {stats['entries_created']}, periodos usados: {stats['periods_used']}")
    return stats


# ---------------------------------------------------------------------------
# Fase 7 — ProjectionPeriod (no se importa la matriz de Dist. Temporal)
# ---------------------------------------------------------------------------
def run_fase_7(ctx: ImportContext) -> dict:
    """Generate ProjectionPeriod via PeriodService. Excel 'Dist. Temporal' matrix is ignored."""
    existing = ProjectionPeriod.objects.filter(projectid=ctx.project).count()
    if existing > 0:
        raise RuntimeError(f"Proyecto ya tiene {existing} ProjectionPeriod.")

    if not ctx.project.estimatedstartdate or not ctx.project.estimatedenddate:
        raise RuntimeError("Fase 7: proyecto sin estimatedstartdate/enddate.")

    PeriodService.regenerate_projection_periods(ctx.project, confirm=False)
    periods = list(ProjectionPeriod.objects.filter(projectid=ctx.project).order_by('periodnumber'))

    cd_count = CostDistribution.objects.filter(projectid=ctx.project).count()
    stats = {
        'periods_created': len(periods),
        'period_labels': [p.periodlabel for p in periods],
        'cost_distribution_rows': cd_count,
        'matrix_ignored': True,
    }
    print(f"  ProjectionPeriod creados: {stats['periods_created']} "
          f"({', '.join(stats['period_labels'])})")
    print("  AVISO: matriz 'Dist. Temporal' del Excel ignorada (granularidad incompatible).")
    return stats


# ---------------------------------------------------------------------------
# Fase 8 — PNT (parámetros financieros)
# ---------------------------------------------------------------------------
def _find_pnt_row(rows: dict, label_substring: str) -> Optional[int]:
    target = normalize_label(label_substring)
    for r in sorted(rows.keys()):
        c_val = normalize_label((rows[r].get('C') or '').strip())
        if target in c_val:
            return r
    return None


def _days_to_periods(days: int, periodtype: int) -> int:
    return round(days / 7) if periodtype == 0 else round(days / 15)


def run_fase_8(ctx: ImportContext) -> dict:
    """Parse 'PNT' → EstimationFinancialSettings + EstimationBillingRule."""
    rows = read_sheet(ctx.xlsx_path, 9)
    periodtype = ctx.project.periodtype
    inputs = {}

    r = _find_pnt_row(rows, 'COBRO FACTURACION')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['client_lag_days'] = days
        inputs['client_lag_periods'] = _days_to_periods(days, periodtype)

    r = _find_pnt_row(rows, 'ANTICIPO CONCEDIDO')
    if r:
        inputs['advance_rate'] = to_decimal(rows[r].get('D', '0'))
        amount = to_decimal(rows[r].get('CQ') or rows[r].get('E', '0'))
        inputs['advance_amount'] = amount
        inputs['advance_entry_period'] = 1

    r = _find_pnt_row(rows, 'ANTICIPO AMORTIZADO')
    if r:
        inputs['advance_amortization_rate'] = to_decimal(rows[r].get('D', '0'))

    r = _find_pnt_row(rows, 'RETENCIONES IMSS')
    if r:
        inputs['imss_retention_rate'] = to_decimal(rows[r].get('D', '0'))

    r = _find_pnt_row(rows, 'OTRAS RETENCIONES')
    if r:
        inputs['other_retention_rate'] = to_decimal(rows[r].get('D', '0'))

    r = _find_pnt_row(rows, 'TRANSF (VALOR')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['direct_lag_days'] = days
        inputs['direct_lag_periods'] = _days_to_periods(days, periodtype)

    r = _find_pnt_row(rows, 'TRANSFERENCIA COSTE CONTABLE')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['indirect_lag_days'] = days
        inputs['indirect_lag_periods'] = _days_to_periods(days, periodtype)

    _, settings_created = EstimationFinancialSettings.objects.update_or_create(
        projectid=ctx.project,
        defaults={
            'advanceamountnotax': inputs.get('advance_amount', Decimal('0')),
            'advanceentryperiod': inputs.get('advance_entry_period', 1),
            'advanceamortizationrate': inputs.get('advance_amortization_rate', Decimal('0')),
            'imssretentionrate': inputs.get('imss_retention_rate', Decimal('0.05')),
            'otherretentionrate': inputs.get('other_retention_rate', Decimal('0')),
            'directpaymentlag': inputs.get('direct_lag_periods', 0),
            'indirectpaymentlag': inputs.get('indirect_lag_periods', 0),
            'createdby': ctx.user,
            'modifiedby': ctx.user,
        },
    )

    EstimationBillingRule.objects.filter(projectid=ctx.project).delete()
    billing_rules_created = 0
    if 'client_lag_periods' in inputs:
        EstimationBillingRule.objects.create(
            projectid=ctx.project,
            sequence=1,
            percent=Decimal('1.0000'),
            lagperiods=inputs['client_lag_periods'],
            createdby=ctx.user,
            modifiedby=ctx.user,
        )
        billing_rules_created = 1

    stats = {
        'settings_created': settings_created,
        'billing_rules_created': billing_rules_created,
        'inputs_detected': {k: float(v) if isinstance(v, Decimal) else v for k, v in inputs.items()},
    }
    print(f"  EstimationFinancialSettings: {'creado' if settings_created else 'actualizado'}")
    print(f"  EstimationBillingRule: {billing_rules_created} regla(s)")
    if 'advance_amount' in inputs:
        print(f"  Anticipo: ${inputs['advance_amount']:,.2f} ({inputs.get('advance_rate', 0)*100:.0f}%)")
    return stats


# ---------------------------------------------------------------------------
# Audit de paridad
# ---------------------------------------------------------------------------
@dataclass
class ParityCheck:
    label: str
    bd_value: Decimal
    excel_value: Decimal
    informational: bool = False  # if True, mismatch warns but doesn't fail audit

    @property
    def delta(self) -> Decimal:
        return abs(self.bd_value - self.excel_value)

    @property
    def passed(self) -> bool:
        if self.delta <= PARITY_TOLERANCE_ABS:
            return True
        if self.excel_value:
            rel = self.delta / abs(self.excel_value)
            return rel <= PARITY_TOLERANCE_REL
        return False


@dataclass
class AuditResult:
    checks: list[ParityCheck]

    @property
    def passed(self) -> bool:
        # Solo bloquean los checks no-informational
        return all(c.passed for c in self.checks if not c.informational)


def run_parity_audit(ctx: ImportContext) -> AuditResult:
    """Compare BD aggregates against Excel cells from 'Hoja Cierre Estudio'.

    Nota sobre indirecto: G42 de Hoja Cierre incluye "COSTOS EXTERNOS" (fianzas,
    impuestos, financiamiento) que NO se modelan en IndirectCostDetail. Por eso
    el check de indirecto es informational: warning si difiere pero no bloquea.
    """
    excel = ctx.excel_totals

    direct_bd = sum(
        (c.directunitcost or Decimal('0')) * (c.quantity or Decimal('0'))
        for c in BudgetConcept.objects.filter(projectid=ctx.project)
    )
    indirect_bd = sum(
        (d.amount or Decimal('0'))
        for d in IndirectCostDetail.objects.filter(projectid=ctx.project)
    )
    sale_bd = sum(
        (c.totalamount or Decimal('0'))
        for c in BudgetConcept.objects.filter(projectid=ctx.project)
    )

    checks = []
    if excel.get('direct'):
        checks.append(ParityCheck('Costo directo total', direct_bd, excel['direct']))
    if excel.get('indirect'):
        checks.append(ParityCheck(
            'Costo indirecto total (vs G42)', indirect_bd, excel['indirect'],
            informational=True,  # G42 puede incluir externos no modelados
        ))
    if excel.get('sale_net'):
        checks.append(ParityCheck(
            'Venta neta', sale_bd, excel['sale_net'],
            informational=True,  # depende de indirecto
        ))
    return AuditResult(checks=checks)


def print_audit(result: AuditResult) -> None:
    banner('Auditoría de paridad')
    if not result.checks:
        print("  (sin checks ejecutables — Hoja Cierre Estudio no reportó totales)")
        return
    for c in result.checks:
        if c.passed:
            status = '[OK]  '
        elif c.informational:
            status = '[WARN]'
        else:
            status = '[FAIL]'
        cmp = '==' if c.delta == 0 else ('~=' if c.passed else '!=')
        print(f"  {status} {c.label:32s}  ${c.bd_value:>15,.2f}  {cmp}  "
              f"${c.excel_value:>15,.2f}  (delta ${c.delta:,.2f})")
    print()
    if result.passed:
        info_warns = [c for c in result.checks if not c.passed and c.informational]
        if info_warns:
            print("  OK: Auditoría pasó (con avisos informacionales — revisar [WARN]).")
        else:
            print("  OK: Auditoría pasó.")
    else:
        print("  ERROR: Auditoría falló (algún [FAIL] no-informational).")


def print_concept_sample(ctx: ImportContext, n: int = 5) -> None:
    """Diagnóstico: imprime conteo + suma total + primeros N conceptos."""
    all_concepts = list(BudgetConcept.objects.filter(projectid=ctx.project).order_by('code'))
    total_count = len(all_concepts)
    total_direct = sum((c.directunitcost or Decimal('0')) * (c.quantity or Decimal('0')) for c in all_concepts)
    total_amount = sum((c.totalamount or Decimal('0')) for c in all_concepts)
    total_bd = UnitCostBreakdown.objects.filter(conceptid__projectid=ctx.project).count()

    banner(f'Diagnóstico — {total_count} conceptos, {total_bd} breakdowns')
    print(f"  Sum direct = sum(directunitcost x quantity) = ${total_direct:,.2f}")
    print(f"  Sum totalamount (BD)                          = ${total_amount:,.2f}")
    print()
    print(f"  Sample de primeros {n}:")
    print(f"  {'CODE':<22s} {'QTY':>10s} {'DIRECT/U':>14s} {'P.U.':>14s} {'TOTAL':>16s}  N_BD")
    for c in all_concepts[:n]:
        n_bd = UnitCostBreakdown.objects.filter(conceptid=c).count()
        direct = c.directunitcost or Decimal('0')
        unitp = c.unitprice or Decimal('0')
        total = c.totalamount or Decimal('0')
        print(f"  {c.code[:22]:<22s} {c.quantity:>10,.2f} ${direct:>13,.2f} "
              f"${unitp:>13,.2f} ${total:>15,.2f}  {n_bd}")


# ---------------------------------------------------------------------------
# Phase orchestration
# ---------------------------------------------------------------------------
PHASES = {
    1: ('Datos Generales (Hoja Cierre Estudio)', run_fase_1),
    2: ('Conceptos (E7 Fase Estudio)', run_fase_2),
    3: ('Desglose CDU (Desglose de C.D.U.)', run_fase_3),
    4: ('Costos Indirectos (Costo Indirecto)', run_fase_4),
    5: ('Catálogo de Insumos (derivado)', run_fase_5),
    6: ('Plan de Obra (Plan de obra)', run_fase_6),
    7: ('Distribución Temporal (ProjectionPeriod)', run_fase_7),
    8: ('PNT (PNT)', run_fase_8),
}


def parse_phases_arg(spec: str) -> list[int]:
    """Parse '1-8' or '1,3,5' or '1-4,7' → sorted list of phase numbers."""
    selected = set()
    for chunk in spec.split(','):
        chunk = chunk.strip()
        if '-' in chunk:
            lo, hi = chunk.split('-', 1)
            selected.update(range(int(lo), int(hi) + 1))
        else:
            selected.add(int(chunk))
    invalid = [p for p in selected if p not in PHASES]
    if invalid:
        raise ValueError(f"Fases inválidas: {invalid}. Válidas: {sorted(PHASES.keys())}")
    return sorted(selected)


def validate_excel(xlsx_path: Path) -> None:
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Excel no encontrado: {xlsx_path}")
    sheets = list_sheets(xlsx_path)
    if not sheets or sheets[0] != 'Hoja Cierre Estudio':
        raise RuntimeError(
            f"Plantilla no reconocida. Primera hoja: {sheets[0] if sheets else '(ninguna)'}. "
            f"Esperado: 'Hoja Cierre Estudio'."
        )
    # Tolerar diferencias menores en nombres (acentos en 'Explosión')
    for expected, actual in zip(EXPECTED_SHEETS, sheets):
        if normalize_label(expected) != normalize_label(actual):
            print(f"  AVISO: hoja '{actual}' difiere de esperada '{expected}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--xlsx', required=True, help='Path absoluto al .xlsx')
    parser.add_argument('--owner-email', required=True,
                        help='Email del SystemUser para ownerid')
    parser.add_argument('--account-id', default=None,
                        help='UUID de Account existente a reusar (default: crear desde Excel)')
    parser.add_argument('--phases', default='1-8',
                        help='Subset de fases: "1-8", "1,3,5", "1-4,7" (default: 1-8)')
    parser.add_argument('--commit', action='store_true',
                        help='Persistir cambios. Sin este flag = dry-run (rollback al final).')

    # Overrides para estudios INTERNOS (Excel con celdas vacías)
    parser.add_argument('--client-name', default=None,
                        help='Override para I7 (CLIENTE). Necesario en estudios INTERNOS.')
    parser.add_argument('--presentation-date', default=None,
                        help='Override para C9 (YYYY-MM-DD).')
    parser.add_argument('--start-date', default=None,
                        help='Override para E9 (YYYY-MM-DD). Requerido si E9 vacío.')
    parser.add_argument('--bidding-type', type=int, choices=[0, 1, 2], default=None,
                        help='Override para G9: 0=LIC.PUB, 1=INV.3, 2=ADJ.DIRECTA')
    parser.add_argument('--project-type', type=int, choices=[0, 1], default=None,
                        help='Override para E12: 0=PUBLICO, 1=PRIVADO')
    parser.add_argument('--period-type', type=int, choices=[0, 1], default=None,
                        help='Override para I12: 0=SEMANAL, 1=QUINCENAL')

    args = parser.parse_args()

    xlsx_path = Path(args.xlsx).resolve()
    validate_excel(xlsx_path)

    try:
        user = SystemUser.objects.get(emailaddress1=args.owner_email)
    except SystemUser.DoesNotExist:
        sys.exit(f"ERROR: SystemUser con email '{args.owner_email}' no existe en esta BD.")

    account_id = UUID(args.account_id) if args.account_id else None
    selected_phases = parse_phases_arg(args.phases)

    presentation = date.fromisoformat(args.presentation_date) if args.presentation_date else None
    start_d = date.fromisoformat(args.start_date) if args.start_date else None

    ctx = ImportContext(
        xlsx_path=xlsx_path,
        user=user,
        account_id_override=account_id,
        client_name_override=args.client_name,
        presentation_date_override=presentation,
        start_date_override=start_d,
        bidding_type_override=args.bidding_type,
        project_type_override=args.project_type,
        period_type_override=args.period_type,
    )

    mode = 'COMMIT' if args.commit else 'DRY-RUN'
    banner(f'Import Estudio Excel — modo {mode}')
    print(f"  Excel:        {xlsx_path.name}")
    print(f"  Owner:        {user.emailaddress1}")
    print(f"  Account:      {'reuse ' + str(account_id) if account_id else '(crear desde Excel)'}")
    print(f"  Phases:       {selected_phases}")

    audit_passed = False
    try:
        with transaction.atomic():
            sid = transaction.savepoint()
            try:
                for phase_num in selected_phases:
                    label, func = PHASES[phase_num]
                    banner(f'Fase {phase_num}: {label}', char='-')
                    ctx.phase_stats[phase_num] = func(ctx)
            except Exception:
                transaction.savepoint_rollback(sid)
                raise

            if ctx.project is not None:
                print_concept_sample(ctx, n=8)
                audit = run_parity_audit(ctx)
                print_audit(audit)
                audit_passed = audit.passed
            else:
                print("\n  (sin auditoría — fase 1 no ejecutada)")
                audit_passed = True  # subset sin fase 1 no requiere paridad

            if args.commit and audit_passed:
                transaction.savepoint_commit(sid)
                banner(f'COMMITTED — EstimationProject {ctx.project.estimationnumber if ctx.project else "?"} persistido.')
            else:
                transaction.savepoint_rollback(sid)
                if not args.commit:
                    banner('DRY-RUN — rollback ejecutado. Ningún cambio persistido.')
                else:
                    banner('ERROR: Auditoría falló. Rollback ejecutado.', char='!')
                    sys.exit(2)
    except Exception as exc:
        banner(f'ERROR durante import: {exc}', char='!')
        raise


if __name__ == '__main__':
    main()
