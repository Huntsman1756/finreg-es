"""G0.7-B — Real assessment run sobre artefactos congelados.

Ejecuta ``assess()`` (semantica G0.4 congelada) sobre los 21 casos
preregistrados de ``fixtures/g0.7/assessment-cases.json``, usando como
entradas unicas los artefactos fijados por sha256:

  corpus G0.5 -> ledger G0.6 -> ruleset + derivadas G0.7-A -> casos

El runner no modifica expectativas ni reclasifica nada: registra por
caso la consulta, las aserciones que cubren la unidad, las que
sustentan el veredicto, los claim ids de origen, el resultado del motor
y el match contra el preregistro. Las divergencias se auditan en
G0.7-C; este modulo solo las deja constar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical import canonical_json, strict_json_loads
from .contracts import load_contract
from .derivation import to_entitlement_assertions, to_identity_index
from .semantics import assess


ASSESSMENT_RUN_VERSION = "FINREG_G07B_ASSESSMENT_V1"
G1_ASSESSMENT_RUN_VERSION = "FINREG_G1_ASSESSMENT_V1"

G07_DIR = Path("fixtures") / "g0.7"
DERIVED_PATH = G07_DIR / "derived-assertions-g0.5-a-003.json"
RULESET_PATH = G07_DIR / "derivation-rules.json"
CASES_PATH = G07_DIR / "assessment-cases.json"
LEDGER_PATH = Path("fixtures") / "g0.6" / "claim-provenance-g0.5-a-003.json"
CORPUS_PATH = Path("fixtures") / "g0.5" / "corpus" / "entities.json"
MANIFEST_PATH = Path("fixtures") / "g0.5" / "sources" / "manifest.json"
CONTRACTS_DIR = Path("fixtures") / "contracts"

G1_DIR = Path("fixtures") / "g1"
G1_DERIVED_PATH = G1_DIR / "derived-assertions-g1-a-001.json"
G1_RULESET_PATH = G1_DIR / "derivation-rules-g1-a.json"
G1_CASES_PATH = G1_DIR / "assessment-cases.json"

G1C_DERIVED_PATH = G1_DIR / "derived-assertions-g1-c-001.json"
G1C_CASES_PATH = G1_DIR / "assessment-cases-g1-c.json"
G1C_LEDGER_PATH = G1_DIR / "claim-ledger-g1-c-001.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _code_sha(repo_root: Path) -> tuple[str, list[dict[str, str]]]:
    """Huella del codigo ejecutable: todos los modulos finreg_es/*.py."""
    parts: list[bytes] = []
    metadata: list[dict[str, str]] = []
    for path in sorted((repo_root / "finreg_es").glob("*.py")):
        relative = path.relative_to(repo_root).as_posix()
        payload = path.read_bytes()
        parts.extend([relative.encode("utf-8"), b"\0", payload, b"\0"])
        metadata.append({"path": relative, "sha256": hashlib.sha256(payload).hexdigest()})
    return hashlib.sha256(b"".join(parts)).hexdigest(), metadata


def _head_commit(repo_root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _load_contracts(repo_root: Path) -> dict[str, Any]:
    contracts_dir = repo_root / CONTRACTS_DIR
    return {
        contract.register_id: contract
        for contract in (
            load_contract(path) for path in sorted(contracts_dir.glob("*.json"))
        )
    }


def run_assessment(
    repo_root: Path,
    *,
    run_id: str,
    g1: bool = False,
    g1c: bool = False,
    executed_at: str | None = None,
    code_commit: str | None = None,
) -> dict[str, Any]:
    if g1c:
        artifact_path = repo_root / G1C_DERIVED_PATH
        ruleset_path = repo_root / G1_DIR / "derivation-rules.json"
        cases_path = repo_root / G1C_CASES_PATH
        ledger_path = repo_root / G1C_LEDGER_PATH
        run_version = G1_ASSESSMENT_RUN_VERSION
        gate = "G1-C6"
        semantics_version = "V2"
    elif g1:
        artifact_path = repo_root / G1_DERIVED_PATH
        ruleset_path = repo_root / G1_RULESET_PATH
        cases_path = repo_root / G1_CASES_PATH
        ledger_path = repo_root / LEDGER_PATH
        run_version = G1_ASSESSMENT_RUN_VERSION
        gate = "G1-A8"
        semantics_version = "V2"
    else:
        artifact_path = repo_root / DERIVED_PATH
        ruleset_path = repo_root / RULESET_PATH
        cases_path = repo_root / CASES_PATH
        ledger_path = repo_root / LEDGER_PATH
        run_version = ASSESSMENT_RUN_VERSION
        gate = "G0.7-B"
        semantics_version = "V1"
    corpus_path = repo_root / CORPUS_PATH

    artifact = strict_json_loads(artifact_path.read_text(encoding="utf-8"))
    cases_doc = strict_json_loads(cases_path.read_text(encoding="utf-8"))

    # Integridad de la cadena congelada: las derivadas solo valen si sus
    # inputs declarados coinciden con los ficheros vivos.
    declared = artifact["artifact"]
    input_shas = {
        "corpus_sha256": _sha256_file(corpus_path),
        "claims_ledger_sha256": _sha256_file(ledger_path),
        "derivation_ruleset_sha256": _sha256_file(ruleset_path),
        "assessment_cases_sha256": _sha256_file(cases_path),
        "derived_assertions_sha256": _sha256_file(artifact_path),
    }
    integrity = {
        key: declared[key] == input_shas[key]
        for key in ("corpus_sha256", "claims_ledger_sha256", "derivation_ruleset_sha256")
    }

    index = to_identity_index(artifact)
    assertions = to_entitlement_assertions(artifact)
    reported_facts = artifact.get("reported_facts", [])
    by_id = {a["assertion_id"]: a for a in artifact["assertions"]}
    contracts = _load_contracts(repo_root)

    case_results: list[dict[str, Any]] = []
    for case in cases_doc["cases"]:
        result = assess(
            case["entity_id"],
            index,
            activity=case["activity"],
            jurisdiction=case["jurisdiction"],
            as_of=case["as_of"],
            assertions=assertions,
            contracts=contracts,
            semantics_version=semantics_version,
            reported_facts=reported_facts if (g1 or g1c) else None,
        )
        matching_ids = [
            e["assertion_id"] for e in result.assertion_evaluations
        ]
        used_ids = [a["assertion_id"] for a in result.assertions]
        source_claim_ids = sorted(
            {
                claim_id
                for assertion_id in matching_ids
                for claim_id in by_id[assertion_id]["source_claim_ids"]
            }
        )
        entry_mechanisms = sorted(
            {a["entry_mechanism"] for a in result.assertions}
        )
        case_result = {
            "case_id": case["case_id"],
            "query": {
                "entity_id": case["entity_id"],
                "activity": case["activity"],
                "jurisdiction": case["jurisdiction"],
                "as_of": case["as_of"],
            },
            "identity_resolution": str(result.identity_resolution),
            "assessment": str(result.assessment),
            "reason": str(result.reason),
            "diagnostics": list(result.diagnostics),
            "matching_assertion_ids": matching_ids,
            "used_assertion_ids": used_ids,
            "derived_assertion_ids": [
                assertion_id
                for assertion_id in matching_ids
                if by_id[assertion_id].get("derived_by")
            ],
            "source_claim_ids": source_claim_ids,
            "assertion_evaluations": [
                dict(evaluation) for evaluation in result.assertion_evaluations
            ],
            # expected_* es salida-comparacion, nunca entrada del
            # motor: ausente no rompe la evaluacion, mutado solo
            # cambia los flags de match.
            "expected_assessment": case.get("expected_assessment"),
            "expected_reason": case.get("expected_reason"),
            "match": case.get("expected_assessment") is not None
            and str(result.assessment) == case["expected_assessment"],
            "reason_match": case.get("expected_reason") is not None
            and str(result.reason) == case["expected_reason"],
        }
        if g1 or g1c:
            matched_facts = [
                f["fact_id"]
                for f in reported_facts
                if f.get("corpus_id") == case["entity_id"]
            ]
            expected_mechanism = case.get("expected_entry_mechanism")
            case_result["matched_reported_fact_ids"] = matched_facts
            case_result["entry_mechanisms"] = entry_mechanisms
            case_result["expected_entry_mechanism"] = expected_mechanism
            case_result["entry_mechanism_match"] = (
                expected_mechanism is None
                or expected_mechanism in entry_mechanisms
            )
        case_results.append(case_result)

    mismatches = [c["case_id"] for c in case_results if not c["match"]]
    executed_at = executed_at or datetime.now(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    code_sha, code_files = _code_sha(repo_root)
    result: dict[str, Any] = {
        "run": {
            "run_id": run_id,
            "run_version": run_version,
            "gate": gate,
            "code_sha": code_sha,
            "code_files": code_files,
            "code_commit": code_commit,
            "derivation_version": declared["derivation_version"],
            "ruleset_version": declared["ruleset_version"],
            **input_shas,
            "frozen_input_integrity": integrity,
            "executed_at": executed_at,
            **({"semantics_version": "ASSESSMENT_SEMANTICS_V2"} if (g1 or g1c) else {}),
        },
        "summary": {
            "cases_total": len(case_results),
            "matches": sum(c["match"] for c in case_results),
            "mismatches": mismatches,
            "reason_mismatches": [
                c["case_id"] for c in case_results if not c["reason_match"]
            ],
            "assessments": {
                outcome: sum(c["assessment"] == outcome for c in case_results)
                for outcome in sorted({c["assessment"] for c in case_results})
            },
        },
        "cases": case_results,
    }
    result["result_sha"] = hashlib.sha256(
        canonical_json(result).encode("utf-8")
    ).hexdigest()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--g1", action="store_true",
                        help="Artefactos y casos G1-A + ASSESSMENT_SEMANTICS_V2")
    parser.add_argument("--g1c", action="store_true",
                        help="Artefactos y casos G1-C + ASSESSMENT_SEMANTICS_V2")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--executed-at")
    parser.add_argument("--code-commit")
    args = parser.parse_args(argv)

    result = run_assessment(
        args.repo_root.resolve(),
        run_id=args.run_id,
        g1=args.g1,
        g1c=args.g1c,
        executed_at=args.executed_at,
        code_commit=args.code_commit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(result) + "\n")
    print(
        json.dumps(
            {
                "run_id": result["run"]["run_id"],
                "result_sha": result["result_sha"],
                "cases_total": result["summary"]["cases_total"],
                "matches": result["summary"]["matches"],
                "mismatches": result["summary"]["mismatches"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
