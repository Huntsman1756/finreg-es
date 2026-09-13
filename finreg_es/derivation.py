"""G0.7-A — Derivacion SourceAssertion[] -> EntitlementAssertion[].

Interprete determinista del ruleset congelado
``fixtures/g0.7/derivation-rules.json`` sobre el ledger de claims de
G0.6. No ejecuta assessment: produce aserciones de entitlement,
findings clasificados de derivacion y el indice de identidad del corpus.

Reglas congeladas del modulo:
  - ningun fallo de derivacion inventa una asercion positiva: produce un
    finding con clasificacion de la taxonomia del ruleset;
  - ninguna regla emite NOT_ENTITLED: el corpus no contiene evidencia
    negativa explicita ni enumeracion completa verificada;
  - identificadores con diagnostico LEI distinto de VALID nunca entran
    en el indice de identidad (no soportan joins); el raw se conserva;
  - N fuentes que repiten el mismo hecho soportan una unica conclusion:
    la multiplicidad de evidencia no es multiplicidad juridica.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .canonical import canonical_json, strict_json_loads
from .identity import Identifier, IdentityIndexEntry
from .semantics import EntitlementAssertion, SourceAssertion
from .vocab import LegalEffect


DERIVATION_VERSION = "FINREG_G07_DERIVATION_V1"
ARTIFACT_VERSION = "FINREG_G07_DERIVED_ASSERTIONS_V1"

# Identificadores admitidos como clave de join en el indice de identidad
# del corpus. Los LEI solo entran si su diagnostico V2 es VALID.
IDENTIFIER_KIND_BY_FIELD = {
    ("EBA_PSD2_REGISTER", "entity_code"): "BDE_REGISTRY_ID",
    ("CNMV_ESI_FPS", "official_number"): "CNMV_REGISTRY_ID",
    ("BDE_MFI_CLASSIFICATION_ES", "european_code"): "BDE_REGISTRY_ID",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_ddmmyyyy(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _group_claims(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Agrupa claims por (corpus_id, source) conservando el orden del run."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for claim in ledger["claims"]:
        key = (claim["corpus_id"], claim["source"])
        group = groups.setdefault(
            key,
            {
                "corpus_id": claim["corpus_id"],
                "source": claim["source"],
                "fields": {},
                "raws": {},
                "claim_ids": [],
                "context": {
                    "authority": claim["authority"],
                    "register_id": claim["register_id"],
                    "snapshot_file": claim["snapshot_file"],
                    "snapshot_sha256": claim["snapshot_sha256"],
                    "record_key": claim["record_key"],
                    "raw_record_sha256": claim["raw_record_sha256"],
                    "extractor_version": claim["extractor_version"],
                    "retrieved_at": claim["retrieved_at"],
                    "source_as_of": claim["source_as_of"],
                    "source_date_reliability": claim["source_date_reliability"],
                },
            },
        )
        group["fields"][claim["field"]] = claim["normalized_value"]
        group["raws"][claim["field"]] = claim["raw_value"]
        group["claim_ids"].append(claim["claim_id"])
    return list(groups.values())


def _source_assertion(group: dict[str, Any], manifest: dict[str, Any]) -> dict:
    ctx = group["context"]
    item = next(
        s for s in manifest["snapshots"] if s["snapshot_file"] == ctx["snapshot_file"]
    )
    return {
        "authority": ctx["authority"],
        "register_id": ctx["register_id"],
        "source_url": item["source_url"],
        "retrieved_at": ctx["retrieved_at"],
        # date.fromisoformat exige componente fecha: el datetime EBA se
        # reduce a su parte de fecha (el raw completo queda en raw_value).
        "source_as_of": (
            ctx["source_as_of"].split("T")[0] if ctx["source_as_of"] else None
        ),
        "source_date_reliability": ctx["source_date_reliability"],
        "raw_value": canonical_json(
            {"record_key": ctx["record_key"], "fields": group["raws"]}
        ),
        "raw_snapshot_sha256": ctx["snapshot_sha256"],
        "extractor_version": ctx["extractor_version"],
        "observed_current": True,
    }


def _condition(fields: dict[str, Any], condition: dict[str, Any]) -> bool:
    value = fields.get(condition["field"])
    op = condition["op"]
    if op == "EQ":
        return value == condition["value"]
    if op == "NOT_NULL":
        return value is not None and value != ""
    if op == "IN":
        return value in condition["value"]
    if op == "NOT_IN":
        return value not in condition["value"]
    raise ValueError(f"operador de condicion desconocido: {op}")


def _iterate_items(
    fields: dict[str, Any], spec: dict[str, Any]
) -> list[str] | None:
    raw = fields.get(spec["field"])
    if spec["mode"] == "SPLIT":
        if not isinstance(raw, str) or not raw.strip():
            return None
        items = [part.strip() for part in raw.split(spec["separator"])]
    elif spec["mode"] == "DICT_KEYS":
        if not isinstance(raw, list):
            return None
        items = [key for entry in raw if isinstance(entry, dict) for key in entry]
    else:
        raise ValueError(f"modo de iteracion desconocido: {spec['mode']}")
    excluded = set(spec.get("exclude_values", []))
    if spec.get("exclude_field_value"):
        excluded.add(fields.get(spec["exclude_field_value"]))
    seen: list[str] = []
    for item in items:
        if item and item not in excluded and item not in seen:
            seen.append(item)
    return seen


def _resolve_effective(
    spec: dict[str, Any] | None,
    fields: dict[str, Any],
    evidence_as_of: str,
) -> tuple[str | None, bool]:
    """Devuelve (valor_iso, ok). ok=False => REQUIRED_FIELD_UNDERIVABLE."""
    if spec is None or spec["derivation"] == "CONSTANT_NULL":
        return None, True
    kind = spec["derivation"]
    if kind == "EVIDENCE_AS_OF":
        return evidence_as_of, True
    if kind == "FIELD_DDMMYYYY":
        parsed = _parse_ddmmyyyy(fields.get(spec["field"]))
        return parsed, parsed is not None
    if kind == "FIELD_DDMMYYYY_OR_NULL":
        return _parse_ddmmyyyy(fields.get(spec["field"])), True
    raise ValueError(f"derivacion efectiva desconocida: {kind}")


def _emit_assertion(
    assertion_id: str,
    emit: dict[str, Any],
    group: dict[str, Any],
    evidence_as_of: str,
    source_assertion: dict[str, Any],
    item: str | None,
    findings: list[dict[str, Any]],
    rule: dict[str, Any],
) -> dict[str, Any] | None:
    """Materializa una asercion desde el bloque emit de la regla.

    Devuelve None (con finding registrado) cuando la derivacion falla:
    ningun fallo produce una asercion positiva inventada.
    """
    fields = group["fields"]

    def _resolve(key: str, failure: str) -> str | None:
        mapped = emit.get(f"{key}_from")
        if mapped is not None:
            value = fields.get(mapped["field"])
            result = mapped["map"].get(value)
            if result is None:
                findings.append(
                    _finding(group, rule, failure, f"{mapped['field']}={value!r} no mapeable")
                )
            return result
        literal = emit.get(key)
        if literal == "$ITEM":
            return item
        return literal

    entity_class = _resolve("entity_class", "UNSUPPORTED_ENTITY_CLASS")
    activity = _resolve("activity", "UNSUPPORTED_ACTIVITY_MAPPING")
    jurisdiction = _resolve("jurisdiction", "UNSUPPORTED_ACTIVITY_MAPPING")
    if entity_class is None or activity is None or jurisdiction is None:
        return None

    effective_from, ok = _resolve_effective(
        emit.get("effective_from"), fields, evidence_as_of
    )
    if not ok:
        findings.append(
            _finding(
                group,
                rule,
                "REQUIRED_FIELD_UNDERIVABLE",
                f"effective_from no derivable desde {emit['effective_from']}",
            )
        )
        return None
    effective_to, ok = _resolve_effective(
        emit.get("effective_to"), fields, evidence_as_of
    )
    if not ok:
        findings.append(
            _finding(
                group,
                rule,
                "REQUIRED_FIELD_UNDERIVABLE",
                f"effective_to no derivable desde {emit['effective_to']}",
            )
        )
        return None

    return {
        "assertion_id": assertion_id,
        "register_id": group["context"]["register_id"],
        "entity_id": group["corpus_id"],
        "entity_class": entity_class,
        "activity": activity,
        "jurisdiction": jurisdiction,
        "legal_effect": emit["legal_effect"],
        "entry_mechanism": emit["entry_mechanism"],
        "territorial_basis": emit["territorial_basis"],
        "legal_basis": emit["legal_basis"],
        "effective_from": effective_from,
        "effective_to": effective_to,
        "scope": emit["scope"],
        "rule_id": rule["rule_id"],
        "ruleset_version": DERIVATION_VERSION,
        "source_claim_ids": group["claim_ids"],
        "source_assertions": [source_assertion],
        "derived_by": None,
        "principal_entity_id": None,
    }


def _finding(
    group: dict[str, Any] | None,
    rule: dict[str, Any],
    classification: str,
    detail: str,
    entity_id: str | None = None,
) -> dict[str, Any]:
    return {
        "finding_id": None,  # asignado en secuencia al final
        "corpus_id": entity_id or (group["corpus_id"] if group else None),
        "source": group["source"] if group else None,
        "rule_id": rule["rule_id"],
        "classification": classification,
        "detail": detail,
    }


def build_identity_index(
    corpus: dict[str, Any], groups: list[dict[str, Any]], manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Indice de identidad del corpus + identificadores invalidos.

    Solo entran identificadores verificados: LEI con diagnostico VALID y
    codigos de registro de fuente. El entity_id es el corpus_id: el
    corpus congelado ES el marco de identidad de G0.5.
    """
    groups_by_entity: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        groups_by_entity.setdefault(group["corpus_id"], []).append(group)

    index: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for entity in corpus["entities"]:
        corpus_id = entity["corpus_id"]
        identifiers: list[dict[str, str]] = []
        classes: list[str] = []
        for group in groups_by_entity.get(corpus_id, []):
            item = next(
                s
                for s in manifest["snapshots"]
                if s["snapshot_file"] == group["context"]["snapshot_file"]
            )
            lei = group["fields"].get("lei")
            diagnostic = group["fields"].get("lei_diagnostic")
            if lei and diagnostic == "VALID":
                identifiers.append(
                    {
                        "kind": "LEI",
                        "value": lei,
                        "source_url": item["source_url"],
                        "retrieved_at": group["context"]["retrieved_at"],
                    }
                )
            elif lei:
                invalid.append(
                    {
                        "corpus_id": corpus_id,
                        "kind": "LEI",
                        "value": lei,
                        "lei_diagnostic": diagnostic,
                    }
                )
            for (source, field_name), id_kind in IDENTIFIER_KIND_BY_FIELD.items():
                if source != group["source"]:
                    continue
                value = group["fields"].get(field_name)
                if value:
                    identifiers.append(
                        {
                            "kind": id_kind,
                            "value": str(value),
                            "source_url": item["source_url"],
                            "retrieved_at": group["context"]["retrieved_at"],
                        }
                    )
        index.append(
            {
                "entity_id": corpus_id,
                "legal_name": entity["legal_name"],
                "entity_classes": classes,
                "identifiers": identifiers,
                "principal_entity_id": None,
            }
        )
    return index, invalid


def derive_entitlements(
    ledger: dict[str, Any],
    ruleset: dict[str, Any],
    manifest: dict[str, Any],
    corpus: dict[str, Any],
) -> dict[str, Any]:
    """Ejecuta el ruleset sobre el ledger: aserciones + findings + indice."""
    spec = ruleset["ruleset"]
    groups = _group_claims(ledger)
    evidence_as_of = manifest["retrieved_at"]
    assertions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    for group in groups:
        fields = group["fields"]
        source_assertion = _source_assertion(group, manifest)
        for rule in spec["rules"]:
            match = rule["match"]
            if match["source"] != group["source"]:
                continue
            if not all(_condition(fields, c) for c in match["conditions"]):
                continue
            missing = [
                f for f in rule.get("required_fields", []) if fields.get(f) is None
            ]
            if missing:
                findings.append(
                    _finding(
                        group, rule, "REQUIRED_FIELD_MISSING", f"campos: {missing}"
                    )
                )
                continue
            if "emit_per" in rule:
                items = _iterate_items(fields, rule["emit_per"]["iterate"])
                if not items:
                    continue
                emits = [(rule["emit_per"]["emit"], item) for item in items]
            elif rule.get("emit") is None:
                spec_finding = rule["finding"]
                findings.append(
                    _finding(group, rule, spec_finding["classification"], spec_finding["detail"])
                )
                continue
            else:
                emits = [(rule["emit"], None)]
            for emit, item in emits:
                assertion = _emit_assertion(
                    f"g07-asm-{len(assertions) + 1:03d}",
                    emit,
                    group,
                    evidence_as_of,
                    source_assertion,
                    item,
                    findings,
                    rule,
                )
                if assertion is not None:
                    assertions.append(assertion)

    # Segunda pasada: reglas derivadas sobre las aserciones emitidas.
    for rule in spec["derived_rules"]:
        base = rule["base"]
        fired = False
        for assertion in list(assertions):
            if not all(assertion[k] == v for k, v in base.items()):
                continue
            fired = True
            derived = {
                "assertion_id": f"g07-asm-{len(assertions) + 1:03d}",
                "register_id": assertion["register_id"],
                "entity_id": assertion["entity_id"],
                "entity_class": assertion["entity_class"],
                "activity": rule["emit"]["activity"],
                "jurisdiction": assertion["jurisdiction"],
                "legal_effect": rule["emit"]["legal_effect"],
                "entry_mechanism": rule["emit"]["entry_mechanism"],
                "territorial_basis": assertion["territorial_basis"],
                "legal_basis": rule["emit"]["legal_basis"],
                "effective_from": assertion["effective_from"],
                "effective_to": assertion["effective_to"],
                "scope": rule["emit"]["scope"],
                "rule_id": rule["rule_id"],
                "ruleset_version": rule["ruleset_version"],
                "source_claim_ids": assertion["source_claim_ids"],
                "source_assertions": assertion["source_assertions"],
                "derived_by": {
                    "rule_id": rule["rule_id"],
                    "ruleset_version": rule["ruleset_version"],
                    "effective_from": assertion["effective_from"],
                },
                "principal_entity_id": None,
            }
            assertions.append(derived)
        if not fired:
            candidates = {
                a["entity_id"]
                for a in assertions
                if a["entity_class"] == base["entity_class"]
            }
            for entity_id in sorted(candidates):
                findings.append(
                    _finding(
                        None,
                        rule,
                        rule["untriggered_finding"]["classification"],
                        rule["untriggered_finding"]["detail"],
                        entity_id=entity_id,
                    )
                )

    for index, finding in enumerate(findings, start=1):
        finding["finding_id"] = f"g07-fnd-{index:03d}"

    # Clases evidenciadas: union de las clases de las aserciones emitidas.
    index, invalid = build_identity_index(corpus, groups, manifest)
    classes_by_entity: dict[str, set[str]] = {}
    for assertion in assertions:
        classes_by_entity.setdefault(assertion["entity_id"], set()).add(
            assertion["entity_class"]
        )
    for entry in index:
        entry["entity_classes"] = sorted(classes_by_entity.get(entry["entity_id"], ()))

    return {
        "assertions": assertions,
        "findings": findings,
        "identity_index": index,
        "invalid_identifiers": invalid,
    }


def to_entitlement_assertions(artifact: dict[str, Any]) -> list[EntitlementAssertion]:
    return [
        EntitlementAssertion(
            assertion_id=a["assertion_id"],
            register_id=a["register_id"],
            entity_id=a["entity_id"],
            entity_class=a["entity_class"],
            activity=a["activity"],
            jurisdiction=a["jurisdiction"],
            legal_effect=LegalEffect(a["legal_effect"]),
            entry_mechanism=a["entry_mechanism"],
            territorial_basis=a["territorial_basis"],
            legal_basis=a["legal_basis"],
            effective_from=a["effective_from"],
            effective_to=a["effective_to"],
            scope=a["scope"],
            source_assertions=tuple(
                SourceAssertion(**s) for s in a["source_assertions"]
            ),
            derived_by=a.get("derived_by"),
            principal_entity_id=a.get("principal_entity_id"),
        )
        for a in artifact["assertions"]
    ]


def to_identity_index(artifact: dict[str, Any]) -> list[IdentityIndexEntry]:
    return [
        IdentityIndexEntry(
            entity_id=e["entity_id"],
            legal_name=e["legal_name"],
            entity_classes=tuple(e["entity_classes"]),
            identifiers=tuple(
                Identifier(
                    kind=i["kind"],
                    value=i["value"],
                    source_url=i["source_url"],
                    retrieved_at=i["retrieved_at"],
                )
                for i in e["identifiers"]
            ),
            principal_entity_id=e.get("principal_entity_id"),
        )
        for e in artifact["identity_index"]
    ]


def build_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto congelado de G0.7-A: inputs fijados por sha256."""
    ledger_path = repo_root / "fixtures" / "g0.6" / "claim-provenance-g0.5-a-003.json"
    ruleset_path = repo_root / "fixtures" / "g0.7" / "derivation-rules.json"
    corpus_path = repo_root / "fixtures" / "g0.5" / "corpus" / "entities.json"
    manifest_path = repo_root / "fixtures" / "g0.5" / "sources" / "manifest.json"

    ledger = strict_json_loads(ledger_path.read_text(encoding="utf-8"))
    ruleset = strict_json_loads(ruleset_path.read_text(encoding="utf-8"))
    corpus = strict_json_loads(corpus_path.read_text(encoding="utf-8"))
    manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))

    result = derive_entitlements(ledger, ruleset, manifest, corpus)
    return {
        "artifact": {
            "artifact_version": ARTIFACT_VERSION,
            "derivation_version": DERIVATION_VERSION,
            "ruleset_version": ruleset["ruleset"]["ruleset_version"],
            "claims_ledger_sha256": _sha256_file(ledger_path),
            "derivation_ruleset_sha256": _sha256_file(ruleset_path),
            "corpus_sha256": _sha256_file(corpus_path),
            "source_manifest_sha256": _sha256_file(manifest_path),
            "claims_consumed": len(ledger["claims"]),
            "assertions_emitted": len(result["assertions"]),
            "findings_emitted": len(result["findings"]),
            "assessment": "NOT_RUN",
        },
        **result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    artifact = build_artifact(args.repo_root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(artifact) + "\n")
    summary = artifact["artifact"]
    print(
        f"assertions={summary['assertions_emitted']} "
        f"findings={summary['findings_emitted']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
