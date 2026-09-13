"""Invariantes del cierre G0.5-C: remediación del runner, adjudicación de
las omisiones de preregistro y diagnósticos LEI versionados.

Frontera explícita del hallazgo 1 -> 9: el defecto del runner sólo afecta
a la métrica ``unexpected_divergences`` registrada por G0.5-A. Los 30/30
MATCH y la extracción determinista se auditaron de forma independiente en
G0.5-B y no quedan invalidados.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from finreg_es.canonical import canonical_json


ROOT = Path(__file__).parents[2]
RUN_V1_PATH = ROOT / "fixtures" / "g0.5" / "runs" / "g0.5-a-2026-09-13-001.json"
RUN_V2_PATH = ROOT / "fixtures" / "g0.5" / "runs" / "g0.5-a-2026-09-13-002.json"
AUDIT_PATH = ROOT / "fixtures" / "g0.5" / "audit" / "g0.5-b-corpus-audit.json"
CORPUS_PATH = ROOT / "fixtures" / "g0.5" / "corpus" / "entities.json"
GROUND_TRUTH_PATH = ROOT / "fixtures" / "g0.5" / "corpus" / "ground-truth.json"
MANIFEST_PATH = ROOT / "fixtures" / "g0.5" / "sources" / "manifest.json"

OMISSION_DIVERGENCE_IDS = [4, 6, 11, 13, 15, 19, 21, 23]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _result_sha(result: dict) -> str:
    without_hash = {key: value for key, value in result.items() if key != "result_sha"}
    return hashlib.sha256(canonical_json(without_hash).encode("utf-8")).hexdigest()


def _expected_risks() -> dict[str, set[str]]:
    ground_truth = _read(GROUND_TRUTH_PATH)
    return {
        row["corpus_id"]: set(row.get("expected_contract_risks", []))
        for row in ground_truth["entity_expectations"]
    }


def _strict_unexpected(run: dict, risks: dict[str, set[str]]) -> list[int]:
    return [
        index
        for index, divergence in enumerate(run["divergences"], start=1)
        if divergence["classification"] not in risks[divergence["corpus_id"]]
    ]


def _annotation_mismatches(run: dict, risks: dict[str, set[str]]) -> list[int]:
    return [
        index
        for index, divergence in enumerate(run["divergences"], start=1)
        if divergence["expected_in_ground_truth"]
        != (divergence["classification"] in risks[divergence["corpus_id"]])
    ]


def test_g05c_original_run_data_is_immutable_with_known_defective_metric():
    """G0.5-A RESULT DATA: immutable; RUNNER METRIC: known defective.

    El run congelado sigue diciendo ``unexpected=1`` y conserva la misma
    anotación defectuosa; no se reescribe. Su ``result_sha`` sigue
    verificándose, lo que prueba que el artefacto no ha mutado.
    """
    run = _read(RUN_V1_PATH)
    risks = _expected_risks()

    assert run["run"]["run_version"] == "FINREG_G05A_EXTRACTION_V1"
    assert "supersedes_run_id" not in run["run"]
    assert "expectation_annotation_rule" not in run["run"]
    assert run["summary"]["unexpected_divergences"] == 1
    assert run["summary"]["ground_truth_entities"] == {"MATCH": 30}
    assert run["result_sha"] == _result_sha(run)

    # La métrica defectuosa sigue siendo reproducible: las ocho filas cuya
    # clase no está preregistrada se anotaron como esperadas.
    assert _annotation_mismatches(run, risks) == OMISSION_DIVERGENCE_IDS
    assert _strict_unexpected(run, risks) == OMISSION_DIVERGENCE_IDS + [24]


def test_g05c_successor_run_reports_strict_unexpected_nine_on_same_inputs():
    """El run sucesor aplica la regla corregida sobre los mismos artefactos.

    Misma corpus_sha/contracts_sha/source_baseline, mismos snapshots y mismo
    ground truth; sólo cambia la anotación de expectativas.
    """
    original = _read(RUN_V1_PATH)
    run = _read(RUN_V2_PATH)
    risks = _expected_risks()

    assert run["run"]["run_version"] == "FINREG_G05A_EXTRACTION_V2"
    assert run["run"]["supersedes_run_id"] == "g0.5-a-2026-09-13-001"
    assert (
        run["run"]["expectation_annotation_rule"]
        == "CLASSIFICATION_IN_ENTITY_EXPECTED_CONTRACT_RISKS"
    )
    for field in (
        "corpus_sha",
        "contracts_sha",
        "source_baseline_sha",
        "corpus_manifest_sha256",
        "ground_truth_sha256",
        "source_snapshot_sha",
    ):
        assert run["run"][field] == original["run"][field]

    assert run["summary"]["entities_attempted"] == 30
    assert run["summary"]["source_attempts"] == 34
    assert run["summary"]["divergences_total"] == 40
    assert run["summary"]["ground_truth_entities"] == {"MATCH": 30}
    assert run["summary"]["unexpected_divergences"] == 9
    assert run["result_sha"] == _result_sha(run)

    # Regla corregida: la anotación ya no tiene discrepancias con el
    # preregistro y el unexpected estricto coincide con el valor auditado.
    assert _annotation_mismatches(run, risks) == []
    assert _strict_unexpected(run, risks) == OMISSION_DIVERGENCE_IDS + [24]


def test_g05c_successor_run_differs_from_original_only_in_expectation_flags():
    """El sucesor es el mismo resultado con la anotación corregida: la
    secuencia de divergencias es idéntica salvo los ocho flags defectuosos.
    """
    original = _read(RUN_V1_PATH)
    run = _read(RUN_V2_PATH)

    identity_of = [
        (
            row["corpus_id"],
            row["source"],
            row["snapshot_file"],
            row["layer"],
            row["classification"],
            row["reason"],
        )
        for row in run["divergences"]
    ]
    original_identity_of = [
        (
            row["corpus_id"],
            row["source"],
            row["snapshot_file"],
            row["layer"],
            row["classification"],
            row["reason"],
        )
        for row in original["divergences"]
    ]
    assert identity_of == original_identity_of

    flag_differences = [
        index
        for index, (before, after) in enumerate(
            zip(original["divergences"], run["divergences"]), start=1
        )
        if before["expected_in_ground_truth"] != after["expected_in_ground_truth"]
    ]
    assert flag_differences == OMISSION_DIVERGENCE_IDS
    for index in flag_differences:
        assert original["divergences"][index - 1]["expected_in_ground_truth"] is True
        assert run["divergences"][index - 1]["expected_in_ground_truth"] is False


def test_g05c_audited_value_nine_matches_successor_recomputation():
    """G0.5-B AUDITED VALUE: 9 — el sucesor reproduce el valor auditado."""
    audit = _read(AUDIT_PATH)
    run = _read(RUN_V2_PATH)
    risks = _expected_risks()

    assert audit["controls"]["strict_unexpected_divergences"] == 9
    assert audit["controls"]["run_recorded_unexpected_divergences"] == 1
    assert audit["controls"]["run_expectation_annotation_mismatches"] == 8
    assert len(_strict_unexpected(run, risks)) == 9
    assert {
        (row["corpus_id"], row["reason"])
        for row in run["divergences"]
        if not row["expected_in_ground_truth"]
    } == {
        ("G05-004", "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING"),
        ("G05-004", "ENT_AUT_DATE_HAS_NO_SAFE_STATUS_MAPPING"),
        ("G05-009", "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING"),
        ("G05-009", "ENT_AUT_DATE_HAS_NO_SAFE_STATUS_MAPPING"),
        ("G05-011", "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING"),
        ("G05-012", "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING"),
        ("G05-012", "ENT_AUT_DATE_HAS_NO_SAFE_STATUS_MAPPING"),
        ("G05-014", "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING"),
        ("G05-015", "LEI_CHECKSUM_INVALID"),
    }


def test_g05c_frozen_inputs_keep_their_audited_hashes():
    """Corpus, ground truth y manifest conservan los hashes del audit."""
    audit = _read(AUDIT_PATH)["audit"]
    assert hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest() == audit[
        "corpus_file_sha256"
    ]
    assert hashlib.sha256(GROUND_TRUTH_PATH.read_bytes()).hexdigest() == audit[
        "ground_truth_sha256"
    ]
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == audit[
        "source_manifest_sha256"
    ]
