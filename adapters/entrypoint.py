"""G3-E — entrypoint del console script ``finreg``.

Contrato congelado: ``docs/g3-e0-packaging-contract.md`` S7.

Shim minimo stdlib-only: el wheel base instala con
``project.dependencies = []``, asi que este modulo no puede
importar typer a nivel de modulo. Si el extra ``cli`` no esta
instalado, emite un error estructurado en stderr y sale con codigo
!= 0 — nunca un traceback como resultado publico.
"""
from __future__ import annotations

import sys
from importlib.util import find_spec


def main() -> None:
    if find_spec("typer") is None:
        from finreg_es.canonical import canonical_json

        print(
            canonical_json(
                {
                    "error": {
                        "code": "missing_extra",
                        "message": (
                            "el CLI es un extra opcional: "
                            "instale finreg-es[cli]"
                        ),
                    }
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
    from adapters.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
