"""G4-G1 — public projection gate tests (preregistered cases P01–P13).

Contract: docs/gates/G4-G1-PREREG.md. The builder must emit the read
model deterministically from frozen evidence, with zero false adverse
attribution and no invented dates.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "projections/public"
SCHEMA = json.loads(
    (ROOT / "schemas/public/entity-v1.schema.json").read_text(encoding="utf-8"))


def load(eid):
    return json.loads((OUT / "entities" / f"{eid}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def built():
    subprocess.run([sys.executable, "tools/g4/build_projection.py"],
                   cwd=ROOT, check=True, capture_output=True)
    return OUT


def test_deterministic_rebuild(built):
    """P13: two consecutive builds → identical bytes + stable bundle hash."""
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(OUT.rglob("*.json"))}
    subprocess.run([sys.executable, "tools/g4/build_projection.py"],
                   cwd=ROOT, check=True, capture_output=True)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(OUT.rglob("*.json"))}
    assert before == after


def test_all_entities_validate_schema(built):
    for p in sorted((OUT / "entities").glob("*.json")):
        jsonschema.validate(json.loads(p.read_text(encoding="utf-8")), SCHEMA)


def test_entity_count(built):
    assert len(list((OUT / "entities").glob("*.json"))) == 20


def test_p01_anti_case_alantrafx_not_attributed(built):
    """The webtrader.alantrafx.com clone targets reg 245 (ALANTRA EQUITIES),
    never reg 258. Zero false adverse attribution."""
    e = load("esi-a87515540")
    names = [w["warned_name"].lower() for w in e["regulatory_record"]["impersonations"]]
    assert not any("alantrafx" in n for n in names)
    for w in e["regulatory_record"]["impersonations"]:
        assert w["legitimate_entity"]["registry_number"] == "258"
        assert w["relation"] == "IMPERSONATES"


def test_p02_abante_impersonations_by_registry_number(built):
    e = load("esi-a83217281")
    imp = e["regulatory_record"]["impersonations"]
    assert len(imp) >= 1
    assert all(w["legitimate_entity"]["registry_number"] == "194" for w in imp)
    assert all(w["legitimate_entity"]["relation"] == "MENTIONED_AS_LEGITIMATE_ENTITY"
               for w in imp)


def test_p03_sanction_document_derivation(built):
    e = load("sgiic-a28867000")
    s = e["regulatory_record"]["sanctions"]
    assert len(s) == 1
    assert s[0]["basis"] == "OFFICIAL_DOCUMENT_DERIVATION"
    assert s[0]["register_date"] == "17/07/2026"
    fs_states = [t for t in e["timeline"] if t["kind"] == "OFFICIAL_AS_OF_STATE"]
    assert fs_states, "SAN-1 must carry fs as-of states"


def test_p04_no_invented_dates_on_observed_change(built):
    """Any OBSERVED_CHANGE must carry an interval [a, b], never a point date."""
    for p in sorted((OUT / "entities").glob("*.json")):
        for t in json.loads(p.read_text(encoding="utf-8"))["timeline"]:
            if t["kind"] == "OBSERVED_CHANGE":
                assert isinstance(t["date_or_interval"], list), (p.name, t)


def test_p05_esi_history_explicit_absence(built):
    for eid in ["esi-a87515540", "esi-b22526768", "esi-a64911100", "esi-a83217281"]:
        assert load(eid)["coverage"]["history"] == "NO HISTORICAL EVIDENCE", eid
    e = load("esi-a87515540")
    assert e["coverage"]["permission"] == "COVERED"
    svc = e["permissions"][0]
    assert svc["instruments"] and svc["basis"] == "OFFICIAL_AS_OF_STATE"


def test_p06_bde_dated_facts(built):
    e = load("ede-6702")
    kinds = {t["kind"] for t in e["timeline"]}
    assert "EXPLICIT_OFFICIAL_EVENT" in kinds
    assert e["coverage"]["permission"] == "COVERED"
    assert isinstance(e["locations"]["passporting"], list) and e["locations"]["passporting"]


def test_p07_bde5_date_conflict_preserved(built):
    e = load("ede-6712")
    dates = {r["date"] for r in e["registrations"]}
    assert "14/01/2019" in dates and "2019-05-27" in dates


def test_p08_pecunia_notice_is_candidate_only(built):
    e = load("ede-6707")
    assert e["regulatory_record"]["direct_warnings"] == []
    assert e["regulatory_record"]["impersonations"] == []
    cand = e["regulatory_record"]["candidates"]
    assert any("PECUNIACO" in c["warned_name"].upper() for c in cand)


def test_p09_ins_identity_consumed_from_upstream(built):
    e = load("ins-c0001")
    assert e["identity"]["resolution"] == "EXACT"
    schemes = {i["scheme"] for i in e["identity"]["identifiers"]}
    assert {"dgsfp:clave", "es:nif", "lei"} <= schemes
    assert e["identity"]["legal_name"] != f"DGSFP C0001"


def test_p10_ins5_cancelled_bounded(built):
    e = load("ins-e0006")
    assert e["status"]["value"] == "DEREGISTERED"
    assert e["status"]["source_value"] == "Cancelada"
    assert e["status"]["as_of"] != "UNKNOWN"


def test_p11_coverage_denominators(built):
    dims = {"identity", "registration", "permission", "history", "sanction",
            "warning", "branch", "passport", "provenance"}
    for p in sorted((OUT / "entities").glob("*.json")):
        cov = json.loads(p.read_text(encoding="utf-8"))["coverage"]
        assert dims <= set(cov), p.name


def test_p12_no_rating_fields(built):
    banned = {"rating", "score", "rank", "ranking", "recommendation",
              "risk_score", "reputation"}
    for p in OUT.rglob("*.json"):
        obj = json.loads(p.read_text(encoding="utf-8"))
        keys = set()
        def walk(o):
            if isinstance(o, dict):
                keys.update(k.lower() for k in o)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(obj)
        assert not (keys & banned), (p.name, keys & banned)


def test_changes_classification(built):
    changes = json.loads((OUT / "changes.json").read_text(encoding="utf-8"))
    classes = {c["class"] for c in changes}
    assert classes <= {"OFFICIAL_EVENT", "RECONSTRUCTED_HISTORICAL",
                       "OBSERVED_CURRENT", "BACKFILL"}


def test_manifest_bundle(built):
    man = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert man["schema"] == "regulatory-record-public/v1"
    assert man["entity_count"] == 20
    assert len(man["bundle_sha256"]) == 64
