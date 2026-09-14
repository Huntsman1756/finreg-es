"""G1-D3 — Corpus territorial preregistrado: los anclas son reales.

Cada entrada del corpus D3 declara (source, snapshot_file, sha256,
record_key). Este test verifica que el snapshot existe y que su sha256
coincide con el declarado — el preregistro no puede apuntar a fuentes
inexistentes — y que el record_key resuelve a una fila real dentro del
snapshot congelado.

Cobertura estructural adicional:
  - toda referencia case_id del corpus existe en assessment-cases-g1-d
  - toda entidad de caso tiene entrada de corpus (y viceversa)
  - nada positivo esperado para LIMITED_LP / mutations (H12-E, no
    synthetic positive route)
"""
from __future__ import annotations

import hashlib
import json
import zipfile
import re
import csv
from pathlib import Path

ROOT = Path(__file__).parents[2]
G1 = ROOT / "fixtures" / "g1"
CORPUS = json.loads(
    (G1 / "sources" / "extracted" / "g1-d-territorial-corpus.json").read_text(
        encoding="utf-8"
    )
)
CASES = json.loads(
    (G1 / "assessment-cases-g1-d.json").read_text(encoding="utf-8")
)

_SNAPSHOT_DIRS = [G1 / "sources", ROOT / "fixtures" / "g0.5" / "sources"]


def _snapshot_bytes(snapshot_file: str) -> bytes:
    for d in _SNAPSHOT_DIRS:
        p = d / snapshot_file
        if p.exists():
            return p.read_bytes()
    raise AssertionError(f"snapshot not found: {snapshot_file}")


def test_corpus_snapshot_sha256_anchors():
    for ent in CORPUS["entities"]:
        for rec in ent["source_records"]:
            raw = _snapshot_bytes(rec["snapshot_file"])
            assert hashlib.sha256(raw).hexdigest() == rec["snapshot_sha256"], (
                ent["corpus_id"], rec["snapshot_file"]
            )


def _eba_record(entity_code: str, entity_type: str) -> dict | None:
    zf = zipfile.ZipFile(_snapshot_path("raw/h4-eba-psd2-20260913.zip"))
    data = json.loads(zf.read(zf.namelist()[0]))[1]
    for e in data:
        if e["EntityCode"] == entity_code and e["EntityType"] == entity_type:
            return e
    return None


def _snapshot_path(snapshot_file: str) -> Path:
    for d in _SNAPSHOT_DIRS:
        p = d / snapshot_file
        if p.exists():
            return p
    raise AssertionError(snapshot_file)


def _bde_xlsx_has_codigo(path: Path, codigo: str) -> bool:
    zf = zipfile.ZipFile(path)
    x = zf.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
    return bool(
        re.search(
            rf'<c r="A\d+"[^>]*>.*?<t[^>]*>{re.escape(codigo)}</t>',
            x,
            re.S,
        )
    )


def _esma_casp_row(lei: str) -> dict | None:
    with open(
        _snapshot_path("raw/esma-mica-casps.csv"), encoding="utf-8-sig",
        errors="replace",
    ) as fh:
        for row in csv.DictReader(fh):
            if row.get("ae_lei") == lei:
                return row
    return None


def test_eba_records_resolve():
    eba_recs = [
        rec
        for ent in CORPUS["entities"]
        for rec in ent["source_records"]
        if rec["source"] == "EBA_PSD2_REGISTER"
    ]
    assert eba_recs
    for rec in eba_recs:
        rk = rec["record_key"]
        found = _eba_record(rk["EntityCode"], rk["EntityType"])
        assert found is not None, rk
        for field, expected in rec["fields"].items():
            if field in ("Services_ES", "Services_ES_LPS", "Services_ES_branch"):
                svcs = found.get("Services", [])
                es = [s["ES"] for s in svcs if "ES" in s]
                flat = [c for grp in es for c in (grp if isinstance(grp, list) else [grp])]
                assert set(expected) <= set(flat), (rk, expected, flat)
            elif field == "role":
                continue
            else:
                props = {
                    k: v
                    for p in found.get("Properties", [])
                    for k, v in p.items()
                }
                assert str(props.get(field, "")).upper() == str(
                    expected
                ).upper() or expected in str(props.get(field, "")), (
                    rk, field, expected, props.get(field)
                )


def test_bde_records_resolve():
    bde_recs = [
        rec
        for ent in CORPUS["entities"]
        for rec in ent["source_records"]
        if rec["source"] == "BDE_REGISTRO_SERVICIOS_PAGO"
    ]
    assert len(bde_recs) == 2
    for rec in bde_recs:
        assert _bde_xlsx_has_codigo(
            _snapshot_path(rec["snapshot_file"]), rec["record_key"]["codigo_be"]
        ), rec


def test_esma_records_resolve():
    esma_recs = [
        rec
        for ent in CORPUS["entities"]
        for rec in ent["source_records"]
        if rec["source"] == "ESMA_MICA_REGISTER"
    ]
    assert len(esma_recs) == 3
    for rec in esma_recs:
        row = _esma_casp_row(rec["record_key"]["ae_lei"])
        assert row is not None, rec
        if rec["fields"].get("ac_serviceCode_cou_contains_ES"):
            assert "ES" in row["ac_serviceCode_cou"].split("|")
            assert row["ae_homeMemberState"] != "ES"


def test_case_corpus_referential_integrity():
    corpus_ids = {e["corpus_id"] for e in CORPUS["entities"]}
    corpus_case_ids = {
        cid for e in CORPUS["entities"] for cid in e["case_ids"]
    }
    case_ids = {c["case_id"] for c in CASES["cases"]}
    assert corpus_case_ids == case_ids
    for c in CASES["cases"]:
        assert c["entity_id"] in corpus_ids, c["case_id"]


def test_no_synthetic_positive_route():
    """H12-E + 'no synthetic positive route': nada sintetico puede
    esperar CONFIRMED_ENTITLED."""
    synthetic_entities = {
        e["corpus_id"] for e in CORPUS["entities"] if e.get("synthetic")
    }
    mutated_cases = {"G1D-09", "G1D-10"}
    for c in CASES["cases"]:
        if c["entity_id"] in synthetic_entities or c["case_id"] in mutated_cases:
            assert c["expected_assessment"] != "CONFIRMED_ENTITLED", c["case_id"]
            assert c["expected_territorial_basis"] == []
            assert c["expected_legal_basis"] == []


def test_entry_mechanism_survives_territorialization():
    """Ningun caso con asercion territorial esperada declara
    NOTIFICATION como mecanismo — la comunicacion passport no es un
    mecanismo de base."""
    for c in CASES["cases"]:
        if c["expected_territorial_basis"]:
            assert c["expected_entry_mechanism"] == "AUTHORISATION", (
                c["case_id"]
            )
