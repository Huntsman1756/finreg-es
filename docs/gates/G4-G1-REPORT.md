# G4-G1 — Informe: proyección pública determinista (read model v1)

Ejecutado sobre `tools/g4/build_projection.py` contra evidencia
congelada exclusivamente. Veredicto: **CONDITIONAL/GO** — todas las
propiedades de seguridad se verifican; un caso preregistrado (P01) era
incorrecto tal como se escribió y queda documentado como finding.

## Resultados por caso preregistrado

| Caso | Resultado | Evidencia |
|---|---|---|
| P01 | **FINDING — expectativa incorrecta** | ESI-1 `impersonations` **no** está vacío: existen 4 clones que citan explícitamente reg. **258** (`ALANTRAGLOBAL`, `ALT-CPM`, `OLYMPUS-CAPITALLIMITED` ×2 filas upstream). El anti-caso sí se verifica: `webtrader.alantrafx.com` (target 245) **no** está atribuido. La propiedad de seguridad preregistrada — *0 atribuciones adversas falsas* — se cumple; el valor literal esperado era erróneo. Caso corregido a registrar en el gate sucesor. |
| P02 | PASS | ESI-4: 4 impersonations por `registry_number=194` (`ABANTETHER.XYZ` ×2, `ABANTECAPITAL.COM` ×2) |
| P03 | PASS | SAN-1: sanción `OFFICIAL_DOCUMENT_DERIVATION` (17/07/2026, BOE 03/08/2026) + 3 estados `fs` como `OFFICIAL_AS_OF_STATE` |
| P04 | PASS | `fs` acota estados; todo `OBSERVED_CHANGE` lleva intervalo `[a,b]` (test dedicado) |
| P05 | PASS | Las 4 ESI declaran `history: NO HISTORICAL EVIDENCE`; programa de actividades parseado con instruments a–k + clientes |
| P06 | PASS | BDE: alta + actividades + operación transfronteriza fechadas como `EXPLICIT_OFFICIAL_EVENT` |
| P07 | PASS | BDE-5: `14/01/2019` (BdE) y `2019-05-27` (EBA) coexisten como registros distintos con `conflict_with` |
| P08 | PASS | `HTTP://PECUNIACO.COM` → `candidates` (name-similarity-only); nunca warning |
| P09 | PASS | INS-1..4 `EXACT` con identificadores completos; `legal_name` desde `PUBLISHES_NAME`/`REGISTERED_AS` |
| P10 | PASS | INS-5 `DEREGISTERED`, `as_of` acotado; `fecha_cancelacion: null` upstream → `OBSERVED_CHANGE [UNKNOWN, 2026-09-13]`, sin fecha inventada |
| P11 | PASS | `coverage` con 9 denominadores en las 20 fichas |
| P12 | PASS | 0 campos rating/score/rank/recommendation en todos los artefactos |
| P13 | PASS | Dos builds consecutivos → mismos bytes; `bundle_sha256` estable |

## Métricas

- 20/20 fichas emitidas y validadas contra `schemas/public/entity-v1.schema.json`.
- 164 entradas en `changes.json` clasificadas (`OFFICIAL_EVENT |
  RECONSTRUCTED_HISTORICAL | OBSERVED_CURRENT | BACKFILL`).
- 17 tests de gate en `tests/g4/test_public_projection.py` — todos PASS.
- Builder offline: slices upstream congelados en
  `fixtures/g4/upstream/` (manifest con sha256 de los artefactos fuente).

## Gaps explícitos (declarados, no disimulados)

- ESI: `history: NO HISTORICAL EVIDENCE` en las 4 fichas (`fs` rechazado
  por la fuente — comportamiento preregistrado).
- SGIIC/SAN-1: `permission: NO_EVIDENCE` — la ficha SGIIC no publica
  programa de actividades de servicios de inversión (vista_17 vacía);
  su permiso es la gestión de IIC, no la matriz MiFID. Cobertura honesta.
- ESI-1: `branch: NO_EVIDENCE` para sucursales España (vista_9 vacía);
  sucursales EEE/libre prestación (vistas 10–13) no estaban en el
  corpus congelado G0 — candidato a congelar en la siguiente refresh.
- INS: `permissions: UNKNOWN` — OpenDGSFP no publica ramos autorizados
  en el artefacto v0.1.
- AlertaFin: notices duplicados upstream (misma advertencia, distinta
  `notice_id`/fila) se conservan como evidencias distintas; la UI
  deberá agrupar por (warned_name, target).

## Veredicto

**CONDITIONAL/GO.** La proyección es correcta, determinista y segura.
El gap material no es del builder sino de cobertura de fuente:
historia ESI y permisos SGIIC/INS no son representables con la
evidencia congelada — se declaran, no se rellenan. El gate formal se
cierra CONDITIONAL hasta que un gate sucesor registre el caso P01
corregido (ESI-1 con 4 impersonations legítimas reg-258 + anti-caso
reg-245 excluido).

## Artefactos

```text
tools/g4/build_projection.py
fixtures/g4/upstream/{manifest,alertafin-notices-slice,opendgsfp-slice}.jsonl/json
projections/public/{manifest,entities,search,changes,sources}.json
projections/public/entities/*.json (20)
schemas/public/entity-v1.schema.json
tests/g4/test_public_projection.py (17 tests)
```
