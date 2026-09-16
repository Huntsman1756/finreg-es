"""G3-C — proyeccion SQLite lossless (casos C1-C5 via sqlite3).

Contrato: docs/g3-c-projection-contract.md. Binding: schema congelado,
payload_json round-trip lossless, referencias de provenance resueltas,
determinismo logico (logical_projection_sha256, no el SHA del fichero).
"""
from __future__ import annotations

import ast
import hashlib
import sqlite3
import sys
from pathlib import Path

import pytest

from adapters import sqlite_projection as sp
from finreg_es.bitemporal import load_evidence_set
from finreg_es.canonical import canonical_json, strict_json_loads

ROOT = Path(__file__).parents[2]
DB = ROOT / "fixtures/g3/projection/finreg-g3.sqlite"
MANIFEST = ROOT / "fixtures/g3/projection/manifest.json"
EVIDENCE_SET = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
COMPARISONS_DIR = ROOT / "fixtures/g2/comparisons"
EVENTS_DIR = ROOT / "fixtures/g2/events"

REAL_PAIR = "g2-b-comparison-eba-psd2-20260914-20260915"
ADDED_RECORD_KEY = "PSD_AG:ES_BE!006813!Z2843910B"
CHANGED_RECORD_KEY = "PSD_AG:ES_BE!006813!60014413F"

_ES_DOC = strict_json_loads(EVIDENCE_SET.read_text(encoding="utf-8"))
ES_ID = load_evidence_set(EVIDENCE_SET).evidence_set_id


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB)
    yield c
    c.close()


def _payloads(conn, table: str) -> list:
    return [
        strict_json_loads(r[0])
        for r in conn.execute(f"SELECT payload_json FROM {table}")
    ]


# --- Frontera estructural -------------------------------------------


def test_builder_stdlib_only_and_no_semantics():
    tree = ast.parse(
        (ROOT / "adapters/sqlite_projection.py").read_text(encoding="utf-8")
    )
    stdlib = sys.stdlib_module_names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        else:
            continue
        for m in mods:
            root = m.split(".")[0]
            assert root in stdlib or root == "finreg_es", m
            assert m not in (
                "finreg_es.semantics",
                "finreg_es.derivation",
            ), m
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.id if isinstance(f, ast.Name) else f.attr)
    assert not called & {"assess", "assess_bitemporal"}


# --- Lossless: payload_json round-trip -------------------------------


def test_payloads_are_canonical_json(conn):
    for table in sp.TABLE_ORDER:
        for (p,) in conn.execute(f"SELECT payload_json FROM {table}"):
            assert canonical_json(strict_json_loads(p)) == p


def test_payloads_equal_source_objects(conn):
    # artifacts.payload_json = documento fuente completo
    inputs = (
        [EVIDENCE_SET]
        + sorted(COMPARISONS_DIR.glob("*.json"))
        + sorted(EVENTS_DIR.glob("*.json"))
    )
    expected_docs = {
        canonical_json(strict_json_loads(p.read_text(encoding="utf-8")))
        for p in inputs
    }
    got = {
        r[0] for r in conn.execute("SELECT payload_json FROM artifacts")
    }
    assert got == expected_docs

    expected = {a["assertion_id"]: a for a in _ES_DOC["assertions"]}
    for aid, p in conn.execute(
        "SELECT assertion_id, payload_json FROM assertions"
    ):
        assert strict_json_loads(p) == expected[aid]

    expected_facts = {f["fact_id"]: f for f in _ES_DOC["reported_facts"]}
    for fid, p in conn.execute(
        "SELECT fact_id, payload_json FROM reported_facts"
    ):
        assert strict_json_loads(p) == expected_facts[fid]

    expected_sa = {}
    for a in _ES_DOC["assertions"]:
        for i, sa in enumerate(a.get("source_assertions", [])):
            expected_sa[("assertion", a["assertion_id"], i)] = sa
    for f in _ES_DOC["reported_facts"]:
        for i, sa in enumerate(f.get("source_assertions", [])):
            expected_sa[("reported_fact", f["fact_id"], i)] = sa
    for ot, oid, o, p in conn.execute(
        "SELECT owner_type, owner_id, ordinal, payload_json"
        " FROM source_assertions"
    ):
        assert strict_json_loads(p) == expected_sa[(ot, oid, o)]

    expected_changes = []
    for p in sorted(COMPARISONS_DIR.glob("*.json")):
        doc = strict_json_loads(p.read_text(encoding="utf-8"))
        for kind in ("added", "changed", "removed"):
            expected_changes += [
                canonical_json(el) for el in doc["changes"].get(kind, [])
            ]
    got_changes = sorted(
        r[0]
        for r in conn.execute("SELECT payload_json FROM structural_changes")
    )
    assert got_changes == sorted(expected_changes)

    expected_cand = []
    for p in sorted(EVENTS_DIR.glob("*.json")):
        doc = strict_json_loads(p.read_text(encoding="utf-8"))
        expected_cand += [
            canonical_json(c) for c in doc.get("candidates", [])
        ]
    got_cand = sorted(
        r[0]
        for r in conn.execute("SELECT payload_json FROM change_candidates")
    )
    assert got_cand == sorted(expected_cand)


# --- Provenance: toda referencia resuelve ----------------------------


def test_provenance_references_resolve(conn):
    artifacts = {
        r[0] for r in conn.execute("SELECT artifact_id FROM artifacts")
    }
    comparisons = {
        r[0] for r in conn.execute("SELECT comparison_id FROM comparisons")
    }
    for (ref,) in conn.execute(
        "SELECT DISTINCT source_artifact_id FROM assertions"
        " UNION SELECT DISTINCT source_artifact_id FROM reported_facts"
    ):
        assert ref in artifacts
    for (ref,) in conn.execute(
        "SELECT DISTINCT comparison_id FROM structural_changes"
        " UNION SELECT DISTINCT comparison_id FROM change_candidates"
    ):
        assert ref in comparisons
    for (es_id,) in conn.execute(
        "SELECT DISTINCT evidence_set_id FROM assertions"
    ):
        assert es_id == ES_ID
    for ot, oid in conn.execute(
        "SELECT DISTINCT owner_type, owner_id FROM source_assertions"
    ):
        table = (
            "assertions" if ot == "assertion" else "reported_facts"
        )
        key = "assertion_id" if ot == "assertion" else "fact_id"
        assert conn.execute(
            f"SELECT 1 FROM {table} WHERE {key}=?", (oid,)
        ).fetchone()


def test_candidate_record_keys_join_structural_changes(conn):
    # En pares con artefacto de comparacion real, todo record_key de
    # candidato esta en structural_changes del mismo comparison_id.
    real = {
        r[0]
        for r in conn.execute(
            "SELECT comparison_id FROM comparisons"
            " WHERE comparison_id LIKE 'g2-b-comparison-%'"
        )
    }
    for cid in real:
        keys = {
            r[0]
            for r in conn.execute(
                "SELECT record_key FROM structural_changes"
                " WHERE comparison_id=?",
                (cid,),
            )
        }
        for (rk,) in conn.execute(
            "SELECT DISTINCT record_key FROM change_candidates"
            " WHERE comparison_id=?",
            (cid,),
        ):
            assert rk in keys


# --- Determinismo logico ----------------------------------------------


def test_manifest_contract_shape(conn):
    m = strict_json_loads(MANIFEST.read_text(encoding="utf-8"))
    assert m["projection_version"] == "FINREG_G3_SQLITE_PROJECTION_V1"
    assert [i["path"] for i in m["inputs"]] == sorted(
        i["path"] for i in m["inputs"]
    )
    assert [t["name"] for t in m["tables"]] == sp.TABLE_ORDER
    for t in m["tables"]:
        (n,) = conn.execute(
            f"SELECT COUNT(*) FROM {t['name']}"
        ).fetchone()
        assert t["rows"] == n
    for i in m["inputs"]:
        p = ROOT / i["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == i["sha256"]
    assert isinstance(m["sqlite_version"], str)
    assert len(m["logical_projection_sha256"]) == 64


def test_logical_digest_reproducible_build_x2(tmp_path):
    m1 = sp.build(tmp_path / "a.sqlite", tmp_path / "a.json")
    m2 = sp.build(tmp_path / "b.sqlite", tmp_path / "b.json")
    assert m1["logical_projection_sha256"] == m2["logical_projection_sha256"]
    assert [t["logical_sha256"] for t in m1["tables"]] == [
        t["logical_sha256"] for t in m2["tables"]
    ]
    committed = strict_json_loads(MANIFEST.read_text(encoding="utf-8"))
    assert (
        m1["logical_projection_sha256"]
        == committed["logical_projection_sha256"]
    )


# --- Casos de aceptacion C1-C5 (binding) -------------------------------


def test_c1_evidence_set_lookup(conn):
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM assertions WHERE evidence_set_id=?",
        (ES_ID,),
    ).fetchone()
    assert n == 166
    (nf,) = conn.execute("SELECT COUNT(*) FROM reported_facts").fetchone()
    assert nf == 19


def test_c2_assertion_provenance(conn):
    aid = _ES_DOC["assertions"][0]["assertion_id"]
    rows = conn.execute(
        "SELECT authority, register_id, source_url, retrieved_at,"
        " source_as_of, raw_snapshot_sha256 FROM source_assertions"
        " WHERE owner_type='assertion' AND owner_id=? ORDER BY ordinal",
        (aid,),
    ).fetchall()
    assert rows
    src = _ES_DOC["assertions"][0]["source_assertions"]
    assert len(rows) == len(src)
    for row, sa in zip(rows, src):
        assert row[0] == sa["authority"]
        assert row[3] == sa["retrieved_at"]
        assert row[5] == sa["raw_snapshot_sha256"]


def test_c4_longitudinal_change(conn):
    row = conn.execute(
        "SELECT kind FROM structural_changes"
        " WHERE comparison_id=? AND record_key=?",
        (REAL_PAIR, ADDED_RECORD_KEY),
    ).fetchone()
    assert row == ("added",)
    cand = conn.execute(
        "SELECT candidate_type, admissibility FROM change_candidates"
        " WHERE comparison_id=? AND record_key=?",
        (REAL_PAIR, ADDED_RECORD_KEY),
    ).fetchone()
    assert cand == ("ENTITY_RECORD_APPEARED", "SUPPORTED")
    row2 = conn.execute(
        "SELECT kind FROM structural_changes"
        " WHERE comparison_id=? AND record_key=?",
        (REAL_PAIR, CHANGED_RECORD_KEY),
    ).fetchone()
    assert row2 == ("changed",)


def test_c5_blocked_no_preregistered_rule(conn):
    (n,) = conn.execute(
        "SELECT COUNT(*) FROM change_candidates WHERE comparison_id=?"
        " AND blocker='NO_PREREGISTERED_RULE' AND admissibility='BLOCKED'",
        (REAL_PAIR,),
    ).fetchone()
    assert n == 312
    # el cambio original es visible: todo candidato BLOCKED liga a
    # un structural_change 'changed' del mismo par (EXISTS, no join
    # — un record_key puede tener varios field_paths)
    orphans = conn.execute(
        "SELECT COUNT(*) FROM change_candidates cc"
        " WHERE cc.comparison_id=?"
        " AND cc.blocker='NO_PREREGISTERED_RULE'"
        " AND NOT EXISTS (SELECT 1 FROM structural_changes sc"
        "  WHERE sc.comparison_id=cc.comparison_id"
        "  AND sc.record_key=cc.record_key AND sc.kind='changed')",
        (REAL_PAIR,),
    ).fetchone()[0]
    assert orphans == 0
