# ADR-004 — El core canónico de Regulatory Record ES es `finreg_es`

Fecha: 2026-09-18 · Estado: aceptado · Contexto: productización G4.

## Decisión

No se crea un backend nuevo. `finreg_es` (stdlib-only, determinista,
fail-closed, bitemporal) sigue siendo el modelo canónico. El producto
añade: importers de artefactos upstream, un read model público
(`projections/public/`) y una web SSG (`apps/web/`). Ninguno contiene
semántica regulatoria propia.

## Motivo

FinReg ya implementa lo que costaría años reconstruir bien: claim
ledger con provenance por aserción, `valid_at × known_at`, source
contracts, diff estructural con gates de comparabilidad, candidatos a
evento regulatorio, serialización canónica `FINREG_CANONICAL_JSON_V1`,
OpenLineage, CLI/MCP/Datasette — todo contract-tested (569 tests).

## Consecuencias

- Las superficies G3 (CLI `finreg`, MCP, Datasette) se conservan
  intactas; cualquier migración será explícita y contract-tested.
- `finreg_es/` permanece stdlib-only; las deps de producto viven en
  extras y en `apps/web` (JS), nunca en el core.
- Lo que el producto necesita y el core no tiene (enum de basis de
  evidencia, relaciones warning/clone, read model público) se añade
  como módulos nuevos, no como reescritura.
