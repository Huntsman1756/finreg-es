# FinReg España — G1: preregistro de ampliación regulatoria

> **Estado: CLOSED / PASS** (`g1-regulatory-semantics-closed`).
> Veredictos finales en `G1-FINAL-REPORT.md`. G1 no se reabre salvo
> defecto reproducible nuevo.

G1 amplía la **capacidad regulatoria real** sobre la infraestructura ya
cerrada en G0 (`g0-portfolio-closed`). No añade infraestructura nueva.

## Objetivo

Convertir `INDETERMINATE` en resultado jurídicamente demostrable donde
las fuentes oficiales lo permitan, sin aumentar falsos positivos:

```text
INDETERMINATE  →  resultado demostrable   (meta de G1)
positivo/negativo sin soporte             (sigue prohibido)
```

## Principio de diseño (heredado de G0)

El riesgo principal sigue siendo publicar una conclusión jurídicamente
incorrecta a partir de datos técnicamente correctos. `INDETERMINATE`
es aceptable; un positivo o negativo sin soporte, no. Los artefactos
congelados G0 no se modifican: G1 trabaja sobre corpus/ruleset/casos
nuevos versionados como G1.

## Infraestructura congelada (no reabrir)

`canonical.py` (KEEP), schemas JSON v1 (ADOPTED), export OpenLineage
(PILOT PASS / LOCAL_ONLY). Cambios aquí requieren justificación
explícita y revisión separada — no forman parte del trabajo de G1.

## Workstreams preregistrados

| ID | Área | Pregunta a resolver |
|----|------|---------------------|
| G1-A | EBA PSD2 — temporalidad | Semántica real de `ENT_AUT`: ¿es fecha de autorización, de registro, de efecto? ¿Basta, con el resto de la cadena, para que PI/EMI reales salgan de `INDETERMINATE`? |
| G1-B | BdE — enumeración | ¿Existe un volcado oficial completo y autoritativo apto para `negative_evidence_capability`? Si existe → promoción con evidencia. Si no → congelar el límite declarado (C3 de G0) con rationale. |
| G1-C | MiCA art. 60 vs art. 63 | Casos reales de notification/statutory entitlement frente a authorisation CASP — la distinción que G0 no podía representar. |
| G1-D | Cross-border / FPS | Cobertura territorial real: inbound FPS, y el caso no ejercitado en G0 de **múltiples rutas de entitlement** para la misma `(entity, activity, jurisdiction)`. |
| G1-E | Expiración / conflicto / negativos | Sólo después de A–D, y con casos reales si existen: `effective_to` vencido, conflicto entre fuentes, negativo demostrable desde enumeración verificada. |

## Hipótesis pendientes de fuente primaria (continúa la numeración H*)

| Pr. | ID | Hipótesis | Fuente primaria |
|-----|----|-----------|------------------|
| P0 | H9-A | **Data semantics**: el JSON EBA representa mecánicamente `authorisation_from`, `authorisation_withdrawn_at` y estado current/expired sin inferencia heurística. No se asume que `ENT_AUT` coincida 1:1 con la terminología de Reg. (UE) 2019/410 — ese fue el riesgo de G0. **→ PROVEN** (`g1-a-eba-psd2-semantics.md` A4, acotado por EntityType) | JSON EBA congelado + Reg. 2019/410, 2019/411, RTS/ITS, Q&A 2019_4650 |
| P0 | H9-B | **Evidentiary sufficiency**: presencia EBA con servicio X + fecha autorización + sin retirada — ¿suficiente para `ENTITLED_TO_PROVIDE` o exige corroboración NCA? Decisión de jerarquía probatoria: el registro EBA central *no confiere derechos* (disclaimer EBA); la autorización es competencia NCA. **→ PROVEN WITH QUALIFICATION** (A5: T2 = capa de reporte NCA oficial, no constitutiva; suficiencia claim-specific) | Disclaimer EBA register; registros NCA |
| P0 | H10 | BdE publica export máquina-legible de su registro con cobertura declarada completa (o declara explícitamente lo contrario). **→ PROVEN BY SLICE / GLOBAL CLAIM DISPROVEN** (`g1-b-bde-enumeration.md`: `COMPLETE_ENUMERATION` sólo donde demostrado; sin completitud BdE global) | BdE registro de entidades; notas metodológicas |
| P0 | H11 | Art. 60 MiCA produce entitlement estatutario por notificación distinto de la autorización CASP de art. 63; las etiquetas del listado CNMV/ESMA distinguen ambas vías. **→ PROVEN** (`g1-c-mica-60-63.md`) | Reg. (UE) 2023/1114 arts. 60/63 consolidado; listados CNMV/ESMA |
| P1 | H12 | Existen entidades reales con doble ruta de entitlement (p. ej. autorización PI EBA + registro CNMV) para la misma `(entity, activity, ES)`. **→ PROVEN** (`g1-d-territorial-routes.md`: FPS + BRANCH coexisten, route-aware) | Cruce de snapshots congelados G0 + fuentes G1 |
| P1 | H13 | Alguna fuente G1 publica estados terminados (revocación/withdrawal) con fecha, suficiente para negativo demostrable en entidades fuera de enumeración completa. **→ PROVEN** (`g1-e-negative-semantics.md`) | Registros BdE/CNMV/EBA |

## G1-A — plan de resolución de H9 (preregistrado)

### Paquete de evidencia a congelar (A1)

```text
EBA register JSON snapshot          (ya congelado en G0: h4-eba-psd2)
EBA register landing/disclaimer
Regulation (EU) 2019/410            (exige fecha de autorización Y
                                     fecha de retirada para PI)
Regulation (EU) 2019/411
EBA final RTS/ITS report
EBA Q&A 2019_4650
```

### Invariante explícito

```text
not found in EBA PSD2  +  entity_class = credit institution
≠ negative evidence
```

Las entidades de crédito prestan servicios de pago pero van por el
Credit Institutions Register, no por el registro PSD2 central.

### Criterios de salida (A4/A5)

```text
CASE 1  authorisation date + withdrawal date explícita
        → intervalo de entitlement histórico derivable
CASE 2  authorisation date + semántica documentada que prueba
        ausencia de retirada = vigente
        → candidato a entitlement vigente
CASE 3  ausencia de campo de retirada es mero dato faltante
        → INDETERMINATE
CASE 4  semántica del campo indocumentada/ambigua
        → INDETERMINATE
CASE 5  evidencia EBA insuficiente por jerarquía de fuente
        → requiere corroboración NCA
```

### Orden

```text
A1  freeze primary evidence
A2  map 2019/410 concepts → raw JSON fields
A3  inspect withdrawn + active real cases
A4  decide H9-A
A5  decide H9-B / source hierarchy
A6  sólo entonces: draft derivation-rule delta
```

`derivation.py` no se toca antes de A5. G1-A puede cerrar en PASS sin
cambiar ningún assessment — el objetivo es reducir `INDETERMINATE`
sólo cuando la evidencia lo soporte.

## Reglas de G1

1. **Preregistro antes que reglas.** Cada workstream declara casos y
   expectations antes de tocar `derivation`/`assessment`. Las omisiones
   se auditan como en G0.7-C, no se corrigen en silencio.
2. **Casos reales primero.** Sintéticos sólo si el caso real no existe;
   se marcan explícitamente como sintéticos.
3. **Cero degradación.** Los 21 casos G0 congelados siguen produciendo
   los mismos verdicts; cualquier regla nueva se verifica contra ellos.
4. **Semántica en contratos.** Toda nueva lectura jurídica entra por
   `SourceContract`/`derivation ruleset`, nunca hardcodeada en adapters.
5. **Fail-closed.** Si H9–H13 no se verifican contra fuente primaria,
   el resultado correcto es `INDETERMINATE` con rationale, no la
   promoción.

## Criterios de cierre de G1 — TODOS SATISFECHOS

```text
- H9–H13 resueltas contra fuente primaria con snapshot congelado   PASS
- casos G1 preregistrados ejecutados; divergencias auditadas       PASS
  (22/22 G1-E; 0 divergencias)
- 21/21 casos G0 sin regresión                                     PASS
- negative_evidence_capability por fuente: promovida CON evidencia PASS
  o congelada CON rationale
- 0 falsos positivos demostrados en la auditoría de cierre         PASS
- mismo gate que G0: replay determinista, 0 deps runtime,          PASS
  tests verdes (431)
- E6 quality probe: Hypothesis 0 violaciones; mutmut 1059/1086     PASS
  (~97.5%), 27 supervivientes equivalentes documentados
```

## Fuera de alcance en G1

Frontend, API pública, MCP, RAG, agentes, LLM, histórico como
producto, reguladores fuera del cuadro EBA/BdE/ESMA/CNMV, fuzzy
matching automático.
