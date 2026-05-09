"""Compare CDU sheet codes vs imported BudgetConcept codes."""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from apps.proyeccion.models import EstimationProject, BudgetConcept

XLSX = Path(r'C:\TestAI\erp_project\docs\samples\001. Estudio Oferta Entronque San Cristobal COMPLETO.xlsx')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

z = zipfile.ZipFile(str(XLSX))
ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
shared = [
    ''.join(t.text or '' for t in si.iter(f'{NS}t'))
    for si in ss.findall(f'{NS}si')
]
tree = ET.fromstring(z.read('xl/worksheets/sheet3.xml'))

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
        col = ''.join(ch for ch in ref if ch.isalpha())
        rows[r][col] = val

# Get DB codes
project = EstimationProject.objects.get(estimationnumber='EST-2026-009')
db_codes = set(c.code for c in BudgetConcept.objects.filter(projectid=project))
print(f'Concepts en DB: {len(db_codes)}')

# Iterate CDU blocks (every 43 rows from R11)
r = 11
cdu_real = []
cdu_with_data = []
while r in rows:
    rr = rows[r]
    code = (rr.get('C') or '').strip()
    desc = (rr.get('D') or '').strip()
    if code and desc and desc != '-':
        cdu_real.append(code)
        # check non-zero detail amount
        for r2 in range(r + 1, r + 42):
            v = (rows.get(r2, {}).get('I', '') or '').strip()
            try:
                if float(v) > 0:
                    cdu_with_data.append(code)
                    break
            except (TypeError, ValueError):
                pass
    r += 43

print(f'Bloques CDU con descripcion != "-": {len(cdu_real)}')
print(f'Bloques CDU con detalle no-cero:    {len(cdu_with_data)}')

in_cdu_not_db = sorted(set(cdu_real) - db_codes)
in_db_not_cdu = sorted(db_codes - set(cdu_real))

print(f'\nEn CDU pero NO en DB ({len(in_cdu_not_db)}):')
for c in in_cdu_not_db[:20]:
    print(f'  {c}')

print(f'\nEn DB pero NO en CDU ({len(in_db_not_cdu)}):')
for c in in_db_not_cdu[:20]:
    print(f'  {c}')

# Codes in DB and CDU intersection (most important)
both = sorted(db_codes & set(cdu_real))
print(f'\nEn ambos: {len(both)}')

# Of those in both, how many have actual non-zero data in CDU?
both_with_data = sorted(db_codes & set(cdu_with_data))
print(f'En ambos con detalle no-cero: {len(both_with_data)}')
