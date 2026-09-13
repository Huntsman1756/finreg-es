# FinReg-ES

Registro auditable y pipeline de assessment para autorizaciones
financieras en España. Responde una sola pregunta por entidad:

> ¿Está esta entidad autorizada para esta actividad, en este régimen,
> a esta fecha — y qué evidencia oficial lo soporta?

Cero dependencias runtime (stdlib Python). Determinista, offline,
fail-closed. Construido como estudio de caso de ingeniería de datos
regulatoria: cada afirmación que el sistema emite es trazable hasta un
snapshot congelado de una fuente oficial.

## Arquitectura

```text
SNAPSHOTS OFICIALES (bytes congelados, sha256)
        │
        ▼
extraction      adapters read-only por fuente
        │       → extraction records (no deciden nada)
        ▼
provenance      claim ledger: 337 claims, 1 por hecho atómico
        │       → cada claim apunta a snapshot + campo + fecha
        ▼
derivation      reglas declarativas sobre claims
        │       → derived assertions (cobertura, identidad, temporalidad)
        ▼
assessment      casos preregistrados vs assertions
        │       → verdict fail-closed + rationale
        ▼
openlineage     export opcional: lineage de artefactos (OSS std)
```

`canonical.py` fija la serialización determinista
(`FINREG_CANONICAL_JSON_V1`: sin floats, sin claves duplicadas,
rechaza NaN/Inf). Todo hash de contenido deriva de ahí.

## Fuentes oficiales

| Fuente | Formato | Cobertura |
|--------|---------|-----------|
| EBA PSD2 register | JSON EAV (zip, 218 MB payload) | entidades PSD2 salvo entidades de crédito y CASP |
| BdE registro de entidades | CSV (`utf-8-sig`, quirks) | clasificación estadística — **no** autorización |
| ESMA MiCA CASPs | CSV (columna fantasma, multivalor `\|`) | presencia ≠ evidencia negativa |
| CNMV registros ESI/FPS | HTML de detalle | domestic / branch / freedom-to-provide-services |

Los `SourceContract` (`fixtures/contracts/`) codifican por fuente:
autoridad, base jurídica, clases de entidad incluidas/excluidas,
capacidad de evidencia negativa, política de staleness, y notas de
interpretación legal. Son la autoridad semántica; los adapters sólo
extraen.

## Qué responde / qué no responde

**Responde:**

- `CONFIRMED_AUTHORISED` sólo cuando la cadena de evidencia completa
  existe (presencia + identidad + actividad + régimen + temporalidad).
- `REVIEW_REQUIRED` cuando hay presencia pero el join o la cobertura no
  cierran.
- `INDETERMINATE` cuando la fuente no puede sostener la inferencia.
- `UNSUPPORTED_NEGATIVE` se bloquea: la ausencia en una fuente que no
  enumera completamente **no** prueba no-autorización.

**No responde:**

- No inventa cobertura: si la fuente no enumera, el sistema no asume.
- No promociona clasificación estadística (BdE) a autorización.
- No hace joins de identidad sobre identificadores inválidos.
- No afirma nada sin claim trazable a snapshot congelado.

## Resultados de G0

| Métrica | Valor |
|---------|-------|
| Entidades jurídicas reales | 30 |
| Referencias de fuente oficiales | 34 |
| Claims con provenance completa | 337 |
| Assertions derivadas | 257 |
| Assessment cases preregistrados | 21/21 match |
| Inferencias negativas no soportadas | 0 |
| Tests | 178 PASS |
| Dependencias runtime añadidas por revisión OSS | 0 |

Replay determinista: mismos inputs → mismos bytes (verificado por test).

## Fail-closed, en ejemplos reales

- **LEI inválido** — GLEIF devuelve 404 para un LEI publicado →
  `identifier_validity=INVALID` y el join por LEI queda prohibido.
- **Presencia EBA insuficiente** — `ENT_AUT` presente pero la cadena no
  cierra → `UNINTERPRETABLE_EVIDENCE`, no autorización.
- **Clasificación ≠ enumeración** — BdE IFM es clasificación
  estadística → `INDETERMINATE`, nunca promovida a autorización.
- **Métrica defectuosa preservada** — el run runner de G0.5-A tenía un
  defecto conocido (G05-B-F01): se conserva en el artefacto y se
  remedia en runs supersedes, no se reescribe la historia.

## Build vs Reuse (post-G0, cerrado)

Decisión: *FinReg necesita primitivas simples y deterministas sobre un
dominio regulatorio específico; las capas genéricas sólo se adoptan
cuando aportan interoperabilidad verificable sin degradar provenance.*

| Candidato | Decisión | Por qué |
|-----------|----------|---------|
| `canonical.py` | KEEP | propiedad determinista que ninguna lib compra mejor |
| JSON Schema | ADOPTED (tooling) | contratos de artefacto v1, cero coste runtime |
| OpenLineage | PILOT PASS / LOCAL_ONLY | export de lineage stdlib-only validado contra spec 2.0.2 |
| Frictionless | REJECT (medido) | 2/4 fuentes no tabulares; segunda descripción sin consumidor |
| Great Expectations | REJECT | validación semántica ≠ expectations estadísticas |
| DataHub | REJECT | catálogo generalista, provenance insuficiente |

Informe completo: `docs/G0-FINAL-REPORT.md`.
ADRs y verificación por fase: `docs/`.

## Reproducir

```bash
python -m pytest          # 178 tests, offline
python -m finreg_es.openlineage_export   # regenera openlineage/ byte-idéntico
```

Sin servicios, sin red, sin credenciales. Todo input es un fichero del
repo; todo output es un artefacto hash-fijado.
