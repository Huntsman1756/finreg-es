# G3 — informe final

Cierre de la fase G3 de FinReg-ES (`g3-consumability-closed`).
G3 demostró una propiedad nueva del sistema — de "motor validado
que sólo sabe consultarse desde dentro" a:

> FinReg expone assessments, evidencia, historia y provenance
> mediante interfaces read-only estables — CLI, MCP y proyección
> Datasette — que un cliente black-box recorre hasta la evidencia
> oficial sin importar ni conocer módulos internos, y que sobreviven
> byte-iguales a la instalación del wheel fuera del checkout.

## Veredicto

```text
G3 — PASS / CLOSED

G3-0  CLOSED   capability contract público publicado: g3-scope.md
               + contratos por superficie (g3-b/g3-c/g3-d/g3-e0)
G3-A  CLOSED   OSS scan surfaces: ADOPT mcp+typer, ADOPT-PILOT
               datasette, REFERENCE fastapi/duckdb/sqlite-utils,
               REJECT streamlit/custom-transport
G3-B  CLOSED   PASS — facade único adapters/common.py; CLI Typer +
               MCP v2 stdio, 5 ops, payload canónico idéntico,
               errores fail-closed estructurados
G3-C  CLOSED   PILOT_PASS — proyección SQLite lossless (7 tablas,
               payload_json = objeto canónico completo) + Datasette
               0.65.4 immutable; C1-C5 sin UI/plugin custom
G3-D  CLOSED   PASS — harness black-box sin imports FinReg:
               CLI subprocess + MCP stdio real + Datasette HTTP;
               cadena respuesta→evidencia oficial cross-surface
G3-E  CLOSED   PASS — wheel puro instalado en venv limpio fuera
               del repo: runtime evidence bundle byte-idéntico,
               finreg shim stdlib-only, resolution _data
```

G3 no se reabre salvo defecto reproducible nuevo.

## Números

```text
564    tests PASS (suite completa, offline, determinista)
       515 pre-G3 → +21 (B) +16 (C) +2 (D) +10 (E1)
8/8    checks del smoke externo G3-D (S1-S5 + writes.zero)
17     ficheros del runtime evidence bundle, sha256
       repo == wheel == instalado por cada uno
1197   filas proyectadas en 7 tablas (FINREG_G3_SQLITE_PROJECTION_V1)
5      tools MCP descubiertos por protocolo stdio real
5      operaciones públicas: assess, assess-bitemporal, evidence,
       explain, changes
312    candidatos NO_PREREGISTERED_RULE navegables CLI↔Datasette
0      dependencias runtime del paquete base
0      imports de finreg_es/adapters/sqlite3 en el cliente G3-D
0      cambios en finreg_es/ (semántica intacta, stdlib-only)
0      escrituras durante el smoke externo
0      plugins/templates/endpoints Datasette custom
```

## Cadena autoritativa congelada

```text
Core      finreg_es/ stdlib-only — ASSESSMENT_SEMANTICS_V3 intacta
          evidence set: derived-assertions-g1-e-002
          @sha256:2fb08d678a5ee11a… (idéntico en repo y wheel)
Contratos docs/g3-b-adapter-contract.md      (5 ops, facade único)
          docs/g3-c-projection-contract.md   (+ addendum-01)
          docs/g3-d-external-smoke-contract.md (D1-D4, S1-S5)
          docs/g3-e0-packaging-contract.md   (backend scan, bundle)
Proyección fixtures/g3/projection/finreg-g3.sqlite + manifest.json
          logical_projection_sha256
          5a4efd0dc9b7669c999771ce7aa9569ea5d36941697c0a77732d7d657e806d1a
          (determinismo contractual lógico; el SHA del .sqlite es
          observación — recomputado e igual sobre el wheel instalado)
Packaging hatchling>=1.26,<2 · force-include → adapters/_data/
          build ×2: mismo content manifest + mismo wheel SHA
          (evidencia adicional, no requisito)
          wheel de referencia finreg_es-0.0.1-py3-none-any.whl
          sha256 5077fdeabd296bdf… (reproducible por build)
Commits   60b7757 scope · 4d544d9/a375463 scan · 103341f contrato B
          5e1afb3/672d321 impl B · 7ddf39a contrato C ·
          2cb0cf4/0b8ae84 pilot C · a6f0bbb addendum C-01 ·
          9318c60 contrato D · dc5a12f/4b86b6a smoke D ·
          8244c14 contrato E0 · acabd06/120ea76 build E1 ·
          1eb4c22 metadata
CI        35021933204 (B) · 35054929548 (C) · 35056192531 (D) ·
          35056848898 (E0) · 35060039154 (E1) · 35060695370
          (metadata) — todos CI/workflow test+oracles SUCCESS
```

Replay: `python tools/audit_g2f_replay.py` — PASS ×3 tras todos
los cambios de G3 (la cadena G1/G2 permanece byte-idéntica).

## Criterios de cierre de g3-scope — veredicto por criterio

```text
✓ capability contract público publicado
      PROVEN — contratos por superficie en docs/ (ver cadena)
✓ scan OSS ejecutado y documentado con decisión por candidato
      PROVEN — g3-a-oss-scan-surfaces.md, decisión medida
✓ adapter read-only implementado sobre el core sin copiar reglas
      PROVEN — facade delega en finreg_es; test estructural
      prohibe deps de adapter en el core; cero semántica duplicada
✓ provenance surface: cada respuesta expone evidence_set_id + trazas
      PROVEN — todos los payloads llevan evidence_set_id; drill-down
      assertion → source_assertions → raw_snapshot_sha256/url/
      retrieved_at verificado E2E desde el smoke externo
✓ smoke externo reproducible por cliente que no conoce internals
      PROVEN — tools/smoke_g3d_external.py, enforcement AST de D1
✓ cero regresión: full suite + replay G2-F verdes
      PROVEN — 564 passed; replay PASS ×3; CI verde en cada push
```

## Límites declarados

Son límites declarados, no deuda escondida:

- **PyPI no probado**: el gate de packaging construye e instala el
  wheel local en venv limpio; publicación a un registry es
  distribución, no consumibilidad — fuera de alcance preregistrado.
- **Extras ejercitados offline reutilizando dependencias del
  entorno CI**: el venv de extras ve typer/mcp vía
  `site.addsitedir()` al site-packages del entorno de test; no se
  probó `pip install "finreg-es[cli]"` contra registry/wheelhouse.
- **Datasette sigue siendo pilot/local**: visor immutable de la
  proyección; no es superficie de producción ni de hosting.
- **Sin auth/multiusuario/hosting**: fuera de alcance de G3 por
  scope; las superficies son read-only locales.
- **Sin claim/lease atómico de tasks**: ejecución secuencial
  asumida (limitación ya declarada en AGENTS.md).
- **Límites heredados de G2**: profundidad longitudinal del corpus
  (3 observaciones EBA + re-observaciones), calendario superficial
  (PROVEN WITH QUALIFICATION en G2-D) — ver docs/G2-FINAL-REPORT.md.
- **README describe el motor, no aún las superficies G3**: el
  contrato público autoritativo son los docs de contrato; una
  sección de uso en README es polish posterior, no gate.
- **MCP sirve sólo por stdio**: `python -m adapters.mcp_server`;
  no se inventó un segundo ejecutable sin necesidad real.

## Evidencia de calidad

```text
suite completa      python -m pytest            564 passed
replay G2-F         tools/audit_g2f_replay.py   PASS ×3
smoke externo G3-D  tools/smoke_g3d_external.py verdict PASS
packaging E1        tests/g3/test_g3e_packaging.py 10 passed
OpenLineage         export regenera byte-idéntico (CI)
```
