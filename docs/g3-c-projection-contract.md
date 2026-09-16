# G3-C — Contrato de proyección SQLite + pilot Datasette (preregistro)

**Estado:** FROZEN antes de producción (task `g3-c-preregister`;
la ejecución es `g3-c-datasette-pilot`). Deriva de
`docs/g3-scope.md` (frontera arquitectónica),
`docs/g3-a-oss-scan-surfaces.md` (Datasette **ADOPT-PILOT**; la
proyección se construye propia con `sqlite3` stdlib — es semántica
de representación, no infraestructura genérica) y
`docs/g3-b-adapter-contract.md` (SQLite/Datasette expresamente
fuera de G3-B).

## 1. Tesis (falsable)

```text
Una proyección SQLite derivada y lossless permite explorar
evidencia, provenance y cambios longitudinales con Datasette en
modo inmutable, sin ejecutar ni duplicar semántica regulatoria.
```

Datasette **no** hace `assess()` ni `assess_bitemporal()`: eso ya lo
cubren CLI/MCP (G3-B). Datasette resuelve los casos 3–5 del scan —
evidencia, explicación/drill-down y cambios longitudinales.

## 2. Frontera de superficies

```text
CLI/MCP   = query/assessment surfaces        (G3-B, congeladas)
Datasette = evidence/provenance/exploration surface

Datasette NO se convierte en otro motor FinReg.
```

## 3. Proyección lossless + indexable

Cada objeto proyectado conserva su representación canónica completa
— `payload_json` = `canonical_json` del objeto fuente
(`FINREG_CANONICAL_JSON_V1`) — además de columnas indexables para
filtrar. Propiedad vinculante:

```text
fila SQLite → payload_json → canonical_json(...) == objeto original canónico
```

`artifacts.payload_json` contiene el **documento fuente completo**:
aunque una vista no cubra un campo, ningún byte se pierde al
proyectar. No se pierde provenance por "aplanar para SQL".

Tablas (columnas indexables; todo lo demás vive en `payload_json`):

```text
artifacts                     una fila por artefacto fuente
  artifact_id · path · sha256 · kind · payload_json(documento)

assertions                    166 en el evidence set por defecto
  assertion_id · entity_id · activity · jurisdiction · legal_effect
  entry_mechanism · territorial_basis · effective_from · effective_to
  evidence_set_id · source_artifact_id · payload_json

reported_facts                19 en el evidence set por defecto
  fact_id · corpus_id · rule_id · reported_status
  source_artifact_id · payload_json

source_assertions             aplanadas de assertions+reported_facts
  owner_type ∈ {assertion, reported_fact} · owner_id · ordinal
  authority · register_id · source_url · retrieved_at · source_as_of
  raw_snapshot_sha256 · payload_json

comparisons                   artefactos fixtures/g2/comparisons
  comparison_id · left_observation_id · right_observation_id
  succession_state · added_count · removed_count · changed_count
  payload_json

structural_changes            changes.{added,changed,removed} del par
  comparison_id · ordinal · kind ∈ {added,removed,changed}
  record_key · payload_json

change_candidates             candidates de fixtures/g2/events
  comparison_id · ordinal · candidate_type · record_key
  admissibility · blocker · effective_basis · payload_json
```

Verificado contra los artefactos reales (2026-09-16):

- `reported_facts` usa `corpus_id` (no `entity_id`).
- `field_path` **no** existe a nivel de cambio estructural: el
  artefacto de comparación sólo lista `record_key`s por `kind`;
  `field_path` vive en `change_candidates` (artefactos events) y
  queda dentro de su `payload_json`.
- `evidence_set_id` = `<stem>@sha256:<sha256 de los bytes>` — el
  mismo que produce `finreg_es.bitemporal.load_evidence_set`; el
  builder **reutiliza** esa función, no la reimplementa.
- `source_artifact_id` referencia `artifacts.artifact_id` del
  fichero del que se proyectó la fila. Si el artefacto no declara id
  propio, `artifact_id` = `<stem>@sha256:<digest>` (misma forma que
  `evidence_set_id`).
- `comparison_id` = campo `artifact` del artefacto de comparación
  (p.ej. `g2-b-comparison-eba-psd2-20260914-20260915`); los
  candidates lo ligan vía `source_comparison.file`/`sha256` del
  artefacto events.

## 4. Lineage: manifest de la proyección

`manifest.json` junto al `.sqlite`:

```json
{
  "projection_version": "FINREG_G3_SQLITE_PROJECTION_V1",
  "inputs": [{"path": "...", "sha256": "..."}],
  "tables": [
    {"name": "assertions", "rows": 166, "logical_sha256": "..."}
  ],
  "sqlite_version": "...",
  "logical_projection_sha256": "..."
}
```

**Corrección contractual:** el determinismo NO es "el fichero
`.sqlite` tiene el mismo SHA en cualquier máquina". SQLite puede
producir bases lógicamente idénticas con bytes distintos (versión de
SQLite, page layout, pragmas, VACUUM). El gate es:

```text
mismos inputs + mismo projection_version
→ mismo schema → mismos row counts → mismas filas ordenadas
→ mismos canonical row hashes → mismo logical_projection_sha256
```

Bytes idénticos en rebuild dentro del mismo entorno = observación
bienvenida, nunca requisito semántico. Esto evita una futura falsa
divergencia cross-platform.

## 5. Datasette = visor, no autoridad

- Línea estable fijada: `datasette==0.65.4` (extra `datasette` en
  `pyproject.toml`; la alpha 1.0 queda fuera del pilot).
- Sirve la proyección con `-i/--immutable`; sus consultas SQL son
  de lectura.
- Read-only **auditable**:

  ```text
  sha256(.sqlite) antes de servir → smoke HTTP/JSON/SQL
      → sha256(.sqlite) después → idéntico
  sha256(fixtures/ · docs/ · finreg_es/) antes/después → idéntico
  ```

- Si Datasette mantiene estado interno propio, ese estado no es
  FinReg ni parte de la cadena autoritativa. Lo que no puede cambiar
  es la proyección ni ningún artefacto fuente.
- **Cero UI custom**: sin templates, plugins ni endpoints propios
  de Datasette. Si la UI/JSON API estándar no cubre un caso, el
  pilot queda QUALIFIED/FAIL — no se recrea Streamlit dentro de
  Datasette.
- La autoridad sigue en los JSON congelados + sus sha256; el
  `.sqlite` es un derivado reconstruible (lo prueba el manifest).

## 6. Casos de aceptación (binding)

```text
C1 evidence_set
   evidence_set_id → localizar assertions/facts correspondientes
C2 assertion provenance
   assertion_id → source_assertions → snapshot sha/url/retrieved_at
C3 explanation drill-down (cross-surface)
   used_assertion_id de una respuesta CLI/MCP real
   → exactamente esa assertion en Datasette → provenance completa
C4 longitudinal change
   record_key del par eba-psd2-20260914-vs-20260915
   → structural_changes → change_candidates
C5 BLOCKED
   uno de los 312 NO_PREREGISTERED_RULE del par 0914→0915
   → cambio original + candidato BLOCKED + blocker visibles
```

C3 demuestra que G3-B y G3-C forman una única superficie coherente,
no dos productos paralelos.

## 7. Tests estructurales (binding)

```text
✓ builder usa sólo sqlite3 stdlib (sin dependencias OSS)
✓ finreg_es/ sigue sin importar datasette (frontera G3-B extendida)
✓ la proyección nunca llama assess()/assess_bitemporal()/derivation
✓ payload_json round-trip lossless en todas las tablas
✓ todas las referencias de provenance resuelven (FK lógicas)
✓ logical digest reproducible en build ×2
✓ Datasette arranca sobre -i y expone las tablas esperadas
✓ JSON API devuelve las filas esperadas
✓ SELECT funciona; escritura contra la proyección falla
✓ sha256(.sqlite) no cambia durante el smoke
✓ parity G3-B sigue verde · tools/audit_g2f_replay.py PASS
```

## 8. Resultados válidos (declarados antes de ver datos)

```text
PILOT_PASS       C1-C5 resueltos + todos los tests estructurales
PILOT_QUALIFIED  casos resueltos con limitación declarada (p.ej. un
                 caso exige una feature fuera de la UI estándar)
PILOT_FAIL       la UI/JSON estándar no resuelve un caso sin
                 código custom
```

Los tres son resultados válidos y registrables. Prohibido mover
criterios tras observar resultados: contrato incorrecto → finding +
sucesor documental.

## 9. Artefactos objetivo

```text
adapters/sqlite_projection.py        builder stdlib (sqlite3)
fixtures/g3/projection/finreg-g3.sqlite     proyección (derivada)
fixtures/g3/projection/manifest.json        lineage + logical digest
tests/g3/test_g3c_projection.py      lossless, digest, frontera
tests/g3/test_g3c_datasette_smoke.py smoke -i + auditoría read-only
pyproject.toml                       extra datasette==0.65.4
CI job test                          instala el extra datasette
                                     (dep ausente = fallo, no skip)
```

## 10. Fuera de alcance de G3-C

- `assess`/`assess_bitemporal` vía Datasette (cubierto por G3-B).
- Escritura/mutación, auth, multiusuario, despliegue remoto.
- Plugins/templates/endpoints custom de Datasette.
- Promover el `.sqlite` a artefacto autoritativo.
- Mutar `finreg_es/` o reinterpretar `payload_json`.
