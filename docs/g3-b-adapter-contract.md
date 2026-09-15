# G3-B — Contrato de superficies adapter (preregistro B0)

**Estado:** FROZEN antes de producción (task `g3-b-adapters`, paso
B0). Deriva de `docs/g3-scope.md` (frontera arquitectónica) y
`docs/g3-a-oss-scan-surfaces.md` (decisiones: MCP SDK + Typer ADOPT;
Datasette ADOPT-PILOT diferido a G3-C; FastAPI/DuckDB REFERENCE;
Streamlit/custom-transport REJECT).

Este documento congela **cuatro** cosas y nada más.

## 1. Operaciones públicas

Exactamente las medidas en el scan G3-A:

```text
assess              assessment actual → assess(V3, as_of=valid_at)
assess-bitemporal   AssessmentQuery(valid_at × known_at) → E2
evidence            slice del evidence set: item por id/entidad +
                    source_assertions, sin reinterpretar
explain             presenta reason + diagnostics + evidence +
                    assertion_evaluations que el core YA devuelve
changes             candidatos de los artefactos G2-C congelados
                    (por record_key / par de comparación)
```

`explain` no crea semántica: reorganiza campos existentes del
resultado del core. Si el core no produce un campo, la superficie no
lo inventa.

## 2. Un único façade

```text
CLI ─┐
     ├─> adapters/common.py ─> finreg_es/*
MCP ─┘
```

`common.py` sólo: resuelve paths y evidence sets, valida inputs de
interfaz, llama al core, devuelve dicts. Ninguna operación se
implementa dos veces; ninguna regla regulatoria vive en `adapters/`.

## 3. Contrato de salida

```text
business payload    = mismo dict FinReg en todas las superficies
serialización texto = canonical JSON (finreg_es/canonical.py)
transport envelope  != artefacto canónico
```

No se exige que el envelope MCP sea byte-idéntico al stdout del CLI
(depende del SDK). Sí se exige que el **payload FinReg** serializado
canónicamente sea idéntico entre ambas superficies.

## 4. Errores fail-closed de interfaz

```text
input inválido · artefacto inexistente · evidence_set_id
desconocido · query no resoluble
    → error estructurado {error: {code, message}}
    → cero fallback · cero búsqueda heurística · cero mutación
```

## 5. Decisiones técnicas congeladas

- **MCP**: `from mcp.server import MCPServer` (API v2 del SDK
  oficial; `FastMCP` es la API v1 retirada). Transporte: **stdio**
  local. `mcp>=2,<3`.
- **Typer**: `typer>=0.26,<0.28`, CLI `python -m adapters.cli`.
- **Packaging**: todo en `[project.optional-dependencies]`
  (`cli`, `mcp`, `adapters`). Nada se mueve a
  `project.dependencies`: el core se instala con cero runtime deps.
- **Frontera enforcement**: test estructural que recorre los imports
  de `finreg_es/` y falla si aparece `mcp`, `typer`, `datasette`,
  `fastapi`, `duckdb` o `streamlit`.

## 6. Acceptance criteria (binding)

```text
✓ 5 casos reales cubiertos (assess / assess-bitemporal / evidence /
  explain / changes) sobre artefactos congelados del repo
✓ CLI y MCP producen el mismo business payload (canonical JSON)
✓ ninguna importación mcp/typer/datasette/... desde finreg_es/
✓ ninguna escritura en fixtures/, docs/ ni core (read-only real)
✓ cero reglas regulatorias en adapters/
✓ input inválido / artefacto inexistente / id desconocido → error
  estructurado fail-closed
✓ MCP stdio arranca y expone la superficie esperada
✓ CLI: --help + comandos ejecutables
✓ suite core verde · tools/audit_g2f_replay.py PASS
```

## 7. Fuera de alcance de G3-B

- Proyección SQLite + Datasette → G3-C (`ADOPT-PILOT`).
- FastAPI → REFERENCE (sin consumidor HTTP-only medido).
- Escritura, auth, multiusuario, despliegue remoto.
