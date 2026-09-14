"""G2-B — normalizacion de snapshots a records keyed (contrato §3, §6).

La normalizacion es donde viven las clases de campo: convierte bytes
de fuente en ``{record_key: record}`` canonicalizados. Un campo ``set``
sale ordenado (reordenar => 0 cambios); un ``ordered`` conserva orden;
``missing`` nunca se sintetiza.

Cada normalizador declara su ``*_NORMALIZATION_VERSION``: dos snapshots
solo son comparables bajo la misma version (contrato §4).

EBA PSD2 (FINREG_G2_EBA_NORMALIZATION_V1):

    record_key = f"{EntityType}:{EntityCode}"

    record = {
      "ca_owner_id":  scalar
      "properties":   {PROP: valor | set-ordenado}   # nested keyed
      "services":     {CC:  set-ordenado}            # nested keyed
    }

    excluidos:
      __EBA_Disclaimer      seccion editorial, no un record
      __EBA_EntityVersion   stamp de version mutable (contrato §3:
                            versionado, no identidad ni campo semantico)
"""
from __future__ import annotations

import zipfile
from typing import Any

from .canonical import strict_json_loads

FINREG_G2_EBA_NORMALIZATION_V1 = "FINREG_G2_EBA_NORMALIZATION_V1"


def _as_set(value: Any) -> Any:
    """Campos multivalor EBA -> set canonicalizado (lista ordenada)."""
    if isinstance(value, list):
        return sorted(value)
    return value


def normalize_eba_psd2_zip(zip_path: str) -> dict[str, dict]:
    """Normaliza el zip EBA PSD2 a records keyed por (EntityType, EntityCode).

    El zip contiene ``[seccion_disclaimer][{entidades}]``; las entidades
    usan formato EAV: ``Properties`` es una lista de singletons
    ``{PROP: valor}`` y ``Services`` una lista de ``{CC: codigos}``.
    """
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith(".json")]
        if len(names) != 1:
            raise ValueError(f"zip EBA inesperado: {names!r}")
        payload = strict_json_loads(z.read(names[0]).decode("utf-8"))

    entities: list[dict] = []
    for section in payload:
        if (
            isinstance(section, list)
            and section
            and isinstance(section[0], dict)
            and "EntityCode" in section[0]
        ):
            entities.extend(section)
    if not entities:
        raise ValueError("zip EBA sin seccion de entidades")

    records: dict[str, dict] = {}
    for ent in entities:
        record_key = f"{ent['EntityType']}:{ent['EntityCode']}"
        if record_key in records:
            raise ValueError(f"record_key duplicada: {record_key!r}")
        properties: dict[str, Any] = {}
        for prop in ent.get("Properties", []):
            for code, value in prop.items():
                if code in properties:
                    raise ValueError(
                        f"propiedad duplicada {code!r} en {record_key!r}"
                    )
                properties[code] = _as_set(value)
        services: dict[str, Any] = {}
        for svc in ent.get("Services", []):
            for cc, codes in svc.items():
                if cc in services:
                    raise ValueError(
                        f"servicio duplicado {cc!r} en {record_key!r}"
                    )
                services[cc] = _as_set(codes)
        records[record_key] = {
            "ca_owner_id": ent.get("CA_OwnerID"),
            "properties": properties,
            "services": services,
        }
    return records
