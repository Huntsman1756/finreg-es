"""G3-B — superficies read-only (CLI Typer + MCP stdio v2).

Contrato: docs/g3-b-adapter-contract.md. Acceptance binding:
5 casos reales, parity de payload canonico CLI==MCP, frontera
estructural de imports del core, read-only real, errores
estructurados fail-closed, descubrimiento stdio.
"""
from __future__ import annotations

import ast
import asyncio
import hashlib
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import mcp
from adapters import common
from adapters.cli import app as cli_app
from adapters.mcp_server import server as mcp_server
from finreg_es.canonical import canonical_json, strict_json_loads

ROOT = Path(__file__).parents[2]
CASES_PATH = ROOT / "fixtures/g2/e0/bitemporal-cases.json"
EVIDENCE_SET_PATH = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
EVENTS_DIR = ROOT / "fixtures/g2/events"
CONTRACTS_DIR = ROOT / "fixtures/contracts"

EVIDENCE_SET_ID = (
    "derived-assertions-g1-e-002@sha256:"
    "2fb08d678a5ee11a398af7a4a990521d1ca5fde20012ffd8e8af63f058bfc1e7"
)
EXPECTED_TOOLS = {
    "assess",
    "assess_bitemporal",
    "evidence",
    "explain",
    "changes",
}
FORBIDDEN_CORE_IMPORTS = {
    "mcp",
    "typer",
    "datasette",
    "fastapi",
    "duckdb",
    "streamlit",
    "uvicorn",
    "starlette",
    "sqlite_utils",
}

_FIXTURE = strict_json_loads(CASES_PATH.read_text(encoding="utf-8"))
_ES_DOC = strict_json_loads(EVIDENCE_SET_PATH.read_text(encoding="utf-8"))
RUNNER = CliRunner()

# Caso real E0-01 (DENIZEN / E3-001, frontera exclusiva [from,to))
_CASE = _FIXTURE["cases"][0]
_PROBE = _CASE["probes"][0]
_QUERY = _CASE["query"]
_ENTITY = _CASE["entity_id"]
_ACTIVITY = _QUERY["activity"]
_JURISDICTION = _QUERY["jurisdiction"]
_TERRITORIAL = _QUERY["territorial_basis"]
_VALID_AT = _PROBE["valid_at"]
_KNOWN_AT = _PROBE["known_at"]

_ASSESS_ARGS = {
    "entity_id": _ENTITY,
    "activity": _ACTIVITY,
    "jurisdiction": _JURISDICTION,
    "valid_at": _VALID_AT,
}
if _TERRITORIAL is not None:
    _ASSESS_ARGS["territorial_basis"] = _TERRITORIAL
_CLI_ASSESS_ARGS = [
    "--entity-id", _ENTITY,
    "--activity", _ACTIVITY,
    "--jurisdiction", _JURISDICTION,
    "--valid-at", _VALID_AT,
] + (
    ["--territorial-basis", _TERRITORIAL] if _TERRITORIAL else []
)
_REAL_RECORD_KEY = "PSD_AG:ES_BE!006813!Z2843910B"
_REAL_PAIR = "eba-psd2-20260914-vs-20260915"
_REAL_ASSERTION_ID = _ES_DOC["assertions"][0]["assertion_id"]


def _cli_ok(args: list[str]) -> dict:
    result = RUNNER.invoke(cli_app, args)
    assert result.exit_code == 0, result.stderr or result.stdout
    return strict_json_loads(result.stdout)


def _mcp_call(name: str, arguments: dict) -> dict:
    async def go() -> dict:
        async with mcp.Client(mcp_server) as client:
            r = await client.call_tool(name, arguments)
            assert not r.is_error
            return strict_json_loads(r.content[0].text)

    return asyncio.run(go())


# --- 5 casos reales -------------------------------------------------


def test_case_assess_current():
    r = common.op_assess(**_ASSESS_ARGS)
    assert r["assessment"] in {
        "CONFIRMED_ENTITLED",
        "CONFIRMED_NOT_ENTITLED",
        "INDETERMINATE",
        "NO_ENTITLEMENT_EVIDENCED",
    }
    assert r["evidence_set_id"] == EVIDENCE_SET_ID
    assert r["semantics_version"] == "ASSESSMENT_SEMANTICS_V3"


def test_case_assess_bitemporal():
    r = common.op_assess_bitemporal(**_ASSESS_ARGS, known_at=_KNOWN_AT)
    assert r["query"]["valid_at"] == _VALID_AT
    assert r["query"]["known_at"] == _KNOWN_AT
    assert r["evidence_set_id"] == EVIDENCE_SET_ID
    ev = r["evidence"]
    for key in (
        "usable_assertion_ids",
        "excluded_after_known_at_assertion_ids",
        "usable_reported_fact_ids",
    ):
        assert key in ev


def test_case_evidence_by_item_and_entity():
    by_item = common.op_evidence(item_id=_REAL_ASSERTION_ID)
    assert by_item["item_kind"] == "assertion"
    assert by_item["item"]["assertion_id"] == _REAL_ASSERTION_ID
    assert "source_assertions" in by_item["item"]
    by_entity = common.op_evidence(entity_id=_ENTITY)
    assert by_entity["assertions"]
    assert all(
        a["entity_id"] == _ENTITY for a in by_entity["assertions"]
    )


def test_case_explain_presents_core_fields():
    r = common.op_explain(**_ASSESS_ARGS, known_at=_KNOWN_AT)
    assert r["reason"]
    assert "assertion_evaluations" in r
    assert "diagnostics" in r
    assert "evidence" in r  # auditoria usable/excluded del core
    assert r["assessment"] == common.op_assess_bitemporal(
        **_ASSESS_ARGS, known_at=_KNOWN_AT
    )["assessment"]


def test_case_changes_real_pair():
    r = common.op_changes(
        record_key=_REAL_RECORD_KEY, pair=_REAL_PAIR
    )
    assert len(r["results"]) == 1
    res = r["results"][0]
    assert res["summary"]["candidates"] == 379
    assert len(res["candidates"]) == 1
    c = res["candidates"][0]
    assert c["record_key"] == _REAL_RECORD_KEY
    assert c["candidate_type"] == "ENTITY_RECORD_APPEARED"
    assert c["admissibility"] == "SUPPORTED"


# --- Parity CLI == MCP (payload FinReg canonico) --------------------

_PARITY_OPS = [
    ("assess", ["assess", *_CLI_ASSESS_ARGS], _ASSESS_ARGS),
    (
        "assess_bitemporal",
        ["assess-bitemporal", *_CLI_ASSESS_ARGS, "--known-at", _KNOWN_AT],
        {**_ASSESS_ARGS, "known_at": _KNOWN_AT},
    ),
    (
        "evidence",
        ["evidence", "--item-id", _REAL_ASSERTION_ID],
        {"item_id": _REAL_ASSERTION_ID},
    ),
    (
        "explain",
        ["explain", *_CLI_ASSESS_ARGS, "--known-at", _KNOWN_AT],
        {**_ASSESS_ARGS, "known_at": _KNOWN_AT},
    ),
    (
        "changes",
        ["changes", "--record-key", _REAL_RECORD_KEY, "--pair", _REAL_PAIR],
        {"record_key": _REAL_RECORD_KEY, "pair": _REAL_PAIR},
    ),
]


@pytest.mark.parametrize(
    "tool,cli_args,mcp_args", _PARITY_OPS, ids=[op[0] for op in _PARITY_OPS]
)
def test_cli_mcp_payload_parity(tool, cli_args, mcp_args):
    """El payload FinReg serializado canonicamente es identico entre
    stdout del CLI y el contenido del tool MCP (el envelope difiere;
    el payload no)."""
    cli_payload = _cli_ok(cli_args)
    mcp_payload = _mcp_call(tool, mcp_args)
    assert canonical_json(cli_payload) == canonical_json(mcp_payload)


def test_same_query_same_bytes():
    a = _cli_ok(["assess", *_CLI_ASSESS_ARGS])
    b = _cli_ok(["assess", *_CLI_ASSESS_ARGS])
    assert canonical_json(a) == canonical_json(b)


# --- MCP stdio: arranca y descubre la superficie --------------------


def test_mcp_stdio_discovers_surface():
    params = mcp.StdioServerParameters(
        command=sys.executable,
        args=["-m", "adapters.mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    async def go() -> set[str]:
        async with mcp.Client(params) as client:
            tools = await client.list_tools()
            return {t.name for t in tools.tools}

    assert asyncio.run(go()) == EXPECTED_TOOLS


# --- Frontera estructural -------------------------------------------


def test_core_never_imports_adapter_deps():
    offenders = []
    for p in sorted((ROOT / "finreg_es").rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in FORBIDDEN_CORE_IMPORTS:
                    offenders.append(f"{p.name}:{node.lineno}:{n}")
    assert offenders == []


# --- Read-only real -------------------------------------------------


def _fingerprint() -> dict[str, str]:
    files = [EVIDENCE_SET_PATH]
    files += sorted(EVENTS_DIR.glob("*.json"))
    files += sorted(CONTRACTS_DIR.glob("*.json"))
    return {
        str(p.relative_to(ROOT)): hashlib.sha256(
            p.read_bytes()
        ).hexdigest()
        for p in files
    }


def test_ops_never_write():
    before = _fingerprint()
    common.op_assess(**_ASSESS_ARGS)
    common.op_assess_bitemporal(**_ASSESS_ARGS, known_at=_KNOWN_AT)
    common.op_evidence(entity_id=_ENTITY)
    common.op_explain(**_ASSESS_ARGS)
    common.op_changes()
    assert _fingerprint() == before


# --- Errores estructurados fail-closed ------------------------------


def test_invalid_date_fails_closed():
    with pytest.raises(common.AdapterError) as ei:
        common.op_assess(**{**_ASSESS_ARGS, "valid_at": "14-09-2026"})
    assert ei.value.code == "invalid_input"
    with pytest.raises(common.AdapterError) as ei2:
        common.op_assess_bitemporal(
            **_ASSESS_ARGS, known_at="2026-99-99"
        )
    assert ei2.value.code == "invalid_input"


def test_missing_artifact_fails_closed():
    with pytest.raises(common.AdapterError) as ei:
        common.op_assess(
            **_ASSESS_ARGS, evidence_set_path="fixtures/nope.json"
        )
    assert ei.value.code == "artifact_not_found"


def test_unknown_evidence_set_id_fails_closed():
    with pytest.raises(common.AdapterError) as ei:
        common.op_assess(
            **_ASSESS_ARGS,
            evidence_set_id="other@sha256:" + "0" * 64,
        )
    assert ei.value.code == "unknown_evidence_set"


def test_evidence_selector_and_not_found_fail_closed():
    with pytest.raises(common.AdapterError) as ei:
        common.op_evidence()
    assert ei.value.code == "invalid_input"
    with pytest.raises(common.AdapterError) as ei2:
        common.op_evidence(item_id="x", entity_id="y")
    assert ei2.value.code == "invalid_input"
    with pytest.raises(common.AdapterError) as ei3:
        common.op_evidence(item_id="g1e-asm-nonexistent")
    assert ei3.value.code == "not_found"


def test_unknown_pair_fails_closed():
    with pytest.raises(common.AdapterError) as ei:
        common.op_changes(pair="eba-psd2-19990101-vs-19990102")
    assert ei.value.code == "not_found"


def test_cli_error_is_structured_and_exits():
    result = RUNNER.invoke(
        cli_app,
        [
            "assess",
            "--entity-id", _ENTITY,
            "--activity", _ACTIVITY,
            "--jurisdiction", _JURISDICTION,
            "--valid-at", "bogus",
        ],
    )
    assert result.exit_code == 1
    err = strict_json_loads(result.stderr)
    assert err["error"]["code"] == "invalid_input"
    assert "message" in err["error"]


def test_cli_help_lists_five_ops():
    result = RUNNER.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    for cmd in (
        "assess",
        "assess-bitemporal",
        "evidence",
        "explain",
        "changes",
    ):
        assert cmd in result.stdout
