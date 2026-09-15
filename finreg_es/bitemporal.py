"""G2-E — capa bitemporal de consulta.

Contrato congelado: ``docs/g2-e1-bitemporal-assessment-contract.md``
(task ``g2-e1-preregister``). Implementa
``AssessmentQuery(valid_at x known_at) -> BitemporalAssessmentResult``
como una capa fina sobre ASSESSMENT_SEMANTICS_V3:

    universo versionado de assertions + reported_facts (evidence set)
        -> visibility gate: known_at filtra evidencia (E1-R1/R2)
        -> assess(V3, as_of=valid_at) sin cambios (E1-R3)
        -> resultado + auditoria de evidencia incluida/excluida

``known_at`` nunca modifica ``effective_from``/``effective_to`` ni los
intervalos, y no es versionado historico del software: todos los
probes se evaluan con V3 congelado.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from finreg_es.canonical import strict_json_loads
from finreg_es.contracts import SourceContract
from finreg_es.derivation import to_entitlement_assertions, to_identity_index
from finreg_es.semantics import assess

SEMANTICS_VERSION = "ASSESSMENT_SEMANTICS_V3"


@dataclass(frozen=True)
class EvidenceSet:
    """Universo de evidencia versionado (E1-R5).

    ``evidence_set_id`` liga el universo a los bytes consumidos:
    ``<stem del fichero>@sha256:<sha256 de los bytes>`` — el mismo
    hash que los manifiestos/fixtures registran por artefacto.
    """

    evidence_set_id: str
    doc: dict


def load_evidence_set(path: str | Path) -> EvidenceSet:
    """Carga un artefacto derivado congelado ligando su id a los bytes."""
    raw = Path(path).read_bytes()
    doc = strict_json_loads(raw.decode("utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    return EvidenceSet(f"{Path(path).stem}@sha256:{digest}", doc)


def _calendar_date(value: Any) -> date:
    """E1-R4: un retrieved_at date o datetime ISO proyecta a su fecha
    calendario; no hay comparacion sub-day."""
    return date.fromisoformat(str(value)[:10])


def _strict_date(value: Any, field: str) -> date:
    """``valid_at``/``known_at`` son fechas calendario YYYY-MM-DD."""
    text = str(value)
    if len(text) != 10:
        raise ValueError(f"{field} debe ser fecha YYYY-MM-DD: {value!r}")
    return date.fromisoformat(text)


def knowledge_time(item: dict) -> date | None:
    """E1-R1/R2: instante en que la evidencia era observable =
    ``max(retrieved_at)`` de sus fuentes. Un artefacto derivado no es
    mas cognoscible que su input menos observado. ``None`` si no puede
    vincularse a observaciones fuente."""
    sources = item.get("source_assertions") or []
    if not sources:
        return None
    return max(_calendar_date(s["retrieved_at"]) for s in sources)


def observable(item: dict, known_at: Any) -> bool:
    """Visible en K sii tiene fuentes trazables y knowledge_time <= K."""
    kt = knowledge_time(item)
    return kt is not None and kt <= _calendar_date(known_at)


def filter_evidence(doc: dict, known_at: Any) -> dict:
    """Visibility gate (E1-R1/R2): doc nuevo con solo la evidencia
    observable en K. Nunca muta el doc de entrada ni los items
    (E1-R3: los intervalos juridicos son intocables)."""
    k = _calendar_date(known_at)
    filtered = dict(doc)
    filtered["assertions"] = [
        a for a in doc.get("assertions", []) if observable(a, k)
    ]
    filtered["reported_facts"] = [
        f for f in doc.get("reported_facts", []) if observable(f, k)
    ]
    return filtered


def _partition(universe: list[dict], k: date) -> tuple[list, list, list]:
    usable, after_k, untraceable = [], [], []
    for item in universe:
        kt = knowledge_time(item)
        if kt is None:
            untraceable.append(item)
        elif kt <= k:
            usable.append(item)
        else:
            after_k.append(item)
    return usable, after_k, untraceable


def assess_bitemporal(
    entity_id: str,
    *,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    known_at: str,
    evidence_set: EvidenceSet,
    contracts: dict[str, SourceContract],
    territorial_basis: str | None = None,
) -> dict:
    """AssessmentQuery(valid_at x known_at) -> BitemporalAssessmentResult.

    Filtra la evidencia observable en ``known_at`` y delega el
    assessment juridico integramente en V3 con ``as_of=valid_at``.
    El universo auditado es el de la query: aserciones que matchean
    entity_id x activity x jurisdiction (x territorial_basis) mas los
    reported_facts de la entidad.
    """
    k = _strict_date(known_at, "known_at")
    _strict_date(valid_at, "valid_at")
    doc = evidence_set.doc

    universe_assertions = [
        a
        for a in doc.get("assertions", [])
        if a["entity_id"] == entity_id
        and a["activity"] == activity
        and a["jurisdiction"] == jurisdiction
        and (
            territorial_basis is None
            or a["territorial_basis"] == territorial_basis
        )
    ]
    universe_facts = [
        f
        for f in doc.get("reported_facts", [])
        if f.get("corpus_id") == entity_id
    ]

    usable_a, after_k_a, untraceable_a = _partition(universe_assertions, k)
    usable_f, after_k_f, untraceable_f = _partition(universe_facts, k)

    filtered = filter_evidence(doc, k)
    result = assess(
        entity_id,
        to_identity_index(doc),
        activity=activity,
        jurisdiction=jurisdiction,
        as_of=valid_at,
        assertions=to_entitlement_assertions(filtered),
        contracts=contracts,
        semantics_version="V3",
        reported_facts=filtered.get("reported_facts", []),
        territorial_basis=territorial_basis,
    )

    return {
        "query": {
            "entity_id": entity_id,
            "activity": activity,
            "jurisdiction": jurisdiction,
            "territorial_basis": territorial_basis,
            "valid_at": valid_at,
            "known_at": known_at,
        },
        "assessment": str(result.assessment),
        "reason": str(result.reason),
        "evidence": {
            "usable_assertion_ids": sorted(
                a["assertion_id"] for a in usable_a
            ),
            "excluded_after_known_at_assertion_ids": sorted(
                a["assertion_id"] for a in after_k_a
            ),
            "excluded_untraceable_assertion_ids": sorted(
                a["assertion_id"] for a in untraceable_a
            ),
            "usable_reported_fact_ids": sorted(
                f["fact_id"] for f in usable_f
            ),
            "excluded_after_known_at_fact_ids": sorted(
                f["fact_id"] for f in after_k_f
            ),
            "excluded_untraceable_fact_ids": sorted(
                f["fact_id"] for f in untraceable_f
            ),
            "diagnostics": sorted(
                f"no_source_assertions:{i.get('assertion_id') or i.get('fact_id')}"
                for i in (*untraceable_a, *untraceable_f)
            ),
        },
        "used_assertion_ids": [a["assertion_id"] for a in result.assertions],
        "diagnostics": list(result.diagnostics),
        "semantics_version": SEMANTICS_VERSION,
        "evidence_set_id": evidence_set.evidence_set_id,
    }
