"""G3-B — facade compartido de las superficies read-only.

Contrato congelado: ``docs/g3-b-adapter-contract.md``.

CLI (``adapters.cli``) y MCP (``adapters.mcp_server``) delegan aqui.
Este modulo solo resuelve artefactos congelados, valida inputs de
interfaz, llama al core y devuelve dicts — cero decisiones
regulatorias, cero escrituras, cero fallback heuristico.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from finreg_es.bitemporal import (
    assess_bitemporal,
    filter_evidence,
    load_evidence_set,
)
from finreg_es.canonical import strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.derivation import (
    to_entitlement_assertions,
    to_identity_index,
)
from finreg_es.semantics import assess

# G3-E (docs/g3-e0-packaging-contract.md S5): en el wheel instalado
# el runtime evidence bundle viaja en adapters/_data/ y los
# defaults fixtures/* resuelven ahi; en checkout _data no existe y
# ROOT sigue siendo el repo root — comportamiento historico
# identico. Un path explicito del usuario siempre se usa tal cual.
_PKG_DIR = Path(__file__).resolve().parent
ROOT = (
    _PKG_DIR / "_data" if (_PKG_DIR / "_data").is_dir() else _PKG_DIR.parent
)

DEFAULT_EVIDENCE_SET = "fixtures/g1/derived-assertions-g1-e-002.json"
DEFAULT_CONTRACTS_DIR = "fixtures/contracts"
DEFAULT_EVENTS_DIR = "fixtures/g2/events"


class AdapterError(Exception):
    """Error estructurado de interfaz (fail-closed)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _load_evidence_set(path: str | Path, expect_id: str | None):
    p = _resolve(path)
    if not p.is_file():
        raise AdapterError(
            "artifact_not_found", f"evidence set no existe: {p}"
        )
    try:
        es = load_evidence_set(p)
    except Exception as exc:
        raise AdapterError(
            "invalid_artifact", f"evidence set no parseable: {exc}"
        ) from exc
    if expect_id is not None and es.evidence_set_id != expect_id:
        raise AdapterError(
            "unknown_evidence_set",
            f"evidence_set_id no coincide: esperado {expect_id}, "
            f"cargado {es.evidence_set_id}",
        )
    return es


def _load_contracts(contracts_dir: str | Path) -> dict:
    d = _resolve(contracts_dir)
    if not d.is_dir():
        raise AdapterError(
            "artifact_not_found", f"contracts dir no existe: {d}"
        )
    return {
        c.register_id: c
        for c in (load_contract(p) for p in sorted(d.glob("*.json")))
    }


def _strict_input_date(value: str, field: str) -> None:
    text = str(value)
    if len(text) != 10:
        raise AdapterError(
            "invalid_input", f"{field} debe ser YYYY-MM-DD: {value!r}"
        )
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise AdapterError(
            "invalid_input", f"{field} no es fecha valida: {value!r}"
        ) from exc


def _result_payload(result, evidence_set_id: str) -> dict:
    """Serializa AssessmentResult del core a dict — sin reinterpretar
    ningun campo."""
    return {
        "entity_id": result.entity_id,
        "activity": result.activity,
        "jurisdiction": result.jurisdiction,
        "as_of": result.as_of,
        "identity_resolution": str(result.identity_resolution),
        "assessment": str(result.assessment),
        "reason": str(result.reason),
        "used_assertion_ids": [
            a["assertion_id"] for a in result.assertions
        ],
        "assertion_evaluations": [
            dict(e) for e in result.assertion_evaluations
        ],
        "response_freshness": result.response_freshness,
        "diagnostics": list(result.diagnostics),
        "semantics_version": "ASSESSMENT_SEMANTICS_V3",
        "evidence_set_id": evidence_set_id,
    }


def _evaluate(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    *,
    territorial_basis: str | None,
    known_at: str | None,
    evidence_set_path: str | Path,
    evidence_set_id: str | None,
    contracts_dir: str | Path,
):
    _strict_input_date(valid_at, "valid_at")
    if known_at is not None:
        _strict_input_date(known_at, "known_at")
    es = _load_evidence_set(evidence_set_path, evidence_set_id)
    doc = es.doc if known_at is None else filter_evidence(es.doc, known_at)
    result = assess(
        entity_id,
        to_identity_index(doc),
        activity=activity,
        jurisdiction=jurisdiction,
        as_of=valid_at,
        assertions=to_entitlement_assertions(doc),
        contracts=_load_contracts(contracts_dir),
        semantics_version="V3",
        reported_facts=doc.get("reported_facts", []),
        territorial_basis=territorial_basis,
    )
    return es, result


def op_assess(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    territorial_basis: str | None = None,
    *,
    evidence_set_path: str | Path = DEFAULT_EVIDENCE_SET,
    evidence_set_id: str | None = None,
    contracts_dir: str | Path = DEFAULT_CONTRACTS_DIR,
) -> dict:
    """Assessment actual: V3 con as_of=valid_at sobre el universo
    completo del evidence set."""
    es, result = _evaluate(
        entity_id,
        activity,
        jurisdiction,
        valid_at,
        territorial_basis=territorial_basis,
        known_at=None,
        evidence_set_path=evidence_set_path,
        evidence_set_id=evidence_set_id,
        contracts_dir=contracts_dir,
    )
    payload = _result_payload(result, es.evidence_set_id)
    payload["query"] = {
        "entity_id": entity_id,
        "activity": activity,
        "jurisdiction": jurisdiction,
        "territorial_basis": territorial_basis,
        "valid_at": valid_at,
    }
    return payload


def op_assess_bitemporal(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    known_at: str,
    territorial_basis: str | None = None,
    *,
    evidence_set_path: str | Path = DEFAULT_EVIDENCE_SET,
    evidence_set_id: str | None = None,
    contracts_dir: str | Path = DEFAULT_CONTRACTS_DIR,
) -> dict:
    """AssessmentQuery(valid_at x known_at): devuelve el dict
    congelado de ``finreg_es.bitemporal.assess_bitemporal``."""
    _strict_input_date(valid_at, "valid_at")
    _strict_input_date(known_at, "known_at")
    es = _load_evidence_set(evidence_set_path, evidence_set_id)
    try:
        return assess_bitemporal(
            entity_id,
            activity=activity,
            jurisdiction=jurisdiction,
            valid_at=valid_at,
            known_at=known_at,
            evidence_set=es,
            contracts=_load_contracts(contracts_dir),
            territorial_basis=territorial_basis,
        )
    except ValueError as exc:
        raise AdapterError("invalid_input", str(exc)) from exc


def op_explain(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    territorial_basis: str | None = None,
    known_at: str | None = None,
    *,
    evidence_set_path: str | Path = DEFAULT_EVIDENCE_SET,
    evidence_set_id: str | None = None,
    contracts_dir: str | Path = DEFAULT_CONTRACTS_DIR,
) -> dict:
    """Explicacion read-only: reason + diagnostics + evidence +
    assertion_evaluations que el core ya devuelve. Si se pasa
    ``known_at``, la evidencia se filtra por K y se adjunta la
    auditoria bitemporal (usable/excluded/untraceable)."""
    es, result = _evaluate(
        entity_id,
        activity,
        jurisdiction,
        valid_at,
        territorial_basis=territorial_basis,
        known_at=known_at,
        evidence_set_path=evidence_set_path,
        evidence_set_id=evidence_set_id,
        contracts_dir=contracts_dir,
    )
    payload = _result_payload(result, es.evidence_set_id)
    payload["query"] = {
        "entity_id": entity_id,
        "activity": activity,
        "jurisdiction": jurisdiction,
        "territorial_basis": territorial_basis,
        "valid_at": valid_at,
        "known_at": known_at,
    }
    if known_at is not None:
        payload["evidence"] = assess_bitemporal(
            entity_id,
            activity=activity,
            jurisdiction=jurisdiction,
            valid_at=valid_at,
            known_at=known_at,
            evidence_set=es,
            contracts=_load_contracts(contracts_dir),
            territorial_basis=territorial_basis,
        )["evidence"]
    return payload


def op_evidence(
    item_id: str | None = None,
    entity_id: str | None = None,
    *,
    evidence_set_path: str | Path = DEFAULT_EVIDENCE_SET,
    evidence_set_id: str | None = None,
) -> dict:
    """Slice del evidence set: un item por id (con sus
    source_assertions) o el universo de una entidad. Presenta los
    campos del artefacto congelado sin reinterpretarlos."""
    if (item_id is None) == (entity_id is None):
        raise AdapterError(
            "invalid_input",
            "indica exactamente uno de item_id / entity_id",
        )
    es = _load_evidence_set(evidence_set_path, evidence_set_id)
    doc = es.doc
    if item_id is not None:
        for a in doc.get("assertions", []):
            if a.get("assertion_id") == item_id:
                return {
                    "item_kind": "assertion",
                    "item": a,
                    "evidence_set_id": es.evidence_set_id,
                }
        for f in doc.get("reported_facts", []):
            if f.get("fact_id") == item_id:
                return {
                    "item_kind": "reported_fact",
                    "item": f,
                    "evidence_set_id": es.evidence_set_id,
                }
        raise AdapterError(
            "not_found", f"item_id no existe en el evidence set: {item_id}"
        )
    return {
        "entity_id": entity_id,
        "assertions": [
            a for a in doc.get("assertions", []) if a["entity_id"] == entity_id
        ],
        "reported_facts": [
            f
            for f in doc.get("reported_facts", [])
            if f.get("corpus_id") == entity_id
        ],
        "evidence_set_id": es.evidence_set_id,
    }


def op_changes(
    record_key: str | None = None,
    pair: str | None = None,
    *,
    events_dir: str | Path = DEFAULT_EVENTS_DIR,
) -> dict:
    """Candidatos a evento regulatorio de los artefactos G2-C
    congelados. ``pair`` filtra por stem del artefacto
    (p.ej. ``eba-psd2-20260914-vs-20260915``); ``record_key`` filtra
    candidatos. Sin filtros devuelve todos los pares."""
    d = _resolve(events_dir)
    if not d.is_dir():
        raise AdapterError(
            "artifact_not_found", f"events dir no existe: {d}"
        )
    results = []
    for p in sorted(d.glob("*.json")):
        if pair is not None and p.stem != pair:
            continue
        doc = strict_json_loads(p.read_text(encoding="utf-8"))
        candidates = doc.get("candidates", [])
        if record_key is not None:
            candidates = [
                c for c in candidates if c.get("record_key") == record_key
            ]
        results.append(
            {
                "artifact": doc["artifact"],
                "observation": doc["observation"],
                "source_comparison": doc["source_comparison"],
                "summary": doc["summary"],
                "candidates": candidates,
            }
        )
    if pair is not None and not results:
        raise AdapterError(
            "not_found", f"par de comparacion no existe: {pair}"
        )
    return {"results": results}
