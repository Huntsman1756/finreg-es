# `schemas/openlineage/` — piloto OpenLineage (export, tooling-only)

Esquemas del piloto post-G0 de exportación de linaje a OpenLineage.
**Nada aquí es contrato de artefactos FinReg** (eso sigue siendo
`schemas/v1/`): la autoridad del modelo regulatorio no se migra.

## Contenido

| Path | Qué es |
|------|--------|
| `OpenLineage-2.0.2.schema.json` | Spec oficial OpenLineage 2.0.2 **vendored**. Origen: `https://openlineage.io/spec/2-0-2/OpenLineage.json`, sha256 `69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2` (9155 bytes). Pin fijo: validación 100% offline. |
| `JobTypeJobFacet-2.0.2.schema.json` | Facet estándar `jobType` **vendored**. Origen: `https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json`, sha256 `0716fc27d8f4ac450e64bfd25de002523f313d03e510bbc90d212d3af6259d1c` (1173 bytes). |
| `facets/v1/finreg-snapshot-facet.schema.json` | Dataset facet: snapshot de fuente primaria (sha256, url, retrieved_at, source_as_of, autoridad/registro cuando se conoce). |
| `facets/v1/finreg-artifact-facet.schema.json` | Dataset facet: artefacto FinReg (path, sha256 de bytes, result_sha256, git_ref, versión). |
| `facets/v1/finreg-contract-common.schema.json` | `$defs` compartidas de los facets de contrato (input_contract, code, sha256). No es un facet. |
| `facets/v1/finreg-run-contract-run-facet.schema.json` | **Run facet**: contrato del run (`finreg_run_id`, `executed_at`, `input_contract`, `code`, `supersedes_run_id`). Sólo RunEvents. |
| `facets/v1/finreg-job-contract-job-facet.schema.json` | **Job facet**: pins estáticos del artefacto producido (`finreg_artifact_id`, `input_contract`, `freeze_commit_time`). Sin conceptos de ejecución. Sólo JobEvents. |

## Convenciones

- `_schemaURL` de los custom facets usa URNs estables
  `urn:finreg-es:schema:openlineage:v1:<nombre>` que mapean 1:1 a
  `schemas/openlineage/facets/v1/<nombre>-facet.schema.json`.
  **Esto es una extensión local de schema registry, no portabilidad
  completa**: un consumidor externo no puede resolver el URN. Al
  publicar el repo, sustituir por raw URL pinneada a commit (ver
  `docs/openlineage-pilot.md`). Los nombres de facet llevan prefijo
  `finreg_` para evitar colisiones con facets estándar.
- `schemaURL` de cada evento es la URL canónica de la spec:
  `https://openlineage.io/spec/2-0-2/OpenLineage.json`.
- Procedencia upstream (URLs, SHA-256, licencia): `UPSTREAM.md`.
- Validación: `tests/openlineage/` con `python-jsonschema` (extra
  `tooling`). El exportador (`finreg_es/openlineage_export.py`) es
  stdlib-only y read-only: no transporte, no collector, no red.
