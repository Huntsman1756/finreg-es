# PRODUCT-CONTRACT — Regulatory Record ES

v0.1 (post-G0, contrato CONDITIONAL). Fuente de verdad para lo que el
producto afirma y lo que no.

## Pregunta que responde

> Qué entidad es, bajo qué reguladores figura, qué está autorizada a
> hacer, dónde puede operar, cómo ha cambiado y qué hechos regulatorios
> oficiales constan sobre ella.

## Lo que NO hace

- No produce ratings, risk scores, rankings, recomendaciones ni
  inferencias reputacionales. "Safe/trusted/good standing" sólo si el
  regulador usa ese término y se cita.
- No convierte suplantación en advertencia contra la entidad legítima.
- No infiere ausencia por no-presencia en fuentes no exhaustivas.
- No infiere fechas jurídicas desde `retrieved_at`.
- No reconstruye el pasado con evidencia posterior a `known_at`.
- Sin fuzzy matching para identidad canónica; sin LLM/embeddings/RAG
  en runtime.

## Semántica de hechos (enum congelado v1)

```text
EXPLICIT_OFFICIAL_EVENT          la fuente afirma que X ocurrió en fecha Y
OFFICIAL_AS_OF_STATE             la fuente declara estado Y a fecha X
                                 (incluye fs CNMV donde se honra)
OFFICIAL_DOCUMENT_DERIVATION     hecho derivado de documento oficial fechado
OBSERVED_CHANGE                  cambio entre observaciones propias;
                                 intervalo [a,b], nunca fecha inventada
```

Relaciones de advertencia (no contadores):

```text
DIRECT_WARNING_AGAINST | IMPERSONATES | CLONE_OF |
MENTIONED_AS_LEGITIMATE_ENTITY | NOT_RELATED_TO | CANDIDATE
```

## Campos temporales por record

`valid_from/valid_to · effective_at · source_published_at ·
observed_at · known_at · as_of_date` — se informan sólo los que la
fuente sustenta; no se rellenan fechas inexistentes.

## Cobertura (denominadores separados)

`identity, registration, permission, history, sanction, warning,
branch, agent, passport, provenance` — nunca un único porcentaje.

## Contrato CONDITIONAL (post-G0)

Estado regulatorio oficial + historial oficial *disponible* (fs en
IIC, campos fechados, documentos BOE/registro de sanciones) + cambios
detectados por observaciones propias. Donde la fuente no ofrece
histórico, la ficha muestra `NO HISTORICAL EVIDENCE` — explícito,
no implícito.

## MVP

SEARCH · ENTITY RECORD · PERMISSIONS · REGULATORY STATUS · TIMELINE ·
SANCTIONS/WARNINGS · EVIDENCE · AS-OF. Pospuesto: alertas, watchlists,
comparador, gráficos, financials BankCall, API server, NLP.
