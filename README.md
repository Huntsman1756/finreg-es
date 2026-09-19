# FinReg-ES

Registro auditable y pipeline de assessment para autorizaciones
financieras en España. Responde una sola pregunta por entidad:

> ¿Está esta entidad autorizada para esta actividad, en este régimen,
> a esta fecha — y qué evidencia oficial lo soporta?

Y desde G2, una segunda:

> ¿Qué podía afirmarse *jurídicamente* en `valid_at` usando sólo la
> evidencia observada hasta `known_at` — sin retroproyección?

Desde G3, esas respuestas se consumen por **superficies read-only
estables** — CLI `finreg`, servidor MCP y proyección Datasette —
instalables como wheel puro que lleva su evidencia congelada dentro.

Cero dependencias runtime (stdlib Python). Determinista, offline,
fail-closed. Construido como estudio de caso de ingeniería de datos
regulatoria: cada afirmación que el sistema emite es trazable hasta un
snapshot congelado de una fuente oficial.

## Arquitectura

```text
SNAPSHOTS OFICIALES (bytes congelados, sha256, retrieved_at)
        │
        ▼
extraction      adapters read-only por fuente
        │       → extraction records (no deciden nada)
        ▼
provenance      claim ledger: claims atómicos con provenance
        │       → cada claim apunta a snapshot + campo + fecha
        ▼
derivation      reglas declarativas sobre claims
        │       → derived assertions + reported_facts
        │         (intervalos [from,to), roots, routes)
        ▼
snapshot diff   records normalizados → added/removed/changed
        │       → candidatos a evento regulatorio (fail-closed)
        ▼
assessment      ASSESSMENT_SEMANTICS_V3 congelada
        │       → verdict fail-closed + rationale + diagnostics
        ▼
bitemporal      AssessmentQuery(valid_at × known_at)
        │       → filtra evidencia por K, delega el veredicto en V3
        ▼
openlineage     export opcional: lineage de artefactos (OSS std)
        │
        ▼
superficies     facade único (adapters/common.py), read-only
        │       → CLI `finreg` · MCP stdio v2 (5 operaciones)
        │       → proyección SQLite lossless → Datasette -i
        ▼
runtime bundle  wheel puro: paquetes + fixtures congelados
                byte-for-byte en adapters/_data/
```

`canonical.py` fija la serialización determinista
(`FINREG_CANONICAL_JSON_V1`: sin floats, sin claves duplicadas,
rechaza NaN/Inf). Todo hash de contenido deriva de ahí.

## Fuentes oficiales

| Fuente | Formato | Cobertura |
|--------|---------|-----------|
| EBA PSD2 register | JSON EAV (zip, ~20 MB) | entidades PSD2 salvo entidades de crédito y CASP |
| BdE registro de entidades | CSV (`utf-8-sig`, quirks) | clasificación estadística — **no** autorización |
| BdE registro servicios de pago | XLSX | actividades/entidades declaradas por la fuente |
| ESMA MiCA CASPs | CSV (columna fantasma, multivalor `\|`) | presencia ≠ evidencia negativa |
| CNMV registros ESI/FPS | HTML de detalle | domestic / branch / freedom-to-provide-services |

Los `SourceContract` (`fixtures/contracts/`) codifican por fuente:
autoridad, base jurídica, clases de entidad incluidas/excluidas,
capacidad de evidencia negativa, política de staleness, y notas de
interpretación legal. Son la autoridad semántica; los adapters sólo
extraen.

## Qué responde / qué no responde

Taxonomía actual (`ASSESSMENT_SEMANTICS_V3`; V1/V2 congeladas e
intactas para replay):

**Responde:**

- `CONFIRMED_ENTITLED` sólo cuando la cadena de evidencia completa
  existe (presencia + identidad + actividad + régimen + temporalidad
  + ruta).
- `CONFIRMED_NOT_ENTITLED` sólo con soporte demostrable: retirada
  fechada, `ENUMERATED_ABSENCE` dentro de un slice completo, o raíz
  cerrada. Nunca por ausencia poblacional.
- `INDETERMINATE` cuando la fuente no puede sostener la inferencia
  (p.ej. raíz abierta pero ruta territorial no observada).
- `NO_ENTITLEMENT_EVIDENCED` cuando no hay evidencia en scope —
  incluido el caso "correcto-como-de-K": evidencia que existe en el
  mundo pero aún no era observable en `known_at`.

**No responde:**

- No inventa cobertura: si la fuente no enumera, el sistema no asume.
- No promociona clasificación estadística (BdE) a autorización.
- No hace joins de identidad sobre identificadores inválidos.
- No afirma nada sin claim trazable a snapshot congelado.
- `known_at` nunca reescribe el pasado: filtra qué evidencia era
  observable, jamás modifica fechas jurídicas ni intervalos.

## Evidencia longitudinal (G2)

- Dos dimensiones de query: `valid_at` (tiempo jurídico) × `known_at`
  (cutoff de observación). `known_at = now` reproduce el comportamiento
  actual.
- Diff estructural entre snapshots oficiales: `added`/`removed`/
  `changed` sobre records normalizados, con gates de comparabilidad
  (misma serie, misma versión de normalización, completitud del
  slice).
- Cambios estructurales → candidatos a evento regulatorio con
  provenance bilateral; sin regla preregistrada el candidato queda
  `BLOCKED` — fail-closed, nunca inventado.
- Universo de evidencia versionado: cada resultado registra
  `evidence_set_id` ligado al sha256 de los bytes consumidos.

## Superficies públicas read-only (G3)

Tres superficies sobre una facade única (`adapters/common.py`) —
ninguna contiene semántica regulatoria; todas delegan en el core
congelado:

- **CLI `finreg`** (extra `[cli]`, Typer): `assess`,
  `assess-bitemporal`, `evidence`, `explain`, `changes` — payload
  canonical JSON en stdout; errores estructurados en stderr.
- **MCP stdio** (extra `[mcp]`, SDK v2): las mismas 5 operaciones
  como tools; payload canónico idéntico al CLI.
- **Datasette immutable** (extra `[datasette]`): visor HTTP/JSON de
  la proyección SQLite lossless (`fixtures/g3/projection/`) —
  evidencia, provenance y cambios longitudinales navegables.

Un cliente black-box puede ir de una respuesta a su evidencia oficial
cruzando superficies: `used_assertion_id` → assertion →
`source_assertions` → `raw_snapshot_sha256`/`source_url`/`retrieved_at`
(smoke externo `tools/smoke_g3d_external.py`, veredicto PASS).

### Quickstart (`v0.0.1`)

La pre-release pública [`v0.0.1`](https://github.com/Huntsman1756/finreg-es/releases/tag/v0.0.1)
incluye wheel y sdist con SHA-256 publicados en las notas del release.
No se publica en PyPI: puedes instalar el wheel descargado del release
o reconstruirlo desde el tag exacto.

Crea y activa un entorno virtual según tu shell (Windows o POSIX), como
se indica en [CONTRIBUTING.md](CONTRIBUTING.md#setup-y-verificación).
En ese entorno, instala el wheel descargado:

```bash
python -m pip install "finreg_es-0.0.1-py3-none-any.whl[cli]"
finreg --help
finreg assess-bitemporal --entity-id E3-001 --activity MONEY_REMITTANCE --jurisdiction ES --valid-at 2020-07-22 --known-at 2026-09-13
# → CONFIRMED_ENTITLED / ACTIVE_ENTITLEMENT_EVIDENCED
#   evidence_set_id: derived-assertions-g1-e-002@sha256:2fb08d67…
```

Para reconstruir el mismo artefacto desde fuente:

```bash
git clone https://github.com/Huntsman1756/finreg-es.git
cd finreg-es
git checkout v0.0.1
python -m pip install "build>=1.2,<2" "hatchling>=1.26,<2"
python -m build
```

El wheel incluye el **runtime evidence bundle**
(`adapters/_data/fixtures/`): contracts, evidence set, eventos G2 y
proyección — byte-for-byte idénticos al repo (verificado por sha256
en `tests/g3/test_g3e_packaging.py`). Sin el bundle el CLI también
acepta paths explícitos (`--evidence-set`, `--contracts-dir`,
`--events-dir`). El wheel base sin extras instala con 0 deps y
`finreg` falla limpio indicando `finreg-es[cli]`.

### Ejemplos autoritativos

`docs/examples/` contiene stdout real capturado sobre el tag — cada
fichero es canonical JSON exacto con `command + sha256(stdout)` en
`docs/examples/manifest.json` (extractos en este README; los outputs
completos son los artefactos).

## Resultados

| Métrica | Valor |
|---------|-------|
| Claims con provenance completa | 209 (ledger g1-e-001) |
| Assertions derivadas + reported_facts | 166 + 19 (artefacto g1-e-002) |
| Casos G0 congelados | 21/21 sin regresión |
| Casos G1-E preregistrados | 22/22 match, 0 divergencias |
| Casos bitemporales reales (G2-E0) | 5 casos · 18/18 probes |
| Pares EBA reales comparados (G2-B) | 2 (0/0/0 y 67/0/312) |
| Candidatos regulatorios (G2-C) | 379 → 67 SUPPORTED + 312 BLOCKED |
| Operaciones públicas (G3-B) | 5, payload idéntico CLI ≡ MCP |
| Filas proyectadas a SQLite (G3-C) | 1197 en 7 tablas, digest lógico fijado |
| Smoke externo black-box (G3-D) | 8/8 checks, 0 imports internos |
| Ficheros del runtime bundle (G3-E) | 17, sha256 repo = wheel = instalado |
| Tests — baseline histórico del release `v0.0.1` | 564 PASS |
| Dependencias runtime | 0 (stdlib puro) |

El total actual de tests se obtiene ejecutando `python -m pytest -ra`;
564 es el baseline histórico del release, no un recuento del checkout actual.

Replay determinista: mismos inputs → mismos bytes. La cadena
autoritativa completa regenera byte-idéntico con
`python tools/audit_g2f_replay.py`. Este comando reconstruye artefactos en
rutas históricas: ejecútalo sólo en un checkout desechable, nunca sobre
trabajo en curso.

## Fail-closed, en ejemplos reales

- **LEI inválido** — GLEIF devuelve 404 para un LEI publicado →
  `identifier_validity=INVALID` y el join por LEI queda prohibido.
- **Presencia EBA insuficiente** — `ENT_AUT` presente pero la cadena no
  cierra → `UNINTERPRETABLE_EVIDENCE`, no autorización.
- **Clasificación ≠ enumeración** — BdE IFM es clasificación
  estadística → `INDETERMINATE`, nunca promovida a autorización.
- **Conocimiento retroactivo** — THUNES: la retirada del 2026-08-27 se
  observó el 2026-09-13; con `known_at=09-12` el veredicto es
  `NO_ENTITLEMENT_EVIDENCED`, con `09-13` es `CONFIRMED_NOT_ENTITLED`
  — el mismo `valid_at`, dos verdades por cutoff de observación.
- **Métrica defectuosa preservada** — el run runner de G0.5-A tenía un
  defecto conocido (G05-B-F01): se conserva en el artefacto y se
  remedia en runs supersedes, no se reescribe la historia.
- **Cambio sin regla** — 312 cambios estructurales fuera del catálogo
  quedan `UNCLASSIFIED_STRUCTURAL_CHANGE`/`BLOCKED`, incluida la
  desactivación masiva de `DER_CHI_ENT_AUT` (candidato a extensión
  preregistrada, nunca clasificación retroactiva).

## Build vs Reuse

Regla de arquitectura (ADR `docs/adr-oss-scan-failure-driven.md`):
**ninguna infraestructura genérica nueva sin scan OSS previo** —
fallo concreto → 5–10 candidatos → licencia/mantenimiento/tests/
offline-determinismo → medir contra un caso real →
`ADOPT | WRAP | PORT_PATTERN | REFERENCE | REJECT`. La semántica
regulatoria se implementa en FinReg; la infraestructura genérica se
reutiliza cuando existe una solución madura.

| Candidato | Decisión | Por qué |
|-----------|----------|---------|
| `canonical.py` | KEEP | propiedad determinista que ninguna lib compra mejor |
| JSON Schema | ADOPTED (tooling) | contratos de artefacto, cero coste runtime |
| OpenLineage | PILOT PASS / LOCAL_ONLY | export de lineage stdlib-only validado contra spec 2.0.2 |
| dictdiffer | PORT_PATTERN | modelo de cambio added/removed/changed del differ G2-B |
| Hypothesis / mutmut | ADOPT (dev-only) | oráculos property/mutation, job `oracles` en CI |
| Frictionless | REJECT (medido) | 2/4 fuentes no tabulares; segunda descripción sin consumidor |
| Great Expectations | REJECT | validación semántica ≠ expectations estadísticas |
| DataHub | REJECT | catálogo generalista, provenance insuficiente |

Informes: `docs/G0-FINAL-REPORT.md`, `docs/G1-FINAL-REPORT.md`,
`docs/G2-FINAL-REPORT.md`, `docs/G3-FINAL-REPORT.md`. ADRs y
verificación por fase: `docs/`.

## Reproducir

Prepara el entorno virtual Windows/POSIX descrito en
[CONTRIBUTING.md](CONTRIBUTING.md#setup-y-verificación), desde la raíz del
checkout actual:

```sh
python -m pip install ".[test]"
python -m pip check
python -m pytest -ra
```

El resumen de pytest da el recuento y resultado actuales. Para regenerar
artefactos o ejecutar el replay, prepara ese entorno en un **checkout
desechable**: el replay reconstruye rutas históricas y puede sobrescribirlas.

```sh
python -m finreg_es.openlineage_export
python tools/audit_g2f_replay.py
python -m build
```

La verificación usa inputs locales, sin servicios ni credenciales; la
instalación de dependencias puede requerir red. La regeneración debe ser
byte-idéntica; no publiques cambios sobre artefactos históricos.

## Lo que no es

- **No es un servicio**: superficies locales y read-only; sin auth,
  multiusuario ni hosting. Datasette es un pilot/visor, no producción.
- **No es distribución vía PyPI ni un canal con SLA**: `v0.0.1` se
  publica como GitHub pre-release con wheel, sdist y hashes; no hay
  publicación en PyPI ni compromiso de soporte productivo.
- **No es exhaustivo**: la cobertura es la de los snapshots
  congelados (5 fuentes oficiales), no todo el mercado.

## Licencia

MIT — ver `LICENSE`.
