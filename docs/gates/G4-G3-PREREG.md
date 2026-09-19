# G4-G3 — Preregistro: hardening, refresh de evidencia y deployment real

Baseline: `feat/regulatory-record-g4` @ `caf2adb` (G4-G2 CONDITIONAL/GO).
Remote baseline `main`: `0a1a839`.

G4-G3 cierra los gaps declarados de G4-G2 y lleva el vertical a un
deployment estático real. **No añade features de producto**, no escala el
corpus (sigue en 20 entidades), no implementa G5, no mergea a `main` ni
taggea hasta que este gate determine `v0.1 READY`.

## Scope preregistrado

1. Core-boundary audit (FinReg core vs product layer).
2. Baseline/freeze documentado.
3. CNMV live evidence refresh de las superficies pendientes.
4. Rebuild determinista ×2.
5. Golden impersonations / false adverse attribution.
6. Playwright + axe real.
7. Keyboard / reflow / JS-disabled.
8. Visual regression acotada.
9. Performance.
10. SEO / link / URL contract.
11. Static deployment real + post-deploy smoke.
12. Security / public-repo hygiene.
13. G4-G3 report + G4 final report.

## Resultados válidos (declarados a priori)

- El refresh puede devolver **contenido idéntico** (mismo sha256 por
  vista) — es un resultado válido, no un fallo.
- Una vista puede ser `SOURCE_UNAVAILABLE` (HTTP error, página de error
  CNMV, contenido vacío) — válido si queda registrado con evidencia y la
  proyección sigue emitiendo `NO_EVIDENCE` fail-closed.
- El `bundle_sha256` puede cambiar respecto al baseline `6088a340…` si la
  evidencia nueva aporta hechos; lo inaceptable es que dos builds
  consecutivos sobre los mismos inputs difieran.
- Violaciones axe encontradas → se corrigen dentro de scope (marcado
  a11y de las plantillas) o se declaran como límite con causa; no se
  relaja el umbral a cero por omisión.
- Deployment target: cualquier host estático público (GitHub Pages por
  defecto); el criterio es post-deploy smoke real, no la marca del host.

## Casos preregistrados

### R-01 Boundary audit

`finreg_es/` declara `dependencies = []` y no importa nada fuera de
stdlib + el propio paquete. `tools/` solo toca el core para
serialización/contratos. `apps/web` tiene cero imports de `finreg_es`,
lee únicamente `projections/public` en build y no realiza requests de
red en build ni en runtime.
**Esperado:** PASS. Cualquier import cruzado no declarado = finding.

### R-02 Toolchain deps declaradas

Todo import no-stdlib de `tools/` está cubierto por un extra de
`pyproject.toml` (finding ya detectado: `openpyxl` sin declarar →
remediado con extra `g4`).
**Esperado:** PASS tras remediación; se documenta como finding F-01.

### R-03 Refresh CNMV de vistas pendientes

Nuevo manifiesto independiente `fixtures/g4/sources/manifest-refresh-<fecha>.json`
(los históricos no se modifican). Para cada slot ESI-1..4 / SGIIC-1..5 /
SAN-1 del corpus congelado se capturan las vistas no congeladas en G0
(las que la proyección declara hoy `NO_EVIDENCE`: sucursales EEE, libre
prestación, fondos gestionados, atención al cliente, auditorías — vistas
10–13, 5–6, 16, 38 según `vista=` de la ficha). Por request:
`http_status`, `bytes`, `sha256`, `retrieved_at` por item. Contenido
verificado: HTTP 200 no basta — se descarta la página de error CNMV.
**Esperado:** cada vista pendiente queda (a) congelada con sha, o
(b) registrada como unavailable/error con evidencia. Sin terceras vías.

### R-04 Rebuild determinista ×2

Dos ejecuciones consecutivas de `tools/g4/build_projection.py` sobre los
mismos inputs producen `manifest.json` con `bundle_sha256` idéntico.
**Esperado:** `sha_run1 == sha_run2`. Se registra `sha_old` (6088a340…)
vs `sha_new`; divergencia entre runs = defecto reproducible → STOP.

### R-05 Golden impersonations / false adverse attribution

Sobre la proyección resultante (post-refresh si cambia):

- ESI-1 (ALANTRA CAPITAL MARKETS, reg. 258): sus impersonations contienen
  todos y solo los notices AlertaFin dirigidos a esa entidad concreta;
  el clon `alantrafx` (target reg. 245) **no** aparece atribuido.
- Ninguna entidad del corpus lleva un hecho adverso (warning, sanción,
  clon) cuyo notice/sanción no la identifique inequívocamente.
- Los warnings de AlertaFin siguen presentándose como suplantación
  **de** la entidad, nunca como advertencia contra ella.
**Esperado:** PASS con conteos por entidad en el informe.

### R-06 axe real

axe-core ejecutado con Playwright sobre páginas representativas:
`/`, `/entidad/<ESI-1>/`, `/entidad/<ESI-4>/` (impersonations),
`/buscar/`, `/fuentes/`.
**Esperado:** 0 violaciones (reglas por defecto de axe). Violación =
fix de plantilla dentro de scope o límite declarado con causa.

### R-07 Keyboard / reflow / JS-disabled

- Navegación por teclado: skip link visible al foco, tab order sin
  trampas, foco visible.
- 320 px: sin scroll horizontal en home y ficha.
- JS-disabled: las 20 fichas siguen íntegramente legibles (W08 se
  re-verifica tras cualquier cambio de marcado).
**Esperado:** PASS en las tres dimensiones.

### R-08 Visual regression acotada

Screenshots de `/`, ficha ESI-1, ficha ESI-4 antes/después del refresh:
el único diff admisible es contenido (nuevos hechos de la evidencia
refrescada), nunca layout roto o secciones vacías.
**Esperado:** diff explicable por contenido o cero.

### R-09 Performance

Presupuestos sobre `dist/` servido estáticamente:

- Ficha: transferencia comprimida total < 600 KB, requests < 40,
  0 recursos render-blocking externos (solo origen propio + pagefind
  lazy en /buscar/).
- `/data/` JSON no se descarga hasta uso (Pagefind y fetch lazy).
**Esperado:** dentro de presupuesto; desviación = medición + causa.

### R-10 SEO / link / URL contract

- `sitemap-index.xml` ≥ 30 URLs, canonical por página, trailingSlash
  consistente, metas básicos (title/description) presentes.
- 0 enlaces internos rotos (crawl de `dist/`).
**Esperado:** PASS.

### R-11 Static deployment real + post-deploy smoke

`dist/` publicado en host estático público real. Post-deploy smoke:
HTTP 200 y contenido correcto en `/`, `/entidad/<id>/`, `/data/manifest.json`,
`/buscar/`, `/sitemap-index.xml`.
**Esperado:** PASS con URL pública registrada en el informe.

### R-12 Security / public-repo hygiene

- 0 secretos/keys en el árbol (scan de patrones habituales).
- `.gitignore` cubre `.env*`, `node_modules`, `dist`, `__pycache__`.
- LICENSE + SECURITY.md presentes.
- Los artefactos públicos (`dist/`, `projections/public/`) no contienen
  rutas locales de build (`F:\…`) ni datos de entorno.
**Esperado:** PASS o finding remediado.

### R-13 Reports

`docs/gates/G4-G3-REPORT.md` (veredicto por caso) +
`docs/G4-FINAL-REPORT.md` (estado del vertical + límites declarados +
veredicto `v0.1 READY` o gaps).
**Esperado:** ambos existen y cierran el gate.

## Fuera de scope (declarado)

- Nuevas entidades, nuevas fuentes, nuevos tipos de hecho.
- Ratings, scores, comparadores, recomendaciones — permanentemente.
- Features de producto (G5).
- Rename de repositorio, merge a `main`, tags de release.
- Cambios a gates congelados G1–G4-G2 (salvo defecto reproducible).
