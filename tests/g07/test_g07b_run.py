"""G0.7-B — Real assessment run.

El run `g0.7-001` ejecuta assess() sobre los 21 casos preregistrados
usando unicaente artefactos congelados (corpus, ledger, ruleset,
derivadas, casos). Estos tests fijan el resultado: replay offline
byte-identico, match contra el preregistro, trazabilidad completa de
cada conclusion hasta claims y snapshots, y los criterios de cierre
de G0.7 (sin inferencias legales no soportadas, sin negativos desde
ausencia, sin joins por identificador invalido).
"""
from __future__ import annotations

import json
import socket
import urllib.request
from pathlib import Path

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.assessment_run import run_assessment


ROOT = Path(__file__).parents[2]
RUN_PATH = ROOT / "fixtures" / "g0.7" / "runs" / "g0.7-001.json"
CASES_PATH = ROOT / "fixtures" / "g0.7" / "assessment-cases.json"
ARTIFACT_PATH = ROOT / "fixtures" / "g0.7" / "derived-assertions-g0.5-a-003.json"
LEDGER_PATH = ROOT / "fixtures" / "g0.6" / "claim-provenance-g0.5-a-003.json"


def _read(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def test_run_replays_offline_byte_identical(monkeypatch):
    """El run se reproduce solo con artefactos locales; la red no es una
    dependencia oculta del assessment."""
    def _blocked(*args, **kwargs):
        raise AssertionError("network access forbidden during G0.7-B replay")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)

    frozen = _read(RUN_PATH)
    meta = frozen["run"]
    replayed = run_assessment(
        ROOT,
        run_id=meta["run_id"],
        executed_at=meta["executed_at"],
        code_commit=meta["code_commit"],
    )
    assert canonical_json(replayed) + "\n" == RUN_PATH.read_text(encoding="utf-8")
    assert replayed["result_sha"] == frozen["result_sha"]
    assert all(meta["frozen_input_integrity"].values())


def test_run_matches_preregistered_expectations():
    run = _read(RUN_PATH)
    assert run["run"]["run_version"] == "FINREG_G07B_ASSESSMENT_V1"
    assert run["summary"]["cases_total"] == 21
    assert run["summary"]["mismatches"] == []
    assert run["summary"]["reason_mismatches"] == []
    assert run["summary"]["assessments"] == {
        "CONFIRMED_AUTHORISED": 8,
        "INDETERMINATE": 8,
        "NO_ENTITLEMENT_EVIDENCED": 5,
    }
    for case in run["cases"]:
        assert case["match"] is True
        assert case["reason_match"] is True


def test_every_assessment_traces_to_claims_and_snapshots():
    """100% de las aserciones usadas en conclusiones vuelven a claim_ids
    reales del ledger G0.6 y a snapshots sha256 congelados."""
    run = _read(RUN_PATH)
    artifact = _read(ARTIFACT_PATH)
    ledger = _read(LEDGER_PATH)
    claim_ids = {c["claim_id"] for c in ledger["claims"]}
    by_id = {a["assertion_id"]: a for a in artifact["assertions"]}

    for case in run["cases"]:
        assert set(case["used_assertion_ids"]) <= set(
            case["matching_assertion_ids"]
        )
        for claim_id in case["source_claim_ids"]:
            assert claim_id in claim_ids, (case["case_id"], claim_id)
        for evaluation in case["assertion_evaluations"]:
            for evidence in evaluation["evidence"]:
                assert evidence["raw_snapshot_sha256"]
                assert evidence["retrieved_at"] == "2026-09-13"
        # Multiplicidad de evidencia, no de derecho: los ids derivados
        # son los que el ruleset marco con derived_by.
        for assertion_id in case["derived_assertion_ids"]:
            assert by_id[assertion_id]["derived_by"] is not None


def test_closure_criteria_no_unsupported_inferences():
    """Criterios de cierre de G0.7 evaluados sobre el run real."""
    run = _read(RUN_PATH)
    cases = {c["case_id"]: c for c in run["cases"]}

    # 0 NOT_FOUND -> negative: la identidad no resuelta es INDETERMINATE.
    assert cases["G07-021"]["identity_resolution"] == "NOT_FOUND"
    assert cases["G07-021"]["assessment"] == "INDETERMINATE"

    # 0 negativos sin evidencia explicita: ningun caso produce
    # CONFIRMED_NOT_AUTHORISED (ninguna regla emite NOT_ENTITLED).
    assert not any(
        c["assessment"] == "CONFIRMED_NOT_AUTHORISED" for c in run["cases"]
    )

    # 0 expired entitlement -> global negative: el unico caso temporal
    # es caducidad de evidencia (stale), no expiracion juridica.
    assert cases["G07-020"]["assessment"] == "INDETERMINATE"
    assert cases["G07-020"]["reason"] == "ALL_EVIDENCE_STALE"

    # 0 silent conflict resolution: diagnostics conservan lo inadmisible.
    for case in run["cases"]:
        for diagnostic in case["diagnostics"]:
            assert diagnostic.startswith(
                ("stale_evidence:", "out_of_source_scope:", "not_in_effect:",
                 "agent_missing_principal:", "no_contract:", "identity:",
                 "unknown_scope_no_evidence:", "conflicting_legal_effects")
            )

    # Evidencia no interpretable => INDETERMINATE, nunca falso positivo.
    for case_id in ("G07-005", "G07-007", "G07-009", "G07-010", "G07-015", "G07-019"):
        case = cases[case_id]
        assert case["assessment"] == "INDETERMINATE"
        assert case["reason"] == "UNINTERPRETABLE_EVIDENCE"
        assert case["assertion_evaluations"], case_id
        assert all(
            e["source_legal_effect"] == "UNKNOWN"
            for e in case["assertion_evaluations"]
        )


def test_confirmed_cases_carry_full_evidence():
    """Cada CONFIRMED_AUTHORISED esta sostenido por aserciones ENTITLED
    con cadena completa: assertion -> rule -> claims -> snapshot."""
    run = _read(RUN_PATH)
    for case in run["cases"]:
        if case["assessment"] != "CONFIRMED_AUTHORISED":
            continue
        assert case["used_assertion_ids"], case["case_id"]
        assert case["source_claim_ids"], case["case_id"]
        for evaluation in case["assertion_evaluations"]:
            assert (
                evaluation["effective_legal_effect_at_as_of"]
                == "ENTITLED_TO_PROVIDE"
            )
            assert evaluation["reason"] == "IN_EFFECT"
            assert evaluation["legal_basis"].strip()
