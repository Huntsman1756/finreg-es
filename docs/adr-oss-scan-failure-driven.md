# ADR — OSS scan failure-driven antes de infraestructura genérica

Estado: **ACEPTADO** (congelado al cierre de G1,
`g1-regulatory-semantics-closed`). Regla operativa desde G2, no una
sugerencia.

## Contexto

FinReg-ES separa dos clases de problema:

```text
SEMÁNTICA REGULATORIA     → propiedad del proyecto (fail-closed,
                            provenance, temporalidad, derivación
                            jurídica). Ninguna librería decide que
                            ENT_AUT=[a1,a2,a3], una transformación BdE
                            y una ruta FPS se agregan como exige FinReg.
INFRAESTRUCTURA GENÉRICA  → entity resolution, validadores, parsers,
                            temporal stores, provenance formats, graph
                            tooling, property/mutation testing,
                            diffing, motores de reglas…
```

Para la segunda, construir desde cero cuando existe una implementación
madura es un defecto de ingeniería; adoptarla sin medir contra el caso
real es un defecto de auditoría.

## Decisión

Toda capacidad **genérica** nueva requiere antes un OSS scan
failure-driven:

```text
1. problema concreto
2. criterio de éxito/fallo
3. scan dirigido (GitHub/GitLab por ese fallo)
4. inspección de 5–10 candidatos serios:
   licencia · mantenimiento · tests · arquitectura
5. compatibilidad offline/determinista
6. prueba contra un caso REAL de FinReg
7. ADOPT | WRAP | PORT_PATTERN | REFERENCE | REJECT
```

Restricciones:

- Ninguna dependencia entra por popularidad: entra porque supera el
  gate medido contra nuestro caso.
- Ninguna librería toma una decisión jurídica: el núcleo regulador
  (`vocab`, `semantics`, `coverage`, `identity`, `temporal`,
  `derivation`, `provenance`, `contracts`) sigue siendo FinReg.
- REJECT documentado es un resultado válido del scan: construir la
  pieza mínima propia está justificado sólo cuando ningún candidato
  supera el gate real.
- Runtime sigue stdlib-only salvo beneficio demostrado; tooling puede
  adoptar dependencias en extras dev.

## Evidencia de que funciona

| Candidato | Resultado | Referencia |
|-----------|-----------|------------|
| JSON Schema | ADOPT (tooling) | `adr-post-g0-build-vs-reuse.md` |
| OpenLineage | PILOT → ADOPT como export (stdlib propio) | `openlineage-pilot.md` |
| Frictionless | REJECT medido | `frictionless-evaluation.md` |
| Great Expectations / DataHub | REJECT | `adr-post-g0-build-vs-reuse.md` |
| Hypothesis | ADOPT (dev-only, derandomizado) | `G1-FINAL-REPORT.md` §E6 |
| mutmut | ADOPT (dev-only, Linux/WSL) | `G1-FINAL-REPORT.md` §E6 |

## Consecuencias

- Todo G2 empieza por preregistro + scan, no por hardening
  oportunista.
- Un ADR o sección documenta cada decisión ADOPT/WRAP/REJECT con la
  medición que la produjo.
