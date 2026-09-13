# FinReg España — G0: alcance y orden de congelación

## Objetivo

Registro unificado y verificable de autorizaciones financieras en España. Pregunta que debe
responder el sistema:

> ¿Qué puede hacer legalmente esta entidad financiera en España, bajo qué régimen jurídico
> y qué fuente oficial lo demuestra?

## Principio de diseño

El riesgo principal **no** es extraer mal una página de CNMV o BdE. El riesgo principal es:

> publicar una conclusión jurídicamente incorrecta a partir de datos técnicamente correctos.

Consecuencia operativa: nada de ingesta productiva hasta que G0.1–G0.4 estén congelados con
documentación, contratos, fixtures y tests. El fracaso silencioso aceptable en G0 es
`INDETERMINATE`; el fracaso inaceptable es un negativo o un positivo sin soporte.

## Decisiones de congelación (revisiones incorporadas)

| ID | Decisión |
|----|----------|
| C1 | `identity_resolution` y `assessment` son campos separados; el gate de identidad produce `INDETERMINATE` con reason de identidad, jamás un negativo. |
| C2 | Conflicto de efectos legales admisibles (p. ej. revocación en BdE vs. listado CIR activo) ⇒ `INDETERMINATE`. |
| C3 | Negativos por enumeración solo desde fuentes cuya enumeración completa, autoritativa y adecuada esté **verificada**. BdE/CNMV quedan en `EXPLICIT_NEGATIVE_ONLY` **no** porque sean "solo-consulta", sino porque aún no se ha verificado un volcado apto para negativos: `RATIONALE: no complete, authoritative enumeration suitable for negative inference has yet been verified.` Promoción a `COMPLETE_ENUMERATION` abierta si H8 encuentra un export válido. |
| C4 | Fecha de referencia del sistema (2026-09) es **posterior** al fin de los regímenes transitorios MiCA (H1: verificar 2026-06-30/07-01). Distinción de niveles: una aserción con `effective_to` vencido concluye **a nivel de aserción** `NOT_ENTITLED` + `ENTITLEMENT_EXPIRED`; la **agregación** no puede concluir `CONFIRMED_NOT_AUTHORISED` por esa vía (podría existir otra habilitación vigente) y da `NO_ENTITLEMENT_EVIDENCED` o `INDETERMINATE` salvo demostración completa por la matriz de cobertura. |
| W1 | Asertiones de agentes (`PSP_AGENT`) exigen `principal_entity_id`; sin él, inadmisibles (`INDETERMINATE`). |
| W2 | Exclusión de entidades de crédito del registro EBA PSD2 codificada como regla `OUT` con máxima prioridad. |
| W3 | La cobertura segmenta por `territorial_basis`; los listados inbound FPS se tratan como no-enumerativos hasta verificar H6. |
| W6 | `EXACT` exige ≥ 1 identificador verificado; match solo por denominación ⇒ `AMBIGUOUS` (incluso con candidato único), con adopción de identificadores únicamente desde fuente portadora verificada. |

## Hipótesis pendientes de fuente primaria (bloqueantes de G0.5, no de G0.1–G0.4)

Prioridad P0/P1 para resolver **al comienzo de G0.5 contra fuentes primarias**, no construyendo
más infraestructura.

| Pr. | ID | Hipótesis | Fuente primaria a consultar |
|-----|----|-----------|------------------------------|
| P0 | H1 | Alcance real de arts. 60/63 MiCA, etiquetas del listado CNMV, fecha fin del transitorio. El enunciado del corpus ("entidad financiera art. 60 / CASP art. 63") debe contrastarse con el texto consolidado antes de etiquetar. | Reg. (UE) 2023/1114 consolidado; listado CNMV |
| P0 | H3 | Campos reales del EBA CIR (LEI, permiso de depósito), cadencia, descarga. | webgate EBA CIR; CRD IV art. 10 |
| P0 | H4 | Registro EBA PSD2: AISP registrados, campo LEI, descarga masiva, cadencia. | webgate EBA PSD2; Reg. (UE) 2019/518 |
| P0 | H6 | Si BdE/CNMV enumeran inbound FPS y si el registro home es completo. | Registros BdE/CNMV/NCA home |
| P0 | H8 | Disponibilidad de `source_as_of` y de datos publicados/exportación máquina-legible (incl. CSV de clasificaciones ya publicados por BdE). | BdE; CNMV |
| P1 | H2 | El listado MiCA de CNMV carece de NIF/LEI/número estable. Debe quedar respaldado por **snapshot concreto**, no por recuerdo de inspección. | Listado CNMV |
| P1 | H5 | Vocabulario de estados BdE/CNMV: qué estados son evidencia negativa válida ("cancelada" ≠ extinción de derechos residuales). | Páginas de estados de BdE/CNMV |
| P1 | H7 | Artículos exactos de base legal (Ley 10/2014, LVV, MiCA arts. 107/109) y campos del registro ESMA. | EUR-Lex; ESMA register docs |

## Fuera de alcance en G0

Frontend, web, LLM/IA, MCP, API pública, histórico como producto, DGSFP, reguladores
adicionales, fuzzy matching automático, arquitectura prematura. Ver `g0-scope` original del
encargo.

## Canonicalización y hashing

Perfil **`FINREG_CANONICAL_JSON_V1`** (ver `finreg_es/canonical.py`). **No implementa RFC 8785
/ JCS y no afirma compatibilidad con RFC 8785**: implementar solo claves ordenadas y JSON
compacto no basta para JCS (I-JSON, serialización numérica IEEE-754/ECMAScript, tratamiento
Unicode), y presentarlo como JCS sería una garantía criptográfica falsa.

```text
FINREG_CANONICAL_JSON_V1
allowed:   object, array, string, integer, boolean, null
forbidden: float, NaN, Infinity, duplicate keys
dates:     strings ISO-8601
serialize: UTF-8, orden determinista de claves, sin whitespace
           insignificante, preservación exacta de Unicode (sin normalizar)
```

Si en el futuro se necesita interoperabilidad JCS real, se implementará y testeará RFC 8785
completo por separado, sin reutilizar este módulo bajo el nombre JCS.

## Estado del gate G0.1–G0.4

```text
FinReg España — G0.1–G0.4 FREEZE

G0.1 SOURCE CONTRACTS
  SCHEMA: FROZEN
  PRIMARY-SOURCE VERIFICATION: PARTIAL
  OPEN: H1–H8

G0.2 IDENTITY
  MODEL: FROZEN

G0.3 COVERAGE
  MODEL: FROZEN

G0.4 REGULATORY SEMANTICS
  MODEL: FROZEN

TESTS
  55 PASS

G0.5 REAL-WORLD CORPUS
  READY TO START
```

## Estado actual de G0.5

El freeze anterior conserva el estado histórico de 55 tests. G0.5 ya está en curso:
se ha comprometido la baseline `g0.5-p0-2026-09-13`, con 18 snapshots y hashes
verificados, y el manifest contiene 30 entidades jurídicas distintas. H4 queda
verificada para capacidad de snapshot; H1, H3, H6 y H8 permanecen parciales por
mapping o completitud jurídica. H2, H5 y H7 siguen abiertas.

El detalle de la evidencia está en
[`docs/g0.5-source-verification.md`](g0.5-source-verification.md) y la auditoría del
corpus en [`docs/g0.5-corpus-audit.md`](g0.5-corpus-audit.md). El corte actual suma
58 tests: 55 del freeze y 3 de integridad de G0.5.

El contrato de ingeniería está congelado; algunos hechos regulatorios aún no. Los tests no
demuestran que FinReg funcione con el mundo real: demuestran que existe una semántica
explícita para que el mundo real **no pueda ser forzado silenciosamente** dentro de
conclusiones falsas. El objetivo de G0.5 es intentar que las 30 entidades rompan estos
contratos.

## Plan de G0.5 (orden obligatorio)

1. Resolver **P0** con evidencia primaria: H1, H3, H4, H6, H8.
2. Guardar cada evidencia primaria como snapshot/hash **antes** de usarla para cambiar contratos.
3. Resolver después **P1**: H2, H5, H7.
4. Congelar el manifest de las 30 entidades y su motivo de inclusión.
5. Establecer manualmente el ground truth esperado **antes** de ejecutar los extractores.
6. Ejecutar el corpus intentando deliberadamente encontrar casos que rompan G0.1–G0.4.
7. Clasificar cada ruptura como `SOURCE_CONTRACT_GAP`, `IDENTITY_GAP`, `COVERAGE_GAP`,
   `SEMANTICS_GAP` o `EXTRACTION_BUG`.

**Regla de G0.5**: no adaptar el expected result después de ver lo que devuelve el código sin
dejar constancia de que el ground truth estaba equivocado y de la fuente primaria que lo
demuestra. En caso contrario, el corpus acaba validando la implementación en vez del modelo
regulatorio.

## Definición de hecho congelado (G0.1–G0.4)

1. `fixtures/contracts/*.json` validados por `tests/contract/`.
2. Modelo de identidad con estados `EXACT | AMBIGUOUS | NOT_FOUND | CONFLICTING_IDENTIFIERS`
   y gate hacia assessment (`tests/identity/`).
3. `coverage(register, entity_class, activity, jurisdiction, territorial_basis, effective_date)`
   con salida `IN_SCOPE | OUT_OF_SCOPE | UNKNOWN` y negativos acotados (`tests/coverage/`).
4. Semántica de aserciones (`legal_effect` / `entry_mechanism` / `territorial_basis`
   separados), temporalidad separada (`retrieved_at` / `source_as_of` / `effective_from,to` /
   `observed_current` / `freshness_at` / `response_freshness`) y motor de assessment con los
   cuatro veredictos y reasons trazables (`tests/semantics/`).

Cualquier cambio posterior en estos contratos pasa por nueva versión de contrato/regla y
actualización de fixtures, no por edición silenciosa.
