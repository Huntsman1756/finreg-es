# ADR-005 — Integraciones entre repos por artefactos versionados

Fecha: 2026-09-18 · Estado: aceptado · Contexto: G4 consume datos de
AlertaFin, OpenDGSFP y official-sources-esp.

## Decisión

Las integraciones entre repos del autor se hacen por **artefactos
deterministas versionados**, nunca por imports en runtime desde
checkouts hermanos ni por git submodules.

```text
AlertaFin  → g0/normalized/notices.jsonl (+ provenance/retrievals.jsonl)
OpenDGSFP  → data/derived/v0.1/opendgsfp-0.1.jsonl (+ manifest.json)
official-sources-esp → evidencia BOE congelada (docs + hashes)
BdE        → Registro_ServicioPagos.xlsx (snapshot crudo propio)
```

Cada import registra en su manifiesto:

```text
upstream_repo, upstream_commit, upstream_artifact,
artifact_sha256, schema_version, imported_at
```

`imported_at` es metadata operativa, nunca fecha jurídica. Los bytes
de cada artefacto se congelan bajo `fixtures/g4/sources/` (o el
directorio de fuentes del import) con sha256.

## Motivo

- Reproducibilidad: el build del producto no depende de la posición de
  otros checkouts en disco.
- Las superficies upstream ya son deterministas (notices.jsonl tiene
  identidad por contenido; opendgsfp-0.1.jsonl regenera byte-igual) —
  el contrato de artefacto es la forma más débil de acoplamiento que
  preserva esa propiedad.
- Un submodule fija commit pero no fija *semántica de esquema*; el
  manifiesto con `schema_version` sí.

## Consecuencias

- Importers nuevos viven en `adapters/` o `scripts/imports/` y emiten
  claims/assertions del modelo FinReg; no duplican parsers upstream.
- Semántica upstream NO se importa automáticamente: un notice de
  AlertaFin no es una "sanción"; una aparición en BOE no es un evento.
  La clasificación es de FinReg.
- official-sources-esp necesita LICENSE + DATA-NOTICE upstream antes
  de redistribuir datos derivados (acción registrada en la matriz).
