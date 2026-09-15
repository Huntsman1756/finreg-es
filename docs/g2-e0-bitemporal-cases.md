# G2-E0 — Casos bitemporales preregistrados (`valid_at` × `known_at`)

Preregistro documental (task `g2-e0-select-cases`). Selecciona 5
casos reales del corpus actual y congela sus outcomes esperados para
G2-E — `AssessmentQuery` con `valid_at × known_at`. **Cero código de
producción**: inspección del corpus + fixture de casos + este doc.
El artefacto congelado es
`fixtures/g2/e0/bitemporal-cases.json`
(regenerable byte-idéntico con `tools/build_g2e0_cases.py`; el build
verifica las expectativas contra el oráculo V3+filtro-K y aborta si
divergen — verify-before-freeze, nunca ajuste tras ver resultados).

## 1. Semántica preregistrada de la query bitemporal

Deriva del contrato G2-A (`docs/g2-snapshot-history-contract.md`,
§8). G2-E **reutiliza** `ASSESSMENT_SEMANTICS_V3`, `covers()` y
`effective_effect_at()`; no se crea motor temporal paralelo.

```text
valid_at  → as_of del motor congelado: tiempo jurídico.
            covers(), effective_effect_at(), status_intervals
            [from,to) y la frescura se evalúan en valid_at.
known_at  → filtro de evidencia observable: tiempo de transacción.
            Una aserción derivada o reported_fact es observable en K
            si y sólo si TODAS sus source_assertions tienen
            retrieved_at <= K — un artefacto derivado no puede ser
            más cognoscible que su input menos observado.
```

Reglas congeladas:

- `known_at` **nunca** modifica `effective_from`/`effective_to` ni
  los intervalos (anti-retroproyección §8).
- `source_as_of` **nunca** se usa como tiempo de observación:
  `retrieved_at` es transaction time; la ausencia de `source_as_of`
  se declara `UNAVAILABLE`, nunca se rellena (constraint
  `source_as_of_never_from_retrieved_at`).
- K es una fecha; un `retrieved_at` con hora es observable si su
  fecha calendario es `<= K`.
- Universo de evidencia: la cadena G1-E congelada
  (`derived-assertions-g1-e-002.json` + `corpus-g1-e-001.json` +
  `claim-ledger-g1-e-001.json`; sha256 en el fixture). Las
  observaciones EBA del 14/09 y 15/09 existen en el corpus G2 pero
  aún no han entrado a la cadena de derivación — para estos casos
  K=2026-09-15 es observablemente equivalente a K=2026-09-14.
- `fixtures/regulatory/scenarios.json` + `assertions.json` (inputs
  de la task) se inspeccionaron y se descartaron para la selección:
  son corpus **sintético** G0.4 (`"Aserciones sinteticas para
  congelar semantica G0.4"`); la task exige casos reales.

## 2. Respuestas preregistradas a las preguntas falsables

| Pregunta | Respuesta congelada | Caso |
|---|---|---|
| ¿Assessment distinto para el mismo `valid_at` al cambiar `known_at`, sólo porque la evidencia aún no se había observado? | **SÍ** — demostrado sobre retrieved_at reales divergentes | E0-03, E0-04 |
| Con el mismo `known_at`, ¿cambia la assessment al mover `valid_at` a través de un intervalo jurídico conocido? | **SÍ** — frontera exclusiva y gap raíz reales | E0-01, E0-02 |

## 3. Casos congelados (5; max_cases=5)

Universo de evidencia por caso = aserciones que matchean la query +
reported_facts de la entidad. `usable`/`excluded_after_K` se derivan
mecánicamente de `retrieved_at`; la tabla completa con ids vive en el
fixture.

### E0-01 — DENIZEN: frontera exclusiva `[from,to)` (eje `valid_at`)

`E3-001` · `MONEY_REMITTANCE` · ES · raíz `EBA|PSD_PI|ES_BE!6822`
· intervalo real `[2019-03-15, 2020-07-23)` (retirada dual-source
EBA+BdE el 23/07/2020).

| valid_at | known_at | assessment | reason | usable_a | excluded_a |
|---|---|---|---|---|---|
| 2020-07-22 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-006 | asm-012 |
| 2020-07-22 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-006, asm-012 | — |
| 2020-07-23 | 2026-09-13 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006 | asm-012 |
| 2020-07-23 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006, asm-012 | — |
| 2026-09-14 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | asm-006, asm-012 | — |

La frontera cierra **en** la fecha de retirada (E3-F02 congelado).
Los facts EBA (`fact-001` intervalos, `fact-002` retirada) ya son
observables en K=2026-09-13: el veredicto no depende de la
observación BdE (`fact-003`), que es corroborante.

### E0-02 — MMG: gap de raíz + ruta territorial no observada (eje `valid_at`)

`E3-002` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES · raíz
`EBA|PSD_PI|CZ_CNB!29142024` · intervalos reales
`[2017-05-30, 2019-07-12)` + `[2024-07-12, ∞)`.

| valid_at | known_at | assessment | reason |
|---|---|---|---|
| 2018-06-01 | 2026-09-14 | INDETERMINATE | TERRITORIAL_ENTITLEMENT_UNRESOLVED |
| 2020-01-01 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN |
| 2026-09-14 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |

Congela E3-F04: la raíz abierta en 2018 no prueba la ruta ES (el
vector `Services{ES}` sólo es vigente — el positivo territorial nace
en `EVIDENCE_AS_OF`); el gap 2019–2024 cierra la raíz en 2020; la
reautorización + vector observado reabren en 2026.

### E0-03 — DENIZEN: `known_at` discrimina por ventana probatoria (eje `known_at`)

`E3-001` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES. La evidencia
EBA (`retrieved_at=2026-09-13`) cubre `[2019-03-15, 2020-07-23)`; la
BdE (`retrieved_at=2026-09-14`) cubre `[2011-06-09, 2020-07-23)`.

| valid_at | known_at | assessment | reason | usable_a | excluded_a |
|---|---|---|---|---|---|
| 2015-06-01 | 2026-09-13 | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE | asm-004 | asm-010 |
| 2015-06-01 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004, asm-010 | — |
| 2020-07-22 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004 | asm-010 |
| 2020-07-22 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED | asm-004, asm-010 | — |

`NO_ENTITLEMENT_EVIDENCED` en K=13 es el veredicto **correcto-como-
de-K**: la fila BdE existía en el mundo pero FinReg aún no la había
observado. El contraste intra-caso (2020-07-22 estable en ambas K)
demuestra que el eje es la cobertura de la evidencia, no un sesgo
global.

### E0-04 — THUNES: conocimiento retroactivo (eje `known_at`)

`E3-010` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES · raíz
`EBA|PSD_PI|FR_ACPR!384558` · retirada real `2026-08-27` observada
`2026-09-13` (0 aserciones; sólo facts de raíz — `Services{ES}`
listados tras la retirada no generan positivos, E3-010).

| valid_at | known_at | assessment | reason | usable_f | excluded_f |
|---|---|---|---|---|---|
| 2026-09-01 | 2026-09-12 | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE | — | fact-018, fact-019 |
| 2026-09-01 | 2026-09-13 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | fact-018, fact-019 | — |
| 2026-09-01 | 2026-09-14 | CONFIRMED_NOT_ENTITLED | ROOT_FAMILY_WITHDRAWN | fact-018, fact-019 | — |

El ejemplo §8 verbatim: la observación llegó después del hecho que
describe; en `valid_at < K` el sistema ya conoce la retirada que aún
no era observable cuando ocurría.

### E0-05 — Control: `known_at` no cambia nada dentro del rango observado

`E3-002` · `PAYMENT_CREDIT_TRANSFER_EXECUTION` · ES.

| valid_at | known_at | assessment | reason |
|---|---|---|---|
| 2026-09-14 | 2026-09-13 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |
| 2026-09-14 | 2026-09-14 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |
| 2026-09-14 | 2026-09-15 | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |

Toda la evidencia de MMG es EBA `retrieved_at=2026-09-13`; mover K
por el rango de observaciones disponibles es invariante. La
invarianza negativa análoga queda cubierta por E0-01 (07-23 idéntico
en K=13 y K=14 pese a distinto conjunto observable).

## 4. Findings fail-closed del case_mix

### E0-F01 — NON_REPRESENTABLE_IN_CURRENT_CORPUS

El `case_mix` prefería un `known_at` sobre "un record EBA real de
los 67 added del 15/09 con ENT_AUT interpretable (y si existe,
services.ES)". Inspección del snapshot congelado
`eba-psd2-202609150000.zip` (sha256 `a582908cfa99f3ab…`):

```text
67/67 added son EntityType=PSD_AG (agentes)
0/67 tienen properties.ENT_AUT propia
0/67 tienen services.ES
campos: identidad/dirección del agente + DER_CHI_ENT_AUT (heredado)
```

Ningún record added declara `effective_from` jurídico propio — su
única ancla es la observación (`EVIDENCE_AS_OF`) y *presencia ≠
entitlement* (catálogo G2-C0). El caso preferido **no es
representable**: se documenta aquí (fail-closed), no se fuerza. El
eje `known_at` queda cubierto por E0-03/E0-04 sobre `retrieved_at`
reales divergentes del corpus G1-E.

### E0-F02 — candidato de extensión del catálogo G2-C0 (no requisito E0)

Entre los 312 `changed` del par hay **278 transiciones en
`properties.DER_CHI_ENT_AUT`** (todas en `PSD_AG`): 276
Active→Inactive y 2 Inactive→Active
(`PSD_AG:ES_BE!006842!60607076Y`, `PSD_AG:ES_BE!006842!Y1928881T`).
Concentración por parent: `PSD_EPI ES_BE!6904` (140),
`PSD_PI ES_BE!6842` (105), `PSD_PI FR_ACPR!54167` (23),
`PSD_PI CZ_CNB!01993143` (5), `PSD_PI ES_BE!6828` (4),
`PSD_PI ES_BE!6813` (1) — ninguno está en el corpus G1-E.

`DER_CHI_ENT_AUT` tiene semántica congelada en G1-D (Active/Inactive
heredado del parent). La desactivación masiva de agentes de
`ES_BE!6904` es un candidato relevante para una **extensión
preregistrada futura** del catálogo G2-C0 (`no_catalog_retrofit`):
nunca requisito de E0 ni clasificación retroactiva — los 312 changed
permanecen `UNCLASSIFIED_STRUCTURAL_CHANGE`/`BLOCKED` en el artefacto
de eventos congelado.

## 5. Qué resultados son válidos (objetivo no móvil)

- `NO_ENTITLEMENT_EVIDENCED`, `INDETERMINATE` y
  `CONFIRMED_NOT_ENTITLED` son outcomes legítimos y esperados — el
  objetivo no se mueve si G2-E reproduce la tabla.
- "0 cambios de assessment" (E0-05) es un resultado válido del
  control.
- Las expectativas se verificaron por replay offline del oráculo
  (V3 + filtro-K sobre el artefacto `-002` congelado) **antes** del
  commit; el build aborta en divergencia — las expectativas nunca se
  ajustan tras observar resultados (skill `preregister-gate`,
  anti-regla 1).
- Si la implementación G2-E diverge del fixture: defecto
  reproducible → finding + artefacto/run sucesor; los históricos no
  se reescriben.

## 6. Fuera de alcance de E0 (decisiones diferidas)

- `known_at` sobre evidencia **revocada/corregida** posteriormente
  (contrato §12: diferido hasta un caso real — el corpus sigue sin
  tener uno).
- Slices con `retrieved_at` de datetime: los `retrieved_at` del
  corpus G1-E son fechas; la comparación G2 usa datetimes pero sus
  records aún no están derivados a aserciones.
- Agentes `PSD_AG` como sujeto de query: su ruta es delegada del
  principal (G1-D); los 67 added alimentan E0-F01/F02, no un caso.
