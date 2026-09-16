"""G3-D — smoke externo black-box (wrapper pytest).

Contrato: docs/g3-d-external-smoke-contract.md. El harness
``tools/smoke_g3d_external.py`` se ejecuta como proceso separado;
este test ademas hace enforcement estructural de D1 (cero imports
de finreg_es/adapters/sqlite3 en el cliente).
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
HARNESS = ROOT / "tools/smoke_g3d_external.py"


def test_harness_has_no_forbidden_imports():
    """D1 estructural: el cliente no importa codigo FinReg."""
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    forbidden = {"finreg_es", "adapters", "sqlite3"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module.split(".")[0]]
        else:
            continue
        for n in names:
            if n in forbidden:
                offenders.append(f"{node.lineno}:{n}")
    assert offenders == []


def test_external_smoke_chain():
    """S1-S5 desde fuera: el harness corre como otro programa."""
    proc = subprocess.run(
        [sys.executable, str(HARNESS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    report = json.loads(proc.stdout)
    assert report["verdict"] == "PASS", json.dumps(
        report["checks"], indent=1, ensure_ascii=False
    )
    assert all(c["ok"] for c in report["checks"].values())
