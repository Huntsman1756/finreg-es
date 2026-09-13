# G0 — informe final

Cierre de la fase G0 de FinReg-ES. G0 construyó el pipeline completo
`snapshot → extraction → provenance → derivation → assessment` sobre
fuentes oficiales reales congeladas, y cerró una revisión
build-vs-reuse de componentes OSS.

## Números

```text
30   entidades jurídicas reales en el corpus
34   referencias de fuente oficiales
18   snapshots congelados (manifest, sha256 por fichero)
337  claims trazables (1 por hecho atómico, provenance completa)
257  derived assertions
21   assessment cases preregistrados — 21/21 match con expected
0    inferencias negativas no soportadas
178  tests PASS
0    dependencias runtime (stdlib puro)
0    bytes de fixtures G0 modificados tras freeze
```

Replay: mismos inputs → bytes idénticos (`FINREG_CANONICAL_JSON_V1`).
OpenLineage: export interoperable validado contra spec oficial 2.0.2.

## Qué demuestra G0

- **Fail-closed real.** El sistema prefiere `INDETERMINATE` o
  `REVIEW_REQUIRED` a afirmar. La ausencia en fuentes no exhaustivas
  no produce inferencias negativas.
- **Provenance a nivel de claim.** Cada hecho atómico apunta a
  snapshot + campo + fecha; nada llega a assessment sin cadena.
- **Semántica separada de estructura.** `SourceContract` codifica
  autoridad, cobertura, evidencia negativa y staleness; los parsers
  sólo extraen estructura.
- **Interoperabilidad sin contaminación.** La cadena de artefactos se
  expone en OpenLineage 2.0.2 (export read-only, stdlib) sin migrar
  semántica regulatoria fuera del core.

## Findings incómodos (conservados, no corregidos)

G0 documenta los defectos encontrados en lugar de sanearlos:

| Finding | Documento | Consecuencia |
|---------|-----------|--------------|
| LEI publicado que GLEIF resuelve 404 | `g0.5-corpus-audit.md` | `identifier_validity=INVALID`; join por LEI prohibido |
| Métrica del runner G0.5-A defectuosa (G05-B-F01) | `g0.5-c-remediation-closeout.md` | artefacto preservado como histórico; remediado en runs supersedes 002/003 |
| Omisiones de preregistro auditadas | `g0.7-c-divergence-audit.md` | metadatos de preregistro eliminados de los cases para no contaminar la medición |
| Presencia EBA (`ENT_AUT`) insuficiente | `g0.7-b-assessment-run.md` | `UNINTERPRETABLE_EVIDENCE`, no autorización |
| Clasificación estadística BdE ≠ autorización | `g0.7-b-assessment-run.md` (G07-015) | `INDETERMINATE`; IFM no promovido |

## Build-vs-reuse — matriz cerrada

| Candidato | Decisión | Evidencia |
|-----------|----------|-----------|
| `canonical.py` | KEEP | determinismo que ninguna lib mejora |
| JSON Schema | ADOPTED | contratos v1 de artefactos, tooling-only |
| OpenLineage | PILOT PASS / LOCAL_ONLY | `openlineage-pilot.md`, commit `17860a8`; URN registry local hasta remote público |
| Frictionless | REJECT — medido | `frictionless-evaluation.md`: EBA es JSON EAV, CNMV es HTML, CSVs describibles = segunda descripción sin consumidor |
| Great Expectations | REJECT | expectations estadísticas ≠ semántica fail-closed |
| DataHub | REJECT | catálogo generalista sin provenance de claim |

Criterio aplicado: una capa genérica se adopta sólo si aporta
interoperabilidad verificable sin degradar provenance ni duplicar
`SourceContract`.

## Límites declarados

- CNMV completeness sigue `PENDING`; los cruces ESI/FPS quedan en
  `REVIEW_REQUIRED` hasta verificación de cobertura.
- ESMA no soporta evidencia negativa (presencia ≠ enumeración).
- El export OpenLineage es `LOCAL_ONLY`: los `_schemaURL` de custom
  facets son URNs del registry local; portabilidad completa requiere
  publicar los schemas en un remote estable (procedimiento
  commit-A/commit-B documentado en `openlineage-pilot.md`).

## Artefactos de cierre

| Artefacto | Rol |
|-----------|-----|
| `fixtures/g0.5/` | corpus, sources, contracts — congelado |
| `fixtures/g0.6/` | claim provenance ledger — congelado |
| `fixtures/g0.7/` | ruleset, assertions, cases, run — congelado |
| `schemas/v1/` | JSON Schema de artefactos |
| `schemas/openlineage/` | spec 2.0.2 vendored + custom facets |
| `openlineage/` | 10 eventos exportados (8 RunEvent + 2 JobEvent) |
| `docs/` | ADRs, verificación por fase, evaluaciones |
