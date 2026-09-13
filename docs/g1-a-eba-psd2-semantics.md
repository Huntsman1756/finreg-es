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

## H9-A — evaluación preliminar (pendiente de A4)

```text
authorisation_from          → ENT_AUT[impares]       REPRESENTABLE
authorisation_withdrawn_at  → ENT_AUT[pares]         REPRESENTABLE
current/expired             → paridad de ENT_AUT     REPRESENTABLE
```

sin inferencia heurística: la regla de paridad es semántica
**documentada por la autoridad**, no interpretación nuestra.
Confirmación formal en A4 contra el Annex de 2019/410 (qué campos son
exigibles por tipo — p. ej. si PSD_ENL/PSD_EXC deben llevar `ENT_AUT`).

## H9-B — evidencia acumulada (pendiente de A5)

- Disclaimer del registro (verbatim, en el propio JSON congelado):
  *"this Register has no legal significance and confers no rights in
  law"*; la exactitud es responsabilidad de las NCA.
- Q&A 2019_4650: la autorización es competencia NCA; el registro
  reproduce información notificada (≥1 actualización diaria).
- Ambas apuntan a **CASE 5** (corroboración NCA) para cualquier
  `CONFIRMED_AUTHORISED`, con EBA como evidencia estructural fuerte
  pero no legalmente constitutiva.

## Invariante confirmado por fuente primaria

Q&A 2019_4650 + final report ¶23-26: las entidades de crédito pueden
prestar todos los servicios de pago pero **no están en el registro
PSD2** (van por el Credit Institutions Register):

```text
not found in EBA PSD2 + entity_class = credit institution
≠ negative evidence     (confirmado en fuente primaria)
```
