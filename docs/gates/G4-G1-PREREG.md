# G4-G1 — Preregistro: proyección pública determinista (read model v1)

Preregistrado tras el veredicto G4-G0 CONDITIONAL/GO (`1545ab3`) y los
ADRs/contrato de producto (`6868fe6`), antes de validar ninguna salida
del builder de proyección. Documento congelado: los criterios no se
ajustan tras ver resultados; un contrato incorrecto genera finding +
sucesor, no una re-negociación.

## Afirmación falsable

> A partir exclusivamente de la evidencia congelada G4-G0 (fixtures +
> artefactos upstream AlertaFin/OpenDGSFP/BdE/EBA), un builder
> determinista emite el read model `entity/v1` del corpus completo
> (20 entidades) con identidad exact-first, provenance navegable por
> fact material, hechos clasificados en el enum preregistrado y cero
> atribuciones adversas falsas — verificable byte a byte.

## Inputs congelados (ningún fetch en el builder)

- `fixtures/g4/corpus/entities.json` (20 entidades)
- `fixtures/g4/sources/manifest.json` + `raw/*` (84 snapshots SHA-256)
- `fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip` (EBA PSD2)
- AlertaFin `g0/normalized/notices.jsonl` (10 368 notices)
- OpenDGSFP `data/derived/v0.1/opendgsfp-0.1.jsonl` (`opendgsfp/0.1`)

## Casos preregistrados (expected por slot)

| Caso | Slot | Esperado |
|---|---|---|
| P01 | ESI-1 ALANTRA CAPITAL MARKETS (reg. 258) | `impersonations` **vacío**: el clon `webtrader.alantrafx.com` apunta a reg. 245 (ALANTRA EQUITIES), nunca a 258 |
| P02 | ESI-4 ABANTE (reg. 194) | ≥1 impersonation con `relation: IMPERSONATES` + `MENTIONED_AS_LEGITIMATE_ENTITY`, unidas por `registry_number=194`, no por nombre |
| P03 | SAN-1 GESCONSULT | sanction `OFFICIAL_DOCUMENT_DERIVATION` (registro 17/07/2026, BOE 03/08/2026) + estados `fs` como `OFFICIAL_AS_OF_STATE` con `requested_fs` registrado |
| P04 | SGIIC-1..5 | `fs` states acotan cambios; cambio de dirección ⇒ `OBSERVED_CHANGE` con intervalo `[fs, observación]`, nunca fecha inventada |
| P05 | ESI-1..4 | `history: NO HISTORICAL EVIDENCE` explícito (ESI rechaza `fs`); servicios del programa con instruments/clients |
| P06 | BDE-1..5 | `fecha alta BdE` + actividades + operación transfronteriza con fechas como `EXPLICIT_OFFICIAL_EVENT` |
| P07 | BDE-5 | conflicto `BdE 14/01/2019` vs `EBA 2019-05-27` preservado como dos hechos con fuentes distintas — jamás sintetizado |
| P08 | BDE-3 PECUNIA | notice `HTTP://PECUNIACO.COM` (2020-11-16, sin target explícito) → `candidates` como mucho, nunca `direct_warnings` por similitud de nombre |
| P09 | INS-1..4 | identidad consumida de OpenDGSFP `EXACT`, identificadores completos (LEI donde exista) |
| P10 | INS-5 E0006 | `status: DEREGISTERED` con `as_of` acotado `[UNKNOWN, snapshot]`; sin fecha de baja inventada |
| P11 | todas | `coverage` por denominador (identity, registration, permission, history, sanction, warning, branch, passport, provenance) — nunca un porcentaje único |
| P12 | todas | ningún campo de rating/score/rank/recommendation en ningún artefacto |
| P13 | rebuild | dos builds consecutivos → mismos bytes en todos los artefactos; `bundle_sha256` estable |

## Gates

```text
PASS ⇔  P01–P13 se cumplen en la salida emitida
     ∧  0 hechos con fecha sintetizada (toda fecha traza a fuente)
     ∧  0 atribuciones warning/clone sin identificador exacto
     ∧  schemas JSON de projections/public/ publicados y validando
CONDITIONAL ⇔  un vertical concreto queda parcial (p.ej. INS sin
     cronología) con el gap explícito en coverage/sources
FAIL ⇔  necesidad de fuzzy merge para cualquier join
     ∨  determinismo roto  ∨  atribución adversa falsa
```

## Resultados válidos (declarados antes de ejecutar)

- `impersonations` vacío en 18/20 entidades → válido: los clones del
  corpus son 1 caso real (P02) + 1 anti-caso (P01).
- `history: NO HISTORICAL EVIDENCE` en todas las ESI → válido y esperado.
- `permissions: UNKNOWN` en INS (OpenDGSFP no publica ramos
  autorizados en el artefacto) → válido: gap de cobertura explícito.
- `changes.json` con entradas sólo donde hay evidencia → `0 changes`
  en una entidad es un resultado válido, no un defecto.

## Artefactos comprometidos

```text
tools/g4/build_projection.py        builder (tooling, stdlib+openpyxl)
projections/public/manifest.json    schema_version + bundle_sha256
projections/public/entities/*.json  read model entity/v1 (20 fichas)
projections/public/{entities,search,changes,sources}.json
schemas/public/*.json               schemas versionados del read model
tests/g4/test_public_projection.py  determinismo, P01–P13, schema
```

## Kill criteria

- Descubrir que un join requiere fuzzy matching → STOP: la proyección
  no sale; finding + revisión del modelo de identidad.
- El read model necesita datos no congelados (fetch) → STOP: viola la
  disciplina de evidencia; se congela el input primero.
