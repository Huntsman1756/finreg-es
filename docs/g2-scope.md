# FinReg España — G2: preregistro de evidencia regulatoria longitudinal

> **Estado: OPEN — preregistro**. G1 quedó congelado en
> `g1-regulatory-semantics-closed`; no se reabre salvo defecto
> reproducible nuevo.

## Tesis

```text
FinReg puede reconstruir qué podía hacer una entidad en distintas
fechas, detectar qué cambió entre snapshots oficiales y explicar qué
evidencia produjo el cambio de assessment — sin retroproyectar
conocimiento actual.
```

G2 demuestra una **propiedad nueva** del sistema, no más tamaño:
de "¿qué puede hacer ahora?" a "¿qué podía hacer entonces y por qué
cambió?". Aprovecha lo que ya diferencia al proyecto: `as_of`,
bitemporalidad, provenance, sucesores, `EVIDENCE_AS_OF`, intervalos
`[from,to)`, roots y routes.

## Objetivo observable

```text
Entidad X
  2026-03-01  PIS via FPS  → CONFIRMED_ENTITLED
  2026-06-15  PIS via FPS  → CONFIRMED_ENTITLED
  2026-08-27  PIS via FPS  → CONFIRMED_NOT_ENTITLED  (root withdrawn)

CHANGE EXPLANATION
  snapshot S2 → S3: ENT_AUT ganó withdrawal date 2026-08-27
  source: EBA · claim: … · rule: …
  assessment delta: ENTITLED → NOT_ENTITLED
```

## Workstreams preregistrados

| ID | Área | Pregunta a resolver |
|----|------|---------------------|
| G2-A | snapshot history contract | Qué significa `observed_at` / `source_as_of` / `effective_at` en una serie de snapshots; contrato temporal de la fuente. |
| G2-B | structural snapshot diff | **OSS scan obligatorio primero.** bytes → records added/removed/changed; sin semántica jurídica; offline y determinista; ignora reordenación/formato no semántico. |
| G2-C | regulatory change events | Cambio estructural → evento regulatorio candidato → provenance completa (claim + snapshot + rule). |
| G2-D | longitudinal corpus real | Entidades con cambios conocidos en 2+ snapshots oficiales; preregistro de expectations. |
| G2-E | historical assessment | `query(entity, activity, ES, as_of=t1/t2/t3)` reproduce el veredicto correcto en cada fecha. |
| G2-F | divergence / mutation / replay audit | Mismo gate que G1: replay determinista, Hypothesis, mutmut, 0 deps runtime. |

## Reglas heredadas (G0/G1) + regla nueva

1. **Preregistro antes que reglas.** Casos y expectations antes de
   tocar derivación/assessment; divergencias se auditan, no se
   corrigen en silencio.
2. **Fail-closed.** Si un cambio estructural no es interpretable
   jurídicamente, produce finding clasificado, nunca un evento
   inventado.
3. **Sin retroproyección.** La evidencia atestigua desde su
   `EVIDENCE_AS_OF`; un snapshot nuevo no reescribe el pasado, lo
   explica.
4. **Provenance.** Todo evento regulatorio apunta a snapshot
   (sha256) + claim + regla + delta de assessment.
5. **OSS scan failure-driven** (`adr-oss-scan-failure-driven.md`):
   toda capacidad genérica nueva (diffing, series temporales, etc.)
   pasa el scan antes de construirse.
6. **Cero degradación.** G0 21/21 y G1 22/22 sin regresión; V1/V2/V3
   congeladas.

## Primer OSS scan — G2-B diffing estructural

```text
FAILURE:
  dos snapshots oficiales grandes/heterogéneos
  → detectar cambios de records/campos determinísticamente
  → conservar provenance
  → ignorar reordenación/formato no semántico
  → funcionar offline
```

Formatos reales a cubrir: EBA JSON EAV anidado, BdE xlsx/CSV, CNMV
HTML de detalle, ESMA CSV. Candidatos a evaluar: librerías de diff
estructural JSON, diff tabular, y la alternativa de normalizar a
records (claims) y difear a nivel de registro keyed por identidad.

## Fuera de alcance en G2

- `PAYMENT_SERVICES` umbrella negativo → G2.x/G3 cuando haya
  necesidad real.
- `LIMITED_LP` → sólo con evidencia primaria nueva.
- Nuevos reguladores → probablemente G3; primero demostrar que el
  modelo escala longitudinalmente con las fuentes actuales.
- Identity resolution probabilístico → tooling auxiliar cuando la
  ingestión histórica produzca ambigüedades reales.
- W3C PROV export → interoperabilidad, no objetivo central.
- Frontend, API pública, MCP, RAG, agentes, LLM.

## Criterios de cierre de G2

```text
- contrato temporal de snapshot (G2-A) congelado y verificado
- diff estructural determinista sobre snapshots reales (G2-B)
- eventos regulatorios con provenance completa (G2-C)
- corpus longitudinal real con expectations preregistradas (G2-D)
- assessments históricos reproducidos por fecha (G2-E)
- auditoría E6-equivalente verde (G2-F)
- mismo gate: replay determinista, 0 deps runtime, tests verdes
```
