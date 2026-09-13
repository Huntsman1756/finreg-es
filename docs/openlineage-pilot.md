# Piloto post-G0 — export OpenLineage 2.0.2

Estado: **implementado** (exportador stdlib + validación contra spec
oficial vendored). Decisión del ADR post-G0: `PILOT (exporter)` → stdlib
propia, **sin** `openlineage-python` — no hay transporte, collector ni
backend que justifique la dependencia.

## Principio rector

El export es una **proyección de interoperabilidad**, no el modelo de
linaje. La fuente de verdad regulatoria (337 claims, `SourceAssertion`,
efectos jurídicos, evidencia negativa) no se migra: OpenLineage sólo
dice «este artefacto salió de éstos mediante este job».

```text
FinReg artifacts ──read-only──▶ finreg_es/openlineage_export.py
                                    │
                                    ▼
                            openlineage/*.json
                                    │
                        validación: spec oficial 2.0.2 vendored
                              + facets finreg v1
```

## Modelo de eventos

| Paso FinReg | Evento OL | Por qué |
|-------------|-----------|---------|
| extraction `g0.5-a-*` (×3) | `RunEvent` START+COMPLETE | `executed_at` registrado en el artefacto |
| provenance (ledger G0.6) | **`JobEvent`** | sin instante de ejecución registrado: un RunEvent exigiría inventar `eventTime` de ejecución |
| derivation (G0.7) | **`JobEvent`** | idem |
| assessment `g0.7-001` | `RunEvent` START+COMPLETE | `executed_at` registrado |

`JobEvent` (spec 2.0.2: `job` + `inputs`/`outputs`, `not: run`) expresa
exactamente lo que se conoce: la arista estática del linaje. Su
`eventTime` = **`lineage_observed_at`** — el instante declarado del
export, fijado una vez en `openlineage/pilot-manifest.json` y reusado en
todo replay (nunca `datetime.now()`). El instante histórico de freeze
del artefacto (`git log -1 --format=%cI`) viaja aparte, como
`freeze_commit_time` en el facet `finreg_job_contract`.

Los contratos se separan por entidad, siguiendo la convención de
extensibilidad (`...RunFacet` / `...JobFacet`):

```text
RunEvent  run.facets.finreg_run_contract  → FinregRunContractRunFacet
          (finreg_run_id, executed_at, input_contract, code, supersedes)
JobEvent  job.facets.finreg_job_contract  → FinregJobContractJobFacet
          (finreg_artifact_id, input_contract, freeze_commit_time;
           SIN run_id / executed_at — conceptos de ejecución)
```

Ambos schemas comparten el payload en
`facets/v1/finreg-contract-common.schema.json`.

Resultado: 10 ficheros — 8 RunEvents + 2 JobEvents — que preservan el
100 % de las fronteras:

```text
snapshots ─▶ extraction-run ─▶ claim-ledger ─▶ derived-assertions ─▶ assessment-run
 (input)      (extraction)      (provenance)      (derivation)          (assessment)
```

## Mapping FinReg → OpenLineage

| FinReg | OpenLineage | Notas |
|--------|-------------|-------|
| pipeline G0.5/G0.6/G0.7 | job namespace `finreg-es.g0` | jobs: `finreg.extraction`, `finreg.provenance`, `finreg.derivation`, `finreg.assessment` |
| run con `executed_at` | `run.runId` = **UUIDv5**(`urn:finreg-es:run:<job>:<run_id>`) | determinista; nunca aleatorio |
| snapshot de fuente | Dataset ns `finreg://snapshots`, name = `<sha256>` + facet `finreg_snapshot` | identidad = contenido; sólo los 4 consumidos por cada run |
| artefacto FinReg | Dataset ns `finreg://artifacts`, name = `<kind>/<id>` + facet `finreg_artifact` | `sha256` = bytes del fichero; `result_sha256` = hash de contenido registrado |
| contrato de inputs | `finreg_run_contract` (run) / `finreg_job_contract` (job) `.input_contract` | verbatim del artefacto (git refs y sha256 según lo registrado) |
| código (extractor_sha / code_sha+commit) | `finreg_run_contract.code` | `sourceCodeLocation` aplazado: sin remote público no hay `url` honesta |
| tipo de job | job facet estándar `jobType` | `BATCH / FINREG / TASK` |
| supersedes_run_id | `finreg_run_contract.supersedes_run_id` | cadena 001→002→003 conservada |

### Desviación respecto al boceto aprobado

El boceto colapsaba `extraction → claim ledger` en un solo job. El
ledger G0.6 es una función determinista **del artefacto de run** (lo
produce `provenance.py`, pin `run_result_sha`), no del run de extracción
en sí. El export usa 4 jobs — `finreg.provenance` es el paso intermedio
real — sin pérdida de fidelidad: es el único modo de representar el
100 % de las fronteras de artefacto sin ocultar la arista ledger↔run.

## `_schemaURL`: extensión local de schema registry (limitación declarada)

Los custom facets llevan `_schemaURL` = URN estable
`urn:finreg-es:schema:openlineage:v1:<nombre>` ↔
`schemas/openlineage/facets/v1/<nombre>-facet.schema.json`.

**Esto NO es interoperabilidad portable completa**: un consumidor OL
externo no puede resolver el URN. La convención de extensibilidad pide
una URL canónica e inmutable al schema — eso sólo existe cuando el repo
tenga publicación. Mientras tanto, el piloto se declara formalmente
*local schema-registry extension*:

```text
Si el repo se publica:
  1. commit A: schemas + exporter (sin eventos generados)
  2. commit B: eventos con _schemaURL = raw URL pinneada al SHA de A
  → identificador canónico real, sin circularidad.
```

El URN se valida igualmente contra el facet schema vía `$id` en tests.

## Vendorizado

`schemas/openlineage/` contiene la spec 2.0.2 y el facet `jobType`
oficiales, byte-exactos y con SHA-256 testeado — ver
`schemas/openlineage/UPSTREAM.md` (URLs, hashes, licencia Apache-2.0).

## Decisiones técnicas

- **Serialización** = `FINREG_CANONICAL_JSON_V1` → replay byte-idéntico.
- **`producer`** = `urn:finreg-es:openlineage-export:FINREG_OL_EXPORT_V1`.
- **Sin claims individuales**: los 337 claims viven sólo en el ledger.
- **`file sha256` ≠ `result_sha`**: los contratos FinReg pinnean bytes
  de fichero; el hash de contenido de los run artifacts viaja aparte
  (`result_sha256`). Ambos se declaran, nunca se confunden.
- **Lineage Job Facet** (aristas explícitas) documentado como opción
  futura; el pipeline es lineal y no lo necesita.

## Gate verificado

```text
0 bytes de fixtures tocados        (git status limpio en fixtures/)
suite completa PASS
10 eventos: schema-valid vs spec oficial 2.0.2 (FormatChecker activo)
replay byte-idéntico; runIds UUIDv5 estables
JobEvents sin run ni eventTime de ejecución fabricado
0 claves de semántica regulatoria en el export (test guardarraíl)
0 dependencias runtime nuevas (exportador stdlib; jsonschema sólo tooling)
```

## Revisar para adoptar `openlineage-python`

Sólo si aparece necesidad real de emitir a un backend vivo (Marquez,
DataHub) o integrarse con ecosistema OL. Para el objetivo del piloto —
demostrar interoperabilidad con spec compliance — el exportador
validado cubre el valor con mínima superficie. Cuando el repo se
publique, el salto a `_schemaURL` portable es el paso pendiente ya
descrito arriba.
