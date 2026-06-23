# Retiros editables por periodo (Transversal + Utilidad) en Distribución Temporal

**Fecha:** 2026-06-22
**Estado:** Diseño aprobado (brainstorming con el usuario)
**Módulo:** Proyección → Distribución Temporal / PNT (Tesorería)

---

## 1. Problema y motivación

Hoy el **retiro de utilidades** y el **retiro transversal** del PNT/Tesorería se calculan
automáticamente y son **de solo lectura**:

```python
# services.py — CostDistributionService.compute_rollups (~3842-3843)
base_cost          = [d + i for d, i in zip(direct_by_period, indirect_by_period)]
retiro_by_period   = [round2(c * trans_factor) for c in base_cost]   # transversal
utility_by_period  = [round2(c * prof_factor)  for c in base_cost]   # utilidad
```

Es decir: cada periodo retira `(directo+indirecto del periodo) × %`, proporcional al costo,
**devengado y sin lag**. El usuario no puede decidir *en qué periodos* se retira.

**Requerimiento (validado con el usuario):** que ambos retiros sean **editables por periodo**,
manteniendo el **monto total fijo** (= `% × costo base`), cambiando **solo el timing** de caja.

### Decisiones tomadas

| Decisión | Resultado |
|---|---|
| ¿Editar el total o solo el cuándo? | **Solo el cuándo.** Total pinned = `% × costo(directo+indirecto)`. |
| ¿Mecanismo? | **Fila editable celda por celda** en la matriz, default = forma actual. |
| ¿Alcance? | **Los dos retiros** (Transversal y Utilidad) — son idénticos mecánicamente. |
| ¿Dónde vive? | **Dentro de Distribución Temporal** (no en el PNT, que sigue siendo reporte). |
| ¿Default? | Proporcional al costo → **reproduce lo de hoy**; editar es un override. |
| ¿Cuadre? | **Checksum de aviso, no bloquea** (consistente con líneas de costo). |

---

## 2. Relación financiera (placement)

La utilidad y el transversal son **sumandos de TOTAL COSTO**, hoy ocultos dentro de esa fila:

```
   Directo + Indirecto              (base)
 + Retiro Transversal   ← editable  (= %transv × base)
 + Retiro Utilidad      ← editable  (= %util   × base)
 ─────────────────────────────
 = TOTAL COSTO / PERÍODO
   VENTA / PERÍODO                  (del Plan de Obra)
   MARGEN = VENTA − TOTAL COSTO     (residual, aguas abajo)
```

- **No es Venta** (lado ingreso) ni **Margen** (residual aguas abajo de los retiros).
- Se exponen como **dos filas nuevas** en la banda de costo de la matriz, marcadas
  "(incluido en Total Costo)" para que nadie crea que se suman encima.

**Utilidad ≠ Margen:** Utilidad = lo que se pricea y se decide *retirar* (`%util × costo`).
Margen = sobrante real `Venta − Costo total` (≈0 si todo cuadra con la oferta).

---

## 3. Modelo de datos

Una sola tabla genérica, que **espeja `CostDistribution`** pero discriminada por `kind`
(en vez de FK a una línea de costo):

```python
class RetiroKind(IntegerChoices):
    TRANSVERSAL = 0
    UTILIDAD    = 1

class RetiroDistribution(AuditMixin):
    retirodistributionid = UUIDField(pk)
    projectid   = FK(EstimationProject, related_name='retiro_distributions')
    kind        = IntegerField(choices=RetiroKind.choices)
    periodnumber= IntegerField()                 # 1..N
    fraction    = DecimalField(max_digits=12, decimal_places=8)  # peso del periodo (0..1)
    isderived   = BooleanField(default=True)     # true=auto / false=editado a mano
    version     = IntegerField(default=0)        # lock optimista por celda
    modifiedby  = FK(SystemUser, null=True)
    class Meta:
        unique_together = [('projectid', 'kind', 'periodnumber')]
        constraints = [CheckConstraint(0 <= fraction <= 1)]
```

**Convenciones reusadas:** almacena **fracción** (no monto, así cambiar costos re-escala solo),
flag **`isderived`**, **`version`** para lock optimista por celda.

**Sin data-migration:** los estudios existentes no tienen filas → se comportan como hoy
(derivado). Las filas se crean *lazy* al primer edit.

---

## 4. Cálculo (compute_rollups)

Refactor de las 2 líneas actuales a un helper genérico por `kind`:

```
pinned_total(kind) = factor(kind) × sum(base_cost)        # invariante: NO cambia con el timing
shape(kind):
    si hay override manual (filas con isderived=False) → fraction[p] guardada
    si no                                               → fraction[p] = base_cost[p] / sum(base_cost)
retiro[p] = round2( pinned_total × shape[p] )
```

- `factor(TRANSVERSAL) = trans_pct/100`, `factor(UTILIDAD) = prof_pct/100` (de la alternativa `ischosen`).
- **Invariante clave:** `sum(retiro_by_period) == pinned_total` siempre (independiente del reparto).
- `compute_rollups` sigue devolviendo `retiro_by_period` / `utility_by_period` con la misma forma
  de hoy cuando no hay override → **paridad exacta** (golden test).

El **PNT** (`EstimationPNTCalculator`, filas `RETIRO_TRANSV` / `RETIRO_UTILIDADES`) **solo lee**
estos vectores → fuente única de verdad en Distribución Temporal. Siguen devengados sin lag.

**Consecuencia intencional:** re-timing de retiros cambia el **TOTAL COSTO por periodo** y la
**Caja Acumulada** del PNT, pero **no** los totales.

---

## 5. API (extender, no inventar rutas)

| Endpoint | Cambio |
|---|---|
| `GET  /cost-distribution/` | `build_payload` incluye 2 filas de retiro (fracciones, total pinned, `isderived`, `version`) además de la jerarquía. |
| `PATCH /cost-distribution/bulk/` | `apply_bulk_edits` acepta celdas con `kind=TRANSVERSAL\|UTILIDAD`, mismo `expected_version` + atomicidad. |
| `POST /cost-distribution/reset-line/` | Resetea una fila de retiro a su forma derivada (proporcional al costo). |

**Regenerar periodos:** `regenerate_projection_periods` respeta la misma regla `isderived`
(preserva manual, recalcula derivado).

---

## 6. UI (frontend — reusar, no reconstruir)

Dos filas (`Retiro Transversal`, `Retiro Utilidad`) en la banda de costo de la matriz, usando:
- `distribution-cell.tsx` (celda editable %/$),
- buffer + guardado por lote de `useDistributionEdits`,
- lock optimista (`version` + `conflict-resolution-dialog.tsx`),
- checksum como chip de aviso, presencia.
- Botón **Restablecer** por fila.

Piezas nuevas: solo el render de las 2 filas + el botón Restablecer + tipos del payload.

---

## 7. Edge cases

- **Sin alternativa elegida** → `% = 0` → filas en $0 (comportamiento de hoy).
- **Cambian costos o %** → total pinned se recalcula; fracciones manuales se mantienen; $/celda re-escala.
- **Checksum ≠ total** → avisa, no bloquea.
- **Regenerar/extender periodos** → preserva celdas manuales, recalcula derivadas.
- **Concurrencia** → `VersionConflict` → diálogo existente.

---

## 8. Testing

- **Golden/paridad (crítico):** sin filas de retiro, `retiro_by_period`/`utility_by_period`
  reproducen exactamente lo de hoy → ningún estudio existente cambia.
- **Invariante:** `sum(retiro) == % × base` sin importar las fracciones.
- `apply_bulk_edits` para ambos `kind` con lock + conflicto; `reset_line` restaura derivado;
  regenerar preserva manual.
- **PNT** lee la forma redistribuida y su total no cambia.
- Frontend: render de las 2 filas, modo edición, %/$, checksum, reset, conflicto.

---

## 9. Despliegue

- Migración **aditiva** (nueva tabla `RetiroDistribution`) → segura, sin downtime, sin data-migration.
- **Orden cross-repo:** backend primero (modelo + migración + endpoints + tests), luego frontend.
  PR por repo; mergear backend → deploy → frontend.
- Backward-compatible: lo viejo sigue derivado hasta que alguien edite.
