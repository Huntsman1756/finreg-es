"""G1-E3.1 — Corpus negativo preregistrado: anclas y expectativas ejecutables.

El sucesor ``g1-e-negative-corpus-002.json`` corrige E3-F01/F02/F03:

  E3-F01  todo snapshot_sha256 es hex de 64 chars y coincide con el
          manifest congelado (no prefijo truncado)
  E3-F02  la semantica de intervalo ENT_AUT queda declarada
          ``interval_end = EXCLUSIVE`` en semantic_model
  E3-F03  Fintonic PIS se clasifica ENUMERATED_ABSENCE + blocker
          TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED, no conflicto
          entre un hecho historico inactivo y uno vigente

Ademas fija que ``expected_negative_evidence_class`` es un enum
cerrado (match mecanico en E4, no prosa) y que cada record_key
resuelve a una fila real del snapshot congelado.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[2]
G1 = ROOT / "fixtures" / "g1"
CORPUS = json.loads(
    (G1 / "sources" / "extracted" / "g1-e-negative-corpus-003.json").read_text(
        encoding="utf-8"
    )
)

_SNAPSHOT_DIRS = [G1 / "sources", ROOT / "fixtures" / "g0.5" / "sources"]
_MANIFESTS = [
    G1 / "sources" / "manifest.json",
    G1 / "sources" / "manifest-g1-b1.json",
    ROOT / "fixtures" / "g0.5" / "sources" / "manifest.json",
]

_EVIDENCE_CLASSES = {
    "NONE",
    "EXPLICIT_WITHDRAWAL",
    "EXPIRY",
    "ENUMERATED_ABSENCE",
    "ENTITY_BAJA",
}

_EBA_ZIP = "raw/h4-eba-psd2-20260913.zip"


def _snapshot_path(snapshot_file: str) -> Path:
    for d in _SNAPSHOT_DIRS:
        p = d / snapshot_file
        if p.exists():
            return p
    raise AssertionError(f"snapshot not found: {snapshot_file}")


def _manifest_sha(snapshot_file: str) -> str | None:
    for mf in _MANIFESTS:
        doc = json.loads(mf.read_text(encoding="utf-8"))
        for s in doc.get("snapshots", []):
            if s.get("snapshot_file") == snapshot_file:
                return s["sha256"]
    return None


def _eba_record(entity_code: str, entity_type: str) -> dict | None:
    zf = zipfile.ZipFile(_snapshot_path(_EBA_ZIP))
    data = json.loads(zf.read(zf.namelist()[0]))[1]
    for e in data:
        if e["EntityCode"] == entity_code and e["EntityType"] == entity_type:
            return e
    return None


def _xlsx_has_codigo_be(path: Path, codigo: str) -> bool:
    zf = zipfile.ZipFile(path)
    x = zf.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
    return bool(
        re.search(
            rf'<c r="A\d+"[^>]*>.*?<t[^>]*>{re.escape(codigo)}</t>',
            x,
            re.S,
        )
    )


def test_snapshot_sha256_full_and_manifest_bound():
    """E3-F01: 64 hex chars + igualdad exacta con el manifest + recompute."""
    for ent in CORPUS["entities"]:
        for rec in ent["source_records"]:
            sha = rec["snapshot_sha256"]
            assert re.fullmatch(r"[0-9a-f]{64}", sha), (
                ent["corpus_id"], rec["snapshot_file"], sha,
            )
            manifest_sha = _manifest_sha(rec["snapshot_file"])
            assert manifest_sha == sha, (
                ent["corpus_id"], rec["snapshot_file"], sha, manifest_sha,
            )
            raw = _snapshot_path(rec["snapshot_file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == sha


def test_evidence_class_is_closed_enum():
    """expected_negative_evidence_class debe ser matchable mecanicamente."""
    for ent in CORPUS["entities"]:
        for probe in ent["probes"]:
            cls = probe["expected_negative_evidence_class"]
            assert cls in _EVIDENCE_CLASSES, (ent["corpus_id"], cls)


def test_ent_aut_interval_semantics_declared():
    """E3-F02: el corpus declara interval_end=EXCLUSIVE para ENT_AUT."""
    sem = CORPUS["semantic_model"]["ent_aut_interval_semantics"]
    assert "EXCLUSIVE" in sem


def test_eba_records_resolve():
    for ent in CORPUS["entities"]:
        for rec in ent["source_records"]:
            if rec["source"] != "EBA_PSD2_REGISTER":
                continue
            rk = rec["record_key"]
            found = _eba_record(rk["EntityCode"], rk["EntityType"])
            assert found is not None, (ent["corpus_id"], rk)
            assert found["__EBA_EntityVersion"] == rk["EntityVersion"], rk
            props = {
                k: v
                for p in found.get("Properties", [])
                for k, v in p.items()
            }
            for field, expected in rec["fields"].items():
                if field == "Services_ES":
                    svcs = found.get("Services", [])
                    es = [s["ES"] for s in svcs if "ES" in s]
                    flat = [
                        c for grp in es
                        for c in (grp if isinstance(grp, list) else [grp])
                    ]
                    assert set(expected) == set(flat), (
                        ent["corpus_id"], expected, flat,
                    )
                elif field == "Services":
                    svcs = found.get("Services", [])
                    actual = {
                        c: (v if isinstance(v, list) else [v])
                        for s in svcs for c, v in s.items()
                    }
                    for cou, codes in expected.items():
                        assert set(actual.get(cou, [])) == set(codes), (
                            ent["corpus_id"], cou, expected, actual,
                        )
                elif field == "ENT_AUT":
                    assert props.get("ENT_AUT") == expected, (
                        ent["corpus_id"], expected, props.get("ENT_AUT"),
                    )


def test_bde_records_resolve():
    for ent in CORPUS["entities"]:
        for rec in ent["source_records"]:
            if not rec["source"].startswith("BDE_"):
                continue
            rk = rec["record_key"]
            assert rk["field"] == "CODIGO BE", rk
            assert _xlsx_has_codigo_be(
                _snapshot_path(rec["snapshot_file"]), rk["value"]
            ), (ent["corpus_id"], rk)


def test_fintonic_pis_classification():
    """E3-F03: capability historica de fila bajada != positivo vigente
    en conflicto; la ausencia se clasifica y el bloqueo se nombra."""
    fintonic = next(
        e for e in CORPUS["entities"] if e["corpus_id"] == "E3-006"
    )
    pis = next(
        p for p in fintonic["probes"]
        if p.get("query_activity") == "PAYMENT_INITIATION_SERVICES"
    )
    assert pis["expected_negative_evidence_class"] == "ENUMERATED_ABSENCE"
    assert (
        pis["expected_blocker"] == "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED"
    )
    assert "INDETERMINATE" in pis["expected_global_assessment"]


def test_wise_eupago_adversarial_pair():
    """E3-008/E3-009: misma query, todas-vias-cerradas vs una-via-abierta."""
    by_id = {e["corpus_id"]: e for e in CORPUS["entities"]}
    wise = next(
        p for p in by_id["E3-008"]["probes"]
        if p.get("query_activity") == "PAYMENT_INITIATION_SERVICES"
    )
    eupago = by_id["E3-009"]["probes"][0]
    assert "CONFIRMED_NOT_ENTITLED" in wise["expected_global_assessment"]
    assert "CONFIRMED_ENTITLED" in eupago["expected_global_assessment"]
    assert (
        eupago["expected_negative_evidence_class"] == "ENUMERATED_ABSENCE"
    )


def test_no_synthetic_entities():
    assert CORPUS["counts"]["synthetic_entities"] == 0
    for ent in CORPUS["entities"]:
        assert not ent.get("synthetic"), ent["corpus_id"]


def test_mmg_root_vs_territorial_interval():
    """E3-F04: ENT_AUT es historico; Services{ES} es vigente. La ruta
    territorial no se retroproyecta sobre el pasado ni hereda la fecha
    raiz — effective_from territorial = EVIDENCE_AS_OF."""
    mmg = next(e for e in CORPUS["entities"] if e["corpus_id"] == "E3-002")
    by_asof = {p["as_of"]: p for p in mmg["probes"]}
    p18 = by_asof["2018-06-01"]
    assert "INDETERMINATE" in p18["expected_global_assessment"]
    assert "TERRITORIAL_ENTITLEMENT_UNRESOLVED" in (
        p18["expected_global_assessment"]
    )
    assert "NOT HISTORICALLY OBSERVED" in p18["expected_route_outcome"]
    p20 = by_asof["2020-01-01"]
    assert p20["expected_negative_evidence_class"] == "EXPLICIT_WITHDRAWAL"
    assert "CONFIRMED_NOT_ENTITLED" in p20["expected_global_assessment"]
    p26 = by_asof["2026-09-14"]
    assert "CONFIRMED_ENTITLED" in p26["expected_global_assessment"]
    assert "EVIDENCE_AS_OF" in p26["expected_route_outcome"]
    assert "2024-07-12" not in p26["expected_route_outcome"].split(
        "effective_from"
    )[-1]
