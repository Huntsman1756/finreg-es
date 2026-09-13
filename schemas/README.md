# `schemas/` — contratos estructurales de artefactos

JSON Schema Draft 2020-12 para los artefactos públicos de FinReg-ES.
Validados por `tests/schemas/test_artifact_schemas.py` con
`python-jsonschema` (extra `tooling` de pyproject — **nunca** dependencia
runtime; `finreg_es` sigue stdlib-only).

## Reglas

- **Estructura, no semántica.** Los esquemas validan forma (tipos,
  enums, presencia, cierre de objeto). La lógica regulatoria —
  fail-closed, joins de identidad, evidencia negativa, temporalidad —
  vive en `finreg_es/` y los tests regulatorios. Un test guardarraíl
  prohíbe `if/then/else`/`format`/composición condicional en v1.
- **Inmutables por versión.** `schemas/v1/` no se edita para que
  artefactos viejos "sigan pasando". Ampliación compatible: evaluación
  expresa. Ruptura de contrato: `schemas/v2/`.
- **Contrato cerrado solo en lo que controla FinReg.** Envelopes de
  artefactos usan `additionalProperties: false`. Contenido de autoridad
  (`raw_value`, `record_key`, capturas `raw/`) queda libre: BdE/CNMV/
  EBA/ESMA son quienes deciden su contenido.
- **Cobertura total declarada.** Todo JSON bajo `fixtures/` valida
  contra su esquema o está en la lista `UNSCOPED`/`UNSCOPED_GLOBS` del
  test — ningún artefacto escapa sin declaración.

## Superficie v1

| Schema | Artefactos |
|--------|-----------|
| `source-contract` | `fixtures/contracts/*.json` |
| `entity-corpus` | `fixtures/g0.5/corpus/entities.json` |
| `ground-truth` | `fixtures/g0.5/corpus/ground-truth.json` |
| `source-manifest` | `fixtures/g0.5/sources/manifest.json` |
| `extraction-run` | `fixtures/g0.5/runs/*.json` |
| `claim-ledger` | `fixtures/g0.6/claim-provenance-*.json` |
| `derivation-ruleset` | `fixtures/g0.7/derivation-rules.json` |
| `derived-assertions` | `fixtures/g0.7/derived-assertions-*.json` |
| `assessment-cases` | `fixtures/g0.7/assessment-cases.json` |
| `assessment-run` | `fixtures/g0.7/runs/*.json` |
| `run-audit` | `fixtures/g0.7/audit/*.json` |

Comunes: `v1/common/{identifiers,temporal,provenance}.schema.json`
(sha256/git-ref, fechas ISO, `source_date_reliability`,
`source_assertion`).

Fuera de v1 (declarado en el test): audits históricos de G0.5,
`verification-report`, fixture temporal SUSPECT, fixtures sintéticos
`regulatory/`, y capturas raw de autoridad.
