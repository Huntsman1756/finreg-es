"""G2-B — diff estructural de snapshots normalizados.

Contrato: docs/g2-snapshot-history-contract.md. Sin semantica juridica.

Arquitectura (scan g2-b-oss-scan-diff.md, PORT_PATTERN sobre el modelo
de cambio de dictdiffer: added / removed / changed):

- La NORMALIZACION convierte bytes de fuente en records canonicalizados
  keyed por ``record_key`` (contrato §3). Las clases de campo viven en
  la spec de normalizacion: un ``set`` se canonicaliza a lista ordenada
  (reordenar => 0 cambios); un ``ordered`` conserva su orden (reordenar
  => cambio); un ``nested keyed`` se compone recursivamente por clave.
- El DIFFER compara records ya canonicalizados: exacto, recursivo sobre
  dicts, y distingue ``missing`` de ``null`` (contrato §6).
- La COMPARACION aplica los gates de comparabilidad del contrato:
  misma series_key, misma normalization_version, succession_state,
  completitud del slice para admisibilidad de removals.

El differ nunca emite fechas juridicas ni decide que un cambio sea
regulatorio: eso es G2-C. Un record ausente en el lado derecho es
como mucho STRUCTURAL_REMOVAL, y solo si ambos lados declaran el
slice completo (contrato §5).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MISSING = "__finreg_missing__"


@dataclass(frozen=True)
class ObservationRef:
    """Identidad de una observacion de snapshot (contrato §1-§5)."""

    register_id: str
    series_key: str
    snapshot_file: str
    content_sha256: str
    retrieved_at: str
    source_as_of: str | None
    completeness: str  # "complete" | "partial" | "unknown"
    normalization_version: str

    @property
    def content_id(self) -> str:
        return self.content_sha256

    @property
    def observation_id(self) -> str:
        return f"{self.register_id}|{self.retrieved_at}|{self.content_sha256[:16]}"


def diff_value(path: tuple[str, ...], old: Any, new: Any) -> list[dict]:
    """Diff estructural entre dos valores canonicalizados.

    ``missing`` y ``null`` son distintos (contrato §6): un campo que
    desaparece emite kind=removed; un campo que pasa a null emite
    kind=changed con new=None.
    """
    changes: list[dict] = []
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            o = old.get(key, MISSING)
            n = new.get(key, MISSING)
            if o is MISSING:
                changes.append({"kind": "added", "path": path + (key,), "new": n})
            elif n is MISSING:
                changes.append({"kind": "removed", "path": path + (key,), "old": o})
            else:
                changes.extend(diff_value(path + (key,), o, n))
    elif old != new:
        changes.append({"kind": "changed", "path": path, "old": old, "new": new})
    return changes


def diff_records(
    left: dict[str, dict], right: dict[str, dict]
) -> dict[str, list]:
    """Diff de dos conjuntos de records keyed.

    Record-level: added/removed. Field-level: lista plana de cambios
    ``added``/``removed``/``changed`` con ``record_key`` y ``path``.
    """
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    changed: list[dict] = []
    for key in sorted(set(left) & set(right)):
        for c in diff_value((), left[key], right[key]):
            changed.append({"record_key": key, **c})
    return {"added": added, "removed": removed, "changed": changed}


def _succession_state(left: ObservationRef, right: ObservationRef) -> str:
    """Estado de sucesion de la serie (contrato §9)."""
    if left.source_as_of is None or right.source_as_of is None:
        return "UNKNOWN_SOURCE_AS_OF"
    if right.source_as_of > left.source_as_of:
        return "NORMAL_SUCCESSION"
    if right.source_as_of == left.source_as_of:
        return "SAME_AS_OF_REVISION"
    return "SOURCE_AS_OF_REGRESSION"


def compare_observations(
    left: ObservationRef,
    right: ObservationRef,
    left_records: dict[str, dict],
    right_records: dict[str, dict],
) -> dict:
    """Comparacion entre dos observaciones con gates del contrato.

    Salida separada en dos partes (contrato G2-B):

    - ``comparison``: metadatos — observation_ids, series, succession
      state, normalization_version, completeness, comparable, findings.
    - ``changes``: added / removed / changed (vacio si no comparable).

    Reglas:

    - series distintas => error de invocacion, no un resultado (§2).
    - normalization_version distinta => NON_COMPARABLE_NORMALIZATION_VERSION,
      comparable=False, cero cambios (§4).
    - mismo content_id => short-circuit, cero cambios sin entrar al
      record differ (§1, caso B01).
    - removed solo admisible como STRUCTURAL_REMOVAL si ambos lados son
      ``complete`` para el slice (§5); si no, se reporta con
      ``removal_admissible=False`` y finding NO_REMOVAL_ADMISSIBLE.
    """
    if left.series_key != right.series_key:
        raise ValueError(
            "series distintas no son comparables: "
            f"{left.series_key!r} vs {right.series_key!r}"
        )

    findings: list[dict] = []
    comparable = True

    if left.normalization_version != right.normalization_version:
        comparable = False
        findings.append(
            {
                "classification": "NON_COMPARABLE_NORMALIZATION_VERSION",
                "detail": (
                    f"{left.normalization_version} vs "
                    f"{right.normalization_version}: re-extraer ambos "
                    "lados bajo la misma version (contrato §4)"
                ),
            }
        )

    succession = _succession_state(left, right)
    if succession == "SOURCE_AS_OF_REGRESSION":
        findings.append(
            {
                "classification": "SOURCE_AS_OF_REGRESSION",
                "detail": (
                    f"source_as_of retrocede: {left.source_as_of} -> "
                    f"{right.source_as_of}; bloquea inferencia de sucesion"
                ),
            }
        )
    elif succession == "SAME_AS_OF_REVISION" and left.content_id != right.content_id:
        findings.append(
            {
                "classification": "SAME_AS_OF_REVISION",
                "detail": (
                    "mismo source_as_of con contenido distinto: "
                    "correccion/republicacion, no un nuevo periodo "
                    "juridico (source_date_reliability=SUSPECT)"
                ),
            }
        )

    identical = left.content_id == right.content_id
    if identical:
        changes: dict[str, list] = {"added": [], "removed": [], "changed": []}
    elif comparable:
        changes = diff_records(left_records, right_records)
    else:
        changes = {"added": [], "removed": [], "changed": []}

    removal_admissible = (
        left.completeness == "complete" and right.completeness == "complete"
    )
    if changes["removed"] and not removal_admissible:
        findings.append(
            {
                "classification": "NO_REMOVAL_ADMISSIBLE",
                "detail": (
                    f"{len(changes['removed'])} records no observados en el "
                    "lado derecho pero el slice no es completo en ambos "
                    "lados; no constituyen STRUCTURAL_REMOVAL (contrato §5)"
                ),
            }
        )

    return {
        "comparison": {
            "left_observation_id": left.observation_id,
            "right_observation_id": right.observation_id,
            "series_key": left.series_key,
            "succession_state": succession,
            "normalization_version": left.normalization_version,
            "completeness": {
                "left": left.completeness,
                "right": right.completeness,
            },
            "comparable": comparable,
            "identical_content": identical,
            "removal_admissible": removal_admissible,
            "findings": findings,
        },
        "changes": changes,
    }
