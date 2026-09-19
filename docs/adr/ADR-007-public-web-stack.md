# ADR-007 — Stack de la web pública: Astro SSG + Pagefind

Fecha: 2026-09-18 · Estado: aceptado · Contexto: G0 CONDITIONAL/GO.

## Decisión

`apps/web` se construye con **Astro** (SSG, HTML-first) y **Pagefind**
(índice de búsqueda estático en build). No se introduce Next.js,
runtime de servidor React, base de datos ni API dinámica para v0.1.

```text
core FinReg → projections/public/*.json → Astro build → HTML estático
→ índice Pagefind → CDN/Vercel
```

## Motivo / evidencia

- El encargo fija "SSG por defecto" y explícitamente "no introducir
  Next.js, React server runtime" (§20 del encargo).
- Finding de la reuse audit: `mapa-de-beneficios` **ya no es Astro** —
  migró a Next.js 15 + `output:"export"` (commit `90774e18`; su README
  está desactualizado). Por tanto no hay un codebase Astro del autor
  que clonar; lo reutilizable son sus *patrones* (verificación,
  a11y, SEO, link-check, i18n, sistema de diseño "Registro Público"
  en `DESIGN.md`).
- Reusar su stack Next exportaría también su runtime React y obligaría
  a portar una app grande con dependencias pesadas (jsPDF, marked,
  react 19) para un producto que es esencialmente HTML+CSS.
- Astro sirve HTML sin JS por defecto — encaja con "documental, denso,
  poco JS" y con los budgets de performance del encargo.
- Pagefind 1.5.2 (MIT, activo) indexa en build y permite boost por
  `data-pagefind-*` — suficiente para nombre/alias/identificadores
  sin backend. Benchmark en G0 declarado pendiente pero el riesgo es
  bajo: el corpus cabe en índice estático.
- Fallbacks preregistrados si Pagefind falla medido: índice JSON propio
  → SQLite FTS (superficie técnica) → Yente (rechazado para v0.1).

## Qué se porta de `mapa-de-beneficios`

Patrones, no stack: `link-check.ts`, harness Playwright +
`@axe-core/playwright`, invariantes SEO/canonical/sitemap, tests de
build, enfoque "ficha verificable con fuente oficial", lenguaje de
diseño documental (sin copiar identidad visual).

## Consecuencias

- `apps/web` es paquete JS separado; el core Python no la conoce.
- Las páginas de entidad se generan desde `projections/public/entities/*.json`
  — contrato `PUBLIC-DATA-MODEL.md`.
- La revisión del ADR queda abierta a un benchmark Pagefind en la
  primera ficha E2E; si falla, sucesor documental, no silencio.
