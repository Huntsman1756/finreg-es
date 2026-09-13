"""Invariantes del primer run G0.5-A sobre el corpus preregistrado."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from finreg_es.canonical import canonical_json


ROOT = Path(__file__).parents[2]
RUN = ROOT / "fixtures" / "g0.5" / "runs" / "g0.5-a-2026-09-13-001.json"


def _read_run() -> dict:
    return json.loads(RUN.read_text(encoding="utf-8"))


def test_g05a_run_is_reproducible_and_does_not_run_assessment():
    result = _read_run()
    run = result["run"]
    summary = result["summary"]

    assert run["corpus_sha"] == "a3ed773"
    assert run["contracts_sha"] == "83754ec"
    assert run["source_baseline_sha"] == "1b6132b"
    assert run["assessment_execution"] == "NOT_RUN"
    assert summary["entities_attempted"] == 30
    assert summary["source_attempts"] == 34
    assert summary["ground_truth_entities"] == {"MATCH": 30}
    assert summary["unexpected_divergences"] == 1

    without_hash = {key: value for key, value in result.items() if key != "result_sha"}
    assert result["result_sha"] == hashlib.sha256(
        canonical_json(without_hash).encode("utf-8")
    ).hexdigest()


def test_g05a_attempts_have_independent_layers_and_provenance():
    result = _read_run()
    allowed_classes = {
        "FETCH_ERROR",
        "PARSE_ERROR",
        "IDENTITY_ERROR",
        "IDENTITY_GAP",
        "SOURCE_CONTRACT_GAP",
        "COVERAGE_GAP",
        "SEMANTICS_GAP",
        "GROUND_TRUTH_ERROR",
        "SOURCE_CHANGED",
        "EXTRACTION_BUG",
    }

    assert all(attempt["fetch"]["status"] == "FETCH_OK" for attempt in result["attempts"])
    assert all(attempt["parse"]["status"] == "PARSE_OK" for attempt in result["attempts"])
    assert all(attempt["assessment"] == {"status": "NOT_RUN", "assertions": []} for attempt in result["attempts"])
    assert all(attempt["source_snapshot_sha"] for attempt in result["attempts"])
    assert all(
        attempt["parse"]["record"]["raw_record_sha256"]
        for attempt in result["attempts"]
    )
    assert all(
        divergence["classification"] in allowed_classes
        for divergence in result["divergences"]
    )
    assert {
        (divergence["corpus_id"], divergence["reason"])
        for divergence in result["divergences"]
        if not divergence.get("expected_in_ground_truth", False)
    } == {
        ("G05-015", "LEI_CHECKSUM_INVALID")
    }
