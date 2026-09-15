"""Preflight ejecutable de tasks FinReg (.tasks/*.yaml).

STATUS IS AUTHORITATIVE. Regla fail-closed:

    status: ready            -> exit 0  (ejecutable)
    cualquier otro status    -> exit 1  (BLOCKED/STOP)
    status ausente           -> exit 1
    status desconocido       -> exit 1
    linea status no top-level-> exit 1

No es un parser YAML: exige una linea top-level estricta
``status: <valor>``. Las instrucciones en lenguaje natural del task
(blocker, next_options, comentarios) NUNCA pueden autorizar una
ejecucion — solo este campo lo hace.

Uso:
    python tools/task_preflight.py .tasks/g2-c1.yaml
    exit 0  => procede
    exit 1  => imprime TASK_BLOCKED + razon, cero writes
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_STATUS_LINE = re.compile(r"^status:\s*([A-Za-z_-]+)\s*$", re.MULTILINE)
_KNOWN = {"ready", "blocked", "done", "in_progress", "preregistered-blocked"}


def read_status(path: str) -> str | None:
    """Lee el campo status top-level de un task file (fail-closed)."""
    text = Path(path).read_text(encoding="utf-8")
    found = _STATUS_LINE.search(text)
    if not found:
        return None
    return found.group(1)


def preflight(path: str) -> tuple[bool, str]:
    """(ejecutable, mensaje). Solo ``ready`` autoriza."""
    status = read_status(path)
    if status is None:
        return False, "TASK_BLOCKED: sin linea top-level `status:` estricta"
    if status not in _KNOWN:
        return False, f"TASK_BLOCKED: status desconocido {status!r}"
    if status != "ready":
        return False, f"TASK_BLOCKED: status={status!r} (solo 'ready' ejecuta)"
    return True, "TASK_READY"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python tools/task_preflight.py .tasks/<id>.yaml")
        return 2
    ok, msg = preflight(argv[1])
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
