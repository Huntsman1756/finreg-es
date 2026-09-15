# G3-A — OSS scan: query surfaces (decisión documental)

Scan failure-driven (skill `oss-scan`, ADR
`adr-oss-scan-failure-driven.md` elevado a restricción de
arquitectura en `g3-scope.md`). Task `g3-a-oss-scan`. **Cero código
de producción**: este documento decide qué OSS expone el core;
no implementa nada.

## 1. Fallo concreto

```text
FinReg tiene un motor validado (515 tests, 18/18 probes, replay
byte-idéntico) pero un tercero no puede consultarlo cómodamente:
no existe ninguna superficie de consulta — sólo fixtures, tools y
pytest.
```

## 2. Semántica propia vs genérico

```text
PROPIO (nunca se delega):
  semántica regulatoria V3 · temporalidad (valid_at/known_at,
  intervalos [from,to), EVIDENCE_AS_OF) · provenance · fail-closed

GENÉRICO (candidato a reutilizar):
  transporte (MCP/HTTP/CLI) · exploración/tablas · serving ·
  proyección de almacenamiento analítico
```

## 3. Los 5 casos reales → qué exige cada uno

| # | Caso | Llamada del core existente | Lo que la superficie debe hacer |
|---|------|---------------------------|--------------------------------|
| 1 | assessment actual | `semantics.assess(..., as_of=today, V3)` | invocar con parámetros → JSON canónico |
| 2 | assessment `valid_at × known_at` | `bitemporal.assess_bitemporal(...)` | ídem + `evidence_set` resoluble |
| 3 | evidence_set + source_assertions | `load_evidence_set` + doc | servir slices del artefacto congelado |
| 4 | explicar BLOCKED/INDETERMINATE | `result.reason` + `diagnostics` + `evidence` + `assertion_evaluations` | devolver el payload de auditoría tal cual |
| 5 | cambio longitudinal | artefactos `fixtures/g2/events/*.json` | lookup por record_key/entity/fecha → JSON |

Conclusión de la medición: los 5 casos son **lookups parametrizados
read-only sobre artefactos congelados + dos llamadas de función**.
Ninguno exige semántica nueva en la superficie; toda la respuesta ya
lleva `evidence_set_id`, `reason`, `diagnostics` y conjuntos de
evidencia — la provenance se conserva por paso directo.

## 4. Candidatos

### MCP Python SDK (`mcp`, PyPI)

- Licencia MIT · `v2.2.0` línea estable (v2.0.0 stable 2026-07-28,
  spec MCP 2026-07-28; v1.x en maintenance). Python ≥3.10.
- Mantenimiento: org `modelcontextprotocol`, releases frecuentes,
  docs oficiales; ~24k★.
- Encaje medido: los 5 casos se exponen como tools/resources sobre
  stdio local — transporte puro, offline por construcción. Un
  `MCPServer` con 5 handlers finos que llaman al core y devuelven
  JSON canónico. ~unas decenas de LOC de adapter.
- Read-only: de verdad — sólo definimos tools de consulta; el
  servidor no tiene canal de escritura a artefactos.
- **Decisión: ADOPT** (extra `adapters/`, nunca importado por
  `finreg_es/`). Cubre el consumidor-agente, hoy el caso principal.

### Typer

- Licencia MIT · mantenido (ecosistema tiangolo, releases activas).
- Encaje medido: CLI `finreg assess|assess-bitemporal|evidence|
  explain|changes` — cubre casos 1–5 para humano/script local con
  ~1 función por comando. También sirve de entrada al builder de la
  proyección (G3-B/C).
- Determinismo: salida = JSON canónico del core.
- **Decisión: ADOPT** (extra `adapters/`).

### Datasette

- Licencia Apache-2.0 · muy activo (1.0a39 + 0.65.4 security
  releases 2026-09-11; línea estable 0.65.x + alpha 1.0).
- Encaje medido: necesita una **proyección SQLite** de los
  artefactos (artefacto derivado nuevo, construido con `sqlite3`
  stdlib — tooling FinReg, no OSS nuevo). A cambio da: exploración
  humana, filtros, SQL read-only y JSON API — cubre casos 3–5 para
  humanos y consumidores HTTP ligeros.
- Read-only de verdad: modo `-i` sobre fichero inmutable.
- Determinismo: la proyección es determinista (bytes de entrada
  fijos → DB fija); Datasette sólo la sirve.
- Provenance: las columnas llevan `evidence_set_id`/sha256/claim
  ids — visibles y consultables, no reinterpretados.
- **Decisión: ADOPT-PILOT** — pilot acotado en G3-B/C; el criterio
  de éxito es que la proyección exponga provenance sin pérdida.

### FastAPI

- Licencia MIT · `0.141.1` (2026-07-29), muy activo, Python ≥3.10.
- Encaje medido: daría una API HTTP JSON propia para casos 1–5 —
  pero **duplica superficies ya cubiertas**: MCP sirve al consumidor
  máquina/agente y el JSON API de Datasette sirve HTTP de consulta.
  No hay hoy un consumidor HTTP-only identificado.
- **Decisión: REFERENCE** — se adopta cuando aparezca un consumidor
  concreto que no encaje en MCP ni en Datasette (failure-driven:
  sin fallo no hay pieza). Diverge de la expectativa previa
  (ADOPT/WRAP): el scan no encontró el fallo que la justifique hoy.

### DuckDB

- Licencia MIT · `1.5.5` actual / `1.4.x` LTS; gobierno en DuckDB
  Foundation (DuckLabs→AWS no cambia licencia ni roadmap).
- Encaje medido: no es una superficie de consulta para los 5 casos;
  es motor analítico. El corpus derivado es pequeño (166 assertions,
  19 facts) y la proyección SQLite + `sqlite3` stdlib lo cubre. Los
  330k records normalizados sí son un caso futuro plausible para
  analítica.
- **Decisión: REFERENCE (tooling)** — se evalúa de nuevo si el
  análisis del corpus supera a `sqlite3` stdlib.

### Streamlit

- Licencia Apache-2.0 · `1.63.0` (2026-09-01), activo.
- Encaje medido: exige código de app a medida por vista y duplica el
  rol de Datasette sin ganar read-only ni JSON API estable. Sólo se
  justificaría para una UI guiada a medida — no es el fallo actual.
- **Decisión: REJECT** — revisit only si Datasette se queda corto
  para un caso real.

### sqlite-utils / HTTP propio (honorable mentions)

- `sqlite-utils` (Apache-2.0): REFERENCE — el builder de la
  proyección se queda en `sqlite3` stdlib; se reconsidera si la
  proyección crece en complejidad.
- Servidor HTTP/protocolo propio: **REJECT** — construir transporte
  genérico propio es exactamente lo que la restricción prohíbe.

## 5. Matriz

| Candidato | Licencia | Mantenimiento | LOC FinReg | Read-only real | Determinismo | Provenance | Footprint | Decisión |
|-----------|----------|---------------|-----------|----------------|--------------|------------|-----------|----------|
| MCP SDK | MIT | alto (v2 estable) | ~decenas | sí | transporte puro | paso directo | medio | **ADOPT** |
| Typer | MIT | alto | ~1 fn/comando | sí | sí | paso directo | bajo | **ADOPT** |
| Datasette | Apache-2.0 | alto | proyección + config | sí (`-i`) | proyección fija | columnas | medio | **ADOPT-PILOT** |
| FastAPI | MIT | alto | ~1 fn/endpoint | sí | sí | paso directo | medio | REFERENCE (sin consumidor HTTP-only) |
| DuckDB | MIT | alto | n/a hoy | n/a | n/a | n/a | medio | REFERENCE (tooling futuro) |
| Streamlit | Apache-2.0 | alto | app a medida | sí | sí | paso directo | alto | REJECT |
| sqlite-utils | Apache-2.0 | alto | — | — | — | — | bajo | REFERENCE |
| HTTP propio | — | — | — | — | — | — | — | REJECT (prohibido por la restricción) |

## 6. Qué se construye propio (y por qué)

```text
- proyección SQLite de artefactos congelados: artefacto derivado,
  tooling stdlib (sqlite3); es semántica de representación, no
  infraestructura genérica — no hay OSS que la decida mejor.
- handlers de adapter (MCP/CLI): thin glue que llama al core y
  serializa canonical JSON; contienen cero reglas.
```

Todo lo adoptado vive en extras de `pyproject.toml` +
`adapters/`; `finreg_es/` permanece stdlib-only y congelado.

## 7. Estado / siguiente

```text
G3-A  DONE  (este scan; decisiones arriba)
G3-B  adapter read-only: MCP server + Typer CLI (ADOPT)
G3-C  provenance/explanation surface: pilot Datasette sobre
      proyección SQLite + payloads de explicación (reason +
      diagnostics + evidence audit + evidence_set_id)
G3-D  smoke externo · G3-E  packaging + closeout
```

La expectativa previa del scope queda así corregida por el scan:
FastAPI pasa de "probable ADOPT/WRAP" a **REFERENCE** — sin
consumidor HTTP-only concreto no hay fallo que resolver.
