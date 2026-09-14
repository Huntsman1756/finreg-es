"""Genera los artefactos G2-C1 de candidatos a evento regulatorio.

Entradas (task .tasks/g2-c1.yaml):

1. Par real EBA congelado — ``fixtures/g2/comparisons/eba-psd2-
   20260913-vs-20260914.json`` (0/0/0 cambios => 0 candidatos; la capa
   se ejecuta y no hay nada que clasificar).
2. Slice sintetico del contrato — decision expresa del blocker del task
   (``docs/g2-c0-change-event-contract.md``: "espera primer Type-B/C
   real o slice sintetico decidido expresamente"). Se construye con la
   maquinaria real: records sinteticos -> ``compare_observations`` ->
   ``classify_changes``; cubre cada fila del catalogo EBA.

Salida: ``fixtures/g2/events/*.json`` en serializacion canonica
(FINREG_CANONICAL_JSON_V1), mismo formato que el artefacto G2-B.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finreg_es.canonical import canonical_json, sha256_hex, strict_json_loads
from finreg_es.change_events import FINREG_G2C_EVENT_RULES_V1, classify_changes
from finreg_es.snapshot_diff import ObservationRef, compare_observations

COMPARISON = ROOT / "fixtures/g2/comparisons/eba-psd2-20260913-vs-20260914.json"
OUT_DIR = ROOT / "fixtures/g2/events"


def _emit(path: Path, doc: dict) -> None:
    path.write_bytes(canonical_json(doc).encode("utf-8"))
    print(f"{path.relative_to(ROOT)}  sha256={sha256_hex(doc)[:16]}…")


def _jsonable(obj):
    """tuplas -> listas: la forma canonica JSON del diff (los paths del
    differ en memoria son tuplas; en artefacto son arrays)."""
    if isinstance(obj, tuple):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def _events_doc(artifact: str, source_comparison: dict, result: dict,
                comparison_section: dict) -> dict:
    return {
        "artifact": artifact,
        "rules_version": FINREG_G2C_EVENT_RULES_V1,
        "contract": "docs/g2-c0-change-event-contract.md",
        "source_comparison": source_comparison,
        "observation": result["observation"],
        "comparison": comparison_section,
        "candidates": result["candidates"],
        "summary": result["summary"],
    }


def _real() -> None:
    raw = COMPARISON.read_bytes()
    doc = strict_json_loads(raw.decode("utf-8"))
    result = classify_changes(doc)
    _emit(
        OUT_DIR / "eba-psd2-20260913-vs-20260914.json",
        _events_doc(
            "g2-c1-events-eba-psd2-20260913-20260914",
            {
                "kind": "frozen-comparison",
                "file": "fixtures/g2/comparisons/eba-psd2-20260913-vs-20260914.json",
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
            result,
            doc["comparison"],
        ),
    )


def _obs(sha: str, retrieved: str, as_of: str) -> ObservationRef:
    return ObservationRef(
        register_id="eba-psd2-register",
        series_key="eba-psd2-register|full",
        snapshot_file="synthetic",
        content_sha256=sha,
        retrieved_at=retrieved,
        source_as_of=as_of,
        completeness="complete",
        normalization_version="FINREG_G2_EBA_NORMALIZATION_V1",
    )


def _record(ent_aut=None, es=None, name="Synthetic S.A.", owner="CA-1"):
    properties = {"ENT_NAM": name}
    if ent_aut is not None:
        properties["ENT_AUT"] = ent_aut
    services = {}
    if es is not None:
        services["ES"] = es
    return {
        "ca_owner_id": owner,
        "properties": properties,
        "services": services,
    }


def _synthetic() -> None:
    """Slice sintetico del contrato: una fila por regla del catalogo EBA.

    Trazado claramente como sintetico (observation_ids y record_keys con
    marca SYNTH); NO es evidencia real — demuestra la capa G2-C sobre el
    contrato mientras no haya un Type-B/C real (blocker del task).
    """
    left_records = {
        # ENT_AUT append en posicion par -> ROOT_WITHDRAWAL_CANDIDATE
        "PSD_PI:SYNTH_WITHDRAWN": _record(ent_aut=["2020-01-01"]),
        # ENT_AUT append en posicion impar -> ROOT_REAUTHORISATION_CANDIDATE
        "PSD_PI:SYNTH_REAUTH": _record(ent_aut=["2019-01-01", "2020-06-01"]),
        # services.ES + PS_070 -> CAPABILITY_APPEARED_CANDIDATE
        "PSD_PI:SYNTH_CAP_PLUS": _record(es=["PS_01"]),
        # services.ES - PS_070 -> CAPABILITY_DISAPPEARED_CANDIDATE
        "PSD_PI:SYNTH_CAP_MINUS": _record(es=["PS_01", "PS_070"]),
        # properties.ENT_NAM changed -> UNCLASSIFIED_STRUCTURAL_CHANGE
        "PSD_PI:SYNTH_RENAMED": _record(name="Nombre Antiguo S.A."),
        # services.FR changed -> UNCLASSIFIED (catalogo preregistra ES)
        "PSD_PI:SYNTH_FR": {
            **_record(),
            "services": {"FR": ["PS_01"]},
        },
        # presente solo en left -> ENTITY_RECORD_DISAPPEARED
        "PSD_PI:SYNTH_GONE": _record(ent_aut=["2018-05-05"]),
    }
    right_records = {
        "PSD_PI:SYNTH_WITHDRAWN": _record(ent_aut=["2020-01-01", "2026-09-10"]),
        "PSD_PI:SYNTH_REAUTH": _record(
            ent_aut=["2019-01-01", "2020-06-01", "2026-09-11"]
        ),
        "PSD_PI:SYNTH_CAP_PLUS": _record(es=["PS_01", "PS_070"]),
        "PSD_PI:SYNTH_CAP_MINUS": _record(es=["PS_01"]),
        "PSD_PI:SYNTH_RENAMED": _record(name="Nombre Nuevo S.A."),
        "PSD_PI:SYNTH_FR": {
            **_record(),
            "services": {"FR": ["PS_01", "PS_02"]},
        },
        # nuevo en right -> ENTITY_RECORD_APPEARED
        "PSD_PI:SYNTH_NEW": _record(ent_aut=["2026-09-09"]),
    }
    left = _obs("synthetic-g2c1-left", "2026-09-20", "2026-09-20")
    right = _obs("synthetic-g2c1-right", "2026-09-21", "2026-09-21")
    comparison = _jsonable(
        compare_observations(left, right, left_records, right_records)
    )
    result = classify_changes(comparison)
    _emit(
        OUT_DIR / "g2-c1-synthetic-contract-slice.json",
        _events_doc(
            "g2-c1-events-synthetic-contract-slice",
            {
                "kind": "synthetic-contract-slice",
                "sha256": sha256_hex(comparison),
                "detail": "records sinteticos por contrato G2-C0; no es "
                "evidencia real — el par EBA real produjo 0/0/0 y el "
                "primer Type-B/C real sigue pendiente",
            },
            result,
            comparison["comparison"],
        ),
    )


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _real()
    _synthetic()
