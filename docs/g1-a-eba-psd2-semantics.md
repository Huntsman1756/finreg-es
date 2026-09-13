# G1-A — evidencia EBA PSD2: semántica de `ENT_AUT` (A1–A3)

Registro de hallazgos del workstream G1-A. **No modifica reglas**:
`derivation.py`/`assessment` intactos; esto es investigación de
evidencia según el orden preregistrado A1→A6.

## A1 — paquete de evidencia congelado

`fixtures/g1/sources/manifest.json` (`g1-a1-2026-09-13`), 6 snapshots
nuevos + el JSON EBA ya congelado en G0.5:

| Snapshot | Hipótesis |
|----------|-----------|
| `eba-psd2-json-data-specification.xlsx` | H9-A — spec oficial de campos JSON |
| `eu-2019-410.pdf` | H9-A — info exigible por tipo de entidad |
| `eu-2019-411.pdf` | H9-A — RTS; art. 17(1) exige descarga estandarizada |
| `eba-psd2-register-landing.html` | H9-B — alcance, 9 categorías, disclaimer |
| `eba-qa-2019-4650.html` | H9-B — jerarquía probatoria, CI fuera del registro |
| `eba-rts-its-final-report.pdf` | H9-B — ¶23-26 CI no cubiertos; ¶41-42 agentes |

## A2 — mapeo 2019/410 → campos reales del JSON

Censo sobre el snapshot congelado (330 291 entidades, 9 `EntityType`):

| Concepto regulatorio | Representación física |
|----------------------|------------------------|
| Fecha(s) de autorización/retirada | `ENT_AUT` — **lista** de fechas cronológicas |
| Estado vigente | **derivado por paridad** de `ENT_AUT` (ver abajo) |
| Estado de agente/sucursal | `DER_CHI_ENT_AUT` = `Active`/`Inactive`, heredado del parent |
| Tipo de entidad | `EntityType` (PSD_PI, PSD_EMI, PSD_AISP, PSD_EPI, PSD_EEMI, PSD_ENL, PSD_BR, PSD_AG, PSD_EXC) |
| Referencia nacional | `ENT_NAT_REF_COD` |
| Exclusión art. 3 PSD2 | `ENT_EXC` + `ENT_DES_ACT_EXC_SCP` (sólo PSD_EXC) |
| Parent de agente/sucursal | `ENT_TYP_PAR_ENT` + `ENT_COD_PAR_ENT` |
| Servicios por estado | `Services`: `{país: código(s) PS_*}` |

Distribución `ENT_AUT` por longitud: 1→4 099 · 2→2 271 · 3→37 · 4→14.
Sin `ENT_AUT`: sólo PSD_AG y PSD_BR (derivan del parent).

## A3 — la especificación oficial resuelve la ambigüedad

Texto literal del spec (`sharedStrings`, propiedad `ENT_AUT`):

> "A list of dates representing all dates on which a change in
> Registration/Authorisation status of the Entity has occurred, dates
> listed in chronological order. **Odd numbers show a date of
> authorisation/registration. Even numbers show the date of withdrawal
> of authorisation/registration.**"

Consecuencia mecánica:

```text
len(ENT_AUT) impar  → último evento = autorización → vigente
len(ENT_AUT) par    → último evento = retirada     → retirada
pares consecutivos  → intervalos [aut, retirada]
```

Casos reales verificados en el snapshot:

- `FR_ACPR!384558` (PSD_PI): `['2023-03-23','2026-08-27']` → retirada
  el 2026-08-27; **permanece listada** con servicios en 31 países.
- `LT_LT_BL_277289060` (PSD_PI): `['2012-07-26','2019-06-03']` →
  retirada 2019-06-03.
- `ES_BE!6950` (PSD_PI, corpus G0): `['2026-09-07']` → vigente.

El registro **retiene entidades retiradas con fecha** — 2 552
retiradas vs 3 936 vigentes con `ENT_AUT`. Esto es relevante para
G1-E (negativos demostrables): la retirada es un hecho positivo
registrado, no una ausencia.

Para agentes: el spec indica que `DER_CHI_ENT_AUT` hereda del parent
(`ENT_AUT='NO'` del parent → `Inactive`), y Q&A 2019_4650 (¶41-42 del
final report) confirma que los servicios de agentes **no se listan**:
prestan los del principal. Derivar servicios de un agente exige el
join parent→child, no lectura directa.

## A4 — matriz `EntityType × obligación normativa × representación JSON`

Extraída del Annex de Reg. (UE) 2019/410 (snapshot `eu-2019-410.pdf`)
cruzada con el spec oficial del JSON (`eba-psd2-json-data-specification.xlsx`)
y el censo del snapshot congelado.

| EntityType | Categoría legal | Annex | Fecha auth/reg exigible | Fecha retirada exigible | Raw field | Directo/heredado | Estado actual derivable |
|------------|-----------------|-------|------------------------|-------------------------|-----------|------------------|-------------------------|
| PSD_PI | authorisation (art. 4(4) PSD2) | Table 1 | sí — campo 9 "date of authorisation" | sí — campo 10 "date of withdrawal of authorisation" | `ENT_AUT` | directo | sí (paridad) |
| PSD_EMI | authorisation (art. 2(1) EMD2) | Table 4 | sí — campo 9 "date of authorisation" | sí — campo 10 | `ENT_AUT` | directo | sí (paridad) |
| PSD_EPI | **registration** (art. 32 PSD2 exempt) | Table 2 | sí — campo 9 "date of **registration**" | "where applicable" — campo 10 | `ENT_AUT` | directo | sí (paridad) |
| PSD_AISP | **registration** (art. 33 PSD2) | Table 3 | sí — campo 9 "date of registration" | "where applicable" — campo 10 | `ENT_AUT` | directo | sí (paridad) |
| PSD_EEMI | **registration** (art. 9 EMD2 exempt) | Table 5 | sí — campo 9 "date of registration" | "where applicable" — campo 10 | `ENT_AUT` | directo | sí (paridad) |
| PSD_ENL | national-law entitlement (art. 2(5) PSD2) | Table 7 | **no** — el Annex no exige estado ni fechas | **no** | `ENT_AUT` (EBA lo publica aunque el Annex no lo exija) | directo | parcial — paridad legible, base normativa ausente |
| PSD_EXC | exclusión art. 3(k)(i)(ii)/(l) PSD2 | Table 8 | no — sólo "current registration status" (campo 9, lista) | no | `ENT_AUT` + `ENT_EXC` + `ENT_DES_ACT_EXC_SCP` | directo | parcial — idem |
| PSD_AG | agente (art. 4(38) PSD2) | Table 6 | no — sólo "current registration status" del agente | no | `DER_CHI_ENT_AUT` (`Active`/`Inactive`) | **heredado del parent** | sólo como evidencia de estado del parent |
| PSD_BR | sucursal EEA (art. 4(39) PSD2) | Tables 1–5 (dentro del parent) | no | no | `DER_CHI_ENT_AUT` | **heredado del parent** | sólo como evidencia de estado del parent |

### Las cuatro cuestiones preregistradas, resueltas

**1. Secuencia completa y ordenada — sí.** El spec fija que `ENT_AUT`
es "*all* dates on which a change … has occurred, in chronological
order": el orden posicional *es* el significado. No es un conjunto de
fechas; es el log de transiciones notificado por la NCA.

**2. Cardinalidad — no contractual.** `1–4` es `max_observed_length`
del snapshot (330 291 entidades), no límite del formato. La regla debe
aceptar una secuencia arbitraria válida:

```text
posición impar → authorisation/registration
posición par   → withdrawal
```

**3. Authorisation vs registration — por EntityType, confirmado.**
Tables 1 y 4 exigen "date of **authorisation**"; Tables 2, 3 y 5
"date of **registration**". `ENT_AUT` codifica ambas indistintamente —
el mecanismo jurídico (`AUTHORISATION`/`REGISTRATION`/`EXEMPTION`/…)
lo gobierna el `EntityType`, no el campo. Generalizar `AUTHORISATION`
desde PI/EMI a los nueve tipos sería un falso positivo real: un AISP
"active" está *registrado*, no *autorizado*.

**4. Herencia — semántica distinta.** `DER_CHI_ENT_AUT` reproduce el
estado del parent (spec: parent `ENT_AUT='NO'` → child `Inactive`):
`parent authorised + child declared ≠ child independently authorised`.
El estado del child es evidencia *del parent*, nunca autorización
propia.

## Invariantes de parser preregistrados (antes de A5)

```text
ENT_AUT == [] / missing        → UNKNOWN, nunca active
dates no interpretables        → finding + UNKNOWN
elemento no-fecha              → finding + UNKNOWN
alternancia/cardinalidad rara  → finding + UNKNOWN
secuencia impar válida         → reported status = active
secuencia par válida           → reported status = withdrawn
DER_CHI_ENT_AUT heredado       → evidencia de estado del parent
                                 nunca AUTHORISATION independiente
```

Y preservar **todos los intervalos**, no sólo el estado final:

```text
[{from: d1, to: d2}, {from: d3, to: d4}, …]
```

Las 2 552 entidades retiradas que EBA conserva son evidencia positiva
de retirada (presencia registrada, no ausencia) — hallazgo congelado
para G1-E, sin adelantar reglas.

## H9-A — dictamen A4

```text
PROVEN (acotado):
  PSD_PI / PSD_EMI   → authorisation sequence derivable
  PSD_EPI/AISP/EEMI  → registration sequence derivable
  PSD_AG / PSD_BR    → estado heredado, nunca autorización propia
  PSD_ENL / PSD_EXC  → ENT_AUT legible pero fuera del mínimo Annex;
                       tratar como status reportado sin base normativa
                       explícita → conservador
```

## H9-B — evidencia acumulada + propuesta A5

Precisión semántica: el disclaimer no significa que los datos EBA "no
sirvan como evidencia"; significa que **el registro central no es el
acto jurídico que confiere el derecho**:

```text
EBA evidence CAN establish:
  NCA_REPORTED_AUTH_STATUS = ACTIVE

EBA evidence alone does NOT establish:
  AUTHORISATION_GRANTED_BY_EBA   (el acto constitutivo es NCA)
```

Evidencia:

- Disclaimer del registro (verbatim, en el propio JSON congelado):
  *"this Register has no legal significance and confers no rights in
  law"*; la exactitud es responsabilidad de las NCA.
- Q&A 2019_4650: la autorización es competencia NCA; el registro
  reproduce información notificada (≥1 actualización diaria).
- 2019/411 art. 17(1): la descarga estandarizada es obligación de EBA
  — el JSON *es* el formato oficial de difusión, no un subproducto.

### Política A5 — CONGELADA (suficiencia y conflicto)

Jerarquía de fuentes (no una regla `T0>T1>T2>T3`; la suficiencia es
**claim-specific**):

```text
T0  ACTO / DECISIÓN CONSTITUTIVA NCA    autorización, retirada…
T1  REGISTRO PRIMARIO NCA             publicación oficial del estado
T2  EBA CENTRAL REGISTER              reporte NCA→EBA, oficial,
                                      no constitutivo
T3  CLASIFICACIÓN ESTADÍSTICA/AUX.    BdE IFM, etc.
```

Suficiencia por claim:

```text
T0/T1 → pueden sostener estado jurídico positivo si identidad,
        categoría, actividad, tiempo y ámbito encajan.

T2 EBA → sostiene NCA_REPORTED_AUTH_STATUS = ACTIVE/WITHDRAWN
         con plena trazabilidad de ENT_AUT.
         Para PSD_PI/PSD_EMI puede alimentar EntitlementAssertion
         positiva cuando servicio y demás dimensiones estén
         explícitamente cubiertos.
         NO significa "EBA autoriza" ni la convierte en constitutiva.

T3     → nunca sostiene por sí solo ENTITLED_TO_PROVIDE.
```

Regla conceptual de G1-A (se detiene aquí — el assessment final sigue
siendo `(entity, activity, jurisdiction)` y `ENT_AUT` sólo resuelve
una pieza):

```text
PSD_PI / PSD_EMI
+ exact identity
+ valid ordered ENT_AUT
+ odd final position
+ activity explicitly covered
────────────────────────────────
home_authorisation_status = ACTIVE
evidence_basis  = NCA_REPORTED_VIA_EBA
entry_mechanism = AUTHORISATION
```

```text
PSD_EPI / PSD_AISP / PSD_EEMI
+ odd ENT_AUT
→ REGISTERED_ACTIVE
→ ENTRY_MECHANISM = REGISTRATION    (nunca AUTHORISATION)

PSD_AG / PSD_BR
+ DER_CHI_ENT_AUT
→ parent regulatory status evidence
→ 0 independent authorisation inference

PSD_ENL / PSD_EXC
+ field observable + parity mechanically readable
+ no Annex basis for equivalent status semantics
→ UNKNOWN / finding   (insufficient legal basis)
```

Home authorisation ACTIVE + actividad autorizada **no** demuestra
entitlement en España vía FPS para una entidad extranjera — eso es
G1-D, no G1-A.

### Regla de conflicto (preregistrada)

Los niveles superiores **no ganan silenciosamente**:

```text
T1 says ACTIVE / T2 says WITHDRAWN
→ comprobar: ¿effective time distinto? ¿snapshot time distinto?
  ¿lag EBA? ¿retirada + reautorización?
→ si no se reconcilia mecánicamente:
  CONFLICTING_SOURCE_ASSERTIONS → INDETERMINATE
```

Cero resolución silenciosa de conflictos — principio G0 intacto.

### Dictamen A5

```text
H9-A  PROVEN

H9-B  PROVEN WITH QUALIFICATION

EBA PSD2 = official NCA-reporting evidence layer,
           non-constitutive, but evidentially sufficient
           for reported regulatory status.
           NOT globally sufficient by itself for
           (entity, activity, jurisdiction) entitlement.
```

Alternativa evaluada y descartada: exigir siempre corroboración NCA —
reduciría el registro central a dato informativo pese a contener datos
NCA estructurados y semánticamente definidos.

### Frontera de fases

```text
G1-A rule delta → temporal regulatory status
G1-D            → territorial entitlement / FPS
G1-E            → withdrawal, expiry, negative assessment
```

El corpus real de 2 552 entidades retiradas queda congelado como
evidencia para G1-E — no se adelantan reglas.

## A6 — draft del delta de reglas (pendiente de aprobación)

Alcance: **temporal regulatory status** únicamente. Territorial = G1-D;
semántica de negativos/retirada = G1-E.

### Estado actual (lo que G1-A resuelve)

`_semantics_layer` (`extraction.py:612`) bloquea deliberadamente:
`ENT_AUT_DATE_ARRAY_NOT_STATUS_ENUM` → `BLOCKED_SEMANTICS_GAP`. El
ledger G0.6 ya lleva `ent_aut_raw` por claim (110 claims EBA); el
ruleset G0.7 emite `legal_effect: UNKNOWN` con la limitación
documentada verbatim en `legal_basis`. La evidencia existe; falta la
interpretación autorizada.

### Delta del motor (`derivation.py`)

Una sola derivación efectiva nueva, retrocompatible (el ruleset G0.7
no la usa → output G0 byte-idéntico):

```text
EBA_ENT_AUT_SEQUENCE  sobre  ent_aut_raw
  missing / [] / no-lista      → status UNKNOWN + finding
  elemento no-fecha            → status UNKNOWN + finding
  secuencia válida impar       → status ACTIVE
  secuencia válida par         → status WITHDRAWN
  siempre: intervals = [{from,to},...] preservados
```

Necesita además un mecanismo de *emit condicionado por estado*: la
regla G1 expresa `legal_effect` y `entry_mechanism` en función del
status derivado — implementación propuesta: el motor expone
`ent_aut_status`/`ent_aut_intervals` como campos derivados del grupo
de claims (namespace `eba_*`), y las condiciones de regla pueden
hacer match sobre ellos. Así la lógica queda en el ruleset
declarativo, no hardcodeada.

`build_artifact` se parametriza (rutas + versiones); el artefacto G0.7
sigue reproduciéndose byte-idéntico con sus constantes congeladas.

### Delta del ruleset (`fixtures/g1/derivation-rules.json`, nuevo)

```text
eba-psd2-domestic-presence  (G1)
  match: PI/EMI + country=ES + ent_aut_status=ACTIVE
  emit:  ENTITLED_TO_PROVIDE, AUTHORISATION, DOMESTIC,
         effective_from = última fecha impar (última autorización),
         effective_to = null, evidence_basis = NCA_REPORTED_VIA_EBA

eba-psd2-domestic-presence-withdrawn  (G1, nuevo)
  match: PI/EMI + country=ES + ent_aut_status=WITHDRAWN
  → NO aserción positiva; status WITHDRAWN + intervals registrados
  (la lectura jurídica de la retirada es G1-E)

eba-psd2-passport-services  (G1)
  sin cambio de legal_effect (UNKNOWN): territorial = G1-D;
  se adjunta reported_status como atributo

eba-psd2-registered-types  (G1, nuevo)
  match: EPI/AISP/EEMI + ent_aut_status=ACTIVE
  emit:  REGISTERED_ACTIVE, entry_mechanism=REGISTRATION
  ⚠ requiere extensión de ENTITY_CLASSES/activities (ver abajo)

eba-psd2-enl-exc  (G1, nuevo)
  match: ENL/EXC
  → finding INSUFFICIENT_LEGAL_BASIS (sin base Annex para status)

eba-psd2-agent-branch  (G1, nuevo)
  match: AG/BR con DER_CHI_ENT_AUT
  → evidencia de estado del parent; join parent→child requiere
    soporte cross-record del motor — DECISIÓN: incluir en G1-A o
    aplazar
```

### Delta del schema de aserciones (v1.1)

Tres campos nuevos en `derived-assertions`:

```text
evidence_basis      "NCA_REPORTED_VIA_EBA" | "NCA_PRIMARY" | …
reported_status     "ACTIVE" | "WITHDRAWN" | "UNKNOWN"
status_intervals    [{"from": ..., "to": ...|null}, ...]
```

Retrocompatible: los campos serían `required` sólo en el artefacto G1
(schema `derived-assertions` v1.1 nuevo; v1 congelado no se toca).

### Decisiones tomadas (usuario)

1. **Vocabulario**: extender `vocab.py` — `ACCOUNT_INFORMATION_
   SERVICE_PROVIDER`, `EXEMPTED_PAYMENT_INSTITUTION`,
   `EXEMPTED_E_MONEY_INSTITUTION`, actividad `ACCOUNT_INFORMATION_
   SERVICES`; más constantes `REPORTED_STATUSES` y `EVIDENCE_BASES`.
2. **Agentes/sucursales**: join parent→child incluido en G1-A —
   `ent_cod_par_ent`/`ent_typ_par_ent` resuelven contra
   `(entity_type, ent_cod)` del parent y exponen `eba_parent_status`.
   Sin casos AG/BR en el corpus g0.5 (mecanismo inerte aquí; casos
   reales quedan para G1 posterior).
3. **Retiradas**: `WITHDRAWN` se materializa como `reported_facts`
   (hecho reportado, no EntitlementAssertion; sin `NOT_ENTITLED`).

## A6 — Registro de ejecución

Ruleset `fixtures/g1/derivation-rules.json`
(`FINREG_G1_DERIVATION_V1`), artefacto
`fixtures/g1/derived-assertions-g1-a-001.json`
(`FINREG_G1_DERIVED_ASSERTIONS_V1`):

```text
python -m finreg_es.derivation --g1 \
    --out fixtures/g1/derived-assertions-g1-a-001.json
```

Inputs congelados: corpus g0.5 + claim-ledger g0.6-a-003 + manifest
g0.5 (sin nuevas extracciones; la delta se aplica sobre claims EBA ya
capturados en G0).

Resultado:

```text
assertions      258   (G0: 257)
findings          1   (G0: 3)
reported_facts    1   (nuevo tipo de registro)
```

Divergencias exactas G0 → G1 (sólo en claims `eba-psd2-register`):

```text
eba-psd2-domestic-presence UNKNOWN  ×8  → 0
eba-psd2-domestic-active ENTITLED   ×0  → 7   (PI/EMI ES, ACTIVE,
                                             AUTHORISATION,
                                             effective_from = última
                                             fecha impar ENT_AUT)
eba-psd2-registered-active ENTITLED ×0  → 2   (AISP ES, ACTIVE,
                                             REGISTRATION,
                                             ACCOUNT_INFORMATION_
                                             SERVICES)
finding UNSUPPORTED_ENTITY_CLASS    ×2  → 0   (los 2 AISP ahora
                                             soportados)
G05-017 (PSD_PI, secuencia par)         → reported_fact WITHDRAWN
                                          intervalo 2019-03-15 →
                                          2026-07-01; sin aserción
finding DERIVED_PRECONDITION_NOT_MET    → 1 (sin cambio; G05-030 CI)
```

Todas las aserciones EBA llevan `evidence_basis=NCA_REPORTED_VIA_EBA`,
`reported_status` e `status_intervals`. Las aserciones passport EBA
conservan `legal_effect=UNKNOWN` (G1-D) aunque ahora portan el estado
reportado. Reglas no-EBA: verbatim del ruleset G0.7.

### Verificación / gate

```text
artefacto G0.7   → regeneración byte-idéntica verificada
                   (ruleset G0 no referencia constructos v1.1)
185 tests        → PASS
schema v1        → congelado; artefactos G0 revalidados sin cambio
schema v1.1      → nuevo: +evidence_basis, +reported_status,
                   +status_intervals, +reported_facts, +emit_status_fact;
                   todo opcional → artefactos v1 siguen siendo válidos
```

Pendiente para cierre de G1-A: preregistro de casos de assessment G1
(active/withdrawn/malformed/AISP/parent-child) antes de tratar este
output como resultado de assessment; la semántica jurídica de
WITHDRAWN (expiración/negativo) queda en G1-E.

## A7 — ASSESSMENT_SEMANTICS_V2 (preregistrado, sin ejecutar)

El caso AISP demostró que el enum público de G0 es incoherente:
`CONFIRMED_AUTHORISED` + `entry_mechanism=REGISTRATION` es
contradictorio, y G1-C añadirá `NOTIFICATION`/`STATUTORY_ENTITLEMENT`.
La pregunta real de FinReg es «¿puede esta entidad prestar esta
actividad en esta jurisdicción?» — el resultado público responde
**qué**, `entry_mechanism` explica **por qué**.

### Taxonomía versionada

```text
ASSESSMENT_SEMANTICS_V1 (congelada, artefactos G0)
  CONFIRMED_AUTHORISED / NO_ENTITLEMENT_EVIDENCED /
  CONFIRMED_NOT_AUTHORISED / INDETERMINATE

ASSESSMENT_SEMANTICS_V2 (G1+)
  CONFIRMED_ENTITLED          (ex CONFIRMED_AUTHORISED)
  NO_ENTITLEMENT_EVIDENCED    (sin cambio)
  CONFIRMED_NOT_ENTITLED      (ex CONFIRMED_NOT_AUTHORISED)
  INDETERMINATE               (sin cambio)
```

No se reescribe historia: los artefactos y casos G0 permanecen en V1;
`assess()` seleccionará la versión semántica explícitamente
(`semantics_version`), y el replay G0 sigue byte-idéntico.

### Política de `reported_facts` en assessment

`reported_facts` no es una segunda ruta hacia el resultado: sigue la
arquitectura `SourceAssertion → derivation → EntitlementAssertion →
assess()`. Un reported_fact puede **bloquear o explicar**, nunca
elevar ni crear un negativo:

```text
EntitlementAssertion ACTIVE     → puede producir CONFIRMED_ENTITLED
reported_fact WITHDRAWN         → NO produce CONFIRMED_NOT_ENTITLED
                                  (transformación jurídica = G1-E);
                                  bloquea el positivo -> INDETERMINATE
reported_fact MALFORMED/UNKNOWN → INDETERMINATE
reported parent status          → nunca entitlement propio del child
```

### Reason codes V2 añadidos

```text
ACTIVE_ENTITLEMENT_EVIDENCED        (sustituye a SUPPORTED_BY_ACTIVE_
                                     ASSERTIONS en modo V2)
WITHDRAWAL_SEMANTICS_DEFERRED       (retirada observada; lectura
                                     jurídica = G1-E)
MALFORMED_STATUS_SEQUENCE           (secuencia temporal inválida)
TERRITORIAL_ENTITLEMENT_UNRESOLVED  (FPS/pasaporte = G1-D)
PARENT_STATUS_NOT_CHILD_ENTITLEMENT (estado heredado del parent)
INSUFFICIENT_LEGAL_BASIS            (ENL/EXC y análogos)
```

Los reason codes V1 compartidos (`IDENTITY_NOT_FOUND`,
`NO_ASSERTIONS_IN_SCOPE`, `ALL_EVIDENCE_STALE`, `CONFLICTING_
ASSERTIONS`, `ENTITLEMENT_EXPIRED`, …) se conservan en V2.

### Casos preregistrados — `fixtures/g1/assessment-cases.json`

| caso | entidad | unidad | esperado V2 | razón |
|------|---------|--------|-------------|-------|
| G1A-001 | G05-016 PI activo | PAYMENT_SERVICES/ES | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |
| G1A-002 | G05-004 PI activo | PAYMENT_SERVICES/ES | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |
| G1A-003 | G05-018 EMI activa | E_MONEY_ISSUANCE/ES | CONFIRMED_ENTITLED | ACTIVE_ENTITLEMENT_EVIDENCED |
| G1A-004 | G05-020 AISP | ACCOUNT_INFORMATION_SERVICES/ES | CONFIRMED_ENTITLED + REGISTRATION | ACTIVE_ENTITLEMENT_EVIDENCED |
| G1A-005 | G05-021 AISP | ACCOUNT_INFORMATION_SERVICES/ES | CONFIRMED_ENTITLED + REGISTRATION | ACTIVE_ENTITLEMENT_EVIDENCED |
| G1A-006 | G05-017 PI retirado | PAYMENT_SERVICES/ES | INDETERMINATE | WITHDRAWAL_SEMANTICS_DEFERRED |
| G1A-007 | G05-016 PI activo | PAYMENT_SERVICES/DE | INDETERMINATE | TERRITORIAL_ENTITLEMENT_UNRESOLVED |
| G1A-008 | G05-030 CI | PAYMENT_SERVICES/ES | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE |
| G1A-009 | G05-018 EMI | PAYMENT_SERVICES/ES | NO_ENTITLEMENT_EVIDENCED | NO_ASSERTIONS_IN_SCOPE |
| G1A-010 | G05-999 inexistente | PAYMENT_SERVICES/ES | INDETERMINATE | IDENTITY_NOT_FOUND |

Categorías no representables en el corpus congelado (documentadas en
`cases_meta`, mismo patrón que G0): `MALFORMED_STATUS_SEQUENCE`,
`PARENT_STATUS_NOT_CHILD_ENTITLEMENT`, `INSUFFICIENT_LEGAL_BASIS`
(ENL/EXC), `CONFIRMED_NOT_ENTITLED` y multi-ruta — sin casos reales
que las ejerciten; no se fabrican sintéticos.

### Gate A8/A9

```text
G0 V1 replay        → byte-idéntico, 21/21 casos iguales
G1 casos            → según preregistro
0 reported_fact     → negativo automático
0 REGISTRATION      → AUTHORISATION
0 passport          → domestic entitlement
0 parent status     → child entitlement
```

## A8 — Ejecución y divergencia auditada

Implementación: `assess(semantics_version="V1|V2",
reported_facts=…)`. V1 es el default y reproduce G0 byte-idéntico
(la traducción V1→V2 ocurre en la frontera `emit`; la lógica interna
sigue razonando en V1). `AssessmentV2` y los seis reason codes nuevos
viven en `vocab.py`. Runner: `python -m finreg_es.assessment_run --g1`.

Ejecución `fixtures/g1/runs/assessment-g1-a-001.json`:

```text
cases 10 · matches 10 · reason_mismatches 0 · entry_mechanism 10/10
CONFIRMED_ENTITLED 5 · INDETERMINATE 3 · NO_ENTITLEMENT_EVIDENCED 2
```

**Divergencia auditada (primera ejecución, 8/10):** G1A-004/005
devolvieron `NO_ENTITLEMENT_EVIDENCED /
ASSERTION_OUT_OF_SOURCE_SCOPE` — el contrato de fuente EBA v1.0.0 no
declaraba `ACCOUNT_INFORMATION_SERVICES` en `activities_covered`, así
que las nuevas aserciones AISP eran inadmisibles. Corrección:
`eba-psd2-register.json` → `contract_version 1.1.0` (clases
AISP/EPI/EEMI + actividad AIS añadidas; nota H4 parcialmente
cerrada). La preregistro NO se editó: el fix fue en el contrato de
fuente, que es donde vive la semántica de cobertura. G0 replay no
afectado (ninguna aserción G0 referencia las clases nuevas).

**Gate verificado:**

```text
G0 V1 replay          → test_run_replays_offline_byte_identical PASS
                        (cases + summary byte-idénticos; code_sha
                        difiere por diseño — detecta cambio de código)
G1 casos              → 10/10 match, 0 reason/entry mismatches
reported_fact→neg     → 0 (G1A-006: fact WITHDRAWN → INDETERMINATE)
REGISTRATION→auth     → 0 (G1A-004/005: CONFIRMED_ENTITLED+REGISTRATION)
passport→domestic     → 0 (G1A-007: INDETERMINATE/TERRITORIAL_…)
parent→child          → 0 (sin casos AG/BR en corpus; política activa)
tests                 → suite completa PASS; artefactos G1 validan
                        contra schemas v1.1; v1 intacto
```

## A9 — Closeout G1-A

```text
H9-A  CLOSED — PROVEN (scoped): ENT_AUT es secuencia alternante
      documentada (spec oficial EBA); PI/EMI=authorisation,
      EPI/AISP/EEMI=registration, AG/BR=parent-inherited,
      ENL/EXC=insufficient legal basis.
H9-B  CLOSED — PROVEN WITH QUALIFICATION: EBA PSD2 es capa oficial
      de reporte NCA (T2), no constitutiva; suficiente para
      CONFIRMED_ENTITLED home+domestic cuando servicio y ámbito
      encajan; insuficiente por sí sola para entitlement territorial
      (G1-D) ni para negativos (G1-E).
```

El invariante CI se mantiene: `entity_class=CREDIT_INSTITUTION` +
ausencia en EBA PSD2 → sin inferencia negativa (G1A-008).

Para G1 quedan abiertos, en orden: G1-B (enumeración BdE), G1-C
(MiCA 60/63), G1-D (territorial/FPS y multi-ruta), G1-E (retirada/
expiración/negativos — ya existe el corpus de 2 552 retiradas reales
y los intervalos preservados).

### Invariante separado (confirmado en fuente primaria)

```text
entity_class = CREDIT_INSTITUTION
not found in EBA PSD2
→ NO NEGATIVE INFERENCE
```

Q&A 2019_4650 + final report ¶23-26: las entidades de crédito van por
el Credit Institutions Register; su ausencia aquí no contamina
ninguna lógica de exhaustividad.
