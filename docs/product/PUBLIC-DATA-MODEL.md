# PUBLIC-DATA-MODEL — read model público v1

Proyección estable del modelo interno. El frontend consume **sólo**
estos artefactos; el modelo interno completo no se expone.

## Layout

```text
public/
├── manifest.json          # schema_version, generated_at, counts, bundle_sha256
├── entities.json          # índice: id, name, aliases, ids, status, verticals
├── search.json            # payload de búsqueda (name/alias/ids → id)
├── entities/
│   └── <stable-id>.json   # ficha completa (schema entity/v1)
├── changes.json           # feed de cambios clasificados
└── sources.json           # fuentes, cobertura, freshness
```

`<stable-id>` = slug derivado del identificador autoritativo primario
(`es:cnmv:sgii c:<nif>` → `sg iic-a83133421`); determinista, sin contadores.

## entity/v1 (campos)

```jsonc
{
  "schema": "regulatory-record-entity/v1",
  "id": "sgii c-a83133421",
  "identity": {
    "legal_name": "…", "aliases": ["…"],
    "identifiers": [{"scheme": "es:nif|lei|cnmv|bde|dgsfp|eba|eiopa", "value": "…"}],
    "resolution": "EXACT|CONFLICT|UNRESOLVED|CANDIDATE"
  },
  "status": {"value": "REGISTERED|DEREGISTERED|…|UNKNOWN", "as_of": "…", "basis": "…"},
  "registrations": [{"regulator": "…", "register": "…", "number": "…", "date": "…", "state": "…"}],
  "permissions": [{"service": "…", "instruments": ["…"], "clients": ["…"], "since": "…|null", "basis": "…"}],
  "locations": {"domicile": "…", "branches": [...], "agents": [...], "passporting": [...]},
  "organisation": {"shareholders": [...], "administrators": [...], "auditor": "…", "customer_service": "…"},
  "managed_entities": [...],
  "regulatory_record": {
    "sanctions": [...], "appeals": [...],
    "direct_warnings": [...], "impersonations": [...], "candidates": [...]
  },
  "timeline": [{"date_or_interval": "…", "kind": "EXPLICIT_OFFICIAL_EVENT|OFFICIAL_AS_OF_STATE|OFFICIAL_DOCUMENT_DERIVATION|OBSERVED_CHANGE", "summary": "…", "evidence": "…"}],
  "sources": [{"source": "…", "url": "…", "as_of": "…", "retrieved_at": "…", "sha256": "…", "coverage": "…"}],
  "coverage": {"identity": "…", "permission": "…", "history": "…", "provenance": "…"},
  "freshness": {"last_successful_refresh": "…", "source_status": "…"}
}
```

Cada `…` con `basis` lleva la clase del enum de hechos + referencia de
evidencia (`source_id` + `sha256` de snapshot o de artefacto upstream).

## Reglas

- Orden determinista: arrays ordenados por clave canónica; serialización
  `FINREG_CANONICAL_JSON_V1`; `bundle_sha256` = sha256 de la
  concatenación canónica de todos los artefactos.
- `changes.json` clasifica cada item: `OFFICIAL_EVENT |
  RECONSTRUCTED_HISTORICAL | OBSERVED_CURRENT | BACKFILL`.
- Schemas JSON publicados en `schemas/public/`; versionados; los golden
  fixtures del repo validan cada build.
- Un `…` desconocido se omite o se marca `UNKNOWN` explícito — nunca
  vacío-que-parece-cero.
