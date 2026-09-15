"""G2-F — auditoria de replay byte-identico de la cadena autoritativa.

Task ``g2-f-closeout``. Recomputa cada artefacto congelado y compara
bytes canonicos (FINREG_CANONICAL_JSON_V1):

1. Comparaciones G2-B: ``normalize_eba_psd2_zip`` sobre los zips raw
   congelados -> ``compare_observations`` -> doc -> bytes == fixture.
   Los sha256 de los zips se verifican contra el content_id declarado
   por los manifiestos de adquisicion.
2. Eventos G2-C + fixture E0 + export OpenLineage: se regeneran con
   los builders congelados (subproceso) y se exige ``git status``
   limpio en los directorios de salida — regeneracion byte-identica
   sobre el path real de emision.
3. Los 18 probes E0 se reevaluan con ``assess_bitemporal`` contra el
   fixture (independiente de pytest).

Uso: ``python tools/audit_g2f_replay.py`` — exit 0 si todo replayea.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finreg_es.bitemporal import assess_bitemporal, load_evidence_set
from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.snapshot_diff import ObservationRef, compare_observations
from finreg_es.snapshot_normalize import (
    FINREG_G2_EBA_NORMALIZATION_V1,
    normalize_eba_psd2_zip,
)

SOURCES = ROOT / "fixtures/g2/sources"

# Pares congelados: observation refs reconstruidos desde los
# manifiestos de adquisicion (manifest-g2-d01, manifest-g2-acq-2026-09-15)
# y el precedente g0.5 declarado en ellos.
_PAIRS = [
    {
        "file": "fixtures/g2/comparisons/eba-psd2-20260913-vs-20260914.json",
        "artifact": "g2-b-comparison-eba-psd2-20260913-20260914",
        "left": (
            ROOT / "fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip",
            "948429ad71ea0ccbc03abe8d21eab7082075e09377874852b0fd265c2e0e1f31",
            "2026-09-13",
            "2026-09-13T08:00:04Z",
        ),
        "right": (
            SOURCES / "raw/eba-psd2-202609141600.zip",
            "8e28bb2519277ce5887323e81918cdea571c3ae14f5a967b950fb6bf06808208",
            "2026-09-14T19:36:43Z",
            "2026-09-14T16:00:14Z",
        ),
    },
    {
        "file": "fixtures/g2/comparisons/eba-psd2-20260914-vs-20260915.json",
        "artifact": "g2-b-comparison-eba-psd2-20260914-20260915",
        "left": (
            SOURCES / "raw/eba-psd2-202609141600.zip",
            "8e28bb2519277ce5887323e81918cdea571c3ae14f5a967b950fb6bf06808208",
            "2026-09-14T19:36:43Z",
            "2026-09-14T16:00:14Z",
        ),
        "right": (
            SOURCES / "raw/eba-psd2-202609150000.zip",
            "a582908cfa99f3ab7a0d369c68fbc3186d3069f9af7306d846fed4eb908596e2",
            "2026-09-15T02:35:43Z",
            "2026-09-15T00:00:40Z",
        ),
    },
]

_BUILDERS = [
    (
        "eventos G2-C",
        [sys.executable, str(ROOT / "tools/build_g2c1_events.py")],
        "fixtures/g2/events",
    ),
    (
        "fixture E0",
        [sys.executable, str(ROOT / "tools/build_g2e0_cases.py")],
        "fixtures/g2/e0",
    ),
    (
        "export OpenLineage",
        [sys.executable, "-m", "finreg_es.openlineage_export"],
        "openlineage",
    ),
]

EVIDENCE_SET_PATH = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
CASES_PATH = ROOT / "fixtures/g2/e0/bitemporal-cases.json"


def _jsonable(obj):
    if isinstance(obj, tuple):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def _obs(zip_path: Path, sha: str, retrieved: str, as_of: str):
    raw = zip_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != sha:
        raise SystemExit(
            f"FAIL {zip_path.name}: sha256 {digest[:16]}… != "
            f"content_id declarado {sha[:16]}…"
        )
    return ObservationRef(
        register_id="eba-psd2-register",
        series_key="eba-psd2-register|full",
        snapshot_file=zip_path.name,
        content_sha256=sha,
        retrieved_at=retrieved,
        source_as_of=as_of,
        completeness="complete",
        normalization_version=FINREG_G2_EBA_NORMALIZATION_V1,
    )


def replay_comparisons() -> list[str]:
    failures = []
    for pair in _PAIRS:
        lz, lsha, lret, lasof = pair["left"]
        rz, rsha, rret, rasof = pair["right"]
        left = _obs(lz, lsha, lret, lasof)
        right = _obs(rz, rsha, rret, rasof)
        left_records = normalize_eba_psd2_zip(str(lz))
        right_records = normalize_eba_psd2_zip(str(rz))
        result = compare_observations(left, right, left_records, right_records)
        doc = {
            "artifact": pair["artifact"],
            "changes": _jsonable(result["changes"]),
            "comparison": result["comparison"],
            "record_counts": {
                "left": len(left_records),
                "right": len(right_records),
            },
        }
        frozen = (ROOT / pair["file"]).read_bytes()
        if canonical_json(doc).encode("utf-8") != frozen:
            failures.append(pair["file"])
    return failures


def replay_builders() -> list[str]:
    failures = []
    for name, cmd, watch in _BUILDERS:
        run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if run.returncode != 0:
            failures.append(f"{name}: builder exit {run.returncode}")
            continue
        status = subprocess.run(
            ["git", "status", "--porcelain", watch],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if status.stdout.strip():
            failures.append(f"{name}: regeneracion no byte-identica")
    return failures


def replay_probes() -> list[str]:
    fixture = strict_json_loads(CASES_PATH.read_text(encoding="utf-8"))
    evidence_set = load_evidence_set(EVIDENCE_SET_PATH)
    contracts = {
        c.register_id: c
        for c in (
            load_contract(p)
            for p in sorted((ROOT / "fixtures/contracts").glob("*.json"))
        )
    }
    failures = []
    n = 0
    for case in fixture["cases"]:
        q = case["query"]
        for probe in case["probes"]:
            n += 1
            r = assess_bitemporal(
                case["entity_id"],
                activity=q["activity"],
                jurisdiction=q["jurisdiction"],
                territorial_basis=q["territorial_basis"],
                valid_at=probe["valid_at"],
                known_at=probe["known_at"],
                evidence_set=evidence_set,
                contracts=contracts,
            )
            ev = r["evidence"]
            if not (
                r["assessment"] == probe["expected_assessment"]
                and r["reason"] == probe["expected_reason"]
                and ev["usable_assertion_ids"] == probe["usable_assertion_ids"]
                and ev["excluded_after_known_at_assertion_ids"]
                == probe["excluded_after_K_assertion_ids"]
                and ev["usable_reported_fact_ids"] == probe["usable_fact_ids"]
                and ev["excluded_after_known_at_fact_ids"]
                == probe["excluded_after_K_fact_ids"]
                and r["used_assertion_ids"] == probe["used_assertion_ids"]
                and r["diagnostics"] == probe["diagnostics"]
            ):
                failures.append(
                    f"{case['case_id']} ({probe['valid_at']},"
                    f"{probe['known_at']})"
                )
    if n != 18:
        failures.append(f"probes={n} != 18")
    return failures


def main() -> int:
    checks = [
        ("comparaciones G2-B (2 pares reales)", replay_comparisons),
        ("builders + git-clean (eventos, E0, OpenLineage)", replay_builders),
        ("18 probes bitemporales", replay_probes),
    ]
    failed = False
    for name, fn in checks:
        problems = fn()
        if problems:
            failed = True
            print(f"FAIL {name}: {problems}")
        else:
            print(f"PASS {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
