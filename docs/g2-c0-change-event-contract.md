# G2-C0 — Regulatory change events: contrato de interpretación

Preregistro documental. G2-C **no está demostrado** hasta que exista
al menos un cambio estructural real (Type-B/C) procesado por esta
capa. Este documento congela el contrato de interpretación, no la
demostración.

```text
STRUCTURAL CHANGE (G2-B, sin semántica)
        ↓
REGULATORY CHANGE CANDIDATE (esta capa)
        ↓
domain rule + provenance
        ↓
SUPPORTED_EVENT | BLOCKED | NOT_REGULATORY
```

## Regla esencial

> G2-C interpreta cambios observados; nunca reconstruye un evento que
> el diff no observó.

Un evento sólo existe si hay un `added/removed/changed` estructural
que lo sustente, con provenance bilateral (left + right observation).

## Artefacto de candidato

Cada candidato preserva:

```text
candidate_type
record_key
field_path
old_value / new_value

left_observation_id
right_observation_id
observed_after      # left.retrieved_at — cota inferior del cambio
observed_by         # right.retrieved_at — cota superior

effective_from      # sólo si la fuente lo publica
effective_basis     # SOURCE_DECLARED | EVIDENCE_AS_OF | UNKNOWN

admissibility       # SUPPORTED | BLOCKED
blocker
findings            # p.ej. NO_REMOVAL_ADMISSIBLE heredado de G2-B
```

Sin fecha jurídica publicada, `effective_from` queda ausente y el
evento queda acotado al intervalo `(observed_after, observed_by]`
(contrato §7). `EVIDENCE_AS_OF` es el mecanismo probatorio, no una
fecha jurídica.

## Catálogo de candidatos preregistrado

### EBA PSD2 (series `eba-psd2-register|full`)

```text
properties.ENT_AUT  + fecha (intervalo de retirada se cierra)
  → ROOT_WITHDRAWAL_CANDIDATE

properties.ENT_AUT  + nueva fecha de autorización
  → ROOT_REAUTHORISATION_CANDIDATE

services.ES  + PS_xx
  → CAPABILITY_APPEARED_CANDIDATE

services.ES  − PS_xx
  → CAPABILITY_DISAPPEARED_CANDIDATE
  → NUNCA negativo jurídico automático

record added
  → ENTITY_RECORD_APPEARED
  → presencia ≠ entitlement

record removed (ambos lados completos)
  → ENTITY_RECORD_DISAPPEARED
  → nunca withdrawal por sí solo
```

### BdE (registros tabulares)

```text
FECHA_BAJA  null → fecha
  → ENTITY_BAJA_CANDIDATE

MOTIVO_BAJA  changed / appeared
  → clasificar withdrawal / transformation / unresolved
    (precedente: TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED)

ACTIVIDADES  + código / − código
  → CAPABILITY_VECTOR_CHANGE_CANDIDATE
  → el significado jurídico depende del slice y la completitud
```

### ESMA / CNMV

Preregistro diferido hasta tener normalizadores G2 para esas series;
CNMV además opera bajo completitud `partial` por defecto (contrato
§10) — sus removals casi nunca serán admisibles.

## Anti-reglas congeladas

```text
- removed nunca ⇒ withdrawal/baja sin regla de dominio + completitud
- added nunca ⇒ entitlement (classification ≠ authorization)
- un candidato no consume retroproyección: effective_from sólo viene
  de la fuente o queda UNKNOWN
- candidate ≠ derived assertion: la aserción jurídica la emite la
  cadena de derivación existente (ruleset), alimentada por el evento
- NOT_REGULATORY es un resultado legítimo y debe registrarse
  (p.ej. cambio de dirección postal sin más)
```

## Dependencia con G2-D / G2-E

Los candidatos se evalúan sobre el corpus longitudinal real. La query
`known_at` (contrato §8) filtra qué eventos eran observables en K —
un candidato con `observed_by > K` no existe para esa query.

## Estado

```text
G2-C0  PREREGISTERED  (este documento)
G2-C0-scaffold  DONE (synthetic)
       clasificador implementado (finreg_es/change_events.py,
       FINREG_G2C_EVENT_RULES_V1) bajo task g2-c1-synthetic:
       par real EBA 0/0/0 → 0 candidatos
       (fixtures/g2/events/eba-psd2-20260913-vs-20260914.json) +
       slice sintético del catálogo
       (fixtures/g2/events/g2-c1-synthetic-contract-slice.json).
       El código procede del cold-run fallido sobre una task blocked
       (rama experiment/g2-c1-blocked-smoke); reaplicado tras endurecer
       STATUS IS AUTHORITATIVE (tools/task_preflight.py).
G2-C   OPEN           validado sobre slice sintético; pendiente el
                      primer Type-B/C real del corpus longitudinal
                      (task g2-c1, status=blocked).
```
