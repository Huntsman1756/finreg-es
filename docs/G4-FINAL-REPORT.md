# G4 — informe final

Cierre de la fase G4: **Regulatory Record ES v0.1** — vertical público
completo desde evidencia congelada hasta deployment estático real.

## Veredicto

```text
G4 — PASS / v0.1 READY

G4-G0  CLOSED   preregistro + corpus 20 entidades + freeze de fuentes
                (84 requests, manifest con sha256/retrieved_at por item)
G4-G1  CLOSED   proyección pública determinista (projections/public,
                canonical JSON, bundle_sha256, 24 artefactos)
G4-G2  CLOSED   apps/web estática — Astro 7 + Pagefind (CONDITIONAL/GO;
                gaps: axe real y vistas CNMV pendientes — cerrados en G4-G3)
G4-G3  CLOSED   refresh de evidencia + hardening + deployment real —
                R-01..R-13 PASS (informe: docs/gates/G4-G3-REPORT.md)
```

## Estado del vertical

```text
20   entidades del corpus congelado (ESI×4, SGIIC×5, SAN×1, EDE×5, INS×5)
160  requests de fuente congelados (84 G0 + 76 refresh G4-G3), todos con
     sha256 + retrieved_at; manifests sucesores, historia intacta
24   artefactos públicos (20 fichas + entities/search/changes/sources)
bundle_sha256  2b9f3ae1d209e0ad1a5551737d728bd6b601b636fa3d92867cc8087d997dfae8
     — reproducible byte a byte desde los fixtures (verificado ×2)
586  tests PASS · 36 checks W01–W11 · 0 violaciones axe · 0 errores consola
30   páginas servidas en producción, 30 URLs sitemap, 0 enlaces rotos
```

## Despliegue

```text
URL pública:  https://huntsman1756.github.io/finreg-es/
Hosting:      GitHub Pages (rama gh-pages, build legacy, .nojekyll)
Base path:    /finreg-es/ — todos los enlaces internos via u()
Canonical:    https://huntsman1756.github.io/finreg-es/<ruta>
Smoke real:   10 rutas 200, búsqueda Pagefind funcional bajo el prefijo,
              manifest desplegado == manifest local (mismo bundle_sha256)
```

## Capacidades del producto (verificadas)

- Identidad exacta por entidad + identificadores por regulador
  (NIF, registro CNMV, código BdE, entity code EBA, clave DGSFP, LEI).
- Autorizaciones y servicios por fuente (programa de actividades CNMV
  con instrumentos/clientes; actividades BdE con normativa y fecha).
- Operación territorial: sucursales ES/EEE/fuera-EEE y libre prestación
  (`passporting` con mode/scope/country — refresh G4-G3).
- Organización: socios, administradores, auditorías por ejercicio,
  atención al cliente, IIC gestionadas (refresh G4-G3).
- Hechos regulatorios: sanción oficial con BOE (SAN-1), suplantaciones
  AlertaFin con framing correcto (la entidad es la parte legítima),
  candidatos name-similarity nunca promovidos a atribución.
- Historia: estados `fs=` SGIIC, OBSERVED_CHANGE, intervalos
  `[UNKNOWN → as_of]` para cancelaciones sin fecha exacta (INS-5).
- Búsqueda estática Pagefind + índice noscript; fichas íntegras sin JS.
- Provenance por aserción: cada fuente con URL, sha256, retrieved_at;
  freshness y coverage declarados por superficie.

## No-capacidades (por contrato, no por carencia)

- Sin ratings, scores, rankings ni recomendaciones — verificado W09.
- Sin afirmación de completitud: ausencia de hecho adverso = ausencia
  en la evidencia congelada, declarado explícitamente en cada ficha.
- Sin entidades nuevas, sin G5, sin features fuera del contrato.

## Límites declarados (de G4-G3)

- Corpus fijado en 20 entidades.
- Vista CNMV servida vacía = indistinguible de "sin hechos" (la fuente
  no diferencia); coverage marca NO_EVIDENCE cuando la lista queda vacía.
- `passporting` une BRANCH y FREEDOM_TO_PROVIDE_SERVICES en una lista
  discriminada por `mode`/`scope`.
- Dominio `regulatoryrecord.es` no activo; canonical apunta al deploy
  real (revertir `site` si se configura el dominio).
- Baseline visual congelada post-refresh (sin captura pre-refresh).
- Incidente G4-G3 (deploy de árbol fuente por `.git` anidado borrado
  por astro build) recuperado forward-only — documentado en
  `docs/gates/G4-G3-REPORT.md`.

## Cadena de artefactos autoritativa

```text
docs/gates/G4-G0-PREREG/REPORT.md   corpus + freeze G0
docs/gates/G4-G1-PREREG/REPORT.md   proyección pública
docs/gates/G4-G2-PREREG/REPORT.md   web estática
docs/gates/G4-G3-PREREG/REPORT.md   hardening + refresh + deploy
fixtures/g4/                        corpus, fuentes raw, manifests, probes, browser
projections/public/                 read model público (bundle verificable)
schemas/public/entity-v1.schema.json
docs/product/{PRODUCT-CONTRACT,PUBLIC-DATA-MODEL,WEB-ARCHITECTURE}.md
```

## Siguiente fase (recomendada, no ejecutada)

- G5 queda fuera de scope por contrato. Candidatos naturales: dominio
  propio, refresh programado de evidencia con manifests sucesores,
  más verticales del registro español, contratos schema v1.x para
  `fixtures/g4/` (hoy UNSCOPED declarado).
- Tag `v0.1.0` y merge a `main`: **autorizados por este veredicto**,
  pendientes de ejecución explícita del usuario.
