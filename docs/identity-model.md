# G0.2 — Modelo de identidad

## Principios

1. **Sin fuzzy joins automáticos.** La normalización es determinista (trim, mayúsculas,
   validación de checksum NIF/LEI); la validación no es matching.
2. **LEI nullable.** NIF también: las entidades extranjeras no tienen NIF español.
3. **`EXACT` exige identificador.** Un match solo por denominación no demuestra identidad.

## Identificadores

| kind | Origen | Notas |
|------|--------|-------|
| `NIF` | Registros ES | Checksum validado (módulo 23 / regla CIF). |
| `LEI` | GLEIF / registros | ISO 17442, mod 97-10. Nullable. |
| `BDE_REGISTRY_ID` / `CNMV_REGISTRY_ID` | Registro nacional | Estabilidad por verificar (H8). |
| `HOME_STATE_ID` | Registro del Estado miembro de origen | Clave para cross-border. |
| `ESMA_MICA_ID` | Registro ESMA MiCA | Puente para el listado MiCA de CNMV (H2). |

## Estados de resolución

| Estado | Condición | Efecto en assessment |
|--------|-----------|----------------------|
| `EXACT` | ≥ 1 identificador resuelve a un único `entity_id` sin conflicto | Se evalúa la consulta regulatoria |
| `AMBIGUOUS` | Múltiples candidatos por nombre **o** candidato único solo por nombre (`SINGLE_CANDIDATE_NAME_MATCH`) | `INDETERMINATE` + `AMBIGUOUS_IDENTITY` (C1) |
| `NOT_FOUND` | Ningún candidato | `INDETERMINATE` + `IDENTITY_NOT_FOUND` |
| `CONFLICTING_IDENTIFIERS` | Un identificador resuelve a ≥ 2 `entity_id` | `INDETERMINATE` + `CONFLICTING_IDENTIFIERS` |

Nota C1: el enunciado exige `AMBIGUOUS` (no `NOT_FOUND`) cuando hay varios candidatos por
nombre; congelamos además que **un único candidato por nombre tampoco es `EXACT`** (W6):
la denominación sola no identifica. Esto es deliberadamente conservador.

## Adopción de identificadores (W6) — caso MiCA CNMV

`adopt_identifiers_from_source(index, "ESMA_MICA_ID", nombre)`:

- La lista CNMV aporta solo denominación (H2).
- Se busca en el registro ESMA (portador de identificadores) una entidad con denominación
  exacta. Candidato único ⇒ `EXACT` con razon `ADOPTED_FROM_IDENTIFIER_BEARING_SOURCE`;
  varios ⇒ `AMBIGUOUS`; ninguno ⇒ `NOT_FOUND`.
- La adopción queda registrada como regla versionada, con provenance de los identificadores
  adoptados (fuente + `retrieved_at`).
- El caso ambiguo del corpus (G0.5) debe incluir dos entidades con denominación idéntica
  (fixtures ent-006/ent-007) para impedir regresiones hacia matching difuso.

## Separación identidad / assessment

`identity_resolution` y `assessment` son campos separados del resultado. Un problema de
identidad produce `assessment = INDETERMINATE` **solo** como gate de admisibilidad, con
reason de identidad; nunca produce `CONFIRMED_NOT_AUTHORISED` ni `CONFIRMED_AUTHORISED`.

Implementación: `finreg_es/identity.py` — `resolve_by_identifier`, `resolve_by_name`,
`adopt_identifiers_from_source`, validadores `is_valid_nif` / `is_valid_lei`.

## Diagnósticos LEI (FINREG_LEI_DIAGNOSTIC_V2)

`lei_diagnostic` separa lo que la validez booleana mezclaba:
`VALID | MISSING | INVALID_LENGTH | INVALID_CHARSET | INVALID_CHECK_DIGITS`.
`is_valid_lei` se mantiene como capa agregada (`== "VALID"`). La regla de
identidad no cambia: un LEI inválido conserva su valor raw, nunca se repara
silenciosamente, prohíbe el join automático por LEI y sólo admite resolución
exacta por otro identificador autoritativo; un checksum inválido no implica
por sí mismo `AMBIGUOUS`.
