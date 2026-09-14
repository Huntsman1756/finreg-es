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

`fixtures/g1/sources/extracted/g1-e-negative-corpus.json`
(`g1-e-negative-corpus-2026-09-14`). Cada caso lleva tres
expectativas preregistradas: `expected_negative_evidence_class`,
`expected_route_outcome`, `expected_global_assessment` — así E4 puede
fallar la clase aunque E5 acierte el global. 0 entidades sintéticas.

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

## Secuencia restante

```text
E1  DONE — semántica negativa + agregación route-aware congelada
E2  DONE — vocabulario PSD2 granular congelado (namespace PAYMENT_*,
    mapeo verbatim EBA + correspondencia BdE; BdE "5" = COMPOSITE
    Ley 16/2009, explicado por la columna NORMATIVA del propio xlsx)
E3  DONE — corpus preregistrado, 10 anclas reales, 0 sintéticas
E4  derivation delta (negativos granulares + route_key)
E5  agregación negativa en assess()
E6  divergence audit / cierre G1
```
