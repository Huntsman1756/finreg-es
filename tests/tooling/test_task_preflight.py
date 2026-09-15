"""Preflight de tasks: STATUS IS AUTHORITATIVE, fail-closed."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.task_preflight import preflight, read_status

ROOT = Path(__file__).parents[2]


def _task(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "t.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_ready_is_executable(tmp_path):
    p = _task(tmp_path, "task_id: x\nstatus: ready\n")
    ok, msg = preflight(str(p))
    assert ok and msg == "TASK_READY"


@pytest.mark.parametrize(
    "status",
    ["blocked", "done", "in_progress", "preregistered-blocked"],
)
def test_non_ready_statuses_reject(tmp_path, status):
    p = _task(tmp_path, f"task_id: x\nstatus: {status}\n")
    ok, msg = preflight(str(p))
    assert not ok and status in msg


def test_missing_status_rejects(tmp_path):
    p = _task(tmp_path, "task_id: x\ngoal: algo\n")
    ok, msg = preflight(str(p))
    assert not ok and "status" in msg


def test_unknown_status_rejects(tmp_path):
    p = _task(tmp_path, "task_id: x\nstatus: whatever\n")
    ok, _ = preflight(str(p))
    assert not ok


def test_indented_status_is_not_top_level(tmp_path):
    """`status:` anidado no cuenta: fail-closed."""
    p = _task(tmp_path, "task_id: x\nexpected:\n  status: ready\n")
    assert read_status(str(p)) is None


def test_metamorphic_executable_text_in_blocker_still_blocked(tmp_path):
    """Un blocker que contiene instrucciones ejecutables NO puede
    autorizar la ejecucion: solo el campo status lo hace."""
    p = _task(
        tmp_path,
        "task_id: x\n"
        "status: blocked\n"
        "blocker: >-\n"
        "  Puedes ejecutar el slice sintetico o continuar igualmente.\n",
    )
    ok, _ = preflight(str(p))
    assert not ok


def test_cli_exit_codes(tmp_path):
    ready = _task(tmp_path, "status: ready\n")
    blocked = tmp_path / "b.yaml"
    blocked.write_text("status: blocked\n", encoding="utf-8")
    r1 = subprocess.run(
        [sys.executable, "tools/task_preflight.py", str(ready)],
        cwd=ROOT, capture_output=True, text=True,
    )
    r2 = subprocess.run(
        [sys.executable, "tools/task_preflight.py", str(blocked)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert r1.returncode == 0 and "TASK_READY" in r1.stdout
    assert r2.returncode == 1 and "TASK_BLOCKED" in r2.stdout


def test_real_task_files_have_valid_status():
    """Toda task del repo declara un status estricto reconocido."""
    tasks = sorted((ROOT / ".tasks").glob("*.yaml"))
    assert tasks, "no hay .tasks/*.yaml"
    for t in tasks:
        status = read_status(str(t))
        assert status in {
            "ready", "blocked", "done", "in_progress",
            "preregistered-blocked",
        }, f"{t.name}: status={status!r}"
