"""G3-B — CLI read-only (Typer).

    python -m adapters.cli --help

Cada comando llama a ``adapters.common`` y emite el payload FinReg
como canonical JSON en stdout. Errores de interfaz: JSON
estructurado en stderr + exit 1. Cero escrituras.
"""
from __future__ import annotations

from typing import Optional

import typer

from adapters import common
from finreg_es.canonical import canonical_json

app = typer.Typer(
    name="finreg-es",
    help="Superficie read-only del motor FinReg-ES (G3-B).",
    no_args_is_help=True,
)

_EVIDENCE_SET = typer.Option(
    common.DEFAULT_EVIDENCE_SET,
    "--evidence-set",
    help="Path al artefacto derived-assertions congelado.",
)
_EVIDENCE_SET_ID = typer.Option(
    None,
    "--evidence-set-id",
    help="Pin del universo: <stem>@sha256:<hex>. Mismatch = error.",
)
_CONTRACTS_DIR = typer.Option(
    common.DEFAULT_CONTRACTS_DIR, "--contracts-dir"
)


def _emit(payload: dict) -> None:
    typer.echo(canonical_json(payload))


def _fail(exc: common.AdapterError) -> None:
    typer.echo(canonical_json(exc.to_dict()), err=True)
    raise typer.Exit(1)


@app.command()
def assess(
    entity_id: str = typer.Option(..., "--entity-id"),
    activity: str = typer.Option(..., "--activity"),
    jurisdiction: str = typer.Option(..., "--jurisdiction"),
    valid_at: str = typer.Option(..., "--valid-at"),
    territorial_basis: Optional[str] = typer.Option(
        None, "--territorial-basis"
    ),
    evidence_set: str = _EVIDENCE_SET,
    evidence_set_id: Optional[str] = _EVIDENCE_SET_ID,
    contracts_dir: str = _CONTRACTS_DIR,
) -> None:
    """Assessment actual: V3 con as_of=valid_at."""
    try:
        _emit(
            common.op_assess(
                entity_id,
                activity,
                jurisdiction,
                valid_at,
                territorial_basis,
                evidence_set_path=evidence_set,
                evidence_set_id=evidence_set_id,
                contracts_dir=contracts_dir,
            )
        )
    except common.AdapterError as exc:
        _fail(exc)


@app.command(name="assess-bitemporal")
def assess_bitemporal(
    entity_id: str = typer.Option(..., "--entity-id"),
    activity: str = typer.Option(..., "--activity"),
    jurisdiction: str = typer.Option(..., "--jurisdiction"),
    valid_at: str = typer.Option(..., "--valid-at"),
    known_at: str = typer.Option(..., "--known-at"),
    territorial_basis: Optional[str] = typer.Option(
        None, "--territorial-basis"
    ),
    evidence_set: str = _EVIDENCE_SET,
    evidence_set_id: Optional[str] = _EVIDENCE_SET_ID,
    contracts_dir: str = _CONTRACTS_DIR,
) -> None:
    """AssessmentQuery(valid_at x known_at) sobre evidencia versionada."""
    try:
        _emit(
            common.op_assess_bitemporal(
                entity_id,
                activity,
                jurisdiction,
                valid_at,
                known_at,
                territorial_basis,
                evidence_set_path=evidence_set,
                evidence_set_id=evidence_set_id,
                contracts_dir=contracts_dir,
            )
        )
    except common.AdapterError as exc:
        _fail(exc)


@app.command()
def evidence(
    item_id: Optional[str] = typer.Option(None, "--item-id"),
    entity_id: Optional[str] = typer.Option(None, "--entity-id"),
    evidence_set: str = _EVIDENCE_SET,
    evidence_set_id: Optional[str] = _EVIDENCE_SET_ID,
) -> None:
    """Item por id (con source_assertions) o universo de una entidad."""
    try:
        _emit(
            common.op_evidence(
                item_id,
                entity_id,
                evidence_set_path=evidence_set,
                evidence_set_id=evidence_set_id,
            )
        )
    except common.AdapterError as exc:
        _fail(exc)


@app.command()
def explain(
    entity_id: str = typer.Option(..., "--entity-id"),
    activity: str = typer.Option(..., "--activity"),
    jurisdiction: str = typer.Option(..., "--jurisdiction"),
    valid_at: str = typer.Option(..., "--valid-at"),
    known_at: Optional[str] = typer.Option(None, "--known-at"),
    territorial_basis: Optional[str] = typer.Option(
        None, "--territorial-basis"
    ),
    evidence_set: str = _EVIDENCE_SET,
    evidence_set_id: Optional[str] = _EVIDENCE_SET_ID,
    contracts_dir: str = _CONTRACTS_DIR,
) -> None:
    """Explicacion: reason + diagnostics + assertion_evaluations del core."""
    try:
        _emit(
            common.op_explain(
                entity_id,
                activity,
                jurisdiction,
                valid_at,
                territorial_basis,
                known_at,
                evidence_set_path=evidence_set,
                evidence_set_id=evidence_set_id,
                contracts_dir=contracts_dir,
            )
        )
    except common.AdapterError as exc:
        _fail(exc)


@app.command()
def changes(
    record_key: Optional[str] = typer.Option(None, "--record-key"),
    pair: Optional[str] = typer.Option(None, "--pair"),
    events_dir: str = typer.Option(
        common.DEFAULT_EVENTS_DIR, "--events-dir"
    ),
) -> None:
    """Candidatos a evento regulatorio de los artefactos G2-C."""
    try:
        _emit(common.op_changes(record_key, pair, events_dir=events_dir))
    except common.AdapterError as exc:
        _fail(exc)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
