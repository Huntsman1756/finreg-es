# G4-G3 — Informe: hardening, refresh de evidencia y deployment real

Ejecutado sobre `feat/regulatory-record-g4` (`caf2adb` → `b253cec`).
Preregistro: `docs/gates/G4-G3-PREREG.md` (commit `0f7d329`).
Veredicto: **GO**.

## Resultados por caso preregistrado

| Caso | Resultado | Evidencia |
|---|---|---|
| R-01 Boundary audit | PASS | `finreg_es/` `dependencies=[]`; imports internos exclusivamente (stdlib+paquete). `tools/` aislado; `apps/web` sin imports del core, lee solo `projections/public` en build; 0 requests de red en build/runtime |
| R-02 Toolchain deps | PASS | F-01 remediado: `openpyxl` import duro del builder G4 declarado como extra `g4` (`>=3.1,<4`, tooling-only) |
| R-03 Refresh CNMV | PASS | 76/76 vistas OK (28 ESI + 48 SGIIC): `manifest-refresh-20260919.json` independiente, `manifest.json` G0 intacto; raw en `sources/raw/<slot>__vista_<n>.html` (slugs disjuntos); probes en `probes/refresh/`; por item: sha256, retrieved_at, source_as_of, content_check |
| R-04 Determinismo ×2 | PASS | Dos builds consecutivos → `bundle_sha256` idéntico: `2b9f3ae1d209e0ad1a5551737d728bd6b601b636fa3d92867cc8087d997dfae8`. sha_old `6088a340…` → sha_new `2b9f3ae1…` (cambio esperado: nueva evidencia) |
| R-05 Golden impersonations | PASS | ESI-1 (reg. 258): 4 impersonations, todas `MENTIONED_AS_LEGITIMATE_ENTITY`; anti-caso `alantrafx` (target reg. 245) ausente. ESI-4: 4. SAN-1: 1 sanción. ede-6707: 1 candidato `name-similarity-only` nunca promovido. 0 hechos adversos mal atribuidos en las 20 fichas (tests `test_g4_g3_refresh.py` ×10 + W02/W03b) |
| R-06 axe real | PASS | axe-core 4.13 + Playwright 1.63 sobre `dist/` servido: **0 violaciones** en 5 páginas tras corregir `label-title-only` (input Pagefind → `aria-label`) |
| R-07 Teclado/reflow/JS-off | PASS | Tab order sin trampas (brand→nav→contenido), foco visible; 0 overflow horizontal a 320px en 7 páginas tras `flex-wrap` en nav + `overflow-wrap:anywhere` en celdas; fichas íntegras sin JS (10 tablas, 0 `<script>`) |
| R-08 Visual regression | PASS* | Baseline congelada post-refresh: 5 PNG en `fixtures/g4/browser/`. Diff JSON `caf2adb`→post-refresh verificado estrictamente aditivo (passporting, managed_entities, audits, customer_service, sources×14, coverage.passport→COVERED); ningún contenido previo alterado. *Desviación declarada: no se capturó baseline visual pre-refresh; la verificación del diff se hizo a nivel de proyección |
| R-09 Performance | PASS | Página más pesada 6KB gz (ficha SGIIC-5 con 103 IIC); 1 request en ficha, 0 externos, 0 render-blocking; pagefind lazy solo en /buscar/ |
| R-10 SEO/links/URLs | PASS | 30 páginas, 30 URLs sitemap (base `/finreg-es/`), canonical en todas, description en todas, 0 enlaces internos rotos (crawl dist/) |
| R-11 Deployment real | PASS | `https://huntsman1756.github.io/finreg-es/` — GitHub Pages `built`. Smoke post-deploy: 10 rutas 200, manifest con bundle idéntico, búsqueda Pagefind "alantra" → 5 resultados → navegación a ficha, 0 errores JS |
| R-12 Hygiene repo público | PASS | 0 secretos (scan alta entropía), 0 `.env`/`.pem`/`.key` tracked, LICENSE + SECURITY.md presentes, 0 rutas locales (`F:\`, `_Proyectos`, `mas_joven`) en `projections/public`/`dist`, `.gitignore` cubre env/node_modules/dist/pycache |
| R-13 Reports | PASS | Este informe + `docs/G4-FINAL-REPORT.md` |

## Findings

- **F-01** `openpyxl` no declarado → remediado (extra `g4`, tooling-only; runtime sigue `dependencies=[]`).
- **F-02** `test_every_fixture_json_is_scoped_or_declared` ya fallaba en `caf2adb`: los JSON de `fixtures/g4/` nunca se declararon en ARTIFACT_MAP/UNSCOPED. No encajan en esquemas v1 (forma distinta) → declarados `fixtures/g4/**/*.json` en UNSCOPED_GLOBS como "pendientes de contrato schema" (misma vía que G2/G3). Fail **preexistente**, no regresión.
- **F-03** axe `label-title-only` en input Pagefind Default UI → `aria-label` explícito.
- **F-04** overflow horizontal a 320px (nav sin wrap + tablas min-content) → `flex-wrap` + `overflow-wrap:anywhere`/`word-break` (semántica de tabla preservada; WCAG 1.4.10).
- **F-05** canonical ausente en las 30 páginas, description solo en 21 → canonical desde `Astro.site`+`base` y description por defecto.

## Incidente (documentado, recuperado sin reescritura)

En el segundo deploy, `astro build` vació `dist/` (incluido el `.git` de
despliegue creado dentro). El commit posterior corrió en el repo padre:
`b253cec` ("fix bundlePath") cometió los cambios fuente pendientes en
`feat/regulatory-record-g4` — contenido correcto, mensaje erróneo — y
`gh-pages` quedó apuntando al árbol fuente. Recuperación **forward-only**:
nuevo commit `4b653a9` sobre `gh-pages` restaurando `dist/`; el sitio
redeployó `built` y el smoke pasó. `b253cec` se conserva (contenido
válido); su alcance queda documentado aquí. Lección persistida: los
deploys a `gh-pages` usan `git worktree` fuera del árbol, nunca un `.git`
anidado en `dist/`.

## Artefactos

```text
tools/g4/refresh_g3.py                          captura vistas pendientes
fixtures/g4/sources/manifest-refresh-20260919.json   76 requests congelados
fixtures/g4/sources/raw/*__vista_{5,6,10-13,16,38}.html
fixtures/g4/probes/refresh/*.json               parseo por vista
fixtures/g4/browser/g3-browser-20260919.json    evidencia navegador
fixtures/g4/browser/g3-*-20260919.png           baseline visual (5)
apps/web/scripts/browser-verify.mjs             suite R-06..R-10
tests/g4/test_g4_g3_refresh.py                  10 tests golden/refresh
```

## Cobertura nueva de superficies (post-refresh)

| Superficie | Antes | Ahora |
|---|---|---|
| Sucursales EEE / fuera EEE (v10-11) | NO_EVIDENCE | `passporting` BRANCH ×scope |
| Libre prestación EEE / fuera EEE (v12-13) | NO_EVIDENCE | `passporting` FREEDOM_TO_PROVIDE_SERVICES ×scope (ESI-1: 14 países EEE + Milán) |
| Fondos gestionados (v5, SGIIC) | NO_EVIDENCE | `managed_entities` (SGIIC-5: 103) |
| Sociedades gestionadas (v6) | NO_EVIDENCE | `managed_entities` MANAGED_COMPANY |
| Atención al cliente (v16) | NO_EVIDENCE | `organisation.customer_service` |
| Auditorías (v38) | NO_EVIDENCE | `organisation.audits` + `auditor` (ESI-1: 10 ejercicios, Deloitte) |

## Límites declarados

- El corpus sigue en 20 entidades (congelado por contrato).
- `passporting` mezcla modos BRANCH/LPS en una lista; no hay vista
  separada "sucursal vs libre prestación" en la ficha más allá del
  campo `mode`/`scope` mostrado.
- Una vista servida vacía (0 filas) es indistinguible de "sin
  sucursales reales" — la fuente no diferencia; coverage marca
  NO_EVIDENCE si la lista queda vacía.
- `site`/`canonical` = `huntsman1756.github.io/finreg-es`; si se activa
  `regulatoryrecord.es` como dominio, revertir `site` en astro.config.
- Baseline visual post-refresh (R-08): sin captura pre-refresh.
