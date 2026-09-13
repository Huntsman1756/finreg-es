"""G0.3 — Tests de la matriz de cobertura."""
from finreg_es.coverage import (
    CoverageQuery,
    EnumerationSnapshot,
    can_produce_enumeration_negative,
    coverage,
)
from finreg_es.vocab import ScopeStatus


def _q(register_contract, entity_class, activity, jurisdiction="ES",
       territorial="DOMESTIC", date="2026-09-13"):
    return coverage(
        register_contract,
        CoverageQuery(
            entity_class=entity_class,
            activity=activity,
            jurisdiction=jurisdiction,
            territorial_basis=territorial,
            effective_date=date,
        ),
    )


def test_psd2_register_excludes_credit_institutions_w2(all_contracts):
    d = _q(all_contracts["EBA_PSD2_REGISTER"], "CREDIT_INSTITUTION", "PAYMENT_SERVICES")
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.matched_rule_id == "eba-psd2-out-credit-institutions"


def test_bde_blocks_fps_inbound_w3(all_contracts):
    d = _q(
        all_contracts["BDE_REGISTRO_ENTIDADES"],
        "E_MONEY_INSTITUTION",
        "E_MONEY_ISSUANCE",
        territorial="FREEDOM_TO_PROVIDE_SERVICES",
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE


def test_cir_excludes_payment_institutions(all_contracts):
    d = _q(
        all_contracts["EBA_CREDIT_INSTITUTIONS_REGISTER"],
        "PAYMENT_INSTITUTION",
        "PAYMENT_SERVICES",
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE


def test_activity_outside_register_scope_is_out(all_contracts):
    d = _q(all_contracts["BDE_REGISTRO_ENTIDADES"], "CREDIT_INSTITUTION", "INVESTMENT_SERVICES")
    assert d.status is ScopeStatus.OUT_OF_SCOPE


def test_jurisdiction_outside_register_scope_is_out(all_contracts):
    d = _q(
        all_contracts["BDE_REGISTRO_ENTIDADES"],
        "PAYMENT_INSTITUTION",
        "PAYMENT_SERVICES",
        jurisdiction="LT",
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE


def test_unknown_scope_for_bank_in_esma_mica_h1(all_contracts):
    """Entidades financieras bajo notificacion: ni cubiertas ni excluidas."""
    d = _q(all_contracts["ESMA_MICA_REGISTER"], "CREDIT_INSTITUTION", "CRYPTO_ASSET_SERVICES")
    assert d.status is ScopeStatus.UNKNOWN


def test_unknown_scope_when_no_rule_matches(all_contracts):
    d = _q(
        all_contracts["CNMV_MICA_CASP_LIST"],
        "FUND_MANAGER_SGIIC",
        "CRYPTO_ASSET_SERVICES",
    )
    assert d.status is ScopeStatus.UNKNOWN


def test_in_scope_for_covered_combinations(all_contracts):
    d = _q(all_contracts["EBA_PSD2_REGISTER"], "E_MONEY_INSTITUTION", "PAYMENT_SERVICES",
           territorial="FREEDOM_TO_PROVIDE_SERVICES")
    assert d.status is ScopeStatus.IN_SCOPE
    d2 = _q(all_contracts["BDE_REGISTRO_ENTIDADES"], "CREDIT_INSTITUTION", "DEPOSIT_TAKING")
    assert d2.status is ScopeStatus.IN_SCOPE


def test_temporal_validity_of_rules(all_contracts):
    """Las reglas IN pueden llevar vigencia; fuera de ventana no cubren."""
    c = all_contracts["CNMV_MICA_CASP_LIST"]
    d_in = _q(c, "CASP", "CRYPTO_ASSET_SERVICES", date="2026-09-13")
    assert d_in.status is ScopeStatus.IN_SCOPE


def test_enumeration_negative_blocked_without_verified_complete_enumeration_c3(all_contracts):
    from finreg_es.identity import IdentityResolutionState

    d = _q(all_contracts["BDE_REGISTRO_ENTIDADES"], "PAYMENT_INSTITUTION", "PAYMENT_SERVICES")
    ok, why = can_produce_enumeration_negative(
        all_contracts["BDE_REGISTRO_ENTIDADES"],
        d,
        IdentityResolutionState.EXACT,
        EnumerationSnapshot(
            enumeration_snapshot_sha256="a" * 64,
            enumeration_retrieved_at="2026-09-01",
            enumeration_source_as_of="2026-08-31",
            coverage_rule_id=d.matched_rule_id,
            coverage_ruleset_version="1.0.0",
        ),
    )
    assert not ok
    assert why == "SOURCE_CAPABILITY_DOES_NOT_ALLOW_ENUMERATION_NEGATIVE"


def test_enumeration_negative_gate_requires_exact_identity_and_snapshot(all_contracts):
    """PSD2 en G0 es EXPLICIT_NEGATIVE_ONLY: se clona con COMPLETE_ENUMERATION
    para probar los requisitos del snapshot (upgrade path documentado en G0.5)."""
    import dataclasses

    from finreg_es.identity import IdentityResolutionState
    from finreg_es.vocab import NegativeEvidenceCapability

    c = all_contracts["EBA_PSD2_REGISTER"]
    d = _q(c, "E_MONEY_INSTITUTION", "PAYMENT_SERVICES", territorial="BRANCH")
    assert d.matched_rule_id == "eba-psd2-in-eea"

    ok, why = can_produce_enumeration_negative(
        c, d, IdentityResolutionState.AMBIGUOUS,
        EnumerationSnapshot(
            enumeration_snapshot_sha256="a" * 64,
            enumeration_retrieved_at="2026-09-01",
            enumeration_source_as_of="2026-08-31",
            coverage_rule_id=d.matched_rule_id,
            coverage_ruleset_version="1.0.0",
        ),
    )
    assert not ok and why == "IDENTITY_NOT_EXACT"

    enumerated = dataclasses.replace(
        c, negative_evidence_capability=NegativeEvidenceCapability.COMPLETE_ENUMERATION
    )
    ok, why = can_produce_enumeration_negative(
        enumerated, d, IdentityResolutionState.EXACT, None
    )
    assert not ok and why == "MISSING_ENUMERATION_SNAPSHOT"

    snap_bad = dict(
        enumeration_snapshot_sha256="a" * 64,
        enumeration_retrieved_at="2026-09-01",
        enumeration_source_as_of="2026-08-31",
        coverage_rule_id="otra-regla",
        coverage_ruleset_version="1.0.0",
    )
    ok, why = can_produce_enumeration_negative(
        enumerated, d, IdentityResolutionState.EXACT, EnumerationSnapshot(**snap_bad)
    )
    assert not ok and why == "COVERAGE_RULE_MISMATCH"

    snap_ok = dict(snap_bad, coverage_rule_id=d.matched_rule_id)
    ok, why = can_produce_enumeration_negative(
        enumerated, d, IdentityResolutionState.EXACT, EnumerationSnapshot(**snap_ok)
    )
    assert ok and why == "ENUMERATION_NEGATIVE_ALLOWED"
