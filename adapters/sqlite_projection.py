"""G3-C — proyeccion SQLite lossless de artefactos congelados.

Contrato congelado: ``docs/g3-c-projection-contract.md``.

Builder stdlib-only (``sqlite3``): proyecta el evidence set, los
artefactos de comparacion y los artefactos de eventos a tablas
indexables + ``payload_json`` canonico. Nunca llama a ``assess()``,
``assess_bitemporal()`` ni a ``derivation`` — solo serializa objetos
fuente a canonical JSON. Datasette sirve el resultado en modo
immutable; la autoridad sigue en los JSON congelados y sus sha256.

Determinismo contractual = logico (schema, row counts, filas
ordenadas, canonical row hashes, ``logical_projection_sha256``);
el SHA del fichero .sqlite no es requisito cross-platform.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from pathlib import Path

from finreg_es.bitemporal import load_evidence_set
from finreg_es.canonical import canonical_json, sha256_hex, strict_json_loads

ROOT = Path(__file__).resolve().parents[1]

PROJECTION_VERSION = "FINREG_G3_SQLITE_PROJECTION_V1"

DEFAULT_DB = ROOT / "fixtures/g3/projection/finreg-g3.sqlite"
DEFAULT_MANIFEST = ROOT / "fixtures/g3/projection/manifest.json"
DEFAULT_EVIDENCE_SET = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
DEFAULT_COMPARISONS_DIR = ROOT / "fixtures/g2/comparisons"
DEFAULT_EVENTS_DIR = ROOT / "fixtures/g2/events"

TABLE_ORDER = [
    "artifacts",
    "assertions",
    "reported_facts",
    "source_assertions",
    "comparisons",
    "structural_changes",
    "change_candidates",
]

# Claves primarias: orden canonico de filas para el digest logico.
_PRIMARY_KEY = {
    "artifacts": ["artifact_id"],
    "assertions": ["assertion_id"],
    "reported_facts": ["fact_id"],
    "source_assertions": ["owner_type", "owner_id", "ordinal"],
    "comparisons": ["comparison_id"],
    "structural_changes": ["comparison_id", "ordinal"],
    "change_candidates": ["comparison_id", "ordinal"],
}

_SCHEMA = """
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE assertions (
    assertion_id TEXT PRIMARY KEY,
    entity_id TEXT,
    activity TEXT,
    jurisdiction TEXT,
    legal_effect TEXT,
    entry_mechanism TEXT,
    territorial_basis TEXT,
    effective_from TEXT,
    effective_to TEXT,
    evidence_set_id TEXT NOT NULL,
    source_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    payload_json TEXT NOT NULL
);
CREATE TABLE reported_facts (
    fact_id TEXT PRIMARY KEY,
    corpus_id TEXT,
    rule_id TEXT,
    reported_status TEXT,
    source_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    payload_json TEXT NOT NULL
);
CREATE TABLE source_assertions (
    owner_type TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    authority TEXT,
    register_id TEXT,
    source_url TEXT,
    retrieved_at TEXT,
    source_as_of TEXT,
    raw_snapshot_sha256 TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (owner_type, owner_id, ordinal)
);
CREATE TABLE comparisons (
    comparison_id TEXT PRIMARY KEY,
    left_observation_id TEXT,
    right_observation_id TEXT,
    succession_state TEXT,
    added_count INTEGER,
    removed_count INTEGER,
    changed_count INTEGER,
    payload_json TEXT NOT NULL
);
CREATE TABLE structural_changes (
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    ordinal INTEGER NOT NULL,
    kind TEXT NOT NULL,
    record_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (comparison_id, ordinal)
);
CREATE TABLE change_candidates (
    comparison_id TEXT NOT NULL REFERENCES comparisons(comparison_id),
    ordinal INTEGER NOT NULL,
    candidate_type TEXT,
    record_key TEXT,
    admissibility TEXT,
    blocker TEXT,
    effective_basis TEXT,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (comparison_id, ordinal)
);
CREATE INDEX idx_assertions_evidence_set ON assertions(evidence_set_id);
CREATE INDEX idx_assertions_entity ON assertions(entity_id);
CREATE INDEX idx_facts_corpus ON reported_facts(corpus_id);
CREATE INDEX idx_source_assertions_owner ON source_assertions(owner_id);
CREATE INDEX idx_source_assertions_snapshot
    ON source_assertions(raw_snapshot_sha256);
CREATE INDEX idx_structural_changes_key ON structural_changes(record_key);
CREATE INDEX idx_candidates_key ON change_candidates(record_key);
CREATE INDEX idx_candidates_blocker ON change_candidates(blocker);
"""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_id(path: Path, doc: dict) -> str:
    """Id propio del artefacto si lo declara; si no, el binding
    ``<stem>@sha256:<digest>`` (misma forma que ``evidence_set_id``)."""
    declared = doc.get("artifact")
    if isinstance(declared, str):
        return declared
    return f"{path.stem}@sha256:{_file_sha256(path)}"


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _load(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def _insert_artifact(conn, path: Path, doc: dict, kind: str) -> str:
    artifact_id = _artifact_id(path, doc)
    conn.execute(
        "INSERT INTO artifacts"
        " (artifact_id, path, sha256, kind, payload_json)"
        " VALUES (?,?,?,?,?)",
        (
            artifact_id,
            _rel(path),
            _file_sha256(path),
            kind,
            canonical_json(doc),
        ),
    )
    return artifact_id


def _project_evidence_set(conn, path: Path) -> None:
    # load_evidence_set del core: el mismo evidence_set_id que
    # emiten CLI/MCP — reutilizado, no reimplementado.
    evidence_set_id = load_evidence_set(path).evidence_set_id
    doc = _load(path)
    artifact_id = _insert_artifact(conn, path, doc, "evidence-set")
    for a in doc.get("assertions", []):
        conn.execute(
            "INSERT INTO assertions (assertion_id, entity_id,"
            " activity, jurisdiction, legal_effect, entry_mechanism,"
            " territorial_basis, effective_from, effective_to,"
            " evidence_set_id, source_artifact_id, payload_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                a["assertion_id"],
                a.get("entity_id"),
                a.get("activity"),
                a.get("jurisdiction"),
                a.get("legal_effect"),
                a.get("entry_mechanism"),
                a.get("territorial_basis"),
                a.get("effective_from"),
                a.get("effective_to"),
                evidence_set_id,
                artifact_id,
                canonical_json(a),
            ),
        )
        _project_source_assertions(
            conn, "assertion", a["assertion_id"], a.get("source_assertions", [])
        )
    for f in doc.get("reported_facts", []):
        conn.execute(
            "INSERT INTO reported_facts (fact_id, corpus_id, rule_id,"
            " reported_status, source_artifact_id, payload_json)"
            " VALUES (?,?,?,?,?,?)",
            (
                f["fact_id"],
                f.get("corpus_id"),
                f.get("rule_id"),
                f.get("reported_status"),
                artifact_id,
                canonical_json(f),
            ),
        )
        _project_source_assertions(
            conn, "reported_fact", f["fact_id"], f.get("source_assertions", [])
        )


def _project_source_assertions(conn, owner_type, owner_id, items) -> None:
    for i, sa in enumerate(items):
        conn.execute(
            "INSERT INTO source_assertions (owner_type, owner_id,"
            " ordinal, authority, register_id, source_url,"
            " retrieved_at, source_as_of, raw_snapshot_sha256,"
            " payload_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                owner_type,
                owner_id,
                i,
                sa.get("authority"),
                sa.get("register_id"),
                sa.get("source_url"),
                sa.get("retrieved_at"),
                sa.get("source_as_of"),
                sa.get("raw_snapshot_sha256"),
                canonical_json(sa),
            ),
        )


def _insert_comparison_row(
    conn, comparison_id, cmp: dict, counts: dict, payload
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO comparisons (comparison_id,"
        " left_observation_id, right_observation_id,"
        " succession_state, added_count, removed_count,"
        " changed_count, payload_json) VALUES (?,?,?,?,?,?,?,?)",
        (
            comparison_id,
            cmp.get("left_observation_id"),
            cmp.get("right_observation_id"),
            cmp.get("succession_state"),
            counts.get("added"),
            counts.get("removed"),
            counts.get("changed"),
            canonical_json(payload),
        ),
    )


def _project_comparison(conn, path: Path) -> None:
    doc = _load(path)
    comparison_id = _insert_artifact(conn, path, doc, "comparison")
    cmp = doc["comparison"]
    changes = doc["changes"]
    _insert_comparison_row(
        conn,
        comparison_id,
        cmp,
        {k: len(changes.get(k, [])) for k in ("added", "removed", "changed")},
        doc,
    )
    ordinal = 0
    for kind in ("added", "changed", "removed"):
        for change in changes.get(kind, []):
            # added/removed son record_keys desnudos; changed es un
            # objeto {kind, path, old, new, record_key}. payload_json
            # conserva el elemento fuente integro en ambos casos.
            record_key = (
                change if isinstance(change, str) else change["record_key"]
            )
            conn.execute(
                "INSERT INTO structural_changes (comparison_id,"
                " ordinal, kind, record_key, payload_json)"
                " VALUES (?,?,?,?,?)",
                (
                    comparison_id,
                    ordinal,
                    kind,
                    record_key,
                    canonical_json(change),
                ),
            )
            ordinal += 1


def _project_events(conn, path: Path, comparison_ids: dict) -> None:
    doc = _load(path)
    _insert_artifact(conn, path, doc, "events")
    sc = doc["source_comparison"]
    ref = sc.get("file")
    if ref is not None and ref in comparison_ids:
        comparison_id = comparison_ids[ref]
    else:
        # source_comparison sin fichero resoluble (p.ej. el slice
        # sintetico G2-C1): la fila de comparisons se materializa
        # desde la propia declaracion del artefacto events —
        # determinista y resoluble, sin inventar semantica.
        comparison_id = f"{sc['kind']}@sha256:{sc['sha256']}"
        _insert_comparison_row(
            conn,
            comparison_id,
            doc.get("comparison", {}),
            doc.get("summary", {}).get("input", {}),
            {
                "comparison": doc.get("comparison"),
                "source_comparison": sc,
            },
        )
    for i, c in enumerate(doc.get("candidates", [])):
        conn.execute(
            "INSERT INTO change_candidates (comparison_id, ordinal,"
            " candidate_type, record_key, admissibility, blocker,"
            " effective_basis, payload_json) VALUES (?,?,?,?,?,?,?,?)",
            (
                comparison_id,
                i,
                c.get("candidate_type"),
                c.get("record_key"),
                c.get("admissibility"),
                c.get("blocker"),
                c.get("effective_basis"),
                canonical_json(c),
            ),
        )


def _table_digest(conn, table: str) -> tuple[int, str]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    order = ", ".join(_PRIMARY_KEY[table])
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
    return len(rows), sha256_hex([dict(zip(cols, r)) for r in rows])


def build(
    db_path: Path = DEFAULT_DB,
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    evidence_set: Path = DEFAULT_EVIDENCE_SET,
    comparisons_dir: Path = DEFAULT_COMPARISONS_DIR,
    events_dir: Path = DEFAULT_EVENTS_DIR,
) -> dict:
    """Construye la proyeccion y su manifest. Devuelve el manifest."""
    inputs = (
        [Path(evidence_set)]
        + sorted(Path(comparisons_dir).glob("*.json"))
        + sorted(Path(events_dir).glob("*.json"))
    )
    for p in inputs:
        if not p.is_file():
            raise FileNotFoundError(f"input de proyeccion no existe: {p}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        _project_evidence_set(conn, Path(evidence_set))
        comparison_ids = {}
        for p in sorted(Path(comparisons_dir).glob("*.json")):
            _project_comparison(conn, p)
            comparison_ids[_rel(p)] = _artifact_id(p, _load(p))
        for p in sorted(Path(events_dir).glob("*.json")):
            _project_events(conn, p, comparison_ids)
        conn.commit()

        tables = []
        for t in TABLE_ORDER:
            rows, digest = _table_digest(conn, t)
            tables.append(
                {"name": t, "rows": rows, "logical_sha256": digest}
            )
    finally:
        conn.close()

    manifest = {
        "projection_version": PROJECTION_VERSION,
        "inputs": [
            {"path": _rel(p), "sha256": _file_sha256(p)} for p in inputs
        ],
        "tables": tables,
        "sqlite_version": sqlite3.sqlite_version,
    }
    manifest["logical_projection_sha256"] = sha256_hex(
        {
            "projection_version": PROJECTION_VERSION,
            "inputs": manifest["inputs"],
            "tables": tables,
        }
    )
    manifest_path.write_text(
        canonical_json(manifest) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    manifest = build()
    total = sum(t["rows"] for t in manifest["tables"])
    print(
        f"proyeccion {PROJECTION_VERSION}: {total} filas, "
        f"logical {manifest['logical_projection_sha256'][:16]}…"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
