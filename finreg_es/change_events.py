"""G2-C — cambio estructural -> candidato a evento regulatorio.

Contrato: docs/g2-c0-change-event-contract.md (preregistrado).
Entrada: salida de ``compare_observations`` (G2-B) — un dict con
``comparison`` + ``changes``, o el artefacto JSON equivalente.

Regla esencial: G2-C interpreta cambios observados; nunca reconstruye
un evento que el diff no observo. Un candidato no es una asercion
juridica — la asercion la emite la cadena de derivacion existente.

Catalogo EBA PSD2 (series ``eba-psd2-register|*``):

- ``properties.ENT_AUT`` es el log de transiciones del registro
  (spec oficial, G1-A): posiciones impares = autorizacion/registro,
  pares = retirada. Cada fecha anadida por append estricto es un
  candidato con ``effective_from`` = la fecha publicada por la fuente
  (``SOURCE_DECLARED``; caso B08 del contrato temporal).
- ``services.ES`` es un set de codigos PS: ``+ PS_xx`` =>
  CAPABILITY_APPEARED, ``- PS_xx`` => CAPABILITY_DISAPPEARED (nunca
  negativo juridico automatico). Solo ES esta preregistrado.
- record added => ENTITY_RECORD_APPEARED (presencia != entitlement).
- record removed => ENTITY_RECORD_DISAPPEARED solo si ambos lados
  declaran el slice completo; si no, BLOCKED + NO_REMOVAL_ADMISSIBLE.

Fail-closed bilateral: un cambio sin regla preregistrada produce
UNCLASSIFIED_STRUCTURAL_CHANGE + BLOCKED — ni evento inventado ni
NOT_REGULATORY inventado (afirmar que un cambio no es regulatorio
tambien seria una asercion sin regla).
"""
from __future__ import annotations

from typing import Any

from .snapshot_diff import MISSING

FINREG_G2C_EVENT_RULES_V1 = "FINREG_G2C_EVENT_RULES_V1"

# Tipos de candidato del catalogo preregistrado (G2-C0).
ROOT_WITHDRAWAL_CANDIDATE = "ROOT_WITHDRAWAL_CANDIDATE"
ROOT_REAUTHORISATION_CANDIDATE = "ROOT_REAUTHORISATION_CANDIDATE"
CAPABILITY_APPEARED_CANDIDATE = "CAPABILITY_APPEARED_CANDIDATE"
CAPABILITY_DISAPPEARED_CANDIDATE = "CAPABILITY_DISAPPEARED_CANDIDATE"
ENTITY_RECORD_APPEARED = "ENTITY_RECORD_APPEARED"
ENTITY_RECORD_DISAPPEARED = "ENTITY_RECORD_DISAPPEARED"
UNCLASSIFIED_STRUCTURAL_CHANGE = "UNCLASSIFIED_STRUCTURAL_CHANGE"

# effective_basis (contrato): la fecha juridica la publica la fuente
# o no existe; EVIDENCE_AS_OF es el mecanismo probatorio.
SOURCE_DECLARED = "SOURCE_DECLARED"
EVIDENCE_AS_OF = "EVIDENCE_AS_OF"
UNKNOWN = "UNKNOWN"

SUPPORTED = "SUPPORTED"
BLOCKED = "BLOCKED"

# Findings emitidos por esta capa (ademas de los heredados de G2-B).
NO_PREREGISTERED_RULE = "NO_PREREGISTERED_RULE"
ENT_AUT_SEQUENCE_REWRITTEN = "ENT_AUT_SEQUENCE_REWRITTEN"
NO_REMOVAL_ADMISSIBLE = "NO_REMOVAL_ADMISSIBLE"

_ENT_AUT_PATH = ("properties", "ENT_AUT")
_ES_SERVICES_PATH = ("services", "ES")
_EBA_SERIES_PREFIX = "eba-psd2-register"


def _retrieved_at(observation_id: str) -> str:
    """Extrae retrieved_at de ``register_id|retrieved_at|sha16``."""
    parts = observation_id.rsplit("|", 2)
    if len(parts) != 3 or not parts[1]:
        raise ValueError(
            f"observation_id malformado (error de invocacion): {observation_id!r}"
        )
    return parts[1]


def _code_set(value: Any) -> set | None:
    """Conjunto de codigos PS de un valor services.<CC> (str|list).

    ``None`` si el valor no es un set de codigos interpretable.
    """
    if value is MISSING or value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return set(value)
    return None


def _base_candidate(
    candidate_type: str,
    record_key: str,
    ctx: dict,
    *,
    admissibility: str,
    effective_basis: str,
    detail: str,
    blocker: str | None = None,
) -> dict:
    c = {
        "candidate_type": candidate_type,
        "record_key": record_key,
        "admissibility": admissibility,
        "effective_basis": effective_basis,
        "detail": detail,
        "findings": [],
        **ctx,
    }
    if blocker is not None:
        c["blocker"] = blocker
    return c


def _unclassified(record_key: str, path: list, ch: dict, ctx: dict,
                  finding_class: str, detail: str) -> dict:
    c = _base_candidate(
        UNCLASSIFIED_STRUCTURAL_CHANGE,
        record_key,
        ctx,
        admissibility=BLOCKED,
        effective_basis=UNKNOWN,
        blocker=finding_class,
        detail=detail,
    )
    c["field_path"] = path
    c["findings"].append({"classification": finding_class, "detail": detail})
    if "old" in ch:
        c["old_value"] = ch["old"]
    if "new" in ch:
        c["new_value"] = ch["new"]
    return c


def _classify_ent_aut(record_key: str, path: list, ch: dict, ctx: dict) -> list[dict]:
    """ENT_AUT: log de transiciones; append estricto => un candidato por
    fecha anadida (par => retirada, impar => (re)autorizacion)."""
    old = ch.get("old", MISSING)
    new = ch.get("new", MISSING)
    old_seq = [] if old is MISSING else old
    if not isinstance(old_seq, list) or not isinstance(new, list):
        return [
            _unclassified(
                record_key, path, ch, ctx,
                ENT_AUT_SEQUENCE_REWRITTEN,
                "ENT_AUT no es una secuencia de fechas o el campo "
                "desaparecio: removed/valor-no-lista nunca implica "
                "retirada (anti-regla congelada)",
            )
        ]
    if len(new) <= len(old_seq) or new[: len(old_seq)] != old_seq:
        return [
            _unclassified(
                record_key, path, ch, ctx,
                ENT_AUT_SEQUENCE_REWRITTEN,
                "ENT_AUT modificado sin append estricto (prefijo "
                "distinto o secuencia encogida): posible correccion; "
                "sin regla preregistrada",
            )
        ]
    candidates = []
    for i in range(len(old_seq), len(new)):
        date = new[i]
        if not isinstance(date, str):
            candidates.append(
                _unclassified(
                    record_key, path, ch, ctx,
                    ENT_AUT_SEQUENCE_REWRITTEN,
                    f"elemento ENT_AUT[{i}] no es fecha publicada: {date!r}",
                )
            )
            continue
        position = i + 1  # 1-indexed segun el spec
        if position % 2 == 0:
            ctype, det = (
                ROOT_WITHDRAWAL_CANDIDATE,
                "ENT_AUT: fecha anadida en posicion par — la fuente "
                "declara retirada; el intervalo abierto se cierra",
            )
        else:
            ctype, det = (
                ROOT_REAUTHORISATION_CANDIDATE,
                "ENT_AUT: fecha anadida en posicion impar — la fuente "
                "declara nueva autorizacion/registro",
            )
        c = _base_candidate(
            ctype,
            record_key,
            ctx,
            admissibility=SUPPORTED,
            effective_basis=SOURCE_DECLARED,
            detail=det,
        )
        c["field_path"] = path
        c["old_value"] = old_seq
        c["new_value"] = new
        c["effective_from"] = date
        c["sequence_position"] = position
        candidates.append(c)
    return candidates


def _classify_es_services(record_key: str, path: list, ch: dict, ctx: dict) -> list[dict]:
    """services.ES: set de codigos PS; + => APPEARED, - => DISAPPEARED."""
    old_codes = _code_set(ch.get("old", MISSING))
    new_codes = _code_set(ch.get("new", MISSING))
    if old_codes is None or new_codes is None:
        return [
            _unclassified(
                record_key, path, ch, ctx,
                NO_PREREGISTERED_RULE,
                "services.ES con valor no interpretable como set de "
                "codigos PS",
            )
        ]
    candidates = []
    added = sorted(new_codes - old_codes)
    removed = sorted(old_codes - new_codes)
    if added:
        c = _base_candidate(
            CAPABILITY_APPEARED_CANDIDATE,
            record_key,
            ctx,
            admissibility=SUPPORTED,
            effective_basis=EVIDENCE_AS_OF,
            detail="services.ES gano codigos PS: capability observada, "
            "nunca entitlement (classification != authorization)",
        )
        c["field_path"] = path
        c["added_codes"] = added
        if "old" in ch:
            c["old_value"] = ch["old"]
        if "new" in ch:
            c["new_value"] = ch["new"]
        candidates.append(c)
    if removed:
        c = _base_candidate(
            CAPABILITY_DISAPPEARED_CANDIDATE,
            record_key,
            ctx,
            admissibility=SUPPORTED,
            effective_basis=EVIDENCE_AS_OF,
            detail="services.ES perdio codigos PS: desaparicion "
            "estructural, NUNCA negativo juridico automatico",
        )
        c["field_path"] = path
        c["removed_codes"] = removed
        if "old" in ch:
            c["old_value"] = ch["old"]
        if "new" in ch:
            c["new_value"] = ch["new"]
        candidates.append(c)
    return candidates


def classify_changes(comparison_result: dict) -> dict:
    """Clasifica los cambios de una comparacion G2-B en candidatos.

    ``comparison_result`` es la salida de ``compare_observations`` (o el
    artefacto JSON equivalente: secciones ``comparison`` + ``changes``).

    Devuelve ``{"rules_version", "observation", "candidates",
    "comparison_findings", "summary"}``. Si la comparacion no es
    ``comparable`` (contrato §4), no se emiten candidatos: los cambios
    no son observables bajo una normalizacion comun.
    """
    comp = comparison_result["comparison"]
    changes = comparison_result["changes"]

    ctx = {
        "left_observation_id": comp["left_observation_id"],
        "right_observation_id": comp["right_observation_id"],
        "observed_after": _retrieved_at(comp["left_observation_id"]),
        "observed_by": _retrieved_at(comp["right_observation_id"]),
    }
    series_key = comp["series_key"]
    eba_catalog = series_key.startswith(_EBA_SERIES_PREFIX)

    candidates: list[dict] = []
    if comp.get("comparable", False):
        for record_key in changes.get("added", []):
            if eba_catalog:
                c = _base_candidate(
                    ENTITY_RECORD_APPEARED,
                    record_key,
                    ctx,
                    admissibility=SUPPORTED,
                    effective_basis=EVIDENCE_AS_OF,
                    detail="record presente en la captura derecha; "
                    "presencia != entitlement",
                )
            else:
                c = _base_candidate(
                    UNCLASSIFIED_STRUCTURAL_CHANGE,
                    record_key,
                    ctx,
                    admissibility=BLOCKED,
                    effective_basis=UNKNOWN,
                    blocker=NO_PREREGISTERED_RULE,
                    detail=f"record added en serie {series_key!r} sin "
                    "catalogo preregistrado",
                )
                c["findings"].append(
                    {
                        "classification": NO_PREREGISTERED_RULE,
                        "detail": c["detail"],
                    }
                )
            candidates.append(c)

        removal_admissible = comp.get("removal_admissible", False)
        for record_key in changes.get("removed", []):
            if eba_catalog and removal_admissible:
                c = _base_candidate(
                    ENTITY_RECORD_DISAPPEARED,
                    record_key,
                    ctx,
                    admissibility=SUPPORTED,
                    effective_basis=EVIDENCE_AS_OF,
                    detail="record ausente entre capturas completas "
                    "comparables; nunca withdrawal por si solo",
                )
            elif eba_catalog:
                c = _base_candidate(
                    ENTITY_RECORD_DISAPPEARED,
                    record_key,
                    ctx,
                    admissibility=BLOCKED,
                    effective_basis=UNKNOWN,
                    blocker=NO_REMOVAL_ADMISSIBLE,
                    detail="record no observado en captura no completa; "
                    "no constituye desaparicion admisible (contrato §5)",
                )
                c["findings"].append(
                    {
                        "classification": NO_REMOVAL_ADMISSIBLE,
                        "detail": "heredado de G2-B: el slice no es "
                        "completo en ambos lados",
                    }
                )
            else:
                c = _base_candidate(
                    UNCLASSIFIED_STRUCTURAL_CHANGE,
                    record_key,
                    ctx,
                    admissibility=BLOCKED,
                    effective_basis=UNKNOWN,
                    blocker=NO_PREREGISTERED_RULE,
                    detail=f"record removed en serie {series_key!r} sin "
                    "catalogo preregistrado",
                )
                c["findings"].append(
                    {
                        "classification": NO_PREREGISTERED_RULE,
                        "detail": c["detail"],
                    }
                )
            candidates.append(c)

        for ch in changes.get("changed", []):
            record_key = ch["record_key"]
            path = list(ch["path"])
            tpath = tuple(path)
            if not eba_catalog:
                candidates.append(
                    _unclassified(
                        record_key, path, ch, ctx,
                        NO_PREREGISTERED_RULE,
                        f"sin catalogo preregistrado para la serie "
                        f"{series_key!r}",
                    )
                )
            elif tpath == _ENT_AUT_PATH:
                candidates.extend(_classify_ent_aut(record_key, path, ch, ctx))
            elif tpath == _ES_SERVICES_PATH:
                candidates.extend(
                    _classify_es_services(record_key, path, ch, ctx)
                )
            else:
                detail = (
                    "cambio estructural sin regla de catalogo "
                    f"preregistrada (path {tpath!r}; el catalogo EBA "
                    "cubre properties.ENT_AUT y services.ES)"
                )
                candidates.append(
                    _unclassified(
                        record_key, path, ch, ctx, NO_PREREGISTERED_RULE, detail
                    )
                )

    return {
        "rules_version": FINREG_G2C_EVENT_RULES_V1,
        "observation": ctx,
        "candidates": candidates,
        "comparison_findings": comp.get("findings", []),
        "summary": {
            "input": {
                "added": len(changes.get("added", [])),
                "removed": len(changes.get("removed", [])),
                "changed": len(changes.get("changed", [])),
            },
            "candidates": len(candidates),
            "supported": sum(
                1 for c in candidates if c["admissibility"] == SUPPORTED
            ),
            "blocked": sum(
                1 for c in candidates if c["admissibility"] == BLOCKED
            ),
        },
    }
