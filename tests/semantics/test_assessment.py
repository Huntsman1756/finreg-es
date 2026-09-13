"""G0.4/G0.7 — Tests del motor de assessment y la semantica de aserciones."""
import pytest

from finreg_es.canonical import sha256_hex
from finreg_es.identity import resolve_by_identifier, resolve_by_name
from finreg_es.semantics import assess
from finreg_es.vocab import Assessment, AssessmentReason, IdentityResolutionState


@pytest.fixture(scope="session")
def contracts(all_contracts):
    return all_contracts


def run(contracts, identity_index, assertions, entity, activity, jurisdiction, as_of="2026-09-13", **kw):
    return assess(
        entity, identity_index, activity, jurisdiction, as_of, assertions,
        contracts, **kw
    )


def test_s1_bank_deposits_confirmed(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-001", "DEPOSIT_TAKING", "ES")
    assert r.identity_resolution is IdentityResolutionState.EXACT
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert [a["assertion_id"] for a in r.assertions] == ["asm-001"]
    assert r.response_freshness == "2026-08-31"


def test_s2_bank_payments_derived_by_versioned_rule(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-001", "PAYMENT_SERVICES", "ES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    a = r.assertions[0]
    assert a["derived_by"]["rule_id"] == "credit-institution-implies-payment-services"
    assert a["derived_by"]["ruleset_version"] == "1.0.0"


def test_s3_bank_crypto_via_notification_multiple_mechanisms(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-001", "CRYPTO_ASSET_SERVICES", "ES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert r.assertions[0]["entry_mechanism"] == "NOTIFICATION"


def test_multi_capacity_entity_yields_distinct_mechanisms(contracts, identity_index, assertions):
    """El mismo entity_id sostiene mecanismos distintos segun actividad (G0.4)."""
    dep = run(contracts, identity_index, assertions, "ent-001", "DEPOSIT_TAKING", "ES")
    pay = run(contracts, identity_index, assertions, "ent-001", "PAYMENT_SERVICES", "ES")
    cas = run(contracts, identity_index, assertions, "ent-001", "CRYPTO_ASSET_SERVICES", "ES")
    assert {dep.assertions[0]["entry_mechanism"], pay.assertions[0]["entry_mechanism"], cas.assertions[0]["entry_mechanism"]} == {
        "AUTHORISATION", "AUTHORISATION", "NOTIFICATION"
    }


def test_s4_ambiguous_name_yields_identity_gate_c1(contracts, identity_index, assertions, scenarios):
    resolution = resolve_by_name(identity_index, "Solvia Crypto Services S.A.")
    r = run(contracts, identity_index, assertions, resolution, "CRYPTO_ASSET_SERVICES", "ES")
    assert r.identity_resolution is IdentityResolutionState.AMBIGUOUS
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.AMBIGUOUS_IDENTITY
    assert r.assertions == ()


def test_s5_conflicting_identifiers_gate(contracts, identity_index, assertions):
    resolution = resolve_by_identifier(identity_index, "LEI", "MERIDIANOBANK0000167")
    r = run(contracts, identity_index, assertions, resolution, "DEPOSIT_TAKING", "ES")
    assert r.identity_resolution is IdentityResolutionState.CONFLICTING_IDENTIFIERS
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.CONFLICTING_IDENTIFIERS


def test_s6_identity_not_found_gate(contracts, identity_index, assertions):
    resolution = resolve_by_name(identity_index, "Banco Inexistente del Norte S.A.")
    r = run(contracts, identity_index, assertions, resolution, "DEPOSIT_TAKING", "ES")
    assert r.identity_resolution is IdentityResolutionState.NOT_FOUND
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.IDENTITY_NOT_FOUND


def test_s7_expired_transitional_entitlement_is_not_negative(contracts, identity_index, assertions):
    """asm-006 vencio 2026-06-30 (C4); el CASP sigue autorizado por asm-005.
    Nunca NOT_FOUND/expirado => CONFIRMED_NOT_AUTHORISED."""
    r = run(contracts, identity_index, assertions, "ent-003", "CRYPTO_ASSET_SERVICES", "ES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert r.reason is AssessmentReason.SUPPORTED_BY_ACTIVE_ASSERTIONS
    assert "not_in_effect:asm-006" in r.diagnostics
    ev = {e["assertion_id"]: e for e in r.assertion_evaluations}
    assert ev["asm-006"]["effective_legal_effect_at_as_of"] == "NOT_ENTITLED"
    assert ev["asm-006"]["reason"] == "ENTITLEMENT_EXPIRED"
    assert ev["asm-005"]["effective_legal_effect_at_as_of"] == "ENTITLED_TO_PROVIDE"


def test_absence_before_any_assertion_is_no_entitlement_evidenced(contracts, identity_index, assertions):
    """Antes de la revocacion (2026-05-20) no hay evidencia alguna: ausencia != negativo."""
    r = run(contracts, identity_index, assertions, "ent-011", "PAYMENT_SERVICES", "ES",
            as_of="2026-05-19")
    assert r.assessment is Assessment.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.NO_ASSERTIONS_IN_SCOPE


def test_expired_positive_alone_yields_entitlement_expired_c4(contracts, identity_index, assertions):
    """C4: una autorizacion con ventana cerrada concluye, A NIVEL DE ASERCION,
    NOT_ENTITLED con razon ENTITLEMENT_EXPIRED; pero la agregacion NO puede
    concluir CONFIRMED_NOT_AUTHORISED (podria existir otra via vigente)."""
    subset = [a for a in assertions if a.assertion_id != "asm-005"]
    r = assess(
        "ent-003", identity_index, "CRYPTO_ASSET_SERVICES", "ES", "2026-07-15", subset,
        contracts,
    )
    assert r.assessment is Assessment.NO_ENTITLEMENT_EVIDENCED
    assert r.assessment is not Assessment.CONFIRMED_NOT_AUTHORISED
    assert r.reason is AssessmentReason.ENTITLEMENT_EXPIRED
    ev = {e["assertion_id"]: e for e in r.assertion_evaluations}
    asm006 = ev["asm-006"]
    assert asm006["source_legal_effect"] == "ENTITLED_TO_PROVIDE"
    assert asm006["effective_legal_effect_at_as_of"] == "NOT_ENTITLED"
    assert asm006["reason"] == "ENTITLEMENT_EXPIRED"
    # La evidencia NO se pierde aunque la asercion no soporte el assessment:
    # el SOURCE_ASSERTION sigue accesible y su hash es verificable.
    assert asm006["evidence"]
    assert asm006["evidence"][0]["raw_snapshot_sha256"] == sha256_hex(
        asm006["evidence"][0]["raw_value"]
    )
    # No es evidencia negativa explicita admisible.
    assert r.assertions == ()


def test_s8a_emi_fps_confirmed(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-002", "PAYMENT_SERVICES", "ES",
            territorial_basis="FREEDOM_TO_PROVIDE_SERVICES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert r.assertions[0]["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"


def test_s8b_stale_enumeration_negative_degrades_to_indeterminate(contracts, identity_index, assertions):
    """El negativo por enumeracion vencido (167 dias > 30) NO sostiene negativo (W5)."""
    r = run(contracts, identity_index, assertions, "ent-002", "PAYMENT_SERVICES", "ES",
            territorial_basis="BRANCH")
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.ALL_EVIDENCE_STALE
    assert "stale_evidence:asm-011" in r.diagnostics
    assert r.assertions == ()  # una evidencia caducada no es un claim de soporte


def test_s9_absence_is_not_negative(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-004", "PAYMENT_SERVICES", "ES")
    assert r.assessment is Assessment.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.NO_ASSERTIONS_IN_SCOPE


def test_s10_conflicting_sources_indeterminate_c2(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-010", "DEPOSIT_TAKING", "ES")
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.CONFLICTING_ASSERTIONS
    assert {a["assertion_id"] for a in r.assertions} == {"asm-008", "asm-009"}


def test_s11_explicit_negative_confirmed_not_authorised(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-011", "PAYMENT_SERVICES", "ES")
    assert r.assessment is Assessment.CONFIRMED_NOT_AUTHORISED
    assert r.reason is AssessmentReason.EXPLICIT_NEGATIVE_EVIDENCE
    assert r.response_freshness == "2026-09-08"


def test_s12_agent_without_principal_is_inadmissible_w1(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-013", "PAYMENT_SERVICES", "ES")
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.AGENT_ASSERTION_MISSING_PRINCIPAL


def test_s13_agent_with_principal_confirmed(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-008", "PAYMENT_SERVICES", "ES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert r.response_freshness is not None


def test_s14_unknown_legal_effect_indeterminate(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-005", "CRYPTO_ASSET_SERVICES", "ES")
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.UNINTERPRETABLE_EVIDENCE


def test_s15_registration_mechanism_confirmed(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-004", "INVESTMENT_ADVICE_NON_MIFID", "ES")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED
    assert r.assertions[0]["entry_mechanism"] == "REGISTRATION"
    # freshness cae a retrieved_at porque source_as_of = UNAVAILABLE
    assert r.response_freshness == "2026-09-01"


def test_s16_absence_for_e_money_issuance_fps(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-002", "E_MONEY_ISSUANCE", "ES",
            territorial_basis="FREEDOM_TO_PROVIDE_SERVICES")
    assert r.assessment is Assessment.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.NO_ASSERTIONS_IN_SCOPE


def test_result_shape_matches_g0_output_contract(contracts, identity_index, assertions):
    r = run(contracts, identity_index, assertions, "ent-001", "DEPOSIT_TAKING", "ES")
    d = {
        "entity": r.entity_id,
        "activity": r.activity,
        "jurisdiction": r.jurisdiction,
        "identity_resolution": str(r.identity_resolution),
        "assessment": str(r.assessment),
        "assertions": list(r.assertions),
    }
    assert d["identity_resolution"] == "EXACT"
    assert d["assessment"] == "CONFIRMED_AUTHORISED"
    a = r.assertions[0]
    for key in ("legal_effect", "entry_mechanism", "territorial_basis", "legal_basis",
                "effective_from", "effective_to", "evidence"):
        assert key in a
    ev = a["evidence"][0]
    for key in ("authority", "register_id", "source_url", "retrieved_at", "source_as_of",
                "raw_value", "raw_snapshot_sha256", "extractor_version"):
        assert key in ev


def test_scenario_fixture_replays_end_to_end(
    contracts, identity_index, assertions, scenarios
):
    """scenarios.json es el contrato vivo: se replaya completo."""
    as_of = scenarios["as_of"]
    for sc in scenarios["scenarios"]:
        q = sc["query"]
        exp = sc["expect"]
        if "entity_id" in q:
            r = assess(
                q["entity_id"], identity_index, q["activity"], q["jurisdiction"],
                as_of, assertions, contracts,
                territorial_basis=q.get("territorial_basis"),
            )
        elif "by_name" in q:
            r = assess(
                resolve_by_name(identity_index, q["by_name"]), identity_index,
                q["activity"], q["jurisdiction"], as_of, assertions, contracts,
            )
        else:
            ref = q["by_identifier"]
            r = assess(
                resolve_by_identifier(identity_index, ref["kind"], ref["value"]),
                identity_index, q["activity"], q["jurisdiction"], as_of,
                assertions, contracts,
            )
        assert str(r.identity_resolution) == exp["identity_resolution"], sc["scenario_id"]
        assert str(r.assessment) == exp["assessment"], sc["scenario_id"]
        assert str(r.reason) == exp["reason"], sc["scenario_id"]
        if "assertion_ids" in exp:
            assert {a["assertion_id"] for a in r.assertions} == set(exp["assertion_ids"]), sc["scenario_id"]
        if "diagnostics_contains" in exp:
            for d in exp["diagnostics_contains"]:
                assert d in r.diagnostics, sc["scenario_id"]
