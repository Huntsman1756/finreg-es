"""G3-B — servidor MCP read-only (SDK oficial v2, stdio).

    python -m adapters.mcp_server

Expone las 5 operaciones del contrato como tools MCP sobre
``adapters.common`` — el payload FinReg es el mismo dict que emite
el CLI. Cero semantica, cero escrituras.
"""
from __future__ import annotations

from mcp.server import MCPServer

from adapters import common

server = MCPServer("finreg-es")


@server.tool(
    description="Assessment actual: V3 con as_of=valid_at sobre el "
    "evidence set congelado."
)
def assess(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    territorial_basis: str | None = None,
) -> dict:
    return common.op_assess(
        entity_id, activity, jurisdiction, valid_at, territorial_basis
    )


@server.tool(
    description="AssessmentQuery(valid_at x known_at): filtra la "
    "evidencia por known_at y delega en V3 con as_of=valid_at."
)
def assess_bitemporal(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    known_at: str,
    territorial_basis: str | None = None,
) -> dict:
    return common.op_assess_bitemporal(
        entity_id,
        activity,
        jurisdiction,
        valid_at,
        known_at,
        territorial_basis,
    )


@server.tool(
    description="Item del evidence set por item_id (con "
    "source_assertions) o universo por entity_id."
)
def evidence(
    item_id: str | None = None, entity_id: str | None = None
) -> dict:
    return common.op_evidence(item_id, entity_id)


@server.tool(
    description="Explicacion read-only: reason + diagnostics + "
    "assertion_evaluations que el core ya devuelve; known_at "
    "opcional anade la auditoria de evidencia."
)
def explain(
    entity_id: str,
    activity: str,
    jurisdiction: str,
    valid_at: str,
    known_at: str | None = None,
    territorial_basis: str | None = None,
) -> dict:
    return common.op_explain(
        entity_id,
        activity,
        jurisdiction,
        valid_at,
        territorial_basis,
        known_at,
    )


@server.tool(
    description="Candidatos a evento regulatorio de los artefactos "
    "G2-C congelados; record_key/pair filtran."
)
def changes(
    record_key: str | None = None, pair: str | None = None
) -> dict:
    return common.op_changes(record_key, pair)


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
