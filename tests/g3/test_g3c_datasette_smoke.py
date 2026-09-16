"""G3-C — smoke Datasette immutable sobre la proyeccion congelada.

Contrato: docs/g3-c-projection-contract.md. Binding: Datasette
arranca sobre ``-i`` y expone las tablas; la JSON API devuelve las
filas esperadas; SELECT funciona y la escritura falla; el sha256 del
.sqlite y de los artefactos fuente no cambia durante el smoke.

``datasette`` es dependencia obligatoria de este modulo: si falta,
la coleccion falla — nunca skip silencioso.
"""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import datasette  # noqa: F401 — ausente => fallo de coleccion
import pytest
from typer.testing import CliRunner

from adapters.cli import app as cli_app
from adapters import sqlite_projection as sp
from finreg_es.canonical import strict_json_loads

ROOT = Path(__file__).parents[2]
DB = ROOT / "fixtures/g3/projection/finreg-g3.sqlite"
DB_NAME = DB.stem
ES_DOC = strict_json_loads(
    (ROOT / "fixtures/g1/derived-assertions-g1-e-002.json").read_text(
        encoding="utf-8"
    )
)

# Mismo caso real que G3-B: probe E0-01 (DENIZEN, frontera [from,to))
_CASES = strict_json_loads(
    (ROOT / "fixtures/g2/e0/bitemporal-cases.json").read_text(
        encoding="utf-8"
    )
)
_CASE = _CASES["cases"][0]
_QUERY = _CASE["query"]
_CLI_ASSESS_ARGS = [
    "--entity-id", _CASE["entity_id"],
    "--activity", _QUERY["activity"],
    "--jurisdiction", _QUERY["jurisdiction"],
    "--valid-at", _CASE["probes"][0]["valid_at"],
] + (
    ["--territorial-basis", _QUERY["territorial_basis"]]
    if _QUERY["territorial_basis"] is not None
    else []
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_fingerprint() -> dict:
    """sha256 por fichero de fixtures/, docs/, finreg_es/ — el
    read-only auditable del contrato (cero mutacion de fuentes)."""
    out = {}
    for base in ("fixtures", "docs", "finreg_es"):
        for p in sorted((ROOT / base).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = _sha256(p)
    return out


def _get(url: str) -> tuple[int, object]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None


@pytest.fixture(scope="module")
def datasette_url():
    """Sirve la proyeccion commiteada con ``datasette -i`` y audita
    que ni la base ni los artefactos fuente cambian."""
    port = socket.socket()
    port.bind(("127.0.0.1", 0))
    port_n = port.getsockname()[1]
    port.close()
    before = _tree_fingerprint()
    db_sha_before = _sha256(DB)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "datasette",
            "serve",
            "--immutable",
            str(DB),
            "--host",
            "127.0.0.1",
            "-p",
            str(port_n),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port_n}"
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen(
                    base + "/-/versions.json", timeout=1
                ).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            pytest.fail("datasette no arranco sobre -i")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=15)
        assert _sha256(DB) == db_sha_before
        assert _tree_fingerprint() == before


# --- Smoke: superficie ------------------------------------------------


def test_datasette_starts_and_exposes_tables(datasette_url):
    status, body = _get(f"{datasette_url}/{DB_NAME}.json")
    assert status == 200
    names = {t["name"] for t in body["tables"]}
    assert set(sp.TABLE_ORDER) <= names


def test_json_api_returns_expected_rows(datasette_url):
    aid = ES_DOC["assertions"][0]["assertion_id"]
    status, body = _get(
        f"{datasette_url}/{DB_NAME}/assertions.json"
        f"?_shape=array&assertion_id={aid}"
    )
    assert status == 200
    assert len(body) == 1
    assert body[0]["assertion_id"] == aid

    status, body = _get(
        f"{datasette_url}/{DB_NAME}.json?sql="
        "select+count(*)+as+n+from+change_candidates+where+"
        "comparison_id%3D%27g2-b-comparison-eba-psd2-20260914-20260915%27"
        "+and+blocker%3D%27NO_PREREGISTERED_RULE%27"
    )
    assert status == 200
    assert body["rows"][0][0] == 312


def test_c3_explanation_drilldown_cross_surface(datasette_url):
    """used_assertion_id de una respuesta CLI real (G3-B) resuelve a
    exactamente esa assertion en Datasette, con provenance completa."""
    result = CliRunner().invoke(cli_app, ["assess"] + _CLI_ASSESS_ARGS)
    assert result.exit_code == 0, result.stdout
    payload = strict_json_loads(result.stdout)
    used = payload["used_assertion_ids"]
    assert used

    expected = {a["assertion_id"]: a for a in ES_DOC["assertions"]}
    for aid in used:
        status, body = _get(
            f"{datasette_url}/{DB_NAME}/assertions.json"
            f"?_shape=array&assertion_id={aid}"
        )
        assert status == 200
        assert len(body) == 1
        # misma assertion, payload canonico identico al objeto fuente
        assert strict_json_loads(body[0]["payload_json"]) == expected[aid]
        # mismas source_assertions: sha / url / retrieved_at
        status, sas = _get(
            f"{datasette_url}/{DB_NAME}/source_assertions.json"
            f"?_shape=array&owner_type=assertion&owner_id={aid}"
            f"&_sort=ordinal"
        )
        assert status == 200
        src = expected[aid]["source_assertions"]
        assert [r["raw_snapshot_sha256"] for r in sas] == [
            s["raw_snapshot_sha256"] for s in src
        ]
        assert [r["source_url"] for r in sas] == [
            s["source_url"] for s in src
        ]
        assert [r["retrieved_at"] for r in sas] == [
            s["retrieved_at"] for s in src
        ]


def test_select_works_write_fails(datasette_url):
    status, body = _get(
        f"{datasette_url}/{DB_NAME}.json"
        "?sql=select+comparison_id+from+comparisons"
    )
    assert status == 200
    assert body["ok"] is True
    assert len(body["rows"]) == 3

    # escritura via SQL arbitrario: rechazada (read-only / immutable)
    status, body = _get(
        f"{datasette_url}/{DB_NAME}.json"
        "?sql=insert+into+comparisons+(comparison_id)+values+(%27x%27)"
    )
    assert status != 200 or (
        isinstance(body, dict) and body.get("ok") is False
    )
    # endpoint de escritura sin auth: rechazado (403/405/404 — el
    # criterio binding es que la escritura FALLA, no el codigo exacto)
    req = urllib.request.Request(
        f"{datasette_url}/{DB_NAME}/comparisons/-/insert",
        data=b'{"row": {"comparison_id": "x"}}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
    assert status >= 400
    # y la proyeccion sigue intacta: el intento no dejo fila
    status, body = _get(
        f"{datasette_url}/{DB_NAME}.json"
        "?sql=select+count(*)+as+n+from+comparisons+"
        "where+comparison_id%3D%27x%27"
    )
    assert body["rows"][0][0] == 0


def test_projection_sha_unchanged_while_served(datasette_url):
    before = _sha256(DB)
    _get(f"{datasette_url}/{DB_NAME}/assertions.json?_size=5")
    _get(f"{datasette_url}/{DB_NAME}.json?sql=select+*+from+artifacts")
    assert _sha256(DB) == before
