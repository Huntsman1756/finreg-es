# G2-A — Snapshot history contract

Contrato congelado de semántica temporal y comparabilidad para
evidencia longitudinal. Documental: no introduce producción.
Deriva de `g2-scope.md` y `g2-b-oss-scan-diff.md` (diff sobre records
normalizados, no sobre bytes raw).

## 0. Conceptos ya congelados (no se redefinen)

| Concepto | Semántica congelada | Origen |
|----------|--------------------|--------|
| `retrieved_at` | instante en que FinReg obtuvo los bytes; transaction/observation time; nunca fecha jurídica | ancla G0.6-A |
| `source_as_of` | fecha de vigencia/corte declarada por la autoridad; nullable; **su ausencia se declara (`UNAVAILABLE`), nunca se rellena con `retrieved_at`** | ancla G0.6-A; `supports_source_as_of` exige verificación VERIFIED |
| `effective_from` / `effective_to` | valid time jurídico del hecho; intervalo `[from, to)`, `to` exclusivo; sólo cuando la fuente lo demuestra | semántica G1-E |
| `EVIDENCE_AS_OF` | fallback probatorio: "ya era cierto al observarlo", sin fecha jurídica de inicio | derivation (kind) |
| `freshness_at` | `source_as_of ?? retrieved_at`; staleness se mide sobre él, nunca sobre efecto jurídico | `temporal.py` |
| `source_date_reliability` | `TRUSTED / SUSPECT / UNAVAILABLE`; metadato de provenance, no consumido por `is_stale` | `temporal.py` |
| `lineage_observed_at` | instante del export, no de la observación | export OpenLineage |

No existe ni se crea un `effective_at` genérico: una entidad puede
tener varias fechas jurídicamente distintas (G1 lo demostró).

## 1. Observation ≠ content

```text
observation_id = source + retrieved_at + content_sha256
content_id     = sha256(bytes)
```

Dos descargas en fechas distintas con el mismo `content_id` son dos
observaciones del mismo contenido: la segunda puede renovar evidencia
de actualidad (frescura), pero produce **cero** structural changes.
Un diff nunca compara observaciones del mismo `content_id`.

## 2. Identidad de serie

```text
snapshot_series_key =
  register_id
  + dataset/view
  + jurisdiction/scope cuando proceda
```

"Misma fuente" no es sólo `register_id`. Dos exports distintos del BdE
no se comparan entre sí por ser ambos BdE. Un diff entre series
distintas es un error de invocación, no un resultado.

## 3. `record_key` es contrato por fuente

`record_key` ya es ancla de provenance (G0.6-A). G2 lo eleva a
especificación versionada por fuente. Reglas:

- versionado junto al extractor (`extractor_version`);
- no puede incluir campos mutables (nombre comercial, domicilio,
  fecha del registro);
- `EntityVersion` es evidencia/versionado, no identidad longitudinal.

Especificaciones conceptuales por fuente:

```text
EBA    EntityCode + EntityType
BdE    CODIGO_BE + dataset/view
ESMA   identificador estable + route/category cuando proceda
CNMV   identificador registral estable
```

Las especificaciones concretas se preregistran en G2-D al congelar
el corpus longitudinal.

## 4. Extractor drift no es regulatory drift

```text
raw S1 immutable                    raw S2 immutable
       ↓                                   ↓
re-extract bajo NORMALIZATION_Vx   re-extract bajo NORMALIZATION_Vx
       ↓                                   ↓
              records S1 ── diff ── records S2
```

La unidad de comparación es
`(snapshot_series_key, normalization_version)`, donde
`normalization_version` cubre extractor + reglas de normalización.

- Dos snapshots sólo se difean si pueden normalizarse bajo **la
  misma versión**. Los bytes raw son inmutables; la re-extracción se
  aplica a ambos lados, no sólo al nuevo.
- Si no pueden normalizarse bajo la misma semántica:

```text
NON_COMPARABLE_NORMALIZATION_VERSION
```

  que es un finding de comparabilidad, **nunca** un cambio regulatorio.

## 5. Completitud pertenece al snapshot/slice

Un `record_key` ausente en el snapshot derecho significa
**"no observado en esa captura"**, nada más.

```text
present → absent en pareja completa y comparable
    ⇒ STRUCTURAL_REMOVAL admisible

present → absent en captura parcial / slice incompleto /
    series distintas / normalizaciones distintas
    ⇒ NO_REMOVAL_ADMISSIBLE
```

`STRUCTURAL_REMOVAL` no es una conclusión jurídica: baja, retirada o
pérdida de entitlement lo decide G2-C con las reglas del dominio.
La completitud se declara por slice en el manifiesto del snapshot
(series_key + universo afirmado por la fuente en esa captura).

## 6. Sets ≠ sequences

Antes de cualquier diff, cada campo se clasifica por contrato:

```text
scalar                 comparación directa
set/multivalue         no ordenado — reordenación ⇒ 0 cambios
ordered sequence       orden semántico — reordenación cuenta
nested keyed records   se compone recursivamente por clave
```

Casos congelados:

- reordenar `Services{ES}` ⇒ cero cambios;
- `missing` y `null` son **distintos**: `field→null` y
  `field removed` son eventos estructurales diferentes;
- el modelo de cambio es el del scan G2-B:
  `added / removed / changed(field, old→new)` sobre records keyed.

## 7. Tiempo de detección ≠ tiempo jurídico

```text
S1 retrieved 2026-05-01 : ACTIVE
S2 retrieved 2026-06-01 : WITHDRAWN
```

Sin fecha oficial de retirada, FinReg sólo sabe:

```text
change observed between (2026-05-01, 2026-06-01]
```

Si la fuente publica retirada `2026-05-17`, entonces
`effective_from = 2026-05-17`. El differ **nunca** fabrica esa fecha:
emite el intervalo de observación; la fecha jurídica la aporta la
fuente o no existe. Sin ella, el evento queda acotado al intervalo y
`EVIDENCE_AS_OF` sigue siendo el mecanismo probatorio.

## 8. Dos dimensiones temporales de la query

G2 formaliza la bitemporalidad como capacidad de consulta:

```text
valid_at = ¿qué era jurídicamente cierto en T?
known_at = ¿qué evidencia había observado FinReg hasta K?
```

Son preguntas distintas:

```text
valid_at = 2026-05-17, known_at = 2026-05-20
  → INDETERMINATE admisible (la retirada aún no era observable)

valid_at = 2026-05-17, known_at = 2026-06-01
  → retrospectivamente puede conocerse la retirada efectiva del 17/05
```

Regla anti-retroproyección: una query con `known_at = K` sólo consume
claims con `retrieved_at <= K`. El conocimiento actual no reescribe
assessments históricos; `known_at = now` reproduce el comportamiento
actual.

## 9. Estados de sucesión de la serie

```text
NORMAL_SUCCESSION
  source_as_of aumenta (o primera observación con source_as_of)

SAME_AS_OF_REVISION
  mismo source_as_of, contenido distinto
  → corrección/republicación, no un nuevo periodo jurídico
  → mapped a source_date_reliability = SUSPECT (regla congelada
    en temporal.py); se marca, no se descarta ni crea periodo

SOURCE_AS_OF_REGRESSION
  source_as_of retrocede
  → finding; bloquea inferencia automática de sucesión

UNKNOWN_SOURCE_AS_OF
  sólo retrieved_at disponible (source_date_reliability=UNAVAILABLE)
  → la serie ordena por retrieved_at; frescura por freshness_at
```

`SUSPECT` ya existe como clasificación de fiabilidad; G2-A la eleva a
estado de sucesión sin cambiar su semántica.

## 10. Matriz por fuente (borrador a congelar en G2-D)

| Fuente | series_key | source_as_of | Completitud por slice | Histórico |
|--------|-----------|--------------|----------------------|-----------|
| EBA | register + EntityType scope | fecha de publicación del registro | export completo por clase | sin series públicas — corpus propio |
| BdE | register + dataset/view | fecha de actualización declarada | listado completo del registro | descargas periódicas |
| ESMA | register + route/category | fecha de corte declarada | completo por categoría | descargas periódicas |
| CNMV | register + sección | variable por registro | captura de detalle — **no** completa | descargas puntuales |

CNMV es la fuente donde `present → absent` casi nunca será admisible
como `STRUCTURAL_REMOVAL` (capturas puntuales, no listados completos).

## 11. Casos preregistrados para G2-B

Antes de escribir el differ, estos casos fijan su contrato:

```text
B01  misma observación repetida (mismo content_id)      → 0 diff
B02  reordenación de campos/sets                        → 0 diff
B03  mismo source_as_of + contenido distinto            → SAME_AS_OF_REVISION
B04  record añadido                                     → added
B05  record ausente en captura parcial                  → NO_REMOVAL_ADMISSIBLE
B06  record ausente entre capturas completas comparables → STRUCTURAL_REMOVAL
B07  extractor v1 × extractor v2                        → NON_COMPARABLE_NORMALIZATION_VERSION
B08  cambio con fecha jurídica publicada                → effective_from = fecha fuente
B09  mismo cambio sin fecha jurídica                    → intervalo (t1, t2], sin effective_from
B10  field presente→null vs field removed               → eventos distintos
B11  source_as_of retrocede                             → SOURCE_AS_OF_REGRESSION (finding)
B12  reordenación en campo declared-ordered             → changed (sí cuenta)
```

## 12. Lo que este contrato no decide

- Qué cambio estructural es jurídicamente relevante: G2-C.
- Qué entidades del corpus longitudinal se congelan: G2-D.
- Si `known_at` retroactivo admite evidencia *revocada* posteriormente
  (claim observado antes de K pero corregido después): decisión
  diferida hasta tener un caso real en el corpus.
