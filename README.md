# FinReg-ES

Registro auditable y pipeline de assessment para autorizaciones
financieras en España. Responde una sola pregunta por entidad:

> ¿Está esta entidad autorizada para esta actividad, en este régimen,
> a esta fecha — y qué evidencia oficial lo soporta?

Y desde G2, una segunda:

> ¿Qué podía afirmarse *jurídicamente* en `valid_at` usando sólo la
> evidencia observada hasta `known_at` — sin retroproyección?

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
| Tests | 515 PASS |
| Dependencias runtime | 0 (stdlib puro) |

Replay determinista: mismos inputs → mismos bytes. La cadena
autoritativa completa regenera byte-idéntico con
`python tools/audit_g2f_replay.py`.

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
`docs/G2-FINAL-REPORT.md`. ADRs y verificación por fase: `docs/`.

## Reproducir

```bash
python -m pytest          # 515 tests, offline
python -m finreg_es.openlineage_export   # regenera openlineage/ byte-idéntico
python tools/audit_g2f_replay.py         # replay byte-idéntico de la cadena G2
```

Sin servicios, sin red, sin credenciales. Todo input es un fichero del
repo; todo output es un artefacto hash-fijado.

## Licencia

MIT — ver `LICENSE`.
