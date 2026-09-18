# G4 — Reuse Matrix (Regulatory Record ES)

Auditoría de reutilización previa a cualquier infraestructura nueva, según
`docs/adr-oss-scan-failure-driven.md`. Fallo concreto que G4 resuelve:

> FinReg-ES es hoy un motor de assessment consultable por CLI/MCP/Datasette.
> El producto "Regulatory Record ES" exige (a) incorporar hechos regulatorios
> que otros repos del autor ya capturan, (b) un read model público estable y
> (c) una web SSG con búsqueda — sin duplicar capacidades ya probadas.

Evaluado el 2026-09-18 sobre los checkouts locales indicados. Las decisiones
de integración entre repos son **contratos de artefacto versionado**, nunca
imports en runtime desde checkouts hermanos.

## Repos propios

| Repo / checkout | Licencia | Commit evaluado | Capacidad aprovechable | Integración prevista | Riesgos | Decisión |
|---|---|---|---|---|---|---|
| `Huntsman1756/finreg-es` (este repo) | MIT | `34c6a24` (main, baseline G4) | claim ledger, assertion provenance, `valid_at×known_at`, source contracts, structural diff, candidate regulatory events, canonical JSON+sha256, OpenLineage, CLI/MCP/Datasette, fail-closed, semantics versioning | Es el **core canónico**. Todo lo demás orbita | Ninguno nuevo; no romper superficies G3 | **ADOPT (core)** |
| `Huntsman1756/AlertaFin` @ `F:\_Proyectos\AlertaFin` | MIT | `63f7977` | warnings CNMV (`PaffNoAutorizadas`), `notice_id` estable = sha256(canonical identity fields), provenance por retrieval (`retrievals.jsonl`), dominios extraídos determinista (`domainex.py`), **semántica clone**: sólo si la fuente lo afirma (`clones.py`; `similar a` ≠ clon; dominios de entidad legítima suplantada separados), estados `WARNED/NO_WARNING_FOUND/AMBIGUOUS/SOURCE_UNAVAILABLE` | Artefacto `g0/normalized/notices.jsonl` + `g0/provenance/retrievals.jsonl` → importer FinReg con manifiesto `upstream_repo/commit/artifact_sha256/schema_version` | G1-WI multifuente FAILed (ADR-002): solo el dataset CNMV es release-quality; `notice_id` no incluye `Observaciones`/`Fecha Baja` (cambios ahí = nueva versión, no nuevo aviso) | **WRAP (artefacto v1)** |
| `Huntsman1756/OpenDGSFP` @ `F:\_Proyectos\OpenDGSFP` | MIT | `f0d0035` | identidad exacta DGSFP/BdE-Eurosystem/EIOPA/GLEIF, branch→undertaking, passporting first-class, `EXACT/CONFLICT/UNRESOLVED`, merge_basis por join, assertion provenance, export JSONL byte-determinista | Artefacto `data/derived/v0.1/opendgsfp-0.1.jsonl` + `manifest.json` → importer FinReg | Repo sin tag v0.1 (pin por commit); 74.7% de `L` sin LEI publicado (gap declarado, no defecto); donor submodule | **WRAP (artefacto v0.1)** |
| `Huntsman1756/official-sources-esp` @ `G:\_Proyectos\mcpspain\official-sources` | **SIN LICENCIA declarada** | `0ba76f4` | ingesta BOE (API oficial), snapshots raw + hashing, documentos, citas estables, integrity checks, source registry ejecutable (`config/sources.yaml`), estado de fuente, interfaces read-only (SQLite/FastMCP) | Evidencia BOE congelada → capa de eventos/adjudicación de FinReg. NO se re-importa semántica: una aparición en BOE no es automáticamente sanción/evento | **Sin LICENSE**: reuso interno entre repos del autor es viable; redistribución pública de código o datos derivados exige añadir licencia + DATA-NOTICE antes de publicar | **WRAP (artefacto/evidencia) + acción pendiente: licenciar upstream** |
| `Huntsman1756/ownership-radar` @ `F:\_Proyectos\owership_radar` | MIT | `c661b95` (v0.1.0a2) | ledger bitemporal (source-declared vs derived), facade `OwnershipRadar`, feed incremental con cursor, backfill vs current observation, provenance traversal, coverage por denominadores, `require_authoritative`, relaciones `ANNULS/RECTIFIES`, demo dataset, release engineering | Patrones para: feed `changes.json` (items `OFFICIAL_EVENT/RECONSTRUCTED_HISTORICAL/OBSERVED_CURRENT/BACKFILL`), facade público, coverage surface, fixtures demo | Su dominio (titularidad CNMV) no aporta facts de autorización; copiar internals duplicaría lo que FinReg ya tiene | **PORT_PATTERN** |
| `Huntsman1756/mapa-de-beneficios` @ `G:\_Proyectos\la-ayuda` | MIT | `4444c678` | **OJO: ya no es Astro** — migrado a Next.js 15 App Router + `output:"export"` (SSG estático en `out/`). Reutilizable: `build-locked.ts`, `verify-publication-build.ts`, `link-check.ts`, Playwright + `@axe-core/playwright` (`playwright.audit.config.ts`), postdeploy e2e, SEO (canonical/hreflang/sitemap/OG), i18n multi-idioma, sistema de diseño "Registro Público" (`DESIGN.md`), presupuestos de build | Infra de web pública: harness de verificación, a11y, link-check, SEO, diseño documental. Ver decisión de stack en ADR | El README aún dice "Astro 7.x" (desactualizado); el stack real es Next+React — adoptar Astro "porque la otra web lo usa" sería falso; la elección se decide por benchmark y por lo que ya está probado | **PORT_PATTERN (fuerte) — candidato a ADOPT infra completa** |
| `Huntsman1756/regdelta-es` @ `F:\_Proyectos\regdelta-es` | Apache-2.0 | `53e4206` | raw content-addressed store, identificadores BOE, observations, checks, parser versioning, abstención explícita, event evidence | Referencia de patrones ya probados; para BOE operativo se prefiere `official-sources-esp` | Conserva gates FAILed (G0-G.2/G1.2 FAIL permanentes) y resultados experimentales; sus conclusiones semánticas no se importan | **REFERENCE** |
| `Huntsman1756/bankcall-es` @ `F:\_Proyectos\BankCall España` | Apache-2.0 | `c8c736e` (v0.1.1) | estados financieros XBRL BdE por reporting-slot con identidad legal-entity temporal y provenance | Futura enrichment layer etiquetada por separado (financial ≠ regulatory authorization) | Fuera del core G4; mezclar autorización y salud financiera violaría el contrato de producto | **REFERENCE (integración futura separada)** |
| `Huntsman1756/gloomberb-cnmv` @ `G:\_Proyectos\gloomberb-cnmv-g0` | MIT | `9ad613f` | security-master determinista (FIRDS+MIC+OpenFIGI+GLEIF), validación exacta NIF/LEI contra GLEIF, `UNRESOLVED` si no único, provenance completa | Técnicas de exact-identifier validation y patrón security-master para el resolver de identidad regulatoria | Su dominio es instrumentos/ISIN; las tablas concretas no aplican a entidades regulatorias | **PORT_PATTERN (parcial) / REFERENCE** |

## OSS externo (scan 2026-09-18, GitHub API verificado)

| Candidato | Licencia | Versión/estado | Capacidad | Encaje | Decisión |
|---|---|---|---|---|---|
| `opensanctions/followthemoney` | MIT | activo (push 2026-09-03) | ontología entidad/persona/relación, aliases, identifiers, interchange format | El modelo canónico regulatorio es FinReg; FtM no entiende `valid_at×known_at` ni source contracts. Sí vale como **proyección de export opcional** (`entity → FtM Company/LegalEntity`) para interop | **REFERENCE (+ export opcional P2)** |
| `opensanctions/nomenklatura` | MIT | activo (push 2026-09-14) | candidate generation, resolver graph, juicios explícitos same/different/undecided | Su modelo de adjudicación explícita encaja con `CANDIDATE` + decisión humana. NO puede producir canonical identity automática. Adoptar la librería entera por un resolver graph que FinReg ya modela con estados propios no compensa | **REFERENCE (patrón de adjudicación)** |
| `opensanctions/rigour` | MIT | activo (push 2026-09-17) | normalización nombres/direcciones/jurisdicciones/ids | Útil para candidate generation. Riesgo: normalizaciones incompatibles con determinismo canónico. Medir en corpus real antes de tocar identity paths | **EVALUATE→decidir en G0; por defecto REFERENCE para normalización de candidatos, nunca en cadena de identidad exacta** |
| `opensanctions/yente` | MIT | activo | HTTP matching + Reconciliation API sobre FtM; requiere Elasticsearch/OpenSearch | Introduce cluster ES, servicio permanente y deps pesadas para una necesidad que Pagefind+JSON probablemente resuelven. Penalización arquitectónica explícita | **REJECT para v0.1 (re-benchmark sólo si Pagefind/JSON-FTS falla medido)** |
| `simonw/datasette` | Apache-2.0 | 0.65.4 adoptada en G3 | visor HTTP/JSON de proyección SQLite | Ya ADOPTED-PILOT. Se mantiene como superficie técnica/auditoría; NO es la UX pública | **ADOPT (existente, rol acotado)** |
| `Pagefind/pagefind` | MIT | 1.5.2 (v1.5.0 2026-04-06) | índice de búsqueda estático generado en build, UI de componentes, filtros, bajo ancho de banda | Encaja exacto con SSG: búsqueda por nombre/alias/identificadores sin backend. Filtros y `data-pagefind-*` permiten boost de ids exactos | **ADOPT (pendiente de benchmark G0; ver § búsqueda)** |
| `OpenLineage/OpenLineage` | Apache-2.0 | spec 2.0.2 (adoptado G2) | lineage de artefactos | Ya adoptado; export `finreg_es/openlineage_export.py` regenera byte-idéntico | **ADOPT (existente)** |

## Decisiones de arquitectura derivadas

1. **Imports entre repos = artefactos versionados.** Formato del registro por
   import: `upstream_repo, upstream_commit, upstream_artifact,
   artifact_sha256, schema_version, imported_at`. `imported_at` nunca es
   fecha jurídica.
2. **Stack web**: `mapa-de-beneficios` demuestra que Next.js `output:"export"`
   ya entrega SSG + a11y + SEO + link-check en producción del autor. Astro
   sigue siendo candidato si aporta algo medible que eso no da; la decisión se
   cierra con ADR tras medir ambos sobre una ficha real (G0 depende).
3. **Búsqueda pública**: Pagefind primero; JSON index propio como fallback;
   SQLite FTS/Datasette para la superficie técnica; Yente descartado.
4. **Identidad**: exact-first de FinReg se conserva; rigour/nomenklatura sólo
   en capa de *candidatos*, jamás en `SAME_ENTITY`.

## Acciones pendientes

- [ ] Añadir LICENSE + DATA-NOTICE a `official-sources-esp` antes de publicar
      datos derivados de él.
- [ ] Fijar contrato `warnings-v1` con AlertaFin (schema + manifiesto).
- [ ] Fijar consumo de `opendgsfp-0.1.jsonl` por `manifest.json` (pin commit).
- [ ] Benchmark Pagefind contra corpus real (nombre exacto, NIF, LEI).
