# G2-B — OSS scan: diffing estructural de snapshots

Primer scan failure-driven de G2 (`adr-oss-scan-failure-driven.md`).
Sin cambios de producción.

## Fallo concreto

```text
dos snapshots oficiales grandes/heterogéneos
→ detectar cambios de records/campos determinísticamente
→ conservar provenance
→ ignorar reordenación/formato no semántico
→ funcionar offline
```

Formatos reales: EBA JSON EAV anidado, BdE xlsx/CSV, CNMV HTML de
detalle, ESMA CSV.

## Hallazgo de arquitectura (previo a la matriz)

FinReg ya normaliza `snapshot → claims` con provenance por claim.
Difear **bytes/tree raw** produce ruido no semántico y obliga a un
segundo mapeo de vuelta a claims para G2-C. El nivel correcto es
**records normalizados keyed por identidad** (entidad + ámbito):
`added / removed / changed(field, old→new)` — y ahí la provenance es
gratis porque cada record ya es un claim.

Eso reduce el fallo genérico a: `dict[str, dict]` → diff determinista.
La decisión de qué campos son semánticamente significativos queda en
FinReg (dominio), no en la librería.

## Candidatos

| Candidato | Licencia | Mantenimiento | Encaje | Decisión |
|-----------|----------|---------------|--------|----------|
| `dictdiffer` (inveniosoftware/CERN) | MIT | v0.10.0, estable, larga vida | diff+patch sobre dicts, salida de tuplas predecible | **REFERENCE + oráculo de test** |
| `deepdiff` (qlustered, ex-seperman) | MIT | v9.1.x activo; transferencia reciente de steward a Qluster | tree-diff anidado muy potente; salida path-based exigiría adaptación al modelo de records | **REFERENCE + oráculo de test** |
| `daff` (paulfitz) | MIT | v1.4.2 (2025-05), activo | diff tabular con alineación fila/columna — encaja con fuentes CSV/xlsx | **WRAP opcional (tooling)** si se necesita auditoría del diff tabular raw |
| `jsondiff` (ZoomerAnalytics/xlwings) | MIT | cadencia lenta | tree-diff con sintaxis compact/explicit; redundante frente a dictdiffer | **REJECT** |
| `datacompy` (capitalone) | Apache-2.0 | activo | exige pandas/polars; orientado a DataFrames, capa equivocada | **REJECT** |
| `jsonpatch` (stefankoegl) | BSD | estable | genera patches RFC6902, no es un differ de records | **REFERENCE** (vocabulario de patch si se emite delta formal) |
| differ propio sobre claims (~100 LOC) | — | — | record-diff determinista keyed por identidad, provenance nativa | **PORT_PATTERN** |

## Decisión

**PORT_PATTERN + differential testing.**

- Runtime: differ mínimo propio sobre records normalizados
  (`stdlib`, determinista, `canonical.py`), modelo de cambio tomado
  de dictdiffer (`add/remove/change(path, old→new)`).
  Razón: la operación real es pequeña (set-diff de claves +
  field-diff por clave) y la regla stdlib-only en runtime hace que
  una dependencia para ~100 LOC no pase el gate.
- Tooling: `dictdiffer` y/o `deepdiff` como **oráculos** en tests —
  differential testing de nuestro differ contra implementaciones
  maduras sobre inputs aleatorios derandomizados (mismo patrón que
  Hypothesis/mutmut: OSS en tooling, semántica en FinReg).
- `daff` queda WRAP-tooling documentado si aparece la necesidad de
  auditar el diff tabular raw de BdE/ESMA independientemente de la
  extracción.

## Por qué no ADOPT directo

- `stdlib-only` en runtime es convención no negociable con test que la
  fija; un dep runtime por esta operación no supera el gate.
- El valor de dictdiffer/deepdiff (recursión genérica, ignore_order,
  hashing) no se necesita: los records ya son flat dicts
  normalizados por la capa de extracción, que es la parte difícil y
  ya está hecha.
- La dependencia sí aporta valor como oráculo: differential testing
  detecta divergencias de nuestro differ sin meterla en producción.

## Siguiente paso (G2-A)

Antes del differ: congelar el **snapshot history contract** —
`observed_at` / `source_as_of` / `effective_at` por fuente, y qué
significa "dos snapshots de la misma fuente" (identidad de snapshot,
orden, completitud). El differ se preregistra contra ese contrato.
