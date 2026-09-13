"""Invariantes del corte G0.5-B sobre el run congelado."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
RUN_PATH = ROOT / "fixtures/g0.5/runs/g0.5-a-2026-09-13-001.json"
AUDIT_PATH = ROOT / "fixtures/g0.5/audit/g0.5-b-corpus-audit.json"
GLEIF_EVIDENCE_PATH = ROOT / "fixtures/g0.5/audit/gleif-lei-lookups-2026-09-13.json"
CORPUS_PATH = ROOT / "fixtures/g0.5/corpus/entities.json"
GROUND_TRUTH_PATH = ROOT / "fixtures/g0.5/corpus/ground-truth.json"
MANIFEST_PATH = ROOT / "fixtures/g0.5/sources/manifest.json"
ESMA_PATH = ROOT / "fixtures/g0.5/sources/raw/h7-esma-casps.csv"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _lei_check_digits(base18: str) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    converted = "".join(str(alphabet.index(char)) for char in base18) + "00"
    return f"{98 - (int(converted) % 97):02d}"


def test_g05b_audits_every_frozen_run_divergence_and_reconciles_expectations():
    run = _read(RUN_PATH)
    audit = _read(AUDIT_PATH)
    ground_truth = _read(GROUND_TRUTH_PATH)

    risks = {
        row["corpus_id"]: set(row.get("expected_contract_risks", []))
        for row in ground_truth["entity_expectations"]
    }
    entries = audit["divergence_audits"]
    by_id = {entry["divergence_id"]: entry for entry in entries}

    assert audit["audit"]["run_id"] == run["run"]["run_id"]
    assert audit["audit"]["run_result_sha"] == run["result_sha"]
    assert audit["audit"]["corpus_sha"] == "a3ed773"
    assert audit["audit"]["contracts_sha"] == "83754ec"
    assert audit["audit"]["source_baseline_sha"] == "1b6132b"
    assert audit["audit"]["assessment_execution"] == "NOT_RUN"
    assert audit["audit"]["ground_truth_changes"] == []

    assert len(entries) == len(run["divergences"]) == 40
    assert set(by_id) == set(range(1, 41))
    for index, divergence in enumerate(run["divergences"], start=1):
        entry = by_id[index]
        strict_expected = divergence["classification"] in risks[divergence["corpus_id"]]
        assert entry["run_expected"] == divergence["expected_in_ground_truth"]
        assert entry["strict_preregistered"] == strict_expected
        assert entry["cause"].startswith(
            ("PREREGISTERED_", "SOURCE_DATA_QUALITY")
        )

    mismatches = [
        index
        for index, divergence in enumerate(run["divergences"], start=1)
        if divergence["expected_in_ground_truth"]
        != (
            divergence["classification"] in risks[divergence["corpus_id"]]
        )
    ]
    assert mismatches == [4, 6, 11, 13, 15, 19, 21, 23]
    controls = audit["controls"]
    assert controls["divergences_audited"] == 40
    assert controls["unclassified_divergences"] == 0
    assert controls["strict_preregistered_divergences"] == 31
    assert controls["strict_unexpected_divergences"] == 9
    assert controls["run_recorded_unexpected_divergences"] == 1
    assert controls["run_expectation_annotation_mismatches"] == 8


def test_g05b_preserves_and_blocks_invalid_lei_values():
    run = _read(RUN_PATH)
    audit = _read(AUDIT_PATH)
    findings = {row["corpus_id"]: row for row in audit["identifier_findings"]}
    run_attempts = {
        attempt["corpus_id"]: attempt
        for attempt in run["attempts"]
        if attempt["source"] == "ESMA_MICA_REGISTER"
        and attempt["corpus_id"] in findings
    }
    source_rows = {}
    with ESMA_PATH.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["ae_lei"] in {finding["raw_value"] for finding in findings.values()}:
                source_rows[row["ae_lei"]] = row

    assert set(findings) == {"G05-012", "G05-015"}
    for corpus_id, finding in findings.items():
        raw = finding["raw_value"]
        parsed = run_attempts[corpus_id]["parse"]["record"]["observed"]["lei"]
        assert source_rows[raw]["ae_lei"] == raw
        assert finding["parsed_value"] == parsed == raw
        assert list(finding["raw_value"]) == list(finding["parsed_value"])
        assert finding["differing_positions"] == []
        assert finding["normalization_changed"] is False
        assert finding["ascii_alphanumeric"] is True
        assert finding["validator_result"] == "INVALID"
        assert finding["raw_record_sha256"] == run_attempts[corpus_id]["parse"]["record"][
            "raw_record_sha256"
        ]
        assert finding["resolution"]["raw_identifier"] == "PRESERVED_EXACT"
        assert finding["resolution"]["automatic_lei_join"] == "FORBIDDEN"
        assert finding["resolution"]["identity_resolution"] == "IDENTITY_GAP"
        assert finding["resolution"]["alternate_identifier_available"] is False

        if corpus_id == "G05-012":
            assert len(raw) == 19
            assert finding["control_check"] == "NOT_EVALUABLE_INVALID_LENGTH"
            assert finding["expected_check_digits"] is None
        else:
            assert len(raw) == 20
            assert finding["provided_last_two_chars"] == "41"
            assert finding["expected_check_digits"] == _lei_check_digits(raw[:18]) == "49"
            assert finding["control_check"] == "MISMATCH"


def test_g05b_external_evidence_and_frozen_snapshot_hashes_are_consistent():
    audit = _read(AUDIT_PATH)
    gleif = _read(GLEIF_EVIDENCE_PATH)
    manifest = {
        item["snapshot_file"]: item
        for item in _read(MANIFEST_PATH)["snapshots"]
    }

    evidence_entry = next(
        row for row in audit["source_evidence"] if "evidence_file" in row
    )
    assert evidence_entry["sha256"] == hashlib.sha256(
        GLEIF_EVIDENCE_PATH.read_bytes()
    ).hexdigest()
    assert gleif["not_part_of_g05a_inputs"] is True
    for query in gleif["queries"]:
        assert query["http_status"] == 404
        assert query["response_body_sha256"] == hashlib.sha256(
            query["response_body"].encode("utf-8")
        ).hexdigest()

    for row in audit["source_evidence"]:
        if "snapshot_file" not in row:
            continue
        assert row["sha256"] == manifest[row["snapshot_file"]]["sha256"]


def test_g05b_does_not_introduce_assessment_or_identity_joins():
    run = _read(RUN_PATH)
    audit = _read(AUDIT_PATH)

    assert all(
        attempt["assessment"] == {"status": "NOT_RUN", "assertions": []}
        for attempt in run["attempts"]
    )
    assert all(
        attempt["identity"].get("cross_source_join")
        not in {"EXACT", "AUTOMATIC", "FUZZY"}
        for attempt in run["attempts"]
    )
    assert audit["controls"]["silent_fuzzy_joins"] == 0
    assert audit["controls"]["unsupported_identifier_joins"] == 0
    assert audit["controls"]["source_defects_silently_corrected"] == 0
    assert audit["controls"]["ground_truth_edits_without_primary_evidence"] == 0
