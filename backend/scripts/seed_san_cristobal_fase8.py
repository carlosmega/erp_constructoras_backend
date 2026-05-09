"""Fase 8 — PNT (Posicion Neta de Tesoreria): parametros financieros del proyecto.

Lee la hoja `PNT` y crea/actualiza:
  - EstimationFinancialSettings (1:1 con el proyecto): anticipo, retenciones,
    lag de pagos, finance cost rate.
  - EstimationBillingRule[]: tranches de cobro al cliente.

Estructura de la hoja (filas relevantes):
  - R16 C='COBRO FACTURACION (0/15/30/45/60)', D=lag_dias_cobro
  - R17 C='ANTICIPO CONCEDIDO', D=tasa_anticipo (decimal), E=importe_anticipo
  - R18 C='ANTICIPO AMORTIZADO', D=tasa_amortizacion (decimal)
  - R19 C='RETENCIONES IMSS', D=tasa_imss (decimal)
  - R20 C='OTRAS RETENCIONES', D=tasa_otras (decimal, opcional)
  - R23 C='PAGOS COSTO DIRECTO' (header)
  - R25 C='TRANSF (VALOR 30/60/...)', D=lag_directo_dias
  - R27 C='TRANSFERENCIA COSTE CONTABLE (VALOR 30/...)', D=lag_indirecto_dias

Conversion dias → periodos: round(dias / period_days_per_period).
  periodtype 0 (semanal) → 7 dias/period
  periodtype 1 (quincenal) → 15 dias/period

Filas R32+ son distribucion de pagos por familia/insumo — TODAS estan en 0
en este Excel piloto, por lo que NO se actualiza paymentlagperiods por linea.
Si en otro Excel hubiera lags distintos por categoria, se podria iterar.
"""
import unicodedata
from decimal import Decimal, InvalidOperation
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from django.db import transaction

from apps.proyeccion.models import (
    EstimationProject,
    EstimationFinancialSettings,
    EstimationBillingRule,
)
from apps.users.models import SystemUser

EXCEL_PATH = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
SHEET_INDEX = 9  # 'PNT'
ESTIMATION_NUMBER = 'EST-2026-009'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def to_decimal(s, default='0'):
    try:
        s = str(s).strip()
        if not s:
            return Decimal(default)
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def to_int(s, default=0):
    try:
        return int(float(str(s).strip())) if str(s).strip() else default
    except (ValueError, TypeError):
        return default


def days_to_periods(days: int, periodtype: int) -> int:
    """Convierte dias a numero de periodos del proyecto."""
    if periodtype == 0:
        return round(days / 7)
    return round(days / 15)  # quincenal default


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


def _normalize(s: str) -> str:
    """Upper + sin acentos para matching robusto contra labels del Excel."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').upper()


def find_row_by_label(rows: dict, label_substring: str) -> int | None:
    """Busca la primera fila cuya columna C contenga el substring (case- y accent-insensitive)."""
    target = _normalize(label_substring)
    for r in sorted(rows.keys()):
        c_val = _normalize((rows[r].get('C') or '').strip())
        if target in c_val:
            return r
    return None


def parse_pnt_inputs(rows: dict, periodtype: int) -> dict:
    """Extrae los inputs financieros de las primeras 30 filas de la hoja."""
    inputs = {}

    # Cobro facturacion (lag al cliente)
    r = find_row_by_label(rows, 'COBRO FACTURACION')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['client_lag_days'] = days
        inputs['client_lag_periods'] = days_to_periods(days, periodtype)

    # Anticipo concedido
    r = find_row_by_label(rows, 'ANTICIPO CONCEDIDO')
    if r:
        inputs['advance_rate'] = to_decimal(rows[r].get('D', '0'))
        # Importe del anticipo: columna E (primer periodo) o CQ (total)
        amount = to_decimal(rows[r].get('CQ') or rows[r].get('E', '0'))
        inputs['advance_amount'] = amount
        inputs['advance_entry_period'] = 1  # default: anticipo en P1

    # Anticipo amortizado (tasa)
    r = find_row_by_label(rows, 'ANTICIPO AMORTIZADO')
    if r:
        inputs['advance_amortization_rate'] = to_decimal(rows[r].get('D', '0'))

    # Retenciones IMSS
    r = find_row_by_label(rows, 'RETENCIONES IMSS')
    if r:
        inputs['imss_retention_rate'] = to_decimal(rows[r].get('D', '0'))

    # Otras retenciones
    r = find_row_by_label(rows, 'OTRAS RETENCIONES')
    if r:
        inputs['other_retention_rate'] = to_decimal(rows[r].get('D', '0'))

    # Pagos costo directo (lag) — buscar TRANSF (VALOR ...
    # en seccion PAGOS COSTO DIRECTO. Tomar primer match.
    r = find_row_by_label(rows, 'TRANSF (VALOR')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['direct_lag_days'] = days
        inputs['direct_lag_periods'] = days_to_periods(days, periodtype)

    # Lag indirecto (TRANSFERENCIA COSTE CONTABLE)
    r = find_row_by_label(rows, 'TRANSFERENCIA COSTE CONTABLE')
    if r:
        days = to_int(rows[r].get('D', '0'))
        inputs['indirect_lag_days'] = days
        inputs['indirect_lag_periods'] = days_to_periods(days, periodtype)

    return inputs


def import_pnt(project: EstimationProject, inputs: dict, user) -> dict:
    """Crea/actualiza EstimationFinancialSettings + EstimationBillingRule."""
    stats = {
        'settings_created': False,
        'billing_rules_created': 0,
    }

    with transaction.atomic():
        # 1) FinancialSettings (1:1 con el proyecto)
        settings, created = EstimationFinancialSettings.objects.update_or_create(
            projectid=project,
            defaults={
                'advanceamountnotax': inputs.get('advance_amount', Decimal('0')),
                'advanceentryperiod': inputs.get('advance_entry_period', 1),
                'advanceamortizationrate': inputs.get('advance_amortization_rate', Decimal('0')),
                'imssretentionrate': inputs.get('imss_retention_rate', Decimal('0.05')),
                'otherretentionrate': inputs.get('other_retention_rate', Decimal('0')),
                'directpaymentlag': inputs.get('direct_lag_periods', 0),
                'indirectpaymentlag': inputs.get('indirect_lag_periods', 0),
                # financecostrate y retentionreturnperiod no vienen del Excel — defaults
                'createdby': user,
                'modifiedby': user,
            },
        )
        stats['settings_created'] = created

        # 2) Billing rule: 1 tranche 100% al lag indicado
        # Borrar reglas existentes y recrear (idempotente)
        EstimationBillingRule.objects.filter(projectid=project).delete()
        if 'client_lag_periods' in inputs:
            EstimationBillingRule.objects.create(
                projectid=project,
                sequence=1,
                percent=Decimal('1.0000'),  # 100%
                lagperiods=inputs['client_lag_periods'],
                createdby=user,
                modifiedby=user,
            )
            stats['billing_rules_created'] = 1

    return stats


def run():
    project = EstimationProject.objects.get(estimationnumber=ESTIMATION_NUMBER)
    user = SystemUser.objects.get(emailaddress1='admin@crm.com')

    rows = read_sheet(EXCEL_PATH, SHEET_INDEX)
    inputs = parse_pnt_inputs(rows, project.periodtype)

    print('=== Inputs detectados en hoja PNT ===')
    for key in [
        'client_lag_days', 'client_lag_periods',
        'advance_rate', 'advance_amount', 'advance_entry_period',
        'advance_amortization_rate',
        'imss_retention_rate', 'other_retention_rate',
        'direct_lag_days', 'direct_lag_periods',
        'indirect_lag_days', 'indirect_lag_periods',
    ]:
        val = inputs.get(key, '(no encontrado)')
        if isinstance(val, Decimal):
            print(f'  {key:30s}  {val}')
        else:
            print(f'  {key:30s}  {val}')

    stats = import_pnt(project, inputs, user)

    print()
    print('=== Importacion fase 8 completada ===')
    action = 'creado' if stats['settings_created'] else 'actualizado'
    print(f'  EstimationFinancialSettings:  {action}')
    print(f'  EstimationBillingRule:        {stats["billing_rules_created"]} regla(s)')

    # Verificar lo que quedo en BD
    print()
    print('=== Estado final en BD ===')
    settings = EstimationFinancialSettings.objects.get(projectid=project)
    print(f'  Anticipo s/IVA:                ${settings.advanceamountnotax:,.2f}')
    print(f'  Periodo entrada anticipo:      {settings.advanceentryperiod}')
    print(f'  Tasa amortizacion anticipo:    {settings.advanceamortizationrate}')
    print(f'  Retencion IMSS:                {settings.imssretentionrate}')
    print(f'  Otras retenciones:             {settings.otherretentionrate}')
    print(f'  Lag pago directo (periodos):   {settings.directpaymentlag}')
    print(f'  Lag pago indirecto (periodos): {settings.indirectpaymentlag}')
    print(f'  Finance cost rate:             {settings.financecostrate}')

    print()
    print('  Billing rules:')
    for rule in EstimationBillingRule.objects.filter(projectid=project).order_by('sequence'):
        print(f'    #{rule.sequence}: {float(rule.percent)*100:.0f}% @ +{rule.lagperiods} periodos')


if __name__ == '__main__':
    run()
