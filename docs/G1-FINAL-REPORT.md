# G1 — informe final

Cierre de la fase G1 de FinReg-ES (`g1-regulatory-semantics-closed`).
G1 amplió la **capacidad regulatoria real** sobre la infraestructura
congelada en G0: resolvió H9–H13 contra fuentes primarias congeladas y
convirtió `INDETERMINATE` en resultado jurídicamente demostrable donde
las fuentes oficiales lo permiten — sin aumentar falsos positivos.

## Veredicto

```text
G1 — PASS / CLOSED

G1-A  CLOSED   H9-A  PROVEN — ENT_AUT acotado por EntityType
               H9-B  PROVEN WITH QUALIFICATION — EBA = capa de
                     reporte NCA oficial (T2), no constitutiva
G1-B  CLOSED   H10   PROVEN BY SLICE / GLOBAL CLAIM DISPROVEN —
                     COMPLETE_ENUMERATION sólo donde demostrado;
                     sin ficción de completitud BdE global
G1-C  CLOSED   H11   PROVEN — MiCA art.60 NOTIFICATION y art.63
                     AUTHORISATION son mecanismos jurídicos distintos
G1-D  CLOSED   H12   PROVEN — entitlement multi-ruta real:
                     FPS + BRANCH coexisten, route-aware
G1-E  CLOSED   H13   PROVEN — retirada/baja fechada soporta
                     negativos demostrables bajo las reglas congeladas
```

G1 no se reabre salvo defecto reproducible nuevo.

## Números

```text
22   casos de assessment G1-E preregistrados — 22/22 match, 0 divergencias
21   casos G0 congelados — 21/21 sin regresión
10   anclas reales del corpus negativo (0 sintéticas)
166  assertions + 19 reported_facts derivados (artefacto g1-e-002)
431  tests PASS
1086 mutantes — 1059 killed (~97.5%), 27 supervivientes equivalentes
0    violaciones de invariantes Hypothesis (~1150 casos derandomizados)
0    dependencias runtime añadidas (stdlib puro)
0    bytes de fixtures G0 modificados
0    cambios de producción durante el probe E6
```

## Cadena autoritativa congelada

```text
G1-D   corpus-g1-d-002 · derivation-rules-g1-d-002
       (FINREG_G1_DERIVATION_V4) · derived-assertions-g1-d-002
       · assessment-run-g1-d-002
G1-E   corpus-g1-e-001 · negative-corpus-003 · claim-ledger-g1-e-001
       · derivation-rules-g1-e-002 (FINREG_G1_DERIVATION_V6)
       · derived-assertions-g1-e-002 · assessment-run-g1-e-001
       · ASSESSMENT_SEMANTICS_V3 (V1/V2 congeladas, intactas)
```

Sucesores históricos preservados: `-001` (materialización E4
pre-bridge), corpus `-002`, runs y rulesets anteriores — nunca mutados.

## Qué demuestra G1

- **Negativos con soporte, no por ausencia.** Un `NOT_ENTITLED` exige
  `ENUMERATED_ABSENCE` dentro de un slice
  `CAPABILITY_VECTOR_COMPLETE_WHEN_RECORD_PRESENT` o una retirada
  fechada. La ausencia poblacional nunca infiere.
- **Raíz ≠ entidad.** `root_key` separa familias de autorización:
  la retirada PI de Mollie no cierra su raíz EMI; la baja BdE de
  Fintonic no cierra una raíz AISP distinta.
- **Ruta ≠ rutas.** V3 agrega por `(root_key, territorial_basis)`:
  Wise PIS cierra FPS y BRANCH → `CONFIRMED_NOT_ENTITLED`; Eupago
  cierra FPS pero mantiene BRANCH → `CONFIRMED_ENTITLED`. La query
  con `territorial_basis` explícito no se contamina por la agregación
  global.
- **Bitemporalidad real.** `status_intervals` [from,to) exclusivos:
  MMG es INDETERMINATE @2018, NOT_ENTITLED @2020, ENTITLED @2026 —
  la misma entidad, la misma evidencia, tres verdades por fecha.
- **Fail-closed bajo ambigüedad.** `admissibility=BLOCKED` informa sin
  cerrar (Fintonic PIS → INDETERMINATE, nunca NOT_ENTITLED);
  `TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED` queda como finding.
- **Conflicto explícito.** Positivo + negativo admisibles en la misma
  ruta → `ROUTE_CONFLICT`, nunca resolución silenciosa.

## Auditoría de calidad (E6)

Regla adoptada: **toda capacidad genérica nueva requiere un OSS scan
failure-driven previo**; la semántica regulatoria se implementa en
FinReg, la infraestructura genérica se reutiliza cuando existe una
solución madura.

| Herramienta | Decisión | Evidencia |
|-------------|----------|-----------|
| Hypothesis | ADOPT (dev-only) | 7 propiedades/invariantes V3, ejecución derandomizada, 0 violaciones — `tests/g1/test_g1e_v3_properties.py` |
| mutmut | ADOPT (dev-only, Linux/WSL) | scope `semantics/temporal/coverage`; 1059/1086 killed — `tests/g1/test_g1e_v3_mutation_kills.py` (77 tests binding) |

Los 27 supervivientes son equivalentes (verificados caso a caso):
defaults comparados sólo por desigualdad, acumuladores falsy,
metadatos de provenance no consumidos, strings de diagnóstico
internos del path EXACT. No es una prueba formal; es una medida de
test strength muy superior a coverage.

Detalle completo: `g1-e-negative-semantics.md` §E6.

## Límites declarados (no impiden el PASS)

- El umbrella negativo `PAYMENT_SERVICES` no está definido: el
  universo de constituyentes aplicables por clase sigue pendiente.
  Positivo umbrella por OR es seguro; negativo umbrella no.
- `LIMITED_LP` continúa fail-closed (`TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP`).
- No se inventa historia territorial desde snapshots current:
  `effective_from=EVIDENCE_AS_OF`, cero retroproyección.
- Algunos negativos existen sólo por slice declarado — la
  completitud del vector es propiedad scoped del contrato, nunca
  poblacional.
- `source_date_reliability` es metadato de provenance; no alimenta
  `is_stale` (los mutantes equivalentes lo confirman).

## Artefactos de cierre

| Artefacto | Rol |
|-----------|-----|
| `fixtures/g1/` | corpus, rulesets, ledgers, assertions, cases, runs — congelados |
| `fixtures/contracts/` | contratos de fuente (EBA 1.2.0, BdE-servicios 1.1.0, BdE-establecimiento 1.0.0, …) |
| `schemas/v1.3/` | campos E4.1 (negative_scope, root_key, interval_end, territorial_basis en query) |
| `docs/g1-*.md` | verificación por workstream + E6 |
| `tests/g1/` | binding + propiedades + mutation kills |

## Política congelada para G2

```text
1. preregistro de casos y expectations antes de tocar derivación/assessment
2. OSS scan failure-driven antes de cualquier capacidad genérica nueva:
   fallo concreto → 5–10 candidatos → licencia/mantenimiento/tests/
   compatibilidad offline-determinista → medir contra el caso real →
   ADOPT | WRAP | PORT_PATTERN | REFERENCE | REJECT
3. semántica regulatoria: implementación propia en FinReg;
   infraestructura genérica: reutilización cuando exista madurez
```
