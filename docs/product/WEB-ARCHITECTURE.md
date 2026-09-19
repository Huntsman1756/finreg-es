# WEB-ARCHITECTURE — Regulatory Record ES v0.1

Stack decidido en `docs/adr/ADR-007-public-web-stack.md`.

## Pipeline

```text
fixtures/fuentes congeladas + artefactos upstream
        ↓ importers (adapters/, semántica FinReg)
claims/assertions core
        ↓
projections/public/*.json        (schema versionado, build determinista)
        ↓
apps/web  (Astro SSG)
        ↓
out/  HTML estático + índice Pagefind
        ↓
deploy estático (Vercel u otro CDN)
```

Sin servidor, sin DB de runtime, sin hidratación obligatoria. La
búsqueda es Pagefind sobre el HTML generado.

## Rutas

```text
/                     buscador + qué es esto
/buscar/              resultados (Pagefind)
/entidad/<stable-id>/ ficha regulatoria
/cambios/             feed de cambios clasificados
/reguladores/         superficies y cobertura por regulador
/metodologia/         cómo se construye, enum de hechos, límites
/fuentes/             fuentes, freshness, estados
/datos/               descargas JSON + schema
/aviso-legal/  /privacidad/
```

`noindex` en páginas ambiguas/thin. Canonical + sitemap + OG +
breadcrumbs en todas las indexables.

## Ficha de entidad (jerarquía)

Breadcrumb → nombre → estado+identificadores+última verificación →
resumen → autorizaciones y servicios (tabla semántica) →
presencia/distribución → organización → regulatory record (sanciones /
warnings directos / impersonations — relaciones, no contadores) →
timeline (enum de hechos visible) → fuentes y cobertura.

Cada fact material expone `Ver evidencia` → provenance (fuente, fecha,
sha256 para usuarios técnicos).

## Time machine

`?as_of=YYYY-MM-DD` en ficha: estados `CURRENT | OFFICIAL AS-OF |
RECONSTRUCTED | NO HISTORICAL EVIDENCE`. `known_at` ≠ `valid_at` se
muestra explícitamente.

## Verificación (portada de mapa-de-beneficios)

build + typecheck + unit + schema validation + link-check +
SEO/canonical/sitemap invariants + Playwright + axe (WCAG 2.2 AA) +
responsive breakpoints + JS-disabled smoke + visual regression
(snapshots sólo con actualización explícita) + budgets JS/CSS.

## Diseño

Lenguaje "registro público": sobrio, editorial, tablas y líneas antes
que cards, densidad controlada, fuente+fecha como parte del diseño.
Sin dashboards de KPIs, sin gradientes, sin glassmorphism.
