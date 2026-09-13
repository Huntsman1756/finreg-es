"""Integridad del corpus real G0.5; no ejecuta extractores regulatorios."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[2]
SOURCES = ROOT / "fixtures" / "g0.5" / "sources"
CORPUS = ROOT / "fixtures" / "g0.5" / "corpus"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_corpus_has_30_distinct_entities_and_ground_truth_rows():
    entities = _read_json(CORPUS / "entities.json")
    ground_truth = _read_json(CORPUS / "ground-truth.json")
    source_manifest = _read_json(SOURCES / "manifest.json")

    rows = entities["entities"]
    expected = ground_truth["entity_expectations"]
    source_files = {item["snapshot_file"] for item in source_manifest["snapshots"]}

    assert entities["entity_count"] == 30
    assert len(rows) == 30
    assert len({row["corpus_id"] for row in rows}) == 30
    assert len({row["legal_name"] for row in rows}) == 30
    assert {row["corpus_id"] for row in rows} == {
        row["corpus_id"] for row in expected
    }
    assert all(
        source["snapshot_file"] in source_files
        for row in rows
        for source in row["source_records"]
    )


def test_primary_snapshots_match_manifest_and_key_shapes():
    source_manifest = _read_json(SOURCES / "manifest.json")
    for item in source_manifest["snapshots"]:
        path = SOURCES / item["snapshot_file"]
        payload = path.read_bytes()
        assert len(payload) == item["bytes"], item["snapshot_file"]
        assert hashlib.sha256(payload).hexdigest() == item["sha256"], item[
            "snapshot_file"
        ]

    with (SOURCES / "raw" / "h7-esma-casps.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        esma_rows = list(csv.DictReader(stream))
    esma_es = [row for row in esma_rows if row["ae_homeMemberState"] == "ES"]
    assert len(esma_es) == 15
    assert all(row["ae_lei"] for row in esma_es)

    psd2_metadata = _read_json(SOURCES / "raw" / "h4-eba-psd2-metadata.json")[0]
    entity_types = {
        row["EntityType"] for row in psd2_metadata["PropertiesOfEntityTypes"]
    }
    property_codes = {
        row["PropertyCode"] for row in psd2_metadata["PropertyDefinition"]
    }
    assert "PSD_AISP" in entity_types
    assert {"ENT_COD", "ENT_NAT_REF_COD", "ENT_AUT", "ENT_SER"} <= property_codes


def test_ground_truth_never_turns_presence_into_aggregate_negative():
    ground_truth = _read_json(CORPUS / "ground-truth.json")
    for expectation in ground_truth["source_expectations"]:
        assert expectation["expected_aggregate_assessment"] == "NOT_RUN"
        assert expectation["negative_inference"].startswith("BLOCKED_")
