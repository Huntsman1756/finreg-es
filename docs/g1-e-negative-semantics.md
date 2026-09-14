# G1-E — Negativos: semántica negativa (E1) + granularidad PSD2 (E2)

Freeze jurídico-semántico preregistrado antes de corpus e
implementación. G1-D quedó cerrado con cadena válida `*-g1-d-002` /
`FINREG_G1_DERIVATION_V4`. G1-E es el workstream donde FinReg aprende
a **cerrar una vía sin cerrar erróneamente la entidad completa**.

Este documento congela dos decisiones de modelo. **No emite
`NOT_ENTITLED` todavía**: E3 corpus → E4 derivation delta → E5
agregación → E6 divergence audit.

## Contexto y deuda heredada

Semántica ya fijada que E1 no reabre:

- **G1-A** (`g1-a-eba-psd2-semantics.md`): `ENT_AUT` es lista
  cronológica — impar = autorización, par = retirada; `WITHDRAWN` se
  materializó como `reported_fact`, nunca como negativo. La lectura
  jurídica de la retirada quedó preregistrada aquí.
- **G1-B** (`g1-b-bde-enumeration.md`): la inferencia negativa por
  ausencia sólo es admisible en slices `COMPLETE_ENUMERATION`
  verificados (domestic PI/EMI, AISP, branch; nunca LPS-PI/EMI, cuya
  enumeración vive en EBA). Preconditions duras ya congeladas
  (identidad exacta, ruta en allowlist, fecha current-snapshot, sin
  ruta legal alternativa abierta, sin positivo conflictivo).
- **Regla Fintonic** (B4-03): ninguna cobertura completa autoriza a
  ignorar evidencia oficial contradictoria — T1↔T2 divergente bloquea
  el negativo (`CONFLICTING_SOURCE_ASSERTIONS` → INDETERMINATE).
- **G1-D**: multi-route real probada (Eupago/Wise emiten FPS+BRANCH);
  `evidence_composition=ALL_REQUIRED` ya evalúa admisibilidad por
  fuente requerida.

Deuda explícita que E1/E2 cierra: `assess()` trata hoy cualquier
combinación positivo+negativo como conflicto global y sólo filtra por
`activity` umbrella — no puede preguntar "¿PS_070?" ni responder
"PS_070 ausente → negativo".

## E1 — Semántica negativa congelada

### Route key

Una aserción (positiva o negativa) se evalúa contra una **vía
jurídica**, no contra la entidad abstracta. La clave de vía mínima es:

```text
route_key = (entry_mechanism, territorial_basis)
```

sin objeto de dominio nuevo. Dos aserciones son de la misma vía si y
sólo si comparten route_key y actividad.

### Clases de evidencia negativa (distintas, nunca fusionadas)

```text
EXPLICIT_WITHDRAWAL     secuencia ENT_AUT cerrada en posición par
                        (EBA, oficial NCA-reportada) o baja expresa
                        de la vía en registro del Estado de acogida
EXPIRY                  effective_to cerrado por intervalo temporal
ENUMERATED_ABSENCE      ausencia en slice COMPLETE_ENUMERATION
                        verificado (allowlist B5 intacta)
ENTITY_BAJA             FECHA_BAJA BdE — semántica de ENTIDAD, no de
                        vía ni de autorización (ver prohibiciones)
```

Cada clase produce una aserción `NOT_ENTITLED` con `route_key` propio
o un hecho, según la vía a la que se ancle la evidencia:

```text
retirada ENT_AUT home        → NOT_ENTITLED de TODA la familia de
                               vías que desciende de esa autorización
                               (la base jurídica home desaparece)
baja sucursal BdE            → NOT_ENTITLED de la vía BRANCH únicamente
expiración intervalo         → NOT_ENTITLED de la aserción emitida
                               con esa ventana
ausencia capability (slice   → NOT_ENTITLED de (entidad, servicio
completo enumerado)            concreto, vía) — nunca del umbrella
```

### Agregación route-aware (sustituye "cualquier conflicto → INDETERMINATE")

```text
misma vía, misma actividad:
  ENTITLED + NOT_ENTITLED            → CONFLICT → INDETERMINATE

vías compatibles distintas:
  ENTITLED en cualquier vía vigente
  + NOT_ENTITLED en otra vía         → CONFIRMED_ENTITLED global
                                       (la negativa queda anclada a
                                        su route_key, no al ente)

CONFIRMED_NOT_ENTITLED global        → sólo cuando TODA vía legal
                                       disponible está cerrada bajo
                                       evidencia demostrablemente
                                       completa,
                                       O existe negativo explícito
                                       global (retirada home de la
                                       autorización raíz)
```

La pregunta `(entity, activity, jurisdiction)` se responde por
existencia de vía vigente: Wise `FPS ENTITLED + BRANCH NOT_ENTITLED`
→ `CONFIRMED_ENTITLED` global, con la ruta BRANCH cerrada y visible.

### Cuatro prohibiciones congeladas

```text
FECHA_BAJA por transformación
≠ withdrawal of authorisation
  (B4-05 BANKINTER: baja BdE 2019 "transformación en otro tipo de
   entidad" ≠ retirada EBA 2026 — hechos distintos)

expired route
≠ global NOT_ENTITLED
  (una vía expirada no cierra las demás)

absence outside COMPLETE_ENUMERATION
≠ negative
  (allowlist B5 verbatim; LPS-PI/EMI ausente de BdE es NO
   interpretable, su enumeración vive en EBA)

negative on route A + positive on compatible route B
≠ conflict
  (es agregación legal, no divergencia de fuentes)
```

### Regla Fintonic reafirmada

Una aserción negativa por ausencia enumerada queda **bloqueada**
(`CONFLICTING_SOURCE_ASSERTIONS` → INDETERMINATE, nunca
CONFIRMED_NOT_ENTITLED) si existe cualquier `SourceAssertion`
positiva oficial vigente y no stale para la misma
`(entidad, actividad, vía)`. La cobertura completa no gana
silenciosamente al positivo.

## E2 — Granularidad PSD2 (vocabulario de capability)

Patrón MiCA (`ac_serviceCode` → `CRYPTO_*` por servicio) aplicado a
PSD2: código oficial → actividad canónica granular → una
`EntitlementAssertion` por servicio. Los negativos se emiten **sólo
al nivel granular**.

### Ontología canónica: una actividad, muchos códigos

Regla congelada:

```text
SOURCE VOCABULARY            CANONICAL VOCABULARY
EBA: PS_070                  →
BdE: 7                       →  PAYMENT_INITIATION_SERVICES
PSD2 Annex I: 7              →
```

El código regulatorio vive sólo en mapping/provenance; el namespace
canónico describe el concepto jurídico y **nunca** translitera el
esquema de una fuente (por eso `PAYMENT_*`, no `PS_*`). Nunca dos
actividades canónicas sinónimas por fuente (`PS_080→X`, `BdE 8→Y`).

### Mapeo EBA `PS_*` → PSD2 Annex I → actividad canónica

Etiquetas verbatim del spec oficial congelado
(`eba-psd2-json-data-specification.xlsx`, sheet 6):

| Código EBA | PSD2 Annex I | Etiqueta oficial (verbatim) | Actividad canónica |
|------------|--------------|---------------------------|--------------------|
| `PS_010` | 1 | Services enabling cash to be placed on a payment account as well as all the operations required for operating a payment account | `PAYMENT_ACCOUNT_CASH_PLACEMENT` |
| `PS_020` | 2 | Services enabling cash withdrawals from a payment account as well as all the operations required for operating a payment account | `PAYMENT_ACCOUNT_CASH_WITHDRAWAL` |
| `PS_03A` | 3(a) | Execution of direct debits, including one-off direct debits | `PAYMENT_DIRECT_DEBIT_EXECUTION` |
| `PS_03B` | 3(b) | Execution of payment transactions through a payment card or a similar device | `PAYMENT_CARD_TRANSACTION_EXECUTION` |
| `PS_03C` | 3(c) | Execution credit transfers, including standing orders | `PAYMENT_CREDIT_TRANSFER_EXECUTION` |
| `PS_04A` | 4(a) | Execution of direct debits where funds are covered by a credit line | `PAYMENT_DIRECT_DEBIT_EXECUTION_CREDIT_LINE` |
| `PS_04B` | 4(b) | Execution of payment transactions through a payment card where funds are covered by a credit line | `PAYMENT_CARD_TRANSACTION_EXECUTION_CREDIT_LINE` |
| `PS_04C` | 4(c) | Execution of credit transfers where the funds are covered by a credit line | `PAYMENT_CREDIT_TRANSFER_EXECUTION_CREDIT_LINE` |
| `PS_05A` | 5 | Issuing of payment instruments | `PAYMENT_INSTRUMENT_ISSUING` |
| `PS_05B` | 5 | Acquiring of payment transactions | `PAYMENT_TRANSACTION_ACQUIRING` |
| `PS_060` | 6 | Money remittance | `MONEY_REMITTANCE` |
| `PS_070` | 7 | Payment initiation services | `PAYMENT_INITIATION_SERVICES` |
| `PS_080` | 8 | Account information services | `ACCOUNT_INFORMATION_SERVICES` (existente, reutilizada) |
| `ES_010` | EMD2 | Issuing, distribution and redemption of electronic money | `E_MONEY_ISSUANCE` (existente, reutilizada) |

`PS_080` y `ES_010` reutilizan las actividades ya congeladas — no se
crean sinónimos `PS_ACCOUNT_INFORMATION`/`PS_E_MONEY_*`.

### Correspondencia BdE `ACTIVIDADES` y granularidad de fuente

Correspondencia por código (B3: 1,2,3.A-C,4.A-C,5,6,7,8 + A/B/C
dinero electrónico Ley 21/2011): `1→PS_010`, `2→PS_020`,
`3.A→PS_03A`, `3.B→PS_03B`, `3.C→PS_03C`, `4.A→PS_04A`,
`4.B→PS_04B`, `4.C→PS_04C`, `6→PS_060`, `7→PS_070`, `8→PS_080`,
`A/B/C→ES_010` según alcance.

**Código BdE `5` — granularidad explicada por fuente primaria
(resolución E3).** El propio xlsx discrimina por `NORMATIVA`: el `5`
atómico aparece **sólo bajo LEY 16/2009** (régimen LPSE anterior:
servicio 5 = "emisión y/o adquisición" unitario), mientras `5.A`/`5.B`
aparecen bajo RDL 19/2018 y Ley 21/2011. Idéntico patrón para
`3.1/3.2/3.3` y `4.1/4.2/4.3` (Ley 16/2009) vs `3.A/3.B/3.C` y
`4.A/4.B/4.C` (RDL 19/2018). Por tanto el `5` bare no es "la versión
gruesa" del servicio PSD2: es un código de **otro régimen jurídico**.
Sigue prohibido derivar negativos 05A/05B de un `5` bare, ahora con
justificación primaria y no sólo conservadora. Congelado:

```text
NO  BdE 5 → {PAYMENT_INSTRUMENT_ISSUING,
             PAYMENT_TRANSACTION_ACQUIRING}   como equivalencia

SÍ  representación intermedia conservadora
    (p. ej. PAYMENT_SERVICE_5, scope compuesto):
    - usable como positivo umbrella del servicio 5
    - PROHIBIDO como base de negativos 05A/05B
    - sin negativo separado A/B hasta que E3 demuestre
      la descomposición jurídica de BdE 5
```

Distinción congelada para E4 (derivación/finding, no necesariamente
expuesta públicamente):

```text
raw_capability_code   código tal como lo publica la fuente ("5",
                      "PS_05A", "7")
canonical_activity    actividad del vocabulario canónico
source_granularity    ATOMIC | COMPOSITE

ej: {raw="PS_05A", canonical=PAYMENT_INSTRUMENT_ISSUING,
     granularity=ATOMIC}
    {raw="5",      canonical=PAYMENT_SERVICE_5,
     granularity=COMPOSITE}
```

Una fuente menos granular nunca se convierte en dos hechos más
granulares.

### Semántica de la query

```text
query (entity, PAYMENT_INITIATION_SERVICES, ES)
  → evalúa aserciones cuya actividad canónica = PAYMENT_INITIATION_SERVICES
  → positivo sólo si PS_070 está explícitamente declarado
    para la vía (EBA Services{ES} / BdE ACTIVIDADES)
  → negativo granular sólo si la vía está en slice
    COMPLETE_ENUMERATION y la enumeración es admisible (B5)

query (entity, PAYMENT_SERVICES, ES)   [umbrella]
  → CONFIRMED_ENTITLED si ≥1 servicio granular tiene vía vigente
  → el umbrella derivado NO afirma todos los servicios: el alcance
    real sigue en scope (códigos crudos preservados)
  → NOT_ENTITLED umbrella sólo cuando TODOS los servicios del Annex
    aplicables a la clase están probados ausentes/cerrados bajo
    enumeración completa — jamás por ausencia de un servicio suelto
```

`activity` pasa a ser granular; `scope` conserva los códigos crudos
(como hoy). Las aserciones -001/-002 existentes con
`activity=PAYMENT_SERVICES` permanecen como artefactos históricos de
semántica umbrella; la cadena E4 emite granular.

### Distinción capability vs ruta (precondición de E1)

La granularidad y la vía son dimensiones ortogonales del mismo modelo:
una entidad puede tener `PS_080` vía REGISTRATION (AISP) y `PS_03C`
vía AUTHORISATION+BRANCH. El negativo granular cierra
`(servicio, vía)`; el global exige todas las vías cerradas **y** todos
los servicios cerrados — ambas dimensiones.

## Corpus E3 preregistrado — RESUELTO (10 anclas reales)

Cadena válida: `g1-e-negative-corpus-003.json` (sucesores E3.1 +
E3-F04); `-001`/`-002` preservados como históricos con defectos
documentados. Cada caso lleva expectativas preregistradas:
`expected_negative_evidence_class` (enum cerrado),
`expected_blocker`/`expected_evidence_note` (opcionales),
`expected_route_outcome`, `expected_global_assessment` — así E4 puede
fallar la clase aunque E5 acierte el global. 0 entidades sintéticas.

### Findings E3.1 (sucesor, historia intacta)

```text
E3-F01  snapshot_sha256 truncado a 16 chars en registros BdE
        → -002 lleva el SHA-256 completo del manifest; test exige
        64 hex + igualdad con manifest + recompute
E3-F02  frontera de intervalo ENT_AUT
        → los intervalos son [autorización, retirada): la vía está
        cerrada EN la fecha de retirada (as_of 2020-07-23 → CLOSED).
        El motor actual considera vigente as_of==effective_to
        (legacy inclusive). Congelado: propiedad versionada
        interval_end=EXCLUSIVE para intervalos derivados de
        ENT_AUT; default legacy inclusive para artefactos G0/G1
        anteriores. E4 la materializa, E5 la consume — no se muta
        la semántica histórica
E3-F03  Fintonic PIS clasificado como CONFLICTING_SOURCE_ASSERTIONS
        → reclasificado: la capability de una fila con FECHA BAJA
        es histórico INACTIVO (regla B4), no positivo vigente en
        conflicto. Nueva expectativa: ENUMERATED_ABSENCE +
        blocker TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED →
        INDETERMINATE (el resultado global no cambia; cambia la
        clasificación honesta de la evidencia)
```

Adicionalmente el sucesor convierte `expected_negative_evidence_class`
en enum cerrado `NONE | EXPLICIT_WITHDRAWAL | EXPIRY |
ENUMERATED_ABSENCE | ENTITY_BAJA` y traslada la explicación a
`expected_blocker`/`expected_evidence_note`.

```text
E3-F04  intervalo raíz mezclado con intervalo territorial (E3-002)
        → ENT_AUT sí es histórico ([2017-05-30,2019-07-12) y
        [2024-07-12,∞) reconstruibles), pero Services{ES} del
        snapshot sólo es VIGENTE: no demuestra que la ruta ES
        existiera en 2018 ni que comenzara en 2024-07-12.
        Corrección (expectation-only, anclas intactas):
          as_of 2018-06-01 → raíz OPEN, vía FPS ES
            NOT_HISTORICALLY_OBSERVED → INDETERMINATE
            (TERRITORIAL_ENTITLEMENT_UNRESOLVED)
          as_of 2020-01-01 → raíz CLOSED → CONFIRMED_NOT_ENTITLED
          as_of 2026-09-14 → raíz OPEN + FPS observada →
            CONFIRMED_ENTITLED con territorial
            effective_from=EVIDENCE_AS_OF (nunca 2024-07-12)
```

### Dos clases de completitud que E4 NO debe fusionar

```text
population completeness
  ¿entidad ausente del registro → negativo?
  → NO / no probado globalmente. El contrato EBA sigue
    EXPLICIT_NEGATIVE_ONLY a nivel de población

capability-vector completeness
  dada una fila EXISTENTE, ¿Services{ES} enumera todos sus
  servicios Annex I para ES?
  → SÍ, probado para ese vector (spec: lista completa por país)
  → E4 lo representa de forma SCOPED, p. ej.
    CAPABILITY_VECTOR_COMPLETE_WHEN_RECORD_PRESENT,
    nunca reutilizando el scalar global
```

Idéntica distinción en BdE: el contrato no se vuelve globalmente
`COMPLETE_ENUMERATION`; E4 necesita un delta contractual que recoja
sólo los slices B5 (domestic PI/EMI, AISP, branch + capacidades
granulares) manteniendo LPS-PI/EMI OUT y agentes/distribuidores
fuera de la inferencia negativa.

### Alcance de E4 congelado

```text
E4 materializa (derivación, NO agregación):
  - actividades PSD2 granulares positivas
  - ENUMERATED_ABSENCE por (actividad, route_key)
  - EXPLICIT_WITHDRAWAL como cierre de raíz/familia
  - interval_end=EXCLUSIVE para ENT_AUT nuevos
  - raw_capability_code / source_granularity
  - negative_evidence_class
  - provenance de enumeración/coverage
  - evidencia negativa BLOQUEADA como finding
    (ej. Fintonic: ENUMERATED_ABSENCE +
     TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED),
    nunca NOT_ENTITLED admisible que E5 tenga que deshacer

E4 NO decide:
  - CONFIRMED_ENTITLED global
  - CONFIRMED_NOT_ENTITLED global
  - conflicto entre rutas
  → eso sigue siendo E5
```

```text
E3-001  DENIZEN GLOBAL FINANCIAL (ES_BE!6822)          E3-01
        retirada dual-source mismo día: BdE renuncia 23/07/2020
        + EBA ENT_AUT [2019-03-15, 2020-07-23]. Raíz única.
        probes 2020-07-22 open / 2020-07-23 closed / 2026 closed
E3-002  MMG Corporation (CZ_CNB!29142024)              E3-02
        ENT_AUT [2017-05-30, 2019-07-12, 2024-07-12]
        probes 2018 open / 2020 closed / 2026 open eff 2024-07-12
E3-003  BANKINTER CONSUMER FINANCE (BdE 8832, EBA ES_BE!8832) E3-03
        baja BdE 22/02/2019 transformación + EBA [2019-03-15,
        2026-07-01]. probe 2020-06-01: transformación + EBA ACTIVE
        → 0 negativo por ENTITY_BAJA
E3-004  CERRO CATEDRAL EP (BdE 6844)                   E3-04
        PI doméstica activa, ACTIVIDADES={6} → negativo granular
        PAYMENT_ACCOUNT_CASH_PLACEMENT + positivo MONEY_REMITTANCE
E3-005  Mollie B.V. (NL_DNB!F0038)                     E3-05
        PSD_PI retirada 2025-02-03 + PSD_EMI autorizada el mismo
        día. ROOT_WITHDRAWAL_IS_NOT_ENTITY_GLOBAL: familia PI
        cerrada, familia EMI abierta → CONFIRMED_ENTITLED vía EMI
E3-006  FINTONIC 6892→6935                             E3-06
        6892 PI retirada/escisión 29/01/2024 → 6935 BdE baja
        transformación 26/11/2024 + EBA PSD_AISP ACTIVE 03/12/2024.
        AIS → CONFIRMED_ENTITLED; PIS → INDETERMINATE (negativo
        bloqueado: positivo histórico BdE código 7, transformación
        no demostrable como cierre ni continuidad)
E3-007  SIBS Pagamentos (PSD_PI!PT_BP!8703)            E3-07
        PI portuguesa LPS ausente de ambos xlsx BdE → ausencia
        NO interpretable → NO_NEGATIVE_INFERENCE
E3-008  Wise Europe SA                                 E3-08
        PIS ausente en los TRES vectores: Services{ES} padre,
        PSD_BR ES, BdE sucursal 6946 (sin código 7)
        → CONFIRMED_NOT_ENTITLED PIS (todas las vías cerradas
        bajo enumeración completa)
E3-009  Eupago                                         E3-05+E3-08
        PIS: FPS ausente (Services{ES} padre) vs BRANCH positiva
        (PSD_BR PS_070 + BdE 6938 código 7)
        → CONFIRMED_ENTITLED PIS. Par control/experimento con
        E3-008 (misma query, signo opuesto)
E3-010  THUNES (FR_ACPR!384558)                        E3-01b
        retirada 2026-08-27 con Services{ES} aún listados:
        presencia de códigos tras retirada ≠ entitlement
```

Guardarraíl preregistrado sin reabrir E1: **ROOT WITHDRAWAL IS NOT
ENTITY-GLOBAL** — la retirada de una raíz cierra sólo la familia de
rutas que mecánicamente desciende de ella; otras autorizaciones de la
misma persona jurídica permanecen abiertas (E3-005 lo demuestra con
PI→EMI el mismo día).

Resoluciones E3 que levantan pendientes del freeze:

- **BdE `5` COMPOSITE: explicado por fuente primaria** (ver sección
  E2): bare `5` = Ley 16/2009 (régimen distinto), `5.A`/`5.B` =
  RDL 19/2018. No es correlación EBA; es la columna `NORMATIVA` del
  propio xlsx.
- **Exhaustividad de `Services{ES}`**: el spec congelado define
  `Services` como la lista completa de servicios Annex I por país
  ("Services (as specified in Annex I to PSD2)") — exhaustiva por
  construcción del vector. La advertencia T2 aplica a la *verdad*
  de lo declarado (freshness), no a la *completitud* del vector.

Queda NON_REPRESENTABLE_IN_CURRENT_CORPUS: retirada de raíz +
positivo en dominio distinto de PSD2 (ej. MiCA) — E3-005 lo cubre
intra-PSD2; el caso cross-domain podrá probarse por test metamórfico.

## E4 — Derivación de evidencia negativa (materialización)

E4 es un **delta derivacional**: materializa hechos y aserciones
negativas granulares con su provenance; **no** toca `assess()` ni
produce veredictos globales (`CONFIRMED_ENTITLED` /
`CONFIRMED_NOT_ENTITLED` / resolución de conflicto entre rutas siguen
siendo E5). Artefactos: `fixtures/g1/{claim-ledger,corpus,
derivation-rules,derived-assertions}-g1-e-001.json` +
`sources/manifest-g1-e-run.json`, regenerables byte-idénticos con
`tools/build_g1e_ledger.py`, `tools/build_g1e_ruleset.py` y
`python -m finreg_es.derivation --g1e`.

### negative_scope — la distinción estructural de E4

```text
ROOT_FAMILY        retirada de raíz / baja de entidad.
                   Cierra la familia de rutas que mecánicamente
                   desciende de esa autorización; NUNCA inventa un
                   territorial_basis para una ruta no observada.
                   Clases: EXPLICIT_WITHDRAWAL | ENTITY_BAJA.
                   Se materializa como reported_fact (status fact
                   enriquecido), no como aserción legal.

ROUTE_CAPABILITY   ausencia enumerada en un vector completo de
                   capacidades de una ruta demostrada.
                   Clase: ENUMERATED_ABSENCE.
                   Se materializa como aserción NOT_ENTITLED scoped
                   a (activity, route_key).
```

Consecuencia binding: la retirada de raíz de MMG en 2019 **no**
retroproyecta un negativo FPS-ES sobre 2020 — esa ruta nunca fue
observada para el intervalo `[2017-05-30, 2019-07-12)`. Y la
retirada de THUNES no convierte los `Services{ES}` aún listados en
positivos: la raíz cerrada bloquea toda derivación positiva de la
familia.

### Dos completitudes, nunca fusionadas

```text
population completeness     negative_evidence_capability global del
                            contrato. EBA sigue EXPLICIT_NEGATIVE_ONLY;
                            BdE sigue NO_NEGATIVE_INFERENCE.
                            Sin cambios en coverage.py.

capability-vector           propiedad scoped nueva del contrato
completeness                (capability_vector_completeness):
                            "dado un record presente con identidad
                            exacta y vector completo, la ausencia de
                            una actividad atómica en ese vector sí
                            soporta ENUMERATED_ABSENCE para esa
                            (actividad, ruta)". Slices declarados:
                            EBA Services{país} por entidad-raíz y
                            PSD_BR; BdE ACTIVIDADES domestic PI/EMI
                            y sucursal con-establecimiento.
```

La completitud del vector es **current-only**: el `Services{ES}` del
snapshot 2026-09-14 no prueba qué servicios tenía la entidad en 2018.
Todo `ENUMERATED_ABSENCE` deriva con `effective_from = EVIDENCE_AS_OF`
— nunca la fecha de autorización raíz ni la alta BdE.

### Semántica temporal

- `interval_end = EXCLUSIVE` en los hechos derivados de `ENT_AUT`:
  `[a1, a2)` — la vía está cerrada **en** la fecha de retirada
  (E3-F02). Propiedad versionada del artefacto; el default legacy
  inclusive preserva el replay byte-idéntico de G0/G1-D.
- Intervalo raíz ≠ intervalo territorial (E3-F04): `ENT_AUT` es
  histórico reconstruible; `Services{ES}` es un vector vigente. Los
  positivos territoriales nacen en `EVIDENCE_AS_OF` salvo fecha
  territorial publicada (BdE `FECHA ALTA` sí la publica para BRANCH).

### Clasificación de bajas BdE (motivo)

```text
transformación / fusión / escisión  → ENTITY_BAJA  (no es withdrawal:
                                      la continuidad del sucesor es
                                      una cuestión distinta)
renuncia / revocación / retirada    → EXPLICIT_WITHDRAWAL
otro / irreconocible                → UNRESOLVED_MOTIVO (finding,
                                      nunca negativo silencioso)
```

`ENTITY_BAJA` por transformación produce además el finding
`TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED` y marca los negativos
que dependerían de esa continuidad como `admissibility = BLOCKED`
(Fintonic: el código 7 histórico de la fila dada de baja no es un
positivo vigente — regla G1-B — pero tampoco demuestra cierre; el
candidato queda bloqueado, no NOT_ENTITLED admisible).

### Contrato de salida por aserción negativa

```text
canonical_activity          vocabulario PAYMENT_* / MONEY_REMITTANCE
raw_capability_code         código verbatim de fuente ("7", "PS_070")
source_granularity          ATOMIC | COMPOSITE (COMPOSITE nunca se
                            descompone: BdE "5" Ley 16/2009 queda fuera
                            de los universos de ausencia)
entry_mechanism             AUTHORISATION | REGISTRATION | ...
territorial_basis           sólo si la ruta está demostrada
negative_evidence_class     ENUMERATED_ABSENCE
negative_scope              ROUTE_CAPABILITY
effective_from              EVIDENCE_AS_OF (ausencias) o fecha
                            publicada (retiradas)
effective_to / interval_end EXCLUSIVE para intervalos ENT_AUT nuevos
coverage_policy_id          slice contractual que legitimó la ausencia
admissibility / blocker     ADMISSIBLE | BLOCKED + motivo
provenance                  enumeration claim(s) del vector usado
```

### Versionado contractual (bumps, no mutaciones)

```text
eba-psd2-register.json              1.1.0 → 1.2.0
  + actividades granulares en activities_covered
  + capability_vector_completeness (scoped, record-present)

bde-registro-servicios-pago.json    1.0.1 → 1.1.0
  + slices B5: domestic PI/EMI ACTIVIDADES + sucursal
  + LPS/agentes siguen fuera de negativos (OUT explícito)

bde-registro-con-establecimiento.json   NUEVO 1.0.0
  workbook BdE separado: sucursales comunitarias + actividades

schemas/v1.3/                       NUEVO (v1/v1.2 intocados)
  source-contract / derivation-ruleset / derived-assertions /
  entity-corpus — campos E4 opcionales, mismas restricciones
  estructurales (sin if/then/dependencies/format)
```

### Resultado sobre el corpus E3-003

```text
166 aserciones · 11 findings · reported_facts con negative_scope
DENIZEN   retirada dual-source 23/07/2020 [2019-03-15,2020-07-23)
MMG       raíz ACTIVA [2017,2019,2024) + FPS sólo desde EVIDENCE_AS_OF
BANKINTER ENTITY_BAJA transformación 2019-02-22 ≠ retirada EBA 2026-07-01
CERRO     +MONEY_REMITTANCE / −PAYMENT_ACCOUNT_CASH_PLACEMENT (DOMESTIC)
MOLLIE    raíz PI cerrada + raíz EMI abierta (misma fecha)
FINTONIC  PIS BLOCKED + TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED
SIBS      0 negativos BdE (LPS fuera); ausencias FPS scoped del vector
WISE      PIS cerrada en FPS y BRANCH (≥2 ROUTE_CAPABILITY)
EUPAGO    PIS −FPS / +BRANCH (PSD_BR + BdE 6938 código 7)
THUNES    raíz retirada; 0 positivos pese a Services{ES} listados
```

`tests/g1/test_g1e_negative_derivation.py` fija estas expectativas
más el contrato de campos, la exclusividad `[from,to)`, la no-
retroproyección territorial, la ausencia de descomposición de códigos
COMPOSITE y la determinación byte-idéntica del artefacto.

## E4.1/E5-A — Bridge de materialización a assessment

La materialización E4 (`-001`) no llegaba íntegra al motor:
`to_entitlement_assertions()` descartaba la semántica negativa y los
`ROOT_FAMILY` facts no identificaban mecánicamente qué raíz cerraban.
El sucesor `-002` (ruleset `FINREG_G1_DERIVATION_V6`) remedia el
puente sin tocar `-001`:

```text
EntitlementAssertion gana:  negative_scope, negative_evidence_class,
  raw_capability_code, source_granularity, coverage_policy_id,
  admissibility, blocker, interval_end, root_key,
  root_home_jurisdiction
covers()/effective_effect_at():
  interval_end=EXCLUSIVE => [from,to) cerrada EN effective_to
  (default None = semántica legacy inclusiva de G0/G1-D, intacta)

root_key =  EBA|<EntityType>|<EntityCode-core>   (Mollie:
            EBA|PSD_PI|NL_DNB!F0038 != EBA|PSD_EMI|NL_DNB!F0038)
            PSD_BR/PSD_AG heredan la raíz del parent EBA; BdE
            domestic hereda la raíz EBA que casa (tipo+codigo) o
            usa BDE|<familia>|<codigo_be> propia (CERRO, Fintonic-EP)
root_home_jurisdiction:  home==ES => {DOMESTIC};  home!=ES =>
            {FPS, BRANCH}  — el universo de vías se deriva del home
            de la raíz, nunca de un country code incidental

ROOT_FAMILY facts:  + source_claim_ids, source_assertions,
            root_key, root_home_jurisdiction — evaluables en
            freshness y bitemporalmente (status_intervals [from,to))
```

## E5 — ASSESSMENT_SEMANTICS_V3 (agregación route-aware)

Versión nueva en `semantics.py`; V1/V2 no mutan. Algoritmo:

```text
1. matching por query (entity x activity x jurisdiction
   [x territorial_basis]) — la base territorial explicita acota la
   query a una sola vía
2. admissibility=BLOCKED se excluye de toda ruta (informa, no cierra)
3. root_state(as_of) por root_key via status_intervals [from,to) +
   retiradas/bajas con freshness comprobable:
   OPEN | CLOSED | UNRESOLVED (baja sin resolución) | ABSENT
   (la raíz aún no existía en as_of)
4. rutas = (root_key, territorial_basis); positivo+negativo
   admisibles en la misma ruta => ROUTE_CONFLICT => INDETERMINATE
5. cualquier ruta limpia abierta => CONFIRMED_ENTITLED
6. CONFIRMED_NOT_ENTITLED solo si toda raíz aplicable (la raíz debe
   poder sostener la actividad: un PSD_AISP nunca cierra una query
   PIS) está CLOSED o tiene todas sus vías legalmente posibles
   cerradas: ROOT_FAMILY_WITHDRAWN | ALL_AVAILABLE_ROUTES_CLOSED
7. blocked/unresolved/conflicto sin otra vía abierta => INDETERMINATE
```

### Resultado — 22/22 casos preregistrados, 0 divergencias

```text
DENIZEN   07-22 ENTITLED · 07-23 NOT_ENTITLED (ROOT_FAMILY_WITHDRAWN,
          frontera exclusiva) · 2026 NOT_ENTITLED
MMG       2018 INDETERMINATE (TERRITORIAL_ENTITLEMENT_UNRESOLVED)
          · 2020 NOT_ENTITLED (gap ENT_AUT) · 2026 ENTITLED
BANKINTER 2020 ENTITLED (baja transformación no cierra)
          · 2026 NOT_ENTITLED (retirada EBA)
CERRO     CASH_PLACEMENT NOT_ENTITLED (ALL_AVAILABLE_ROUTES_CLOSED)
          · MONEY_REMITTANCE ENTITLED — misma vía, sin contaminación
MOLLIE    MR@2024 NO_ENTITLEMENT_EVIDENCED · CTE@2026 ENTITLED
          (raíz EMI; la retirada PI no es entity-global)
FINTONIC  AIS ENTITLED (raíz AISP) · PIS INDETERMINATE
          (NEGATIVE_EVIDENCE_BLOCKED — nunca NOT_ENTITLED)
SIBS      CTE ENTITLED · ausencia BdE no infiere (poblacional)
WISE      PIS NOT_ENTITLED (ALL_AVAILABLE_ROUTES_CLOSED, global y
          scoped BRANCH) · MR ENTITLED (sin contaminación cruzada)
EUPAGO    PIS ENTITLED global · +FPS NOT_ENTITLED · +BRANCH ENTITLED
THUNES    CTE NOT_ENTITLED (ROOT_FAMILY_WITHDRAWN; Services{ES}
          post-retirada no generan positivos)
```

Metamórficos fijados: conflicto intra-ruta => ROUTE_CONFLICT;
un `ROOT_FAMILY` fact sin `source_assertions` no puede cerrar una
raíz (freshness no comprobable). Umbrella negativo `PAYMENT_SERVICES`
excluido (universo de constituyentes no establecido).

`tests/g1/test_g1e_v3_aggregation.py` (23 tests) fija la cadena:
`-001` intacto, `-002` byte-determinista, run `assessment-run-g1-e-001`
replayable offline, y cada control anterior.

## E6 — Auditoría de calidad (OSS probe)

Regla adoptada: **ninguna infraestructura genérica nueva sin un OSS
scan failure-driven previo**. La semántica regulatoria es propiedad del
proyecto; el tooling genérico se adopta de OSS maduro.

### Hypothesis (ADOPT_EVAL → ADOPT, dev-only)

`tests/g1/test_g1e_v3_properties.py`: 7 propiedades sobre las
invariantes V3 con oráculo metamórfico — el motor no crashea y emite
veredicto válido (P1), CONFIRMED_ENTITLED implica positivo usado (P2),
CONFIRMED_NOT_ENTITLED implica ausencia de positivos usados (P3),
replay determinista (P4), bloquear negativos no crea NOT_ENTITLED (P5),
negativo en otra ruta no derriba una ruta abierta (P6), y semántica
temporal de `covers()`/`effective_effect_at()` (P7). Ejecución
derandomizada (`derandomize=True`, sin database): ~1150 casos, 0
violaciones. Determinista y offline — apto para CI.

### mutmut (ADOPT_EVAL → ADOPT, dev-only, requiere Linux/WSL)

Scope: `semantics.py`, `temporal.py`, `coverage.py` (config en
`[tool.mutmut]` de `pyproject.toml`). mutmut no soporta Windows
nativo; el run se ejecuta en WSL.

```text
run inicial    1086 mutantes · 830 killed (~76%) · 251 survived
+ batch 1      56 tests binding → 77 survived
+ batch 2      21 tests binding → 27 survived
final          1059/1086 killed (~97.5%) · 0 no-tests
```

Los 27 supervivientes restantes son **equivalentes** (verificados caso
a caso, no gaps de test): literales `"UNKNOWN"`/`"OPEN"` en defaults
sólo comparados por desigualdad, `False`→`None` en acumuladores falsy,
strings de `IdentityResolution` nunca observados en el path EXACT,
`or`→`and` con operandos iguales, y `source_date_reliability` como
metadato de provenance no consumido por `is_stale`.

`tests/g1/test_g1e_v3_mutation_kills.py` (77 tests) fija la semántica
que el corpus no ejercitaba: gates fail-closed (`no_contract`,
`unknown_scope_no_evidence`, `out_of_source_scope`,
`can_produce_enumeration_negative` fuera de scope), fronteras temporales
(`age > max_staleness`, `[from,to)` exclusivo, `effective_to < as_of`
legacy, `valid_from`/`valid_to` inclusivos), propagación de
`CoverageQuery` (entity_class, territorial_basis, effective_date) en la
query principal y en ALL_REQUIRED, preferencia `source_as_of` sobre
`retrieved_at` en `freshness_at`, estados de raíz (OPEN/CLOSED/
UNRESOLVED/ABSENT, retirada sin intervalos), y agregación V3
(intersección legal de rutas, cierre por rutas vs retirada, orden de
cierre entre raíces, positivo futuro/expirado, diag de route_conflict).

Sin cambios de producción: cero mutantes se "mataron" modificando
semántica.

## Secuencia restante

```text
E1  DONE — semántica negativa + agregación route-aware congelada
E2  DONE — vocabulario PSD2 granular congelado (namespace PAYMENT_*,
    mapeo verbatim EBA + correspondencia BdE; BdE "5" = COMPOSITE
    Ley 16/2009, explicado por la columna NORMATIVA del propio xlsx)
E3  DONE — corpus preregistrado, 10 anclas reales, 0 sintéticas
    (sucesor -003 tras E3-F01/F02/F03/F04; -001/-002 históricos)
E4  DONE — derivación de negativos granulares materializada
    (negative_scope ROOT_FAMILY|ROUTE_CAPABILITY, interval_end
    EXCLUSIVE, capability-vector completeness scoped; artefactos
    g1-e-001 deterministas; assess() intacto)
E4.1/E5-A
    DONE — bridge al dominio de assessment (campos E4 completos,
    interval_end EXCLUSIVE consumible, root_key + provenance en
    facts, evaluación bitemporal de raíz; sucesor -002)
E5  DONE — ASSESSMENT_SEMANTICS_V3 route-aware (22/22 casos;
    Wise NOT_ENTITLED vs Eupago ENTITLED reproduce el contraste
    preregistrado; V1/V2 congeladas)
E6  DONE — quality probe OSS: Hypothesis derandomizado (7
    propiedades, 0 violaciones) + mutmut 1059/1086 killed
    (~97.5%; 27 supervivientes equivalentes documentados).
    Cierre G1 pendiente de decisión.
```
