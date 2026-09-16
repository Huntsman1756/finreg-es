# G3-C — Addendum 01 al contrato de proyección (corrección documental)

**Estado:** corrección sucesora de
`docs/g3-c-projection-contract.md` (publicado FROZEN en `7ddf39a`).
No reabre ni modifica el contrato: corrige una nota factual.
Ningún criterio binding cambia.

## Corrección

La nota de §3 del contrato afirmaba que "`field_path` no existe a
nivel de cambio estructural" y que el artefacto de comparación
"sólo lista `record_key`s por `kind`". Verificado contra los
artefactos congelados (`fixtures/g2/comparisons/`):

- `changes.added` / `changes.removed` → listas de `record_key`
  (string desnudo)
- `changes.changed` → lista de objetos
  `{kind, path, old, new, record_key}`

Consecuencia: el field path **sí** existe a nivel de cambio
estructural para los elementos `changed` (además de en
`change_candidates`, como afirmaba la nota).

## Impacto

Ninguno sobre lo binding:

- `structural_changes.payload_json` preserva ambos shapes íntegros
  (verificado por `test_payloads_equal_source_objects`).
- El schema de tabla nunca dependió de la nota.
- `logical_projection_sha256`, C1–C5 y el veredicto `PILOT_PASS`
  quedan inalterados.

## Lección

El error vino de muestrear `changes.added` (strings) sin muestrear
`changes.changed` (objetos) durante la verificación del
preregistro. La propiedad lossless por `payload_json` es lo que
hizo la inexactitud inocua para el pilot.
