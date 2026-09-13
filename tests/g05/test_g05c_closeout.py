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
RUN_V3_PATH = ROOT / "fixtures" / "g0.5" / "runs" / "g0.5-a-2026-09-13-003.json"
AUDIT_PATH = ROOT / "fixtures" / "g0.5" / "audit" / "g0.5-b-corpus-audit.json"
RESOLUTION_PATH = (
    ROOT / "fixtures" / "g0.5" / "audit" / "g0.5-b-preregistration-resolution.json"
)
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


def test_g05c_resolution_adjudicates_every_strict_unexpected_divergence():
    """G05-B-F04: las 9 divergencias estrictamente inesperadas quedan
    adjudicadas sin tocar el ground truth congelado."""
    resolution = _read(RESOLUTION_PATH)
    run = _read(RUN_V1_PATH)
    risks = _expected_risks()
    header = resolution["resolution"]

    assert header["status"] == "RESOLVED"
    assert header["audit_finding_id"] == "G05-B-F04"
    assert header["run_id"] == "g0.5-a-2026-09-13-001"
    assert header["successor_run_id"] == "g0.5-a-2026-09-13-002"
    assert header["strict_unexpected_total"] == 9
    assert header["ground_truth_changes"] == []
    assert header["ground_truth_sha256"] == hashlib.sha256(
        GROUND_TRUTH_PATH.read_bytes()
    ).hexdigest()

    taxonomy = {row["code"] for row in resolution["classification_taxonomy"]}
    assert {
        "PREREGISTRATION_OMISSION",
        "SOURCE_CHANGED_AFTER_FREEZE",
        "GROUND_TRUTH_GAP",
        "CONTRACT_INTERPRETATION_GAP",
        "EXTRACTION_UNEXPECTED",
    } <= taxonomy

    entries = resolution["omissions"] + resolution["residual_unexpected"]
    by_divergence = {entry["divergence_id"]: entry for entry in entries}
    assert sorted(by_divergence) == _strict_unexpected(run, risks)
    for divergence_id, entry in by_divergence.items():
        divergence = run["divergences"][divergence_id - 1]
        assert entry["entity_id"] == divergence["corpus_id"]
        assert entry["missing_expected_risk"] == divergence["classification"]
        assert entry["missing_expected_risk"] not in risks[entry["entity_id"]]
        assert entry["divergence_reason"] == divergence["reason"]
        assert entry["classification"] in taxonomy
        assert entry["impact_on_assessment"] == "NONE_ASSESSMENT_NOT_RUN"


def test_g05c_eight_omissions_prove_expected_list_incomplete_not_data():
    """Las ocho omisiones son PREREGISTRATION_OMISSION: cada riesgo omitido
    estaba preregistrado en otra entidad con la misma fuente, lo que
    demuestra que existía en el momento del freeze."""
    resolution = _read(RESOLUTION_PATH)
    corpus = _read(CORPUS_PATH)
    risks = _expected_risks()
    sources_by_entity = {
        row["corpus_id"]: {rec["source"] for rec in row["source_records"]}
        for row in corpus["entities"]
    }

    omissions = resolution["omissions"]
    assert len(omissions) == 8
    assert {e["divergence_id"] for e in omissions} == set(OMISSION_DIVERGENCE_IDS)
    for entry in omissions:
        assert entry["classification"] == "PREREGISTRATION_OMISSION"
        assert entry["would_have_been_expected_if_known"] is True
        assert entry["impact_on_ground_truth"] == "NONE_EXPECTED_LIST_NONEXHAUSTIVE"
        siblings = [
            corpus_id
            for corpus_id, sources in sources_by_entity.items()
            if corpus_id != entry["entity_id"]
            and entry["source"] in sources
            and entry["missing_expected_risk"] in risks[corpus_id]
        ]
        assert siblings, entry


def test_g05c_g05_015_residual_is_source_data_quality_preserved():
    """El noveno inesperado estricto no es una omisión: es el defecto de
    fuente G05-015, ya adjudicado por el audit como SOURCE_DATA_QUALITY."""
    resolution = _read(RESOLUTION_PATH)
    residual = resolution["residual_unexpected"]
    assert len(residual) == 1
    entry = residual[0]
    assert entry["entity_id"] == "G05-015"
    assert entry["classification"] == "EXTRACTION_UNEXPECTED"
    assert entry["root_cause_category"] == "SOURCE_DATA_QUALITY"
    assert entry["audit_finding_id"] == "G05-B-F02"
    assert entry["disposition"] == "RETAIN_RAW_BLOCK_INVALID_LEI_JOIN"
    assert entry["status"] == "RESOLVED_PRESERVED"


def test_g05c_lei_diagnostics_versioned_in_v3_run():
    """G05-B-F03: el extractor V3 separa INVALID_LENGTH de
    INVALID_CHECK_DIGITS sin tocar la validez agregada ni los flags."""
    run = _read(RUN_V3_PATH)
    previous = _read(RUN_V2_PATH)
    original = _read(RUN_V1_PATH)
    risks = _expected_risks()

    assert run["run"]["run_version"] == "FINREG_G05A_EXTRACTION_V3"
    assert run["run"]["supersedes_run_id"] == "g0.5-a-2026-09-13-002"
    for field in (
        "corpus_sha",
        "contracts_sha",
        "source_baseline_sha",
        "corpus_manifest_sha256",
        "ground_truth_sha256",
        "source_snapshot_sha",
    ):
        assert run["run"][field] == original["run"][field]
    assert run["summary"]["unexpected_divergences"] == 9
    assert run["summary"]["divergences_total"] == 40
    assert run["summary"]["ground_truth_entities"] == {"MATCH": 30}
    assert run["result_sha"] == _result_sha(run)
    assert _annotation_mismatches(run, risks) == []
    assert _strict_unexpected(run, risks) == OMISSION_DIVERGENCE_IDS + [24]

    # Fuera de las dos divergencias LEI, el resultado es identico al V2.
    for index, (before, after) in enumerate(
        zip(previous["divergences"], run["divergences"]), start=1
    ):
        if index in {18, 24}:
            continue
        assert before == after

    lei_divergences = {
        row["corpus_id"]: row
        for row in run["divergences"]
        if row["reason"] == "LEI_INVALID"
    }
    assert set(lei_divergences) == {"G05-012", "G05-015"}
    assert lei_divergences["G05-012"]["lei_diagnostic"] == "INVALID_LENGTH"
    assert lei_divergences["G05-015"]["lei_diagnostic"] == "INVALID_CHECK_DIGITS"


def test_g05c_invalid_lei_values_preserved_and_never_joined():
    """Regla de identidad: LEI invalido -> valor raw preservado, sin
    reparacion silenciosa, sin join automatico por LEI y sin promover a
    AMBIGUOUS por el solo checksum."""
    run = _read(RUN_V3_PATH)
    expected_raw = {
        "G05-012": "59800G0P3PV13KLX615",
        "G05-015": "549300746K71T6YJCV41",
    }
    for attempt in run["attempts"]:
        corpus_id = attempt["corpus_id"]
        if attempt["source"] != "ESMA_MICA_REGISTER":
            continue
        identity = attempt["identity"]
        observed = attempt["parse"]["record"]["observed"]
        assert observed["lei"] == identity["identifier"]
        assert observed["lei_valid"] == (
            observed["lei_diagnostic"] == "VALID"
        )
        if corpus_id in expected_raw:
            assert identity["identifier"] == expected_raw[corpus_id]
            assert identity["status"] == "IDENTITY_GAP"
            assert identity["identifier_valid"] is False
            assert identity["identifier_diagnostic"] in {
                "INVALID_LENGTH",
                "INVALID_CHECK_DIGITS",
            }
        assert identity["cross_source_join"] not in {
            "EXACT",
            "AUTOMATIC",
            "FUZZY",
        }
    assert not any(
        "AMBIGUOUS" in divergence.get("reason", "")
        or "AMBIGUOUS" in divergence.get("classification", "")
        for divergence in run["divergences"]
    )
