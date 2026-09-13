"""G0.7-C — Divergence / finding audit del run g0.7-001.

El run se conserva inmutable (0 divergencias que auditar). Este modulo
resuelve los tres findings del review de G0.7-B:

  F01 expected-data independence: se demuestra mecanicamente que
      expected_* no entra en el computo — mutarlos o eliminarlos no
      cambia ningun resultado real.
  F02 code_commit lineage: queda documentado en el artefacto de audit;
      g0.7-001 no se reescribe y el renombrado se programa para la
      siguiente version del runner.
  F03 solape DOMESTIC+FPS: el corpus congelado no ejercita la rama; se
      fija la semantica con un test unitario fuera del corpus (no se
      anade caso al preregistro post-hoc).
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import finreg_es.assessment_run as assessment_run
from finreg_es.assessment_run import run_assessment
from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.identity import IdentityIndexEntry
from finreg_es.semantics import EntitlementAssertion, SourceAssertion, assess
from finreg_es.vocab import Assessment, IdentityResolutionState, LegalEffect


ROOT = Path(__file__).parents[2]
RUN_PATH = ROOT / "fixtures" / "g0.7" / "runs" / "g0.7-001.json"
CASES_PATH = ROOT / "fixtures" / "g0.7" / "assessment-cases.json"
AUDIT_PATH = ROOT / "fixtures" / "g0.7" / "audit" / "g0.7-c-run-audit.json"

RUN_META = _run_meta = strict_json_loads(RUN_PATH.read_text(encoding="utf-8"))["run"]

ACTUAL_FIELDS = (
    "identity_resolution",
    "assessment",
    "reason",
    "diagnostics",
    "matching_assertion_ids",
    "used_assertion_ids",
    "derived_assertion_ids",
    "source_claim_ids",
    "assertion_evaluations",
)


def _patched_cases(monkeypatch, mutate):
    """Ejecuta el run con el documento de casos transformado en vuelo,
    sin tocar el fichero congelado."""
    real_loads = strict_json_loads

    def patched(text):
        doc = real_loads(text)
        if isinstance(doc, dict) and "cases" in doc and "cases_meta" in doc:
            doc = copy.deepcopy(doc)
            for case in doc["cases"]:
                mutate(case)
        return doc

    monkeypatch.setattr(assessment_run, "strict_json_loads", patched)
    return run_assessment(
        ROOT,
        run_id="metamorphic-probe",
        executed_at=RUN_META["executed_at"],
        code_commit=RUN_META["code_commit"],
    )


def test_f01_mutated_expectations_do_not_change_actuals(monkeypatch):
    """Mutar expected_assessment/reason al peor valor posible no altera
    ningun campo real: solo cambian los flags de comparacion."""
    baseline = run_assessment(
        ROOT,
        run_id=RUN_META["run_id"],
        executed_at=RUN_META["executed_at"],
        code_commit=RUN_META["code_commit"],
    )

    def corrupt(case):
        case["expected_assessment"] = "CONFIRMED_NOT_AUTHORISED"
        case["expected_reason"] = "EXPLICIT_NEGATIVE_EVIDENCE"
        case["expected_basis"] = ["CORRUPTED"]

    mutated = _patched_cases(monkeypatch, corrupt)

    for original, corrupt_case in zip(baseline["cases"], mutated["cases"]):
        for field in ACTUAL_FIELDS:
            assert corrupt_case[field] == original[field], (
                corrupt_case["case_id"],
                field,
            )
        # La expectativa corrompida se registra y el match falla: la
        # comparacion funciona, pero no contamina el resultado.
        assert corrupt_case["expected_assessment"] == "CONFIRMED_NOT_AUTHORISED"
        assert corrupt_case["match"] is False


def test_f01_stripped_expectations_do_not_change_actuals(monkeypatch):
    """Eliminar TODOS los expected_* antes del motor produce los mismos
    21 resultados reales: la expectativa no es entrada del computo."""
    baseline = run_assessment(
        ROOT,
        run_id=RUN_META["run_id"],
        executed_at=RUN_META["executed_at"],
        code_commit=RUN_META["code_commit"],
    )

    def strip(case):
        for key in ("expected_assessment", "expected_reason",
                    "expected_basis", "primary_evidence", "known_limitations"):
            case.pop(key, None)

    stripped = _patched_cases(monkeypatch, strip)
    assert len(stripped["cases"]) == len(baseline["cases"])
    for original, bare in zip(baseline["cases"], stripped["cases"]):
        for field in ACTUAL_FIELDS:
            assert bare[field] == original[field], (bare["case_id"], field)
        assert bare["match"] is False  # sin expectativa no hay match


def test_f03_domestic_plus_fps_same_unit_is_not_conflicting(all_contracts):
    """Misma entidad + actividad + ES con ENTITLED DOMESTIC y ENTITLED
    FPS simultaneos: agregan como evidencia, no como conflicto. Fija la
    semantica de la rama que el corpus congelado no ejercita (F03)."""
    source = SourceAssertion(
        authority="TEST",
        register_id="ESMA_MICA_REGISTER",
        source_url="test://synthetic",
        retrieved_at="2026-09-13",
        source_as_of=None,
        source_date_reliability="UNAVAILABLE",
        raw_value="synthetic",
        raw_snapshot_sha256="0" * 64,
        extractor_version="g07c-synthetic",
        observed_current=True,
    )

    def assertion(assertion_id, territorial_basis):
        return EntitlementAssertion(
            assertion_id=assertion_id,
            register_id="ESMA_MICA_REGISTER",
            entity_id="ent-x",
            entity_class="CASP",
            activity="CRYPTO_ASSET_SERVICES",
            jurisdiction="ES",
            legal_effect=LegalEffect.ENTITLED_TO_PROVIDE,
            entry_mechanism="AUTHORISATION",
            territorial_basis=territorial_basis,
            legal_basis="synthetic",
            effective_from="2026-01-01",
            effective_to=None,
            scope="synthetic",
            source_assertions=(source,),
        )

    index = [
        IdentityIndexEntry(
            entity_id="ent-x", legal_name="X", entity_classes=("CASP",)
        )
    ]
    pair = [
        assertion("a-dom", "DOMESTIC"),
        assertion("a-fps", "FREEDOM_TO_PROVIDE_SERVICES"),
    ]

    # territorial_basis=None: ambas entran en scope y agregan a UNA
    # conclusion positiva — multiplicidad de evidencia, no de derechos.
    result = assess(
        "ent-x",
        index,
        activity="CRYPTO_ASSET_SERVICES",
        jurisdiction="ES",
        as_of="2026-09-13",
        assertions=pair,
        contracts=all_contracts,
    )
    assert result.identity_resolution is IdentityResolutionState.EXACT
    assert result.assessment is Assessment.CONFIRMED_AUTHORISED
    assert {a["assertion_id"] for a in result.assertions} == {"a-dom", "a-fps"}

    # Con filtro territorial explicito cada via se evalua por separado.
    fps_only = assess(
        "ent-x",
        index,
        activity="CRYPTO_ASSET_SERVICES",
        jurisdiction="ES",
        as_of="2026-09-13",
        assertions=pair,
        contracts=all_contracts,
        territorial_basis="FREEDOM_TO_PROVIDE_SERVICES",
    )
    assert [a["assertion_id"] for a in fps_only.assertions] == ["a-fps"]


def test_audit_artifact_consistent_with_frozen_run():
    audit = strict_json_loads(AUDIT_PATH.read_text(encoding="utf-8"))
    run_bytes = RUN_PATH.read_bytes()
    frozen = strict_json_loads(RUN_PATH.read_text(encoding="utf-8"))

    assert audit["audit"]["run_id"] == "g0.7-001"
    assert audit["audit"]["run_sha256"] == hashlib.sha256(run_bytes).hexdigest()
    assert audit["audit"]["divergences_total"] == 0
    assert audit["audit"]["run_status"] == "VALID_IMMUTABLE"
    assert {f["finding_id"] for f in audit["findings"]} == {"F01", "F02", "F03"}

    # El run congelado no se ha reescrito: result_sha se verifica sobre
    # su propio contenido.
    recorded = frozen.pop("result_sha")
    assert (
        hashlib.sha256(canonical_json(frozen).encode("utf-8")).hexdigest()
        == recorded
    )
