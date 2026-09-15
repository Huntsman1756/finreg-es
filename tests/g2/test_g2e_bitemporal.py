"""G2-E2 — capa bitemporal AssessmentQuery(valid_at x known_at).

Contrato: docs/g2-e1-bitemporal-assessment-contract.md.
Acceptance binding: los 18 probes congelados de
fixtures/g2/e0/bitemporal-cases.json (FINREG_G2_E0_CASES_V1) mas los
metamorficos preregistrados en .tasks/g2-e2-implement.yaml.
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from finreg_es.bitemporal import (
    EvidenceSet,
    assess_bitemporal,
    filter_evidence,
    knowledge_time,
    load_evidence_set,
    observable,
)
from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.derivation import (
    to_entitlement_assertions,
    to_identity_index,
)
from finreg_es.semantics import assess

ROOT = Path(__file__).parents[2]
EVIDENCE_SET_PATH = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
CASES_PATH = ROOT / "fixtures/g2/e0/bitemporal-cases.json"
CONTRACTS_DIR = ROOT / "fixtures/contracts"

EVIDENCE_SET_ID = (
    "derived-assertions-g1-e-002@sha256:"
    "2fb08d678a5ee11a398af7a4a990521d1ca5fde20012ffd8e8af63f058bfc1e7"
)

_FIXTURE = strict_json_loads(CASES_PATH.read_text(encoding="utf-8"))
EVIDENCE_SET = load_evidence_set(EVIDENCE_SET_PATH)
CONTRACTS = {
    c.register_id: c
    for c in (load_contract(p) for p in sorted(CONTRACTS_DIR.glob("*.json")))
}

_ALL_PROBES = [
    (case, probe)
    for case in _FIXTURE["cases"]
    for probe in case["probes"]
]


def _run(case, probe, evidence_set=EVIDENCE_SET):
    q = case["query"]
    return assess_bitemporal(
        case["entity_id"],
        activity=q["activity"],
        jurisdiction=q["jurisdiction"],
        territorial_basis=q["territorial_basis"],
        valid_at=probe["valid_at"],
        known_at=probe["known_at"],
        evidence_set=evidence_set,
        contracts=CONTRACTS,
    )


# --- Acceptance binding: 18/18 probes E0 ------------------------------


def test_fixture_has_18_binding_probes():
    assert _FIXTURE["cases_meta"]["version"] == "FINREG_G2_E0_CASES_V1"
    assert sum(len(c["probes"]) for c in _FIXTURE["cases"]) == 18


def test_evidence_set_id_binds_consumed_bytes():
    """E1-R5: el id del universo liga stem + sha256 de los bytes
    consumidos (el hash congelado del artefacto, no un rehash del
    doc parseado)."""
    assert EVIDENCE_SET.evidence_set_id == EVIDENCE_SET_ID
    assert EVIDENCE_SET_ID.split("@sha256:", 1)[1] == _FIXTURE["inputs"][
        "derived_assertions"
    ]["sha256"]


@pytest.mark.parametrize(
    "case,probe",
    _ALL_PROBES,
    ids=[
        f"{c['case_id']}:{p['valid_at']}@{p['known_at']}"
        for c, p in _ALL_PROBES
    ],
)
def test_e0_probe_replay(case, probe):
    """18/18 probes reproducen assessment, reason, usable/excluded
    por K, used_assertion_ids y diagnostics congelados."""
    r = _run(case, probe)
    assert r["query"] == {
        "entity_id": case["entity_id"],
        "activity": case["query"]["activity"],
        "jurisdiction": case["query"]["jurisdiction"],
        "territorial_basis": case["query"]["territorial_basis"],
        "valid_at": probe["valid_at"],
        "known_at": probe["known_at"],
    }
    assert r["assessment"] == probe["expected_assessment"]
    assert r["reason"] == probe["expected_reason"]
    ev = r["evidence"]
    assert ev["usable_assertion_ids"] == probe["usable_assertion_ids"]
    assert (
        ev["excluded_after_known_at_assertion_ids"]
        == probe["excluded_after_K_assertion_ids"]
    )
    assert ev["usable_reported_fact_ids"] == probe["usable_fact_ids"]
    assert (
        ev["excluded_after_known_at_fact_ids"]
        == probe["excluded_after_K_fact_ids"]
    )
    assert r["used_assertion_ids"] == probe["used_assertion_ids"]
    assert r["diagnostics"] == probe["diagnostics"]
    assert r["semantics_version"] == "ASSESSMENT_SEMANTICS_V3"
    assert r["evidence_set_id"] == EVIDENCE_SET_ID


def test_usable_excluded_untraceable_partition_universe():
    """usable + excluded_after_K + excluded_untraceable = universo
    declarado por el fixture; la auditoria no pierde evidencia."""
    for case, probe in _ALL_PROBES:
        ev = _run(case, probe)["evidence"]
        a_all = (
            ev["usable_assertion_ids"]
            + ev["excluded_after_known_at_assertion_ids"]
            + ev["excluded_untraceable_assertion_ids"]
        )
        f_all = (
            ev["usable_reported_fact_ids"]
            + ev["excluded_after_known_at_fact_ids"]
            + ev["excluded_untraceable_fact_ids"]
        )
        assert sorted(a_all) == case["evidence_universe"]["assertion_ids"]
        assert sorted(f_all) == case["evidence_universe"]["fact_ids"]


# --- Metamorficos preregistrados ---------------------------------------


def test_known_at_increase_never_shrinks_usable():
    """K creciente => el conjunto usable nunca decrece (el assessment
    no tiene por que ser monotono)."""
    ks = [
        "2026-09-11",
        "2026-09-12",
        "2026-09-13",
        "2026-09-14",
        "2026-09-15",
        "2027-01-01",
    ]
    for case in _FIXTURE["cases"]:
        prev = None
        for k in ks:
            r = _run(
                case,
                {"valid_at": case["probes"][0]["valid_at"], "known_at": k},
            )
            usable = (
                set(r["evidence"]["usable_assertion_ids"]),
                set(r["evidence"]["usable_reported_fact_ids"]),
            )
            if prev is not None:
                assert prev[0] <= usable[0]
                assert prev[1] <= usable[1]
            prev = usable


def test_same_t_same_k_deterministic():
    """Mismo (T,K) => resultado canonicamente identico."""
    for case, probe in _ALL_PROBES:
        assert canonical_json(_run(case, probe)) == canonical_json(
            _run(case, probe)
        )


def test_known_at_never_mutates_intervals_or_input():
    """E1-R3: filtrar por K no toca effective_from/to,
    status_intervals ni interval_end, y el doc de entrada queda
    byte-identico."""
    doc = copy.deepcopy(EVIDENCE_SET.doc)
    before = canonical_json(doc)
    filtered_early = filter_evidence(doc, "2026-09-13")
    filtered_late = filter_evidence(doc, "2026-09-15")
    assert canonical_json(doc) == before
    by_id = {a["assertion_id"]: a for a in doc["assertions"]}
    for filtered in (filtered_early, filtered_late):
        for a in filtered["assertions"]:
            src = by_id[a["assertion_id"]]
            for field in (
                "effective_from",
                "effective_to",
                "interval_end",
                "status_intervals",
            ):
                assert a.get(field) == src.get(field)


def test_evidence_retrieved_after_k_never_used():
    """Ningun id excluido por K aparece en used_assertion_ids."""
    for case, probe in _ALL_PROBES:
        r = _run(case, probe)
        excluded = set(
            r["evidence"]["excluded_after_known_at_assertion_ids"]
        ) | set(r["evidence"]["excluded_untraceable_assertion_ids"])
        assert excluded.isdisjoint(r["used_assertion_ids"])


def test_knowledge_time_is_max_source_retrieved_at():
    """E1-R1: sources [S1@09-13, S2@09-14] => EXCLUDED en 09-13,
    USABLE en 09-14. Nunca parcialmente usable."""
    item = {
        "source_assertions": [
            {"retrieved_at": "2026-09-13"},
            {"retrieved_at": "2026-09-14"},
        ]
    }
    assert knowledge_time(item) == date(2026, 9, 14)
    assert not observable(item, "2026-09-13")
    assert observable(item, "2026-09-14")


def test_retrieved_at_datetime_projects_to_calendar_date():
    """E1-R4: timestamp ISO -> fecha calendario; sin comparacion
    sub-day."""
    item = {"source_assertions": [{"retrieved_at": "2026-09-14T19:36:43Z"}]}
    assert knowledge_time(item) == date(2026, 9, 14)
    assert not observable(item, "2026-09-13")
    assert observable(item, "2026-09-14")


def test_untraceable_fact_excluded_fail_closed_with_diagnostic():
    """E1-R2: un reported_fact sin source_assertions nunca es
    observable, no hereda retrieved_at de nadie y deja diagnostico;
    el assessment no cambia."""
    case, probe = _ALL_PROBES[0]
    doc = copy.deepcopy(EVIDENCE_SET.doc)
    ghost = {
        "fact_id": "ghost-fact-no-src",
        "corpus_id": case["entity_id"],
        "reported_status": "ACTIVE",
        "status_intervals": [{"from": "2000-01-01"}],
        "source": "EBA_PSD2_REGISTER",
    }
    doc["reported_facts"] = doc.get("reported_facts", []) + [ghost]
    r = _run(case, probe, evidence_set=EvidenceSet("synthetic@sha256:0", doc))
    ev = r["evidence"]
    assert "ghost-fact-no-src" in ev["excluded_untraceable_fact_ids"]
    assert "ghost-fact-no-src" not in ev["usable_reported_fact_ids"]
    assert "ghost-fact-no-src" not in ev["excluded_after_known_at_fact_ids"]
    assert "no_source_assertions:ghost-fact-no-src" in ev["diagnostics"]
    base = _run(case, probe)
    assert r["assessment"] == base["assessment"]
    assert r["reason"] == base["reason"]


def test_k_beyond_all_evidence_equals_direct_v3():
    """K posterior a toda la evidencia => la capa es transparente:
    mismo resultado que assess(V3) directo sobre el evidence_set."""
    doc = EVIDENCE_SET.doc
    index = to_identity_index(doc)
    assertions = to_entitlement_assertions(doc)
    facts = doc.get("reported_facts", [])
    for case, probe in _ALL_PROBES:
        q = case["query"]
        direct = assess(
            case["entity_id"],
            index,
            activity=q["activity"],
            jurisdiction=q["jurisdiction"],
            as_of=probe["valid_at"],
            assertions=assertions,
            contracts=CONTRACTS,
            semantics_version="V3",
            reported_facts=facts,
            territorial_basis=q["territorial_basis"],
        )
        r = _run(case, {**probe, "known_at": "9999-12-31"})
        assert r["assessment"] == str(direct.assessment)
        assert r["reason"] == str(direct.reason)
        assert r["used_assertion_ids"] == [
            a["assertion_id"] for a in direct.assertions
        ]
        assert r["diagnostics"] == list(direct.diagnostics)
        assert r["evidence"]["excluded_after_known_at_assertion_ids"] == []
        assert r["evidence"]["excluded_after_known_at_fact_ids"] == []


def test_valid_at_known_at_require_calendar_date():
    """E1-R4: valid_at/known_at son YYYY-MM-DD; un timestamp no se
    reinterpreta silenciosamente."""
    case, probe = _ALL_PROBES[0]
    with pytest.raises(ValueError):
        _run(case, {**probe, "known_at": "2026-09-14T19:36:43Z"})
    with pytest.raises(ValueError):
        _run(case, {**probe, "valid_at": "2020-07-22T00:00:00Z"})
