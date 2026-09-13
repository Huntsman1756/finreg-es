# FinReg España — G1: preregistro de ampliación regulatoria

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
| P0 | H9 | `ENT_AUT` en EBA PSD2 es fecha de autorización efectiva (no de publicación ni de modificación); su combinación con `EntityType` + servicios sostiene entitlement PI/EMI. | EBA PSD2 methodology/glosario; texto PSD2 arts. |
| P0 | H10 | BdE publica export máquina-legible de su registro con cobertura declarada completa (o declara explícitamente lo contrario). | BdE registro de entidades; notas metodológicas |
| P0 | H11 | Art. 60 MiCA produce entitlement estatutario por notificación distinto de la autorización CASP de art. 63; las etiquetas del listado CNMV/ESMA distinguen ambas vías. | Reg. (UE) 2023/1114 arts. 60/63 consolidado; listados CNMV/ESMA |
| P1 | H12 | Existen entidades reales con doble ruta de entitlement (p. ej. autorización PI EBA + registro CNMV) para la misma `(entity, activity, ES)`. | Cruce de snapshots congelados G0 + fuentes G1 |
| P1 | H13 | Alguna fuente G1 publica estados terminados (revocación/withdrawal) con fecha, suficiente para negativo demostrable en entidades fuera de enumeración completa. | Registros BdE/CNMV/EBA |

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

## Criterios de cierre de G1

```text
- H9–H13 resueltas contra fuente primaria con snapshot congelado
- casos G1 preregistrados ejecutados; divergencias auditadas
- 21/21 casos G0 sin regresión
- negative_evidence_capability por fuente: promovida CON evidencia
  o congelada CON rationale
- 0 falsos positivos demostrados en la auditoría de cierre
- mismo gate que G0: replay determinista, 0 deps runtime, tests verdes
```

## Fuera de alcance en G1

Frontend, API pública, MCP, RAG, agentes, LLM, histórico como
producto, reguladores fuera del cuadro EBA/BdE/ESMA/CNMV, fuzzy
matching automático.
