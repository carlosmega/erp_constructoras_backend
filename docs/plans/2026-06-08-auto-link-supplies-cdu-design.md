# Auto-ligar insumos del Desglose C.D.U. al Catálogo (2026-06-08)

## Problema

En el Desglose C.D.U., el editor inline (`breakdown-inline-row.tsx`) captura las líneas como **texto libre** (descripción/unidad/cantidad/precio/rendimiento) y **nunca setea `supplyid`** → las líneas quedan sin ligar al catálogo (`SupplyCatalogItem`).

Consecuencia: la **Explosión de Insumos** (`SupplyExplosionService.generate_consolidated`, filtra `supplyid__isnull=False`) sale vacía → el paso 6 del Costeo nunca se completa (se atora en 67%), no hay lista de compras consolidada, no se puede fijar lag de pago por insumo, y el catálogo no se reutiliza (re-tecleo en cada proyecto).

Caso real: `EST-2026-004` (id `42aeb593-...`) tiene 32 líneas, 0 con `supplyid`.

## Decisiones (validadas con el usuario)

1. **Comportamiento**: auto-crear y ligar al guardar (no un selector manual).
2. **Dónde**: en el **servicio backend** (`create_breakdown`/`update_breakdown`), no en la UI → funciona por cualquier vía (editor inline, import).
3. **Match**: **flexible** (similitud, umbral bajo) — agrupa variantes ("Diesel Excavadora"/"Diesel D6T" → un insumo).
4. **Alcance**: remediar (lo existente, vía backfill) + prevenir (nuevas, al guardar).
5. **No destructivo**: ligar SOLO setea la columna `supplyid`. La `description` de la línea (y qty/precio/amount) **nunca se toca**. La línea conserva "Diesel Excavadora"; solo gana un puntero al insumo.
6. **Transparencia**: cada línea muestra a qué insumo quedó ligada; re-ligar es 1 clic (red de seguridad del match flexible).

## Diseño

### Motor: `match_or_create_supply(description, categorycode, unit, unitprice, user)`
- Normaliza descripción (minúsculas, sin acentos, espacios colapsados).
- Acota por **tipo** derivado del `categorycode` (Materiales→Material, Maquinaria→Maquinaria, M.O.→ManoObra, Subcontratos→Subcontrato, Acarreos→Acarreo).
- **Similitud en Python** (token-set ratio) sobre el subconjunto del catálogo de ese tipo — NO `pg_trgm`, para paridad dev(SQLite)/prod(Postgres). Catálogo chico → barato.
- Si mejor match ≥ umbral (configurable, p.ej. `SUPPLY_MATCH_THRESHOLD = 0.7`) → liga ese insumo. Si no → crea nuevo (código auto por prefijo de tipo vía `core/numbering`, `referenceprice = unitprice`).
- **Omite** líneas de fórmula: categorías Herramienta (6) y EPP (7) / unidad "%" → no crea insumo (quedan sin ligar a propósito; el Costeo se completa con el resto).

### Enganche (prevención)
- En `create_breakdown` y `update_breakdown`: si la línea se guarda **sin `supplyid` explícito**, llamar `match_or_create_supply` y asignar. Respetar `supplyid` explícito si la UI/import ya lo manda.

### Backfill (remediación)
- `POST /api/proyeccion/projects/{id}/supply-explosion/backfill-supplies/` → corre el motor sobre todas las líneas `statecode=0` sin ligar del proyecto. Atómico, idempotente, devuelve `{ligadas, creadas, omitidas}`.
- Reemplaza el script a mano de EST-2026-004.

### Frontend
- Badge ámbar "fuera de catálogo" en líneas con `supplyid` nulo.
- `supplyname` clickeable → reúso de `supply-multi-select-dialog` para re-ligar/crear.
- Botón "Ligar insumos al catálogo (N)" → llama backfill → toast → invalida desglose + explosión.

### Casos borde
- Herramienta/EPP (%): omitidos del auto-crear.
- Código auto / colisión: `core/numbering.create_with_retry`.
- Concurrencia: `match_or_create` dentro de transacción.
- Match equivocado: re-ligar a 1 clic.

## Plan de implementación (TDD)

**Backend** (rama `feat/auto-link-supplies-cdu`)
1. `match_or_create_supply` + tests (reúso exacto, fusión flexible, crea si no hay, no cruza tipos, omite Herramienta/EPP, código único).
2. Enganche en `create_breakdown`/`update_breakdown` + tests (autoliga sin supplyid; respeta explícito).
3. Backfill service + endpoint + tests (idempotente; fixture sin ligar → consolidado>0 / Costeo 3/3).

**Frontend** (misma rama en `erp_constructoras`)
4. Badge + supplyname clickeable + diálogo re-ligar.
5. Botón masivo + invalidación.
6. tsc/eslint/vitest verdes.

**Deploy**: PR backend → main → CD; luego PR frontend → main → CD. Backfill de EST-2026-004 en prod tras deploy (botón o endpoint).

## Pruebas
- Backend: pytest unit + integración (ver pasos 1-3).
- Frontend: vitest (badge, botón, diálogo).
- Manual dev: capturar línea libre → verificar autoliga + aparece en Explosión.
