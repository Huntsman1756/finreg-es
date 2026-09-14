# G2-B — Structural snapshot diff

Implementación del differ estructural según el contrato
`g2-snapshot-history-contract.md` y la decisión del scan
`g2-b-oss-scan-diff.md` (PORT_PATTERN + differential testing).

## Componentes

```text
finreg_es/snapshot_diff.py
  ObservationRef            identidad de observación (§1-§5)
  diff_value / diff_records differ estructural genérico, stdlib
  compare_observations      gates de comparabilidad + salida
                            {comparison, changes} separada

finreg_es/snapshot_normalize.py
  FINREG_G2_EBA_NORMALIZATION_V1
  normalize_eba_psd2_zip    EBA zip → {record_key: record}
                            record_key = EntityType:EntityCode
```

Las clases de campo viven en la normalización: `set` sale ordenado
(reordenar ⇒ 0 cambios), `ordered` conserva orden, `nested keyed` se
compone por clave, `missing` nunca se sintetiza. `__EBA_EntityVersion`
queda excluido (stamp mutable, §3); `__EBA_Disclaimer` no es un record.

## Casos preregistrados B01–B12

Todos binding en `tests/g2/test_g2b_snapshot_diff.py` (15 tests):

```text
B01  mismo content_id → short-circuit, 0 diff sin entrar al differ
B02  sets reordenados → 0 (canonicalizados en normalización)
B03  mismo source_as_of + contenido distinto → SAME_AS_OF_REVISION
B04  record añadido → added
B05  ausente en captura parcial → NO_REMOVAL_ADMISSIBLE
B06  ausente entre capturas completas → removal admisible
B07  normalization v1×v2 → NON_COMPARABLE_NORMALIZATION_VERSION
B08/B09  salida lleva observation_ids, nunca fechas jurídicas
B10  presente→null ≠ removed
B11  source_as_of retrocede → SOURCE_AS_OF_REGRESSION
B12  reorden en campo ordered → changed
```

## Resultado sobre el par real EBA (D0.1)

```text
O1  2026-09-13  sha 948429ad…  source_as_of 2026-09-13T08:00:04Z
O2  2026-09-14  sha 8e28bb25…  source_as_of 2026-09-14T16:00:14Z

succession_state     NORMAL_SUCCESSION
records              330.291 = 330.291
added / removed / changed = 0 / 0 / 0
```

El par EBA demuestra el caso A preregistrado: **bytes distintos, cero
cambios estructurales** — la diferencia de SHA era no semántica para
FinReg (verified: la sección de entidades es byte-idéntica entre ambos
JSON; la variación está fuera de los records). `RAW SHA ≠ change`
queda probado con datos oficiales, no con sintéticos.

BdE servicios-pago (D0.1): mismo `content_id` en ambas observaciones →
Type-A fuerte, 0 diff por short-circuit (B01 real).

Artefacto: `fixtures/g2/comparisons/eba-psd2-20260913-vs-20260914.json`.

## Differential oracle

`tests/g2/test_g2b_oracles.py`: Hypothesis derandomizado (400+200
casos) compara `diff_records` contra `dictdiffer` — el conjunto de
record_keys tocadas coincide exactamente, más propiedades de
determinismo y simetría inversa. dictdiffer entra como dependencia de
tooling, no de runtime (runtime sigue stdlib-only).

## Lo que G2-B no hace

- No interpreta `ENT_AUT`, altas, bajas ni `Services{ES}` — G2-C.
- No infiere fechas jurídicas — emite intervalos de observación.
- No declara bajas: `removed` admisible ≠ conclusión jurídica.

## Estado

```text
G2-A    CLOSED   contrato (dfb10d4)
G2-D0   DONE     inventario (2d9fc1c)
G2-D0.1 PASS     par EBA real + Type-A BdE (f2bcb68)
G2-B    DONE     differ + 15 tests + oráculo + par real (0 cambios)
G2-C    NEXT     structural change → regulatory change candidate
```
