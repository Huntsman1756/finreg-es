# ADR post-G0 — Build vs Reuse / OSS leverage

Auditoría del repo completo tras el cierre de G0 (`8a4f9e3`). Cuatro
pases: inventario → clasificación dominio/genérico → comparación de
candidatos → decisión. **No se modifica runtime durante este análisis.**

## Restricción dura

> Ninguna adopción OSS puede cambiar los resultados congelados de G0.

Gate de cualquier adopción:

```text
artefactos históricos G0 byte-idénticos
21/21 assessments g0.7-001 sin cambio
tests solo aumentan
0 debilitamiento de semántica fail-closed
0 dependencia runtime nueva sin beneficio demostrado
```

## Inventario (P1)

`finreg_es/` = 3.683 LOC, **0 dependencias runtime**, todo stdlib
(`csv`, `zipfile`, `html`, `re`, `hashlib`, `json`; `subprocess git`
solo para metadato de commit y verificación de freeze en tests). Sin
fetch HTTP: la extracción corre sobre snapshots congelados. Sin CI
configurado, sin linter/formatter, sin backend de packaging en
`pyproject.toml`.

## Matriz de decisión (P2–P4)

| Componente | Implementación actual | ¿Dominio? | Candidato OSS/estándar | Decisión | Coste migración | Riesgo semántico G0 | Valor de perfil |
|---|---|---|---|---|---|---|---|
| `vocab.py` | enums reguladores | Sí | — | KEEP | — | — | Alto (es el modelo) |
| `semantics.py` `assess()` | motor fail-closed | Sí | motores de reglas genéricos | KEEP + REJECT reglas genéricas | — | — | Alto |
| `coverage.py` | matriz cobertura IN/OUT/UNKNOWN | Sí | — | KEEP | — | — | Alto |
| `identity.py` | resolución + LEI mod-97 (~30 LOC) | Sí (política) | libs LEI (iso17442) | KEEP | — | — | Medio |
| `temporal.py` | freshness/staleness/SUSPECT | Sí | dateutil/arrow | KEEP | — | — | Medio |
| `derivation.py` + ruleset JSON | intérprete determinista | Sí | durable-rules/business-rules | KEEP + REJECT | — | — | Alto |
| `provenance.py` | ledger claim-level + replay + mutación | Sí | OpenLineage (modelo interno) | KEEP modelo; EXPORT formato | — | — | Alto |
| `contracts.py` validación | `validate_contract_dict` manual | No (validación); sí (campos) | JSON Schema | ADOPT (tooling) | Bajo | Nulo (valida, no ejecuta) | Medio |
| Schemas de artefactos (runs, ledger, derivadas, casos, audit) | inexistentes (de facto) | No | JSON Schema 2020-12 + `python-jsonschema` | ADOPT (tooling) | Bajo-Medio | Nulo | Alto (contratos públicos) |
| Fuentes tabulares (ESMA CSV, BdE CSV, EBA zip) | parsers stdlib + `SourceContract` | Sí (semántica); no (estructura) | Frictionless descriptors | PILOT (export opcional) | Bajo | Nulo si es export | Medio-Alto |
| Lineage interoperable | provenance propio JSON | Sí (modelo); no (intercambio) | OpenLineage RunEvent | PILOT (exporter) | Bajo-Medio | Nulo si es export | Alto |
| `canonical.py` | canonical JSON propio (94 LOC) | No | RFC 8785 / `canonicaljson` | KEEP (+ conformance check opcional) | — | Cambiarlo rompe todos los sha | Bajo |
| `loaders.py` | JSON loads | No | — | KEEP | — | — | Bajo |
| `extraction.py` parsers | `csv`/`zipfile`/`html`/`re` | Mixto (parseo genérico, mapeo dominio) | Frictionless extract, pandas | KEEP (zero-dep es ventaja) | — | — | Medio |
| `subprocess git` (commit/freeze) | 2 usos | No | GitPython | KEEP | — | — | Bajo |
| `assessment_run.py` | orquestador + fingerprint código | Sí | — | KEEP | — | — | Medio |
| Data quality empresarial | n/a | No | Great Expectations | REJECT (escala) | — | — | — |
| Catálogo/plataforma metadata | n/a | No | DataHub | REJECT (desproporcionado) | — | — | — |
| CI / lint / packaging | inexistente | No | GH Actions, ruff, hatchling | ADOPT (tooling, mínimo) | Bajo | Nulo | Medio |

## Decisiones

### ADOPT — JSON Schema (tooling-only) — IMPLEMENTADO

Formalizar como esquemas públicos (`schemas/*.schema.json`) los
artefactos que hoy son contratos de facto: `SourceContract`,
`derivation-rules.json`, `assessment-cases.json`, claim ledger,
`derived-assertions`, run artifacts, audit ledgers. `python-jsonschema`
en **dependencia opcional/dev** — nunca en el path runtime de
`assess()`. Valor: convierte el formato interno en interfaz declarada y
detecta deriva de artefactos sin código imperativo.

**Estado: implementado** — `schemas/v1/` (3 common + 11 artefactos),
`tests/schemas/test_artifact_schemas.py` (47 tests: validación de
artefactos congelados + integridad de bytes + negativos por tipo +
guardarraíl anti-semántica + runtime sin dependencia). Ver
`schemas/README.md`.

### PILOT — OpenLineage exporter

`OpenLineage` como **formato de salida**, no modelo interno. Mapping:

```text
job   = finreg-es.pipeline
runs  = extraction g0.5-a-003 → derivation → assessment g0.7-001
datasets = snapshots (sha256 facet) → claim ledger → derived assertions → run
facets = finreg-specific: source_as_of, contract_version, ruleset_version
```

Los 337 claims y `SourceAssertion` siguen siendo la fuente de verdad.
Decisión pendiente dentro del piloto: emitir JSON spec-compliant con
stdlib vs depender de `openlineage-python`. Criterio: si el cliente OL
solo se usa para serializar, stdlib + validación por JSON Schema del
spec puede ser más ligero — medir antes de decidir la dependencia.

### PILOT — Frictionless (compatibilidad opcional)

Exportador `SourceContract → descriptor Frictionless` (TableSchema /
Data Resource) para las fuentes tabulares (ESMA `CASPS.csv`, BdE MFI
CSV, EBA PSD2 zip). `SourceContract` sigue siendo la autoridad
semántica: cobertura, evidencia negativa, política de staleness y base
jurídica no son expresables en TableSchema. Frictionless solo describe
lo estructural. Validación en tooling, no runtime.

### KEEP — todo el núcleo regulador

`vocab`, `semantics`, `coverage`, `identity`, `temporal`, `derivation`,
`provenance`, parsers de extracción, `canonical`, `loaders`,
`assessment_run`. Justificación: la capa difícil del proyecto es la
semántica jurídica fail-closed; es exactamente lo que ningún OSS
genérico resuelve. La ausencia de dependencias runtime es además un
activo: auditabilidad total, replay air-gapped, cero superficie de
supply chain.

### REJECT

- **Great Expectations**: framework de data quality genérico; la
  semántica reguladora no se reduce a expectativas tabulares. Reevaluar
  solo si crece mucho la superficie de datos.
- **DataHub**: catálogo/plataforma completa; desproporcionado.
- **Motores de reglas genéricos**: introducirían semántica opaca en el
  salto claims→entitlements, que es precisamente el punto auditado.
- **Reemplazar provenance interno por OpenLineage**: perdería
  granularidad claim-level regulatoria.
- **Lib LEI / dateutil**: dependencias por ~30 LOC triviales.

### ADOPT (tooling, fuera de alcance funcional)

Mínimo: `ruff` (lint), un backend de build (`hatchling`) y CI básico.
Sin efecto sobre artefactos congelados.

## Nota de perfil

La narrativa resultante: la capa difícil (semántica reguladora,
identidad, evidencia negativa, derivación jurídica, assessment) es
propia y auditada; la infraestructura genérica habla estándares
(JSON Schema, OpenLineage, Frictionless) por exportación, no por
invasión. Una contribución upstream a Frictionless/OpenLineage, si
aparece una necesidad real, vale más que su equivalente interno.
