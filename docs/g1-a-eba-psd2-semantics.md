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

### Propuesta A5 — jerarquía de fuentes (pendiente de ratificación)

```text
Nivel 0  acto constitutivo           registro NCA (BdE/CNMV/…)
Nivel 1  reporte NCA→EBA             registro central EBA (esta fuente)
Nivel 2  clasificación/estadística   p. ej. BdE MFI (nunca constitutivo)
```

Consecuencia propuesta:

```text
EBA presence + ENT_AUT impar + servicio X + territorio
  → SourceAssertion fuerte: NCA_REPORTED_AUTH_STATUS=ACTIVE
  → puede sostener ENTITLED_TO_PROVIDE como evidencia oficial de
    reporte, marcada evidence_level=NCA_REPORTED (no NCA_CONSTITUTIVE)

CONFIRMED_AUTHORISED
  → exige corroboración NCA (CASE 5) o decisión explícita de
    jerarquía que declare NCA_REPORTED suficiente para el output
    público — esa declaración es una decisión de política de
    evidencia de G1, no un default del parser
```

Alternativa evaluada y descartada: tratar `ENT_AUT` impar como
autorización constitutiva — contradice el disclaimer y la
distribución de competencias del propio marco (art. 11 PSD2: granting
queda en NCA).

### Invariante separado (confirmado en fuente primaria)

```text
entity_class = CREDIT_INSTITUTION
not found in EBA PSD2
→ NO NEGATIVE INFERENCE
```

Q&A 2019_4650 + final report ¶23-26: las entidades de crédito van por
el Credit Institutions Register; su ausencia aquí no contamina
ninguna lógica de exhaustividad.
