# G2-E1 — Bitemporal assessment contract (`AssessmentQuery` → `BitemporalAssessmentResult`)

Preregistro documental (task `g2-e1-preregister`, skill
`preregister-gate`). Congela el contrato de la query bitemporal de
G2-E — `valid_at` × `known_at` — **antes** de cualquier
implementación. Cero código de producción: la salida es este
contrato, sus reglas congeladas y los 18 probes E0 convertidos en
acceptance criteria vinculantes.

Deriva del contrato G2-A (`docs/g2-snapshot-history-contract.md`,
§8 — dos dimensiones temporales de la query) y de los casos reales
congelados en G2-E0 (`docs/g2-e0-bitemporal-cases.md`;
fixture `fixtures/g2/e0/bitemporal-cases.json`,
`FINREG_G2_E0_CASES_V1`, artifact_sha256
`784d489e5d0aa8aaaf829f5d287f2bfa6c45b910563239d753a771ec4b8b41c7`).

## 1. `AssessmentQuery`

```text
AssessmentQuery
  entity_id            corpus_id de la entidad (p.ej. E3-001)
  activity             p.ej. PAYMENT_CREDIT_TRANSFER_EXECUTION
  jurisdiction         p.ej. ES
  territorial_basis?   opcional — igual que en assess()/V3
  valid_at             YYYY-MM-DD — tiempo jurídico
  known_at             YYYY-MM-DD — cutoff de conocimiento
```

Universo de evidencia de la query: las aserciones del evidence set
que matchean `entity_id × activity × jurisdiction` (×
`territorial_basis` cuando se declara) más los `reported_facts` de
la entidad — la misma definición de universo usada por E0.

## 2. Pipeline congelado

```text
universo versionado de assertions + reported_facts (evidence set)
        ↓
visibility gate:
  observable(item, K) sii item.source_assertions ≠ ∅
    ∧ ∀ fuente: calendar_date(retrieved_at) <= known_at
        ↓
ASSESSMENT_SEMANTICS_V3 SIN CAMBIOS — as_of = valid_at
        ↓
BitemporalAssessmentResult + auditoría de evidencia
incluida/excluida
```

`known_at` filtra antes de evaluar; nunca reescribe la evaluación.

## 3. Reglas congeladas

### E1-R1 — `knowledge_time` de una aserción = última fuente necesaria

```text
knowledge_time(assertion) = max(source_assertion.retrieved_at)
usable iff knowledge_time <= known_at
```

No basta con que una de las fuentes ya fuese conocida: un artefacto
derivado no puede ser más cognoscible que su input menos observado.
Encaja con `ALL_REQUIRED`: si una fuente necesaria aún no era
observable en K, la aserción no existe para esa query.

### E1-R2 — misma regla para `reported_facts`; sin vínculo → exclusión fail-closed

`knowledge_time` y el umbral se aplican igual a `reported_facts`.
Un fact sin `source_assertions` vinculadas **no es observable en
ningún K**: se excluye fail-closed — nunca se inventa un
`retrieved_at` ni se toma prestado el de otro artefacto.

Formalmente (idéntico al oráculo de verificación de E0):

```text
observable(item, K) =
    item.source_assertions ≠ ∅
    ∧ ∀ s ∈ source_assertions:
        calendar_date(s.retrieved_at) <= K
```

### E1-R3 — `known_at` sólo filtra evidencia; jamás toca el motor temporal

`known_at` no modifica `effective_from`, `effective_to`,
`status_intervals`, `interval_end`, `covers()` ni
`effective_effect_at()`. Tampoco altera la lógica de frescura:
V3 sigue recibiendo `valid_at` como `as_of` y toda la evaluación
temporal jurídica permanece en el motor congelado. Las reglas
temporales ya están concentradas en V3; no se crea un segundo
motor.

### E1-R4 — granularidad de `known_at`: fecha calendario

```text
known_at = YYYY-MM-DD
retrieved_at (date o datetime ISO) → su fecha calendario
```

Un `retrieved_at` con hora es observable si su fecha calendario es
`<= K` — la proyección ya usada por el oráculo E0.
`sub-day transaction ordering = OUT_OF_SCOPE_G2_E1`: distinguir
02:00 de 18:00 del mismo día requerirá una versión sucesora del
contrato, nunca una reinterpretación silenciosa de E0.

### E1-R5 — `known_at` opera sobre un universo versionado, no sobre el repo

El filtro se aplica a un **evidence set** concreto — la cadena de
derivación congelada identificada por artefacto + sha256 — no a
todos los raw snapshots que existan en el repo. Las observaciones
EBA del 14/09 y 15/09 existen en el corpus G2 pero aún no forman
parte de la cadena derivada G1-E: `known_at=2026-09-15` no adquiere
mágicamente nuevas assertions (demostrado por E0-05). El resultado
registra `evidence_set_id` para hacer la traza explícita.

```text
evidence_set_id = <artifact_name>@sha256:<hex>
```

Evidence set de los acceptance criteria:

```text
derived-assertions-g1-e-002
  @sha256:2fb08d678a5ee11a398af7a4a990521d1ca5fde20012ffd8e8af63f058bfc1e7
+ corpus-g1-e-001        (entidades/anclas E3)
+ claim-ledger-g1-e-001  (provenance de claims)
  sha256 de ambos en fixtures/g2/e0/bitemporal-cases.json → inputs
```

## 4. `BitemporalAssessmentResult`

```text
BitemporalAssessmentResult
  query
    entity_id / activity / jurisdiction / territorial_basis?
    valid_at
    known_at

  assessment            # veredicto V3
  reason                # reason code V3

  evidence
    usable_assertion_ids
    excluded_after_known_at_assertion_ids
    usable_reported_fact_ids
    excluded_after_known_at_fact_ids

  semantics_version = ASSESSMENT_SEMANTICS_V3
  evidence_set_id
```

Los campos de auditoría del motor (`used_assertion_ids`,
`diagnostics`) se emiten también y quedan congelados por probe en
el fixture E0.

## 5. Acceptance criteria binding — los 18 probes E0

Los 18 probes de `fixtures/g2/e0/bitemporal-cases.json` se
convierten **íntegramente** en criterios de aceptación de la
implementación: `expected_assessment`, `expected_reason` y los
cuatro conjuntos de evidencia por probe — sin seleccionar sólo los
favorables. Ids con prefijo `g1e-` abreviados (`g1e-asm-006` →
`asm-006`); la forma canónica binding es la del fixture.

### E0-01 — DENIZEN: frontera exclusiva `[from,to)` (eje `valid_at`)

`E3-001` · `MONEY_REMITTANCE` · ES · raíz `EBA|PSD_PI|ES_BE!6822`
· intervalo real `[2019-03-15, 2020-07-23)`.

| valid_at | known_at | assessment | reason | usable_a | excl_a | usable_f | excl_f |
|---|---|---|---|---|---|---|---|
| 2020-07-22 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-006 | asm-012 | fact-001, fact-002 | fact-003 |
| 2020-07-22 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-006, asm-012 | — | fact-001, fact-002, fact-003 | — |
| 2020-07-23 | 2026-09-13 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006 | asm-012 | fact-001, fact-002 | fact-003 |
| 2020-07-23 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006, asm-012 | — | fact-001, fact-002, fact-003 | — |
| 2026-09-14 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006, asm-012 | — | fact-001, fact-002, fact-003 | — |

`used_assertion_ids`: `asm-006` / `asm-006, asm-012` en los probes
ENTITLED; `[]` en los NOT_ENTITLED. `diagnostics` no vacíos:
`not_in_effect:asm-006` (probe 3) y `not_in_effect:asm-006,
not_in_effect:asm-012` (probes 4–5).

### E0-02 — MMG: gap de raíz + ruta territorial no observada (eje `valid_at`)

`E3-002` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES · raíz
`EBA|PSD_PI|CZ_CNB!29142024` · intervalos `[2017-05-30,
2019-07-12)` + `[2024-07-12, ∞)`.

| valid_at | known_at | assessment | reason | usable_a | excl_a | usable_f | excl_f |
|---|---|---|---|---|---|---|---|
| 2018-06-01 | 2026-09-14 | INDETERMINATE | TERRITORIAL_ENTITLEMENT_UNRESOLVED | asm-015 | — | fact-004 | — |
| 2020-01-01 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-015 | — | fact-004 | — |
| 2026-09-14 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-015 | — | fact-004 | — |

`used_assertion_ids`: `[]` en los dos primeros probes (diag
`not_in_effect:asm-015`); `asm-015` en el tercero.

### E0-03 — DENIZEN: `known_at` discrimina por ventana probatoria (eje `known_at`)

`E3-001` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES. Evidencia EBA
`retrieved_at=2026-09-13` cubre `[2019-03-15, 2020-07-23)`; BdE
`retrieved_at=2026-09-14` cubre `[2011-06-09, 2020-07-23)`.

| valid_at | known_at | assessment | reason | usable_a | excl_a | usable_f | excl_f |
|---|---|---|---|---|---|---|---|
| 2015-06-01 | 2026-09-13 | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE | asm-004 | asm-010 | fact-001, fact-002 | fact-003 |
| 2015-06-01 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004, asm-010 | — | fact-001, fact-002, fact-003 | — |
| 2020-07-22 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004 | asm-010 | fact-001, fact-002 | fact-003 |
| 2020-07-22 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004, asm-010 | — | fact-001, fact-002, fact-003 | — |

`used_assertion_ids`: `[]` (probe 1), `asm-010` (probe 2),
`asm-004` (probe 3), `asm-004, asm-010` (probe 4). `diagnostics`
no vacíos: `not_in_effect:asm-004` en los probes 1–2.

### E0-04 — THUNES: conocimiento retroactivo (eje `known_at`)

`E3-010` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES · raíz
`EBA|PSD_PI|FR_ACPR!384558` · retirada real `2026-08-27` observada
`2026-09-13` (0 aserciones; sólo facts de raíz).

| valid_at | known_at | assessment | reason | usable_a | excl_a | usable_f | excl_f |
|---|---|---|---|---|---|---|---|
| 2026-09-01 | 2026-09-12 | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE | — | — | — | fact-018, fact-019 |
| 2026-09-01 | 2026-09-13 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | — | — | fact-018, fact-019 | — |
| 2026-09-01 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | — | — | fact-018, fact-019 | — |

`used_assertion_ids` = `[]` y `diagnostics` = `[]` en los tres
probes.

### E0-05 — Control: `known_at` no cambia nada dentro del rango observado

`E3-002` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES.

| valid_at | known_at | assessment | reason | usable_a | excl_a | usable_f | excl_f |
|---|---|---|---|---|---|---|---|
| 2026-09-14 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-015 | — | fact-004 | — |
| 2026-09-14 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-015 | — | fact-004 | — |
| 2026-09-14 | 2026-09-15 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-015 | — | fact-004 | — |

`used_assertion_ids` = `asm-015` y `diagnostics` = `[]` en los
tres probes.

### Criterio de éxito/fallo medible

```text
ÉXITO  18/18 probes reproducen expected_assessment + expected_reason
       + usable/excluded_after_known_at (assertions y facts)
       + used_assertion_ids + diagnostics congelados,
       sobre el evidence_set_id congelado.
FALLO  cualquier divergencia, o necesidad de modificar V3 o la
       regla del filtro para pasar → defecto reproducible:
       finding + artefacto/run sucesor. El fixture y este
       contrato no se reescriben.
```

## 6. Qué resultados son válidos (objetivo no móvil)

- `NO_ENTITLEMENT_EVIDENCED`, `INDETERMINATE` y
  `CONFIRMED_NOT_ENTITLED` son outcomes legítimos y esperados —
  el objetivo no se mueve si la implementación reproduce la tabla.
- "0 cambios de assessment" (E0-05) es un resultado válido del
  control.
- Un `evidence_set_id` distinto del congelado no invalida el
  contrato, pero invalida la comparación con estos probes →
  finding clasificado, nunca un pase silencioso.
- Una divergencia real entre implementación y fixture es un
  defecto reproducible → finding + artefacto/run sucesor; los
  históricos no se reescriben (anti-regla 1 de
  `preregister-gate`).

## 7. Fuera de alcance de E1 (decisiones diferidas)

- `sub-day transaction ordering` — versión sucesora del contrato
  (E1-R4).
- Evidencia revocada/corregida después de K (G2-A §12: diferido
  hasta tener un caso real; el corpus sigue sin tenerlo).
- Extensión del catálogo G2-C0 para `DER_CHI_ENT_AUT` (E0-F02:
  276 Active→Inactive + 2 Inactive→Active) — futura extensión
  preregistrada de G2-C, ortogonal a demostrar
  `valid_at × known_at`.
- `PSD_AG` como sujeto de query (ruta delegada del principal,
  G1-D).
- Cualquier cambio en `ASSESSMENT_SEMANTICS_V3`, `temporal.py` o
  la cadena de derivación.

## 8. Sucesión

La implementación es una task posterior (`g2-e2-implement`): una
capa fina **filtrar por K → llamar a V3 con T**, sin reescribir
V3. Cambios futuros de granularidad de `known_at` o de definición
del evidence set = nueva versión del contrato, preregistrada —
nunca una reinterpretación de E0/E1.

## Estado

```text
G2-E1  PREREGISTERED  (este documento, task g2-e1-preregister)
G2-E2  NOT STARTED    (implementación fina sobre V3; consume este
                       contrato + fixture E0 como acceptance)
```
