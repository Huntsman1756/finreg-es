"""G0.7-A — Derivation rule freeze.

Congela las dos piezas que preceden a cualquier ejecucion de assess():
el ruleset de derivacion (SourceAssertion[] -> EntitlementAssertion[])
y el preregistro de casos (entity_id, activity, jurisdiction, as_of).
Los expected_* de los casos se fijaron por razonamiento sobre el
contrato congelado, antes de cualquier run de assessment; este modulo
NO ejecuta assess() — eso es G0.7-B.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.derivation import (
    ARTIFACT_VERSION,
    DERIVATION_VERSION,
    build_artifact,
    to_entitlement_assertions,
    to_identity_index,
)
from finreg_es.identity import resolve_by_identifier
from finreg_es.vocab import (
    ACTIVITIES,
    ENTITY_CLASSES,
    Assessment,
    AssessmentReason,
    IdentityResolutionState,
)


ROOT = Path(__file__).parents[2]
G07 = ROOT / "fixtures" / "g0.7"
RULESET_PATH = G07 / "derivation-rules.json"
CASES_PATH = G07 / "assessment-cases.json"
ARTIFACT_PATH = G07 / "derived-assertions-g0.5-a-003.json"
LEDGER_PATH = ROOT / "fixtures" / "g0.6" / "claim-provenance-g0.5-a-003.json"
CORPUS_PATH = ROOT / "fixtures" / "g0.5" / "corpus" / "entities.json"

REQUIRED_RULE_FIELDS = (
    "rule_id",
    "required_source_contract",
    "match",
    "required_fields",
    "coverage_preconditions",
    "failure_behavior",
    "rationale",
    "known_limitations",
)
REQUIRED_EMIT_FIELDS = (
    "activity",
    "jurisdiction",
    "territorial_basis",
    "legal_effect",
    "entry_mechanism",
    "legal_basis",
    "scope",
    "effective_from",
    "effective_to",
)


def _read(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------- ruleset


def test_ruleset_structure_and_frozen_vocabulary():
    ruleset = _read(RULESET_PATH)["ruleset"]
    assert ruleset["ruleset_version"] == DERIVATION_VERSION
    taxonomy = set(ruleset["failure_taxonomy"])

    rule_ids = [r["rule_id"] for r in ruleset["rules"]]
    assert len(rule_ids) == len(set(rule_ids))

    for rule in ruleset["rules"]:
        for field in REQUIRED_RULE_FIELDS:
            assert field in rule, (rule["rule_id"], field)
        assert rule["failure_behavior"] == "FINDING_AND_NO_ASSERTION"
        emits = [rule["emit"]] if rule.get("emit") else []
        if "emit_per" in rule:
            emits = [rule["emit_per"]["emit"]]
        if rule.get("finding"):
            assert rule["finding"]["classification"] in taxonomy
        for emit in emits:
            for field in REQUIRED_EMIT_FIELDS:
                assert field in emit or f"{field}_from" in emit, (
                    rule["rule_id"],
                    field,
                )
            assert emit["legal_effect"] in ("ENTITLED_TO_PROVIDE", "UNKNOWN")
            assert emit["entry_mechanism"] in (
                "AUTHORISATION",
                "NOTIFICATION",
                "REGISTRATION",
                "EXEMPTION",
                "STATUTORY_ENTITLEMENT",
            )
            assert emit["territorial_basis"] in (
                "DOMESTIC",
                "BRANCH",
                "FREEDOM_TO_PROVIDE_SERVICES",
                "OTHER",
            )
            assert emit["legal_basis"].strip()
            for key in ("entity_class", "activity", "jurisdiction"):
                literal = emit.get(key)
                if literal and literal != "$ITEM":
                    if key == "entity_class":
                        assert literal in ENTITY_CLASSES
                    if key == "activity":
                        assert literal in ACTIVITIES
                    if key == "jurisdiction":
                        assert len(literal) == 2

    # Ninguna regla emite NOT_ENTITLED: el corpus no contiene evidencia
    # negativa explicita ni enumeracion completa verificada.
    for rule in ruleset["rules"]:
        for emit in [rule.get("emit"), rule.get("emit_per", {}).get("emit")]:
            if emit:
                assert emit["legal_effect"] != "NOT_ENTITLED"
    for rule in ruleset["derived_rules"]:
        assert rule["emit"]["legal_effect"] != "NOT_ENTITLED"


# --------------------------------------------------------------- cases


def test_cases_preregistration_integrity():
    cases_doc = _read(CASES_PATH)
    corpus = _read(CORPUS_PATH)
    ledger = _read(LEDGER_PATH)
    corpus_ids = {e["corpus_id"] for e in corpus["entities"]}
    claim_ids = {c["claim_id"] for c in ledger["claims"]}

    case_ids = [c["case_id"] for c in cases_doc["cases"]]
    assert len(case_ids) == len(set(case_ids))

    for case in cases_doc["cases"]:
        assert case["entity_id"] in corpus_ids or case["entity_id"] == "G05-999"
        assert case["activity"] in ACTIVITIES
        assert len(case["jurisdiction"]) == 2
        assert case["expected_assessment"] in {str(a) for a in Assessment}
        assert case["expected_reason"] in {str(r) for r in AssessmentReason}
        for claim_id in case["primary_evidence"]:
            assert claim_id in claim_ids, (case["case_id"], claim_id)
        # Ningun caso espera un negativo: la evidencia congelada no lo
        # permite (ningun contrato COMPLETE_ENUMERATION).
        assert case["expected_assessment"] != "CONFIRMED_NOT_AUTHORISED"

    probed = {case["probes"] for case in cases_doc["cases"]}
    for required_probe in (
        "AUTORIZACION_DOMESTICA_CASP",
        "FPS_INBOUND_NOTIFICACION",
        "ESTADO_NO_INTERPRETABLE",
        "IDENTIFICADOR_INVALIDO_IDENTIDAD_CORPUS",
        "AUSENCIA_NO_CONCLUYENTE",
        "INTENT_ONLY_PASSPORT",
        "EVIDENCIA_CADUCADA_TEMPORAL",
        "IDENTIDAD_NO_ENCONTRADA",
        "VOCABULARY_GAP_AISP",
        "CLASIFICACION_NO_ENUMERACION",
        "DERIVACION_ESTATUTARIA_BLOQUEADA",
    ):
        assert required_probe in probed, required_probe


# ------------------------------------------------------------ artifact


def test_artifact_regenerates_byte_identical():
    regenerated = build_artifact(ROOT)
    assert canonical_json(regenerated) + "\n" == ARTIFACT_PATH.read_text(
        encoding="utf-8"
    )
    assert regenerated["artifact"]["artifact_version"] == ARTIFACT_VERSION
    assert regenerated["artifact"]["claims_ledger_sha256"] == _sha256(LEDGER_PATH)
    assert regenerated["artifact"]["derivation_ruleset_sha256"] == _sha256(
        RULESET_PATH
    )
    assert regenerated["artifact"]["assessment"] == "NOT_RUN"


def test_every_assertion_is_traceable_to_claims_and_rules():
    artifact = _read(ARTIFACT_PATH)
    ledger = _read(LEDGER_PATH)
    ruleset = _read(RULESET_PATH)["ruleset"]
    claim_ids = {c["claim_id"] for c in ledger["claims"]}
    rule_ids = {r["rule_id"] for r in ruleset["rules"]} | {
        r["rule_id"] for r in ruleset["derived_rules"]
    }

    assert len(artifact["assertions"]) == 257
    for assertion in artifact["assertions"]:
        assert assertion["rule_id"] in rule_ids
        assert assertion["source_claim_ids"]
        assert set(assertion["source_claim_ids"]) <= claim_ids
        assert assertion["source_assertions"], assertion["assertion_id"]
        for source in assertion["source_assertions"]:
            for field in (
                "authority",
                "register_id",
                "source_url",
                "retrieved_at",
                "raw_value",
                "raw_snapshot_sha256",
                "extractor_version",
            ):
                assert source[field], (assertion["assertion_id"], field)
            assert source["observed_current"] is True

    taxonomy = set(ruleset["failure_taxonomy"])
    for finding in artifact["findings"]:
        assert finding["classification"] in taxonomy
        assert finding["rule_id"] in rule_ids

    # Dataclass conversion exercised: las aserciones congeladas son
    # instanciables por el motor de G0.4 sin perdida.
    assertions = to_entitlement_assertions(artifact)
    assert len(assertions) == len(artifact["assertions"])


def test_identity_index_never_indexes_invalid_identifiers():
    artifact = _read(ARTIFACT_PATH)
    index = to_identity_index(artifact)

    assert {(i["corpus_id"], i["value"]) for i in artifact["invalid_identifiers"]} == {
        ("G05-012", "59800G0P3PV13KLX615"),
        ("G05-015", "549300746K71T6YJCV41"),
    }
    indexed_values = {
        i.value for entry in index for i in entry.identifiers
    }
    for invalid in artifact["invalid_identifiers"]:
        assert invalid["value"] not in indexed_values
        resolution = resolve_by_identifier(index, "LEI", invalid["value"])
        assert resolution.state is IdentityResolutionState.NOT_FOUND

    # G05-012 conserva una via de identidad exacta alternativa.
    g05_012 = next(e for e in index if e.entity_id == "G05-012")
    assert any(
        i.kind == "BDE_REGISTRY_ID" and i.value == "ES_BE!6950"
        for i in g05_012.identifiers
    )


def test_cases_are_statically_consistent_with_frozen_ruleset():
    """Consistencia estructural, no assessment: expected CONFIRMED exige
    una asercion ENTITLED emitable; NO_ENTITLEMENT_EVIDENCED exige que
    ninguna asercion cubra la unidad consultada. No ejecuta assess()."""
    artifact = _read(ARTIFACT_PATH)
    cases = _read(CASES_PATH)["cases"]
    corpus = _read(CORPUS_PATH)
    corpus_ids = {e["corpus_id"] for e in corpus["entities"]}
    assertions = artifact["assertions"]

    def matching(case):
        return [
            a
            for a in assertions
            if a["entity_id"] == case["entity_id"]
            and a["activity"] == case["activity"]
            and a["jurisdiction"] == case["jurisdiction"]
        ]

    for case in cases:
        matched = matching(case)
        entitled = [a for a in matched if a["legal_effect"] == "ENTITLED_TO_PROVIDE"]
        unknown = [a for a in matched if a["legal_effect"] == "UNKNOWN"]
        expected = case["expected_assessment"]
        if expected == "CONFIRMED_AUTHORISED":
            assert entitled, case["case_id"]
        elif expected == "NO_ENTITLEMENT_EVIDENCED":
            assert not matched, case["case_id"]
        elif expected == "INDETERMINATE":
            if case["expected_reason"] == "UNINTERPRETABLE_EVIDENCE":
                assert unknown and not entitled, case["case_id"]
            elif case["expected_reason"] == "IDENTITY_NOT_FOUND":
                assert case["entity_id"] not in corpus_ids
            elif case["expected_reason"] == "ALL_EVIDENCE_STALE":
                assert matched, case["case_id"]
            else:
                raise AssertionError(f"expected_reason no cubierto: {case}")
        else:
            raise AssertionError(f"expected_assessment no cubierto: {case}")
