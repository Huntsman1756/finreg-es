# G4-G2 — Informe: aplicación web estática + primera ficha E2E

Ejecutado sobre `apps/web` (Astro 7 + Pagefind, stack ADR-007).
Veredicto: **CONDITIONAL/GO**.

## Resultados por caso preregistrado

| Caso | Resultado | Evidencia |
|---|---|---|
| W01 | PASS | `dist/` contiene las 10 rutas contratadas + `/entidad/` índice + 20 fichas (`verify-build.mjs`) |
| W02 | PASS | ESI-4: 4 impersonations con redacción "no guarda relación con…"; framing de suplantación **de** la entidad, nunca advertencia contra ella |
| W03 | PASS | ESI-1: `NO HISTORICAL EVIDENCE` visible + servicios con instrumentos/clientes; anti-caso reg-245 no atribuido (check dedicado `alantrafx` ausente de la ficha) |
| W04 | PASS | SAN-1: sanción con fecha de registro + BOE; `fs pedido` visible por estado |
| W05 | PASS | INS-5: Cancelada con intervalo `[UNKNOWN → 2026-09-13]`; sin fecha inventada |
| W06 | PASS | Pagefind indexa 30 páginas / 1616 palabras; UI en `/buscar/` + índice noscript |
| W07 | PASS | `/data/` sirve manifest, entities, changes, sources + fichas JSON |
| W08 | PASS | 0 `<script>` en las 20 fichas (contenido completo sin JS) |
| W09 | PASS | 0 features de rating/score; las únicas menciones son el disclaimer del footer |
| W10 | PASS | sitemap-index.xml generado; breadcrumbs en todas las páginas |
| W11 | PASS* | Checks básicos automatizados (lang, h1 único, labels, alt, nav etiquetado). axe completo diferido — ver gaps |

## Gaps declarados

- **axe/WCAG 2.2 AA completo**: no ejecutado en este gate (toolchain sin
  Playwright aún). W11 pasa con chequeos estructurales ligeros; el gate
  sucesor añade axe real.
- **`astro preview` quirk**: el servidor de preview de Astro resuelve mal
  las URLs `dir/index.html` con `trailingSlash:"always"` (301→404). El
  `dist/` sirve correctamente con cualquier servidor estático
  (`python -m http.server`, `serve`, CDN). No afecta al producto.
- **Pagefind UI**: usa Default UI (deprecated→Component UI sugerido en
  Pagefind 1.5). Funcional; migración cosmética futura.
- **Búsqueda por identificador**: Pagefind indexa texto de fichas;
  NIF/LEI/nº de registro figuran en el HTML y son buscables.
- **Datos CNMV vistas 10–13/5–6/16/38** no congelados en G0: las fichas
  declaran `NO_EVIDENCE` donde aplica (sucursales EEE, libre prestación,
  fondos gestionados, atención al cliente, auditorías) — candidato a
  próxima refresh de evidencia.

## Veredicto

**CONDITIONAL/GO** — sitio funcional, verificable y honesto con un gap
declarado de verificación (axe completo) y de cobertura de fuente
(vistas CNMV no congeladas), ambos acotados y registrados.

## Artefactos

```text
apps/web/                    Astro 7.3.x, static, trailingSlash always
apps/web/src/pages/          10 rutas + /entidad/[id] (getStaticPaths ×20)
apps/web/src/layouts/Base.astro
apps/web/src/lib/data.ts     lectura fs de projections/public en build
apps/web/scripts/sync-data.mjs    projections → public/data
apps/web/scripts/verify-build.mjs W01–W11 (36 checks)
```
