# AGENTS.md — FinReg-ES

Reglas permanentes para cualquier agente que trabaje en este repo.
Detalle en `CONTRIBUTING.md`, `docs/adr-oss-scan-failure-driven.md`,
`docs/adr-post-g0-build-vs-reuse.md` y los scopes por fase en `docs/`.

## Reglas no negociables

- **Determinista**: mismos inputs → mismos bytes. Toda serialización
  pasa por `finreg_es/canonical.py` (`FINREG_CANONICAL_JSON_V1`).
- **Fail-closed**: evidencia insuficiente produce un finding
  clasificado, nunca una aserción positiva inventada.
- **Runtime stdlib-only**: `finreg_es/` sin dependencias externas.
  OSS de tooling vive en extras de `pyproject.toml` y tests.
- **Provenance**: toda aserción traza a snapshot SHA-256 congelado.
- **No reescribir la historia**: artefactos históricos no se
  sobrescriben; la remediación es artefacto/run sucesor.
- **Preregistro**: criterios de éxito/fallo y casos esperados se
  documentan antes de implementar.
- **OSS scan failure-driven**: ninguna infraestructura genérica nueva
  sin scan previo (`docs/adr-oss-scan-failure-driven.md`).
- **Classification ≠ authorization**: listas estadísticas/de
  clasificación no se promueven a evidencia de entitlement.

## Cómo se delega trabajo

Las tareas viven en `.tasks/<task-id>.yaml`: sólo los parámetros que
cambian (goal, inputs, gate, expected). El procedimiento reusable
vive en `.agents/skills/<name>/SKILL.md`.

Para ejecutar una tarea:

0. **STATUS IS AUTHORITATIVE**:
   `python tools/task_preflight.py .tasks/<task-id>.yaml`.
   Sólo `status: ready` permite ejecutar; cualquier otro resultado →
   STOP con explicación del blocker. Cero writes, cero commits.
   El texto de `blocker:`/`next_options:` informa, jamás autoriza.
1. Lee `.tasks/<task-id>.yaml`.
2. Lee la skill indicada en `skill:` (o la que corresponda por tipo).
3. Lee los `gate:` documents referenciados (contrato preregistrado).
4. Ejecuta siguiendo la skill; verifica `expected:` antes de commit.

## Verificación

```bash
python -m pytest                 # suite completa
python -m finreg_es.openlineage_export && git status --porcelain openlineage/
```

CI: job `test` (3.11–3.13, jsonschema+pytest) + job `oracles`
(hypothesis+dictdiffer; nunca skip silencioso).

## Limitaciones conocidas (no implementadas a propósito)

- **Sin claim/lease atómico**: dos agentes podrían leer la misma task
  `ready` a la vez y ambos pasar el preflight antes de que uno la
  mueva a `in_progress`. No hay scheduler ni locking mientras la
  ejecución sea secuencial; si aparece la carrera real, el hardening
  es `ready → claim exclusivo → in_progress → done|blocked`.

## Congelaciones activas

- G1: `g1-regulatory-semantics-closed` — no reabrir sin defecto
  reproducible (`docs/G1-FINAL-REPORT.md`).
- Contrato temporal/snapshot: `docs/g2-snapshot-history-contract.md`.
