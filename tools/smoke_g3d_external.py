"""G3-D — smoke externo black-box.

Contrato: ``docs/g3-d-external-smoke-contract.md``.

D1: este cliente NO importa ``finreg_es.*``, ``adapters.*`` ni
``sqlite3`` — se comporta como otro programa.
D2: interaccion solo via CLI subprocess (canonical JSON en stdout),
cliente MCP estandar por stdio y HTTP/JSON contra Datasette -i.

Uso: ``python tools/smoke_g3d_external.py`` → informe canonical JSON
``{verdict, checks}`` por stdout; exit 0 solo si verdict == PASS.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
PROJECTION_DB = ROOT / "fixtures/g3/projection/finreg-g3.sqlite"
# Caso real documentado (E0-01 = cases[0], probe probes[0]): el
# cliente conoce parametros documentados, nunca respuestas.
E0_CASES = ROOT / "fixtures/g2/e0/bitemporal-cases.json"

_ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
_PROTECTED_DIRS = ("fixtures", "docs", "finreg_es", "adapters", "tools")

_checks: dict[str, dict] = {}


def _canon(obj) -> str:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _check(name: str, ok: bool, detail: str = "") -> None:
    _checks[name] = {"ok": bool(ok), "detail": detail}


def _fingerprint() -> dict[str, str]:
    out = {}
    for base in _PROTECTED_DIRS:
        for p in sorted((ROOT / base).rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
    return out


def _cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "adapters.cli", *args],
        cwd=ROOT,
        env=_ENV,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _http(url: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, None


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def _mcp(query_args: dict):
    """Cliente MCP estandar sobre stdio: descubre tools por
    protocolo y llama por nombre — nunca toca el handler."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "adapters.mcp_server"],
        env=_ENV,
        cwd=str(ROOT),
    )
    async with Client(params) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
        result = await client.call_tool("assess_bitemporal", query_args)
        payload = (
            json.loads(result.content[0].text)
            if not result.is_error
            else None
        )
        evidence = {}
        if payload:
            for aid in payload.get("used_assertion_ids", []):
                r = await client.call_tool("evidence", {"item_id": aid})
                if not r.is_error:
                    evidence[aid] = json.loads(r.content[0].text)
        bad = await client.call_tool(
            "assess",
            {
                "entity_id": "X",
                "activity": "Y",
                "jurisdiction": "Z",
                "valid_at": "15-09-2026",
            },
        )
    return tools, payload, evidence, bad


def _serve_datasette():
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "datasette",
            "serve",
            "--immutable",
            str(PROJECTION_DB),
            "--host",
            "127.0.0.1",
            "-p",
            str(port),
        ],
        cwd=ROOT,
        env=_ENV,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(
                base + "/-/versions.json", timeout=1
            ).close()
            return proc, base
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("datasette no arranco sobre -i")


def main() -> int:
    before = _fingerprint()
    case = json.loads(E0_CASES.read_text(encoding="utf-8"))["cases"][0]
    probe = case["probes"][0]
    q = case["query"]
    cli_args = [
        "--entity-id", case["entity_id"],
        "--activity", q["activity"],
        "--jurisdiction", q["jurisdiction"],
        "--valid-at", probe["valid_at"],
        "--known-at", probe["known_at"],
    ]
    if q.get("territorial_basis") is not None:
        cli_args += ["--territorial-basis", q["territorial_basis"]]
    mcp_args = {
        "entity_id": case["entity_id"],
        "activity": q["activity"],
        "jurisdiction": q["jurisdiction"],
        "valid_at": probe["valid_at"],
        "known_at": probe["known_at"],
        "territorial_basis": q.get("territorial_basis"),
    }

    # S1 — CLI: assessment bitemporal real
    proc = _cli(["assess-bitemporal", *cli_args])
    s1 = None
    if proc.returncode == 0:
        try:
            s1 = json.loads(proc.stdout)
        except Exception:
            pass
    _check(
        "S1.cli_bitemporal",
        bool(
            s1
            and s1.get("assessment")
            and s1.get("reason")
            and s1.get("used_assertion_ids")
            and s1.get("evidence_set_id")
        ),
        f"exit={proc.returncode}",
    )
    if not s1:
        return _report()

    # S2 — MCP: discovery real + mismo payload canonico que CLI
    tools, mcp_payload, mcp_evidence, mcp_bad = asyncio.run(
        _mcp(mcp_args)
    )
    _check(
        "S2.mcp_discovery",
        {
            "assess",
            "assess_bitemporal",
            "evidence",
            "explain",
            "changes",
        }
        <= tools,
        f"tools={sorted(tools)}",
    )
    _check(
        "S2.cli_mcp_parity",
        mcp_payload is not None
        and _canon(mcp_payload) == _canon(s1),
        "mismo business payload canonico CLI==MCP",
    )

    # S3 — Datasette: used_assertion_id -> assertion -> source_assertions
    dproc, base = _serve_datasette()
    try:
        db = PROJECTION_DB.stem
        status, body = _http(f"{base}/{db}.json")
        _check(
            "S3.datasette_surface",
            status == 200
            and {
                "assertions",
                "source_assertions",
                "comparisons",
                "structural_changes",
                "change_candidates",
            }
            <= {t["name"] for t in body.get("tables", [])},
            f"status={status}",
        )
        ok_chain = True
        for aid in s1["used_assertion_ids"]:
            status, rows = _http(
                f"{base}/{db}/assertions.json"
                f"?_shape=array&assertion_id={aid}"
            )
            if status != 200 or len(rows) != 1:
                ok_chain = False
                break
            if rows[0]["evidence_set_id"] != s1["evidence_set_id"]:
                ok_chain = False
                break
            status, sas = _http(
                f"{base}/{db}/source_assertions.json"
                f"?_shape=array&owner_type=assertion&owner_id={aid}"
                f"&_sort=ordinal"
            )
            if status != 200 or not sas:
                ok_chain = False
                break
            # continuidad: las source_assertions de Datasette son las
            # mismas que devuelve la superficie MCP (evidence tool)
            mcp_item = mcp_evidence.get(aid, {}).get("item", {})
            mcp_sas = mcp_item.get("source_assertions", [])
            for field in (
                "raw_snapshot_sha256",
                "source_url",
                "retrieved_at",
            ):
                if [r.get(field) for r in sas] != [
                    s.get(field) for s in mcp_sas
                ]:
                    ok_chain = False
                    break
            if not ok_chain:
                break
        _check(
            "S3.provenance_e2e",
            ok_chain,
            "assertion->source_assertions->snapshot/url/retrieved_at",
        )

        # S4 — longitudinal: changes por CLI -> record_key BLOCKED ->
        # Datasette lo sigue (candidate + structural_change)
        proc = _cli(["changes"])
        cand = None
        if proc.returncode == 0:
            for res in json.loads(proc.stdout).get("results", []):
                for c in res.get("candidates", []):
                    if c.get("admissibility") == "BLOCKED":
                        cand = c
                        break
                if cand:
                    break
        ok_s4 = False
        if cand:
            rk = cand["record_key"]
            status, rows = _http(
                f"{base}/{db}/change_candidates.json"
                f"?_shape=array&record_key={urllib.request.quote(rk)}"
            )
            hit = [
                r
                for r in (rows or [])
                if r.get("blocker") == "NO_PREREGISTERED_RULE"
            ]
            if hit:
                status, schanges = _http(
                    f"{base}/{db}/structural_changes.json"
                    f"?_shape=array&record_key={urllib.request.quote(rk)}"
                    f"&comparison_id={hit[0]['comparison_id']}"
                )
                ok_s4 = status == 200 and bool(schanges)
        _check(
            "S4.blocked_change_cross_surface",
            ok_s4,
            "CLI changes -> record_key BLOCKED -> Datasette "
            "NO_PREREGISTERED_RULE + structural_change",
        )

        # S5 — fail-closed observable desde fuera
        bad = _cli(
            [
                "assess",
                "--entity-id", "X",
                "--activity", "Y",
                "--jurisdiction", "Z",
                "--valid-at", "15-09-2026",
            ]
        )
        err = None
        try:
            err = json.loads(bad.stderr)
        except Exception:
            pass
        _check(
            "S5.fail_closed",
            bad.returncode != 0
            and isinstance(err, dict)
            and "code" in err.get("error", {})
            and getattr(mcp_bad, "is_error", False)
            and _http(f"{base}/{db}/no_such_table.json")[0] == 404,
            "cli stderr estructurado + mcp is_error + datasette 404",
        )
    finally:
        dproc.terminate()
        dproc.wait(timeout=15)

    _check("writes.zero", _fingerprint() == before, "")
    return _report()


def _report() -> int:
    verdict = (
        "PASS" if _checks and all(c["ok"] for c in _checks.values()) else "FAIL"
    )
    print(_canon({"verdict": verdict, "checks": _checks}))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
