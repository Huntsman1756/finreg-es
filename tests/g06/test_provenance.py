"""G0.6 — Provenance & reproducibility verification.

Gate de verificación: replay offline, provenance por claim, detección de
mutación de fuente, traza raw->normalized, provenance temporal e
inmutabilidad de los artefactos históricos de G0.5.
"""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import urllib.request
from pathlib import Path

import pytest

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.extraction import _verify_snapshot, run_extraction
from finreg_es.provenance import (
    FROZEN_ARTIFACTS,
    REQUIRED_PROVENANCE_FIELDS,
    claim_ledger,
    verify_ledger_claims,
)
from finreg_es.temporal import suspect_source_as_of


ROOT = Path(__file__).parents[2]
G05 = ROOT / "fixtures" / "g0.5"
RUN_V1_PATH = G05 / "runs" / "g0.5-a-2026-09-13-001.json"
RUN_V3_PATH = G05 / "runs" / "g0.5-a-2026-09-13-003.json"
MANIFEST_PATH = G05 / "sources" / "manifest.json"
LEDGER_PATH = ROOT / "fixtures" / "g0.6" / "claim-provenance-g0.5-a-003.json"
REPORT_PATH = ROOT / "fixtures" / "g0.6" / "verification-report.json"
SUSPECT_FIXTURE = ROOT / "fixtures" / "g0.6" / "temporal" / "suspect-source-as-of.json"

OMISSION_DIVERGENCE_IDS = [4, 6, 11, 13, 15, 19, 21, 23]


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


# ---------------------------------------------------------------- G0.6-A


def test_g06a_every_extracted_field_has_provenance():
    """0 claims sin provenance: cada campo observado del run sucesor tiene
    snapshot sha, autoridad, registro, locator, retrieved_at, version del
    extractor, valor raw y valor normalizado."""
    run = _read(RUN_V3_PATH)
    ledger = _read(LEDGER_PATH)
    claims = ledger["claims"]

    expected_ids = {
        f"{a['corpus_id']}|{a['source']}|{field}"
        for a in run["attempts"]
        if a["parse"]["status"] == "PARSE_OK"
        for field in a["parse"]["record"]["observed"]
    }
    assert {c["claim_id"] for c in claims} == expected_ids
    assert len(claims) == ledger["ledger"]["claims_total"] == 337
    assert ledger["ledger"]["untraced_fields"] == []
    assert ledger["ledger"]["run_result_sha"] == run["result_sha"]

    for claim in claims:
        for field in REQUIRED_PROVENANCE_FIELDS:
            assert claim.get(field), (claim["claim_id"], field)
        assert "source_as_of" in claim
        assert claim["source_date_reliability"] in {"TRUSTED", "UNAVAILABLE"}
        # La ausencia de source_as_of se declara, no se rellena.
        if claim["source_as_of"] is None:
            assert claim["source_date_reliability"] == "UNAVAILABLE"


# ---------------------------------------------------------------- G0.6-B


def test_g06b_offline_replay_is_byte_identical(monkeypatch):
    """Replay sólo desde artefactos congelados, sin red: el resultado
    canónico es byte-idéntico al run -003 y distinto de los originales.

    La red no es una dependencia oculta: cualquier intento de socket o
    apertura de URL aborta el test.
    """
    def _blocked(*args, **kwargs):
        raise AssertionError("network access forbidden during G0.6 replay")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)

    frozen = _read(RUN_V3_PATH)
    meta = frozen["run"]
    replayed = run_extraction(
        ROOT,
        run_id=meta["run_id"],
        corpus_sha=meta["corpus_sha"],
        contracts_sha=meta["contracts_sha"],
        source_baseline_sha=meta["source_baseline_sha"],
        executed_at=meta["executed_at"],
        supersedes_run_id=meta["supersedes_run_id"],
    )

    assert replayed["summary"]["entities_attempted"] == 30
    assert replayed["summary"]["source_attempts"] == 34
    assert canonical_json(replayed) + "\n" == RUN_V3_PATH.read_text(
        encoding="utf-8"
    )
    assert replayed["result_sha"] == frozen["result_sha"]

    # Sucesores, no reemplazos: el replay no reproduce ni -001 ni -002.
    originals = [
        _read(G05 / "runs" / name)["result_sha"]
        for name in (
            "g0.5-a-2026-09-13-001.json",
            "g0.5-a-2026-09-13-002.json",
        )
    ]
    assert replayed["result_sha"] not in originals


# ---------------------------------------------------------------- G0.6-C


def test_g06c_source_mutation_detection(tmp_path):
    """Mismo identificador de fuente + contenido distinto => nuevo SHA,
    cambio detectable con linaje expected/observed, sin sobrescribir el
    snapshot anterior. Mismos bytes => misma identidad, sin duplicar."""
    manifest = _read(MANIFEST_PATH)
    item = next(
        i for i in manifest["snapshots"] if i["snapshot_file"] == "raw/h8-bde-mfi-es.csv"
    )
    real = G05 / "sources" / "raw" / "h8-bde-mfi-es.csv"

    staged = tmp_path / "raw" / "h8-bde-mfi-es.csv"
    staged.parent.mkdir(parents=True)

    staged.write_bytes(real.read_bytes())
    same = _verify_snapshot(tmp_path, item)
    assert same["status"] == "FETCH_OK"
    assert same["sha256"] == item["sha256"]

    staged.write_bytes(real.read_bytes() + b"\x00")
    mutated = _verify_snapshot(tmp_path, item)
    assert mutated["status"] == "FETCH_ERROR"
    assert mutated["reason"] == "SNAPSHOT_HASH_OR_SIZE_MISMATCH"
    assert mutated["expected_sha256"] == item["sha256"]
    assert mutated["observed_sha256"] != item["sha256"]

    # El snapshot original conserva su identidad: no se sobrescribe.
    assert _sha256(real) == item["sha256"]

    # Identidad por contenido: nombres y hashes no duplican evidencia.
    names = [i["snapshot_file"] for i in manifest["snapshots"]]
    hashes = [i["sha256"] for i in manifest["snapshots"]]
    assert len(names) == len(set(names))
    assert len(hashes) == len(set(hashes))


# ---------------------------------------------------------------- G0.6-D


def test_g06d_transformation_trace_reconstructs_every_claim():
    """raw -> parser/version -> parsed -> regla/version -> normalized ->
    derivación semántica/version -> candidato de aserción. Cada salto es
    reconstruible sin mirar el código actual."""
    run = _read(RUN_V3_PATH)
    manifest = _read(MANIFEST_PATH)
    ledger = _read(LEDGER_PATH)

    # El ledger regenerado es idéntico al artefacto cometido.
    assert claim_ledger(run, manifest) == ledger
    # Y cada claim se re-deriva desde su raw_record sin errores.
    assert verify_ledger_claims(run, ledger) == []

    for claim in ledger["claims"]:
        assert claim["rule_version"]
        assert claim["parser"]
        assert claim["semantic_derivation"]["status"]
        assert claim["assertion_candidate"] == "NOT_CREATED"

    # La derivación semántica no inventa efectos ni ventanas jurídicas.
    for attempt in run["attempts"]:
        assert attempt["assessment"] == {"status": "NOT_RUN", "assertions": []}
        assert attempt["semantics"]["legal_effect"] is None
        assert attempt["semantics"]["entry_mechanism"] is None
        assert "effective_from" not in attempt["semantics"]
        assert "effective_to" not in attempt["semantics"]


# ---------------------------------------------------------------- G0.6-E


def test_g06e_temporal_provenance_separates_capture_and_source_dates():
    manifest = _read(MANIFEST_PATH)
    ledger = _read(LEDGER_PATH)

    assert manifest["retrieved_at"] == "2026-09-13"
    by_snapshot = {c["snapshot_file"]: c for c in ledger["claims"]}

    # retrieved_at (captura) != source_as_of (declaración de la fuente).
    h4 = by_snapshot["raw/h4-eba-psd2-20260913.zip"]
    assert h4["source_as_of"] == "2026-09-13T08:00:04Z"
    assert h4["retrieved_at"] != h4["source_as_of"]
    assert h4["source_date_reliability"] == "TRUSTED"

    # Los snapshots sin fecha declarada quedan UNAVAILABLE, explícito.
    for claim in ledger["claims"]:
        if claim["snapshot_file"] != "raw/h4-eba-psd2-20260913.zip":
            assert claim["source_as_of"] is None
            assert claim["source_date_reliability"] == "UNAVAILABLE"


def test_g06e_suspect_source_as_of_fixture():
    """Contenido distinto con el mismo source_as_of => SUSPECT. La regla
    marca, no descarta: una fecha inmóvil con contenido nuevo puede ser
    una corrección editorial."""
    fixture = _read(SUSPECT_FIXTURE)
    for case in fixture["cases"]:
        hash_t1 = hashlib.sha256(
            canonical_json(case["t1"]["payload"]).encode("utf-8")
        ).hexdigest()
        hash_t2 = hashlib.sha256(
            canonical_json(case["t2"]["payload"]).encode("utf-8")
        ).hexdigest()
        suspect = suspect_source_as_of(
            hash_t1,
            hash_t2,
            case["t1"]["source_as_of"],
            case["t2"]["source_as_of"],
        )
        assert suspect == (case["expected"] == "SUSPECT"), case["case_id"]


# ---------------------------------------------------------------- G0.6-F


def test_g06f_historical_artifacts_are_byte_identical_to_their_commits():
    """Los artefactos congelados de G0.5 siguen byte-idénticos al commit
    que los fijó; los runs -002/-003 y las resoluciones son sucesores."""
    report = _read(REPORT_PATH)
    pinned = {row["path"]: row for row in report["report"]["frozen_artifacts"]}
    assert set(pinned) == {rel for rel, _ in FROZEN_ARTIFACTS}

    for rel, commit in FROZEN_ARTIFACTS:
        path = ROOT / rel
        assert _sha256(path) == pinned[rel]["sha256"], rel
        assert pinned[rel]["unchanged_since_commit"] is True, rel
        assert _git("rev-parse", "--verify", f"{commit}^{{commit}}").returncode == 0
        diff = _git("diff", "--exit-code", commit, "HEAD", "--", rel)
        assert diff.returncode == 0, rel

    # El run original conserva su métrica defectuosa (historia intacta).
    original = _read(RUN_V1_PATH)
    assert original["summary"]["unexpected_divergences"] == 1
    assert [
        index
        for index, d in enumerate(original["divergences"], start=1)
        if d["expected_in_ground_truth"]
    ] == [i for i in range(1, 41) if i != 24]


def test_g06f_omissions_stay_unexpected_and_adjudicated():
    """Fidelidad histórica: las ocho omisiones NO se convierten en
    'expected'. El replay las anota false y la resolución auditada las
    conserva como PREREGISTRATION_OMISSION; ambas cosas coexisten."""
    run = _read(RUN_V3_PATH)
    resolution = _read(
        G05 / "audit" / "g0.5-b-preregistration-resolution.json"
    )

    for index in OMISSION_DIVERGENCE_IDS:
        assert run["divergences"][index - 1]["expected_in_ground_truth"] is False
    assert run["summary"]["unexpected_divergences"] == 9
    assert {
        entry["divergence_id"] for entry in resolution["omissions"]
    } == set(OMISSION_DIVERGENCE_IDS)
    assert all(
        entry["classification"] == "PREREGISTRATION_OMISSION"
        for entry in resolution["omissions"]
    )


# -------------------------------------------------------------- informe


def test_g06_report_is_pass_and_consistent_with_recomputation():
    report = _read(REPORT_PATH)
    run = _read(RUN_V3_PATH)
    manifest = _read(MANIFEST_PATH)
    ledger = claim_ledger(run, manifest)

    assert report["report"]["status"] == "PASS"
    assert report["report"]["report_version"] == "FINREG_G06_PROVENANCE_VERIFICATION_V1"
    sub = report["report"]["subgates"]
    assert sub["G0.6-A"]["claims_total"] == len(ledger["claims"]) == 337
    assert sub["G0.6-A"]["claims_without_provenance"] == 0
    assert sub["G0.6-B"]["canonical_output_identical"] is True
    assert sub["G0.6-B"]["replayed_result_sha"] == run["result_sha"]
    assert sub["G0.6-C"]["mutated_reason"] == "SNAPSHOT_HASH_OR_SIZE_MISMATCH"
    assert sub["G0.6-C"]["original_file_unchanged"] is True
    assert sub["G0.6-D"]["claims_with_full_trace"] == 337
    assert sub["G0.6-D"]["assertion_candidates_created"] == 0
    assert sub["G0.6-F"]["artifacts_unchanged"] is True
    assert report["report"]["history"]["policy"] == "SUCCESSORS_NOT_REPLACEMENTS"
