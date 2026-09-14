"""G0.6 — Provenance & reproducibility verification.

Gate de verificacion, no de construccion: no extrae datos nuevos ni
ejecuta assessment. Relee el run sucesor congelado de G0.5-A y produce

1. un ledger de claims con provenance por campo extraido (G0.6-A/D):
   cada valor observado queda ligado a snapshot sha256, autoridad,
   registro, locator de registro, retrieved_at, source_as_of, version
   del extractor, valor raw y regla de normalizacion versionada;
2. un informe de verificacion con replay offline, deteccion de mutacion
   de fuente e inmutabilidad de artefactos historicos (G0.6-B/C/E/F).

Todo es determinista y recomputable a partir de los artefactos
congelados; el informe solo registra lo que los tests vuelven a exigir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .canonical import canonical_json, strict_json_loads
from .extraction import (
    _flatten_strings,
    _property,
    _verify_snapshot,
    run_extraction,
)
from .identity import LEI_DIAGNOSTIC_VERSION, is_valid_lei, lei_diagnostic


LEDGER_VERSION = "FINREG_G06_CLAIM_PROVENANCE_V1"
REPORT_VERSION = "FINREG_G06_PROVENANCE_VERIFICATION_V1"

# Autoridad y registro que sustentan cada fuente del corpus. Las fuentes
# CNMV_ESI_FPS y BDE_MFI_CLASSIFICATION_ES son vistas/publicaciones del
# registro de entidades de su autoridad; se ligan al contrato del registro
# subyacente.
SOURCE_PROVENANCE = {
    "ESMA_MICA_REGISTER": {
        "authority": "European Securities and Markets Authority (ESMA)",
        "register_id": "ESMA_MICA_REGISTER",
    },
    "EBA_PSD2_REGISTER": {
        "authority": "European Banking Authority (EBA)",
        "register_id": "EBA_PSD2_REGISTER",
    },
    "CNMV_ESI_FPS": {
        "authority": "CNMV",
        "register_id": "CNMV_REGISTRO_EMPRESAS",
    },
    "BDE_MFI_CLASSIFICATION_ES": {
        "authority": "Banco de Espana",
        "register_id": "BDE_REGISTRO_ENTIDADES",
    },
    # G1-D: extract estructurado del listado CNMV de PSC (MiCA).
    "CNMV_PSC_REGISTER": {
        "authority": "Comisión Nacional del Mercado de Valores (CNMV)",
        "register_id": "CNMV_PSC_REGISTER",
    },
    # G1-D: registro especial BdE de entidades de servicios de pago
    # (sucursales/agentes de EP y EDE extranjeras comunitarias).
    "BDE_REGISTRO_SERVICIOS_PAGO": {
        "authority": "Banco de Espana",
        "register_id": "BDE_REGISTRO_SERVICIOS_PAGO",
    },
    # G1-E: registro BdE de entidades comunitarias con establecimiento
    # en Espana (sucursales + actividades por capacidad declaradas).
    "BDE_REGISTRO_CON_ESTABLECIMIENTO": {
        "authority": "Banco de Espana",
        "register_id": "BDE_REGISTRO_CON_ESTABLECIMIENTO",
    },
    # G1-D-F01: fuentes primarias del mecanismo home MiCA (la fecha ESMA
    # ac_authorisationNotificationDate no distingue art.63 de art.60).
    "BAFIN_UNTERNEHMENSDATENBANK": {
        "authority": "Bundesanstalt fuer Finanzdienstleistungsaufsicht (BaFin)",
        "register_id": "BAFIN_UNTERNEHMENSDATENBANK",
    },
    "FINANSTILSYNET_REGISTRY": {
        "authority": "Finanstilsynet (Norwegian Financial Supervisory Authority)",
        "register_id": "FINANSTILSYNET_REGISTRY",
    },
}

# Traza raw -> normalized por campo observado. Cada entrada declara la
# regla aplicada y la referencia raw (columna CSV, property EBA, atributo
# de registro o locator del resumen CNMV). Es la respuesta ejecutable a
# "por que FinReg dice exactamente este valor".
FIELD_TRACES: dict[str, dict[str, tuple[str, str | None]]] = {
    "ESMA_MICA_REGISTER": {
        "legal_name": ("COPY", "ae_lei_name"),
        "lei": ("COPY", "ae_lei"),
        "lei_valid": ("IS_VALID_LEI", "ae_lei"),
        "lei_diagnostic": ("LEI_DIAGNOSTIC_V2", "ae_lei"),
        "home_member_state": ("COPY", "ae_homeMemberState"),
        "competent_authority": ("COPY", "ae_competentAuthority"),
        "commercial_name": ("COPY", "ae_commercial_name"),
        "service_codes_raw": ("COPY", "ac_serviceCode"),
        "service_countries_raw": ("COPY", "ac_serviceCode_cou"),
        "authorisation_notification_date": (
            "COPY",
            "ac_authorisationNotificationDate",
        ),
        "authorisation_end_date": ("EMPTY_TO_NULL", "ac_authorisationEndDate"),
        "last_update": ("COPY", "ac_lastupdate"),
    },
    "EBA_PSD2_REGISTER": {
        "legal_name": ("PROPERTY", "ENT_NAM"),
        "commercial_name": ("PROPERTY", "ENT_NAM_COM"),
        "entity_code": ("ATTR", "EntityCode"),
        "entity_type": ("ATTR", "EntityType"),
        "national_reference_code": ("PROPERTY", "ENT_NAT_REF_COD"),
        "country": ("PROPERTY", "ENT_COU_RES"),
        "ent_aut_raw": ("PROPERTY", "ENT_AUT"),
        "ent_aut_raw_type": ("TYPE_NAME", "ENT_AUT"),
        "services_raw": ("ATTR", "Services"),
        "service_codes": ("FLATTEN_STRINGS", "Services"),
        "entity_version": ("ATTR", "__EBA_EntityVersion"),
    },
    "CNMV_ESI_FPS": {
        "legal_name": ("CNMV_TEXT_EXTRACT", "spanTituloCabecera"),
        "official_number": ("CNMV_TEXT_EXTRACT", "registration_number"),
        "registration_date": ("CNMV_TEXT_EXTRACT", "registration_date"),
        "country": ("CNMV_TEXT_EXTRACT", "country"),
        "lei": ("NOT_PUBLISHED", None),
    },
    "BDE_MFI_CLASSIFICATION_ES": {
        "legal_name": ("COPY", "NOMBRE"),
        "european_code": ("COPY", "CÓDIGO EUROPEO"),
        "lei": ("EMPTY_TO_NULL", "LEI"),
        "lei_valid": ("IS_VALID_LEI", "LEI"),
        "lei_diagnostic": ("LEI_DIAGNOSTIC_V2", "LEI"),
        "category": ("COPY", "CATEGORÍA"),
        # La columna tal cual no aparece verbatim en la cabecera publicada
        # (viene con padding): el extractor aplica default "".
        "supervisor_code": ("COPY_OR_EMPTY", "CÓDIGO DE SUPERVISOR"),
    },
}

RULE_VERSION = {
    "LEI_DIAGNOSTIC_V2": LEI_DIAGNOSTIC_VERSION,
}

# Anclas de provenance exigidas a todo claim (G0.6-A). source_as_of es
# nullable por diseno: su ausencia se declara con UNAVAILABLE, no se
# rellena con retrieved_at.
REQUIRED_PROVENANCE_FIELDS = (
    "authority",
    "register_id",
    "snapshot_file",
    "snapshot_sha256",
    "record_key",
    "raw_record_sha256",
    "rule",
    "rule_version",
    "parser",
    "extractor_version",
    "retrieved_at",
)

# Artefactos historicos cuya inmutabilidad byte-exacta demuestra G0.6-F:
# (path relativo, commit que fija su estado congelado).
FROZEN_ARTIFACTS = (
    ("fixtures/g0.5/corpus/entities.json", "a3ed773"),
    ("fixtures/g0.5/corpus/ground-truth.json", "a3ed773"),
    ("fixtures/g0.5/sources/manifest.json", "a3ed773"),
    ("fixtures/g0.5/runs/g0.5-a-2026-09-13-001.json", "090b95f"),
    ("fixtures/g0.5/audit/g0.5-b-corpus-audit.json", "3db9dfc"),
    ("fixtures/g0.5/audit/gleif-lei-lookups-2026-09-13.json", "3db9dfc"),
    ("fixtures/g0.5/audit/g0.5-b-preregistration-resolution.json", "9320663"),
    ("fixtures/g0.5/runs/g0.5-a-2026-09-13-002.json", "7826e9e"),
    ("fixtures/g0.5/runs/g0.5-a-2026-09-13-003.json", "6e94ce0"),
)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record_sha256(raw_record: Any) -> str:
    if isinstance(raw_record, str):
        return _sha256_bytes(raw_record.encode("utf-8"))
    return _sha256_bytes(canonical_json(raw_record).encode("utf-8"))


def _raw_value(raw_record: Any, rule: str, ref: str | None) -> Any:
    if rule in {"PROPERTY", "TYPE_NAME"}:
        return _property(raw_record, ref)
    if rule == "CNMV_TEXT_EXTRACT":
        return raw_record  # el resumen limpio ES la evidencia raw
    if rule == "NOT_PUBLISHED":
        return None
    return raw_record.get(ref)


def _normalized_from_raw(rule: str, raw_value: Any) -> Any:
    if rule in {"COPY", "PROPERTY", "ATTR", "CNMV_TEXT_EXTRACT"}:
        return raw_value
    if rule == "COPY_OR_EMPTY":
        return raw_value or ""
    if rule == "EMPTY_TO_NULL":
        return raw_value or None
    if rule == "IS_VALID_LEI":
        return is_valid_lei(raw_value or "")
    if rule == "LEI_DIAGNOSTIC_V2":
        return lei_diagnostic(raw_value)
    if rule == "FLATTEN_STRINGS":
        return _flatten_strings(raw_value)
    if rule == "TYPE_NAME":
        return type(raw_value).__name__
    if rule == "NOT_PUBLISHED":
        return None
    raise ValueError(f"regla de traza desconocida: {rule}")


def _rule_version(rule: str, extractor_version: str) -> str:
    return RULE_VERSION.get(rule, extractor_version)


def claim_ledger(run_result: dict[str, Any], source_manifest: dict[str, Any]) -> dict[str, Any]:
    """Ledger de claims del run: un claim por campo observado parseado."""
    manifest_items = {
        item["snapshot_file"]: item for item in source_manifest["snapshots"]
    }
    run_meta = run_result["run"]
    claims: list[dict[str, Any]] = []
    untraced_fields: list[dict[str, Any]] = []
    for attempt in run_result["attempts"]:
        source = attempt["source"]
        if attempt["parse"]["status"] != "PARSE_OK":
            continue
        record = attempt["parse"]["record"]
        item = manifest_items[attempt["snapshot_file"]]
        source_as_of = item.get("source_as_of")
        traces = FIELD_TRACES[source]
        observed = record["observed"]
        for field in observed:
            if field not in traces:
                untraced_fields.append(
                    {
                        "corpus_id": attempt["corpus_id"],
                        "source": source,
                        "field": field,
                    }
                )
        semantics = attempt["semantics"]
        for field, (rule, ref) in traces.items():
            raw_value = _raw_value(record["raw_record"], rule, ref)
            claims.append(
                {
                    "claim_id": f"{attempt['corpus_id']}|{source}|{field}",
                    "corpus_id": attempt["corpus_id"],
                    "source": source,
                    "field": field,
                    "authority": SOURCE_PROVENANCE[source]["authority"],
                    "register_id": SOURCE_PROVENANCE[source]["register_id"],
                    "snapshot_file": attempt["snapshot_file"],
                    "snapshot_sha256": attempt["source_snapshot_sha"],
                    "record_key": attempt["source_record_key"],
                    "raw_record_sha256": record["raw_record_sha256"],
                    "raw_value": raw_value,
                    "normalized_value": observed.get(field),
                    "rule": rule,
                    "rule_version": _rule_version(rule, run_meta["run_version"]),
                    "parser": attempt["parse"]["parser"],
                    "extractor_version": run_meta["run_version"],
                    "retrieved_at": source_manifest["retrieved_at"],
                    "extracted_at": run_meta["executed_at"],
                    "source_as_of": source_as_of,
                    "source_date_reliability": (
                        "TRUSTED" if source_as_of is not None else "UNAVAILABLE"
                    ),
                    "semantic_derivation": {
                        "status": semantics.get("status"),
                        "reason": semantics.get("reason"),
                    },
                    "assertion_candidate": (
                        "NOT_CREATED"
                        if attempt["assessment"]["status"] == "NOT_RUN"
                        else "CREATED"
                    ),
                }
            )
    return {
        "ledger": {
            "ledger_id": f"g0.6-claim-provenance-{run_meta['run_id']}",
            "ledger_version": LEDGER_VERSION,
            "run_id": run_meta["run_id"],
            "run_result_sha": run_result["result_sha"],
            "claims_total": len(claims),
            "untraced_fields": untraced_fields,
        },
        "claims": claims,
    }


def verify_ledger_claims(
    run_result: dict[str, Any], ledger: dict[str, Any]
) -> list[dict[str, Any]]:
    """Re-deriva cada claim desde el raw_record del intento.

    Devuelve la lista de errores; vacia significa que toda la cadena
    raw -> parsed -> normalized es reconstruible con la regla declarada.
    """
    attempts = {
        (a["corpus_id"], a["source"]): a for a in run_result["attempts"]
    }
    errors: list[dict[str, Any]] = []
    for claim in ledger["claims"]:
        attempt = attempts.get((claim["corpus_id"], claim["source"]))
        if attempt is None:
            errors.append({"claim_id": claim["claim_id"], "error": "NO_ATTEMPT"})
            continue
        record = attempt["parse"]["record"]
        raw_record = record["raw_record"]
        rule, ref = FIELD_TRACES[claim["source"]][claim["field"]]
        raw_value = _raw_value(raw_record, rule, ref)
        if claim["raw_value"] != raw_value:
            errors.append({"claim_id": claim["claim_id"], "error": "RAW_MISMATCH"})
            continue
        normalized = claim["normalized_value"]
        if rule == "CNMV_TEXT_EXTRACT":
            ok = isinstance(normalized, str) and normalized in raw_record
        else:
            ok = normalized == _normalized_from_raw(rule, raw_value)
        if not ok:
            errors.append(
                {"claim_id": claim["claim_id"], "error": "NORMALIZED_MISMATCH"}
            )
            continue
        if claim["raw_record_sha256"] != _record_sha256(raw_record):
            errors.append(
                {"claim_id": claim["claim_id"], "error": "RAW_HASH_MISMATCH"}
            )
    return errors


def _git_unchanged(commit: str, rel_path: str, repo_root: Path) -> bool | None:
    """True si ``git diff <commit> HEAD -- path`` esta vacio."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--exit-code", commit, "HEAD", "--", rel_path],
            cwd=repo_root,
            capture_output=True,
        )
    except OSError:
        return None
    return proc.returncode == 0


def verification_report(
    repo_root: Path, run_path: Path, verified_at: str
) -> dict[str, Any]:
    """Informe del gate: recomputa replay, ledger, mutacion e historia."""
    run_result = strict_json_loads(run_path.read_text(encoding="utf-8"))
    run_meta = run_result["run"]
    manifest = strict_json_loads(
        (repo_root / "fixtures" / "g0.5" / "sources" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    ledger = claim_ledger(run_result, manifest)
    trace_errors = verify_ledger_claims(run_result, ledger)
    claims = ledger["claims"]
    orphans = [
        claim["claim_id"]
        for claim in claims
        if any(not claim.get(field) for field in REQUIRED_PROVENANCE_FIELDS)
    ]

    replay = run_extraction(
        repo_root,
        run_id=run_meta["run_id"],
        corpus_sha=run_meta["corpus_sha"],
        contracts_sha=run_meta["contracts_sha"],
        source_baseline_sha=run_meta["source_baseline_sha"],
        executed_at=run_meta["executed_at"],
        supersedes_run_id=run_meta["supersedes_run_id"],
    )

    # Demostracion G0.6-C sobre un snapshot real: mismo identificador,
    # contenido alterado => mismatch detectable con linaje expected/observed;
    # mismos bytes => misma identidad. El snapshot original no se toca.
    mutation_demo: dict[str, Any] = {}
    item = manifest["snapshots"][0]
    real_path = repo_root / "fixtures" / "g0.5" / "sources" / item["snapshot_file"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        rel = Path(*item["snapshot_file"].split("/"))
        staged = tmp_root / rel
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(real_path.read_bytes())
        ok_result = _verify_snapshot(tmp_root, item)
        staged.write_bytes(real_path.read_bytes() + b"\x00")
        mutated = _verify_snapshot(tmp_root, item)
        mutation_demo = {
            "snapshot_file": item["snapshot_file"],
            "same_bytes_status": ok_result["status"],
            "same_bytes_sha256": ok_result.get("sha256"),
            "mutated_status": mutated["status"],
            "mutated_reason": mutated.get("reason"),
            "expected_sha256": mutated.get("expected_sha256"),
            "observed_sha256": mutated.get("observed_sha256"),
            "original_file_unchanged": _sha256_bytes(real_path.read_bytes())
            == item["sha256"],
        }

    original_run = strict_json_loads(
        (repo_root / "fixtures" / "g0.5" / "runs" / "g0.5-a-2026-09-13-001.json").read_text(
            encoding="utf-8"
        )
    )
    frozen = [
        {
            "path": rel,
            "sha256": _sha256_bytes((repo_root / rel).read_bytes()),
            "frozen_commit": commit,
            "unchanged_since_commit": _git_unchanged(commit, rel, repo_root),
        }
        for rel, commit in FROZEN_ARTIFACTS
    ]

    all_ok = (
        not orphans
        and not trace_errors
        and not ledger["ledger"]["untraced_fields"]
        and replay["result_sha"] == run_result["result_sha"]
        and mutation_demo["mutated_reason"] == "SNAPSHOT_HASH_OR_SIZE_MISMATCH"
        and mutation_demo["original_file_unchanged"]
        and all(row["unchanged_since_commit"] for row in frozen)
    )
    return {
        "report": {
            "gate": "G0.6",
            "report_version": REPORT_VERSION,
            "status": "PASS" if all_ok else "FAIL",
            "verified_at": verified_at,
            "subgates": {
                "G0.6-A": {
                    "claims_total": len(claims),
                    "claims_without_provenance": len(orphans),
                    "orphan_claim_ids": orphans,
                    "untraced_fields": ledger["ledger"]["untraced_fields"],
                },
                "G0.6-B": {
                    "run_id": run_meta["run_id"],
                    "expected_result_sha": run_result["result_sha"],
                    "replayed_result_sha": replay["result_sha"],
                    "canonical_output_identical": replay["result_sha"]
                    == run_result["result_sha"],
                    "entities_attempted": replay["summary"]["entities_attempted"],
                    "source_attempts": replay["summary"]["source_attempts"],
                    "network_access": "NOT_REQUIRED",
                },
                "G0.6-C": mutation_demo,
                "G0.6-D": {
                    "claims_with_full_trace": len(claims) - len(trace_errors),
                    "trace_errors": trace_errors,
                    "assertion_candidates_created": sum(
                        claim["assertion_candidate"] == "CREATED" for claim in claims
                    ),
                },
                "G0.6-E": {
                    "suspect_rule": (
                        "content_hash(t1) != content_hash(t2) AND "
                        "source_as_of(t1) == source_as_of(t2) => SUSPECT"
                    ),
                    "fixture": "fixtures/g0.6/temporal/suspect-source-as-of.json",
                    "sources_with_source_as_of": sorted(
                        item["snapshot_file"]
                        for item in manifest["snapshots"]
                        if item.get("source_as_of")
                    ),
                },
                "G0.6-F": {
                    "artifacts_checked": len(frozen),
                    "artifacts_unchanged": all(
                        row["unchanged_since_commit"] for row in frozen
                    ),
                },
            },
            "frozen_artifacts": frozen,
            "history": {
                "original_run_id": original_run["run"]["run_id"],
                "original_run_recorded_unexpected": original_run["summary"][
                    "unexpected_divergences"
                ],
                "audited_strict_unexpected": 9,
                "successor_run_ids": [
                    "g0.5-a-2026-09-13-002",
                    "g0.5-a-2026-09-13-003",
                ],
                "policy": "SUCCESSORS_NOT_REPLACEMENTS",
            },
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--run",
        type=Path,
        default=Path("fixtures/g0.5/runs/g0.5-a-2026-09-13-003.json"),
    )
    parser.add_argument("--ledger-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--verified-at", required=True)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    run_result = strict_json_loads(args.run.read_text(encoding="utf-8"))
    manifest = strict_json_loads(
        (repo_root / "fixtures" / "g0.5" / "sources" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    ledger = claim_ledger(run_result, manifest)
    report = verification_report(repo_root, args.run, args.verified_at)

    args.ledger_out.parent.mkdir(parents=True, exist_ok=True)
    with args.ledger_out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(ledger) + "\n")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    with args.report_out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(report) + "\n")
    print(
        json.dumps(
            {
                "claims_total": ledger["ledger"]["claims_total"],
                "report_status": report["report"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
