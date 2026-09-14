"""G1-E (E6-A) — tests binding para mutantes supervivientes.

El probe mutmut scoped (1086 mutantes, ~830 killed) dejo ~251
supervivientes. La mayoria son cosmeticos (strings de diagnostico,
campos no observados) o equivalentes. Este modulo fija la semantica
que el corpus no ejercitaba — cada test mata una clase de mutante
fail-open o temporal:

  * temporal.py: politica None fail-closed, frontera age==max,
    response_freshness / suspect_source_as_of.
  * coverage.py: fronteras valid_from/valid_to, exclusion de reglas
    por jurisdiccion, gate de enumeracion fuera de scope.
  * semantics.py: admisibilidad fail-closed (sin contrato, scope
    UNKNOWN sin evidencia, ALL_REQUIRED), freshness de hechos,
    estados de raiz (retirada sin intervalos, baja UNRESOLVED,
    ABSENT pre-ventana, [from,to) exclusivo) y agregacion V3
    (raiz no-capaz, ABSENT, UNRESOLVED, cierre por rutas vs
    retirada, positivo futuro/expirado).
"""
from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

from finreg_es.contracts import CoverageRule, load_contract
from finreg_es.coverage import (
    CoverageQuery,
    EnumerationSnapshot,
    _rule_applies,
    can_produce_enumeration_negative,
    coverage,
)
from finreg_es.identity import (
    IdentityIndexEntry,
    IdentityResolution,
    IdentityResolutionState,
)
from finreg_es.semantics import (
    EntitlementAssertion,
    SourceAssertion,
    _assertion_admissible,
    _fact_freshness_ok,
    _reported_fact_reason,
    _root_can_provide,
    _root_states_at,
    assess,
)
from finreg_es.temporal import (
    Freshness,
    is_stale,
    response_freshness,
    suspect_source_as_of,
)
from finreg_es.vocab import (
    Assessment,
    AssessmentReason,
    AssessmentV2,
    LegalEffect,
    ScopeStatus,
)

ROOT = Path(__file__).parents[2]
CONTRACTS = {
    c.register_id: c
    for c in (
        load_contract(p)
        for p in sorted((ROOT / "fixtures" / "contracts").glob("*.json"))
    )
}
EBA = CONTRACTS["EBA_PSD2_REGISTER"]  # pos 45 / neg 30

ENTITY = IdentityIndexEntry(
    entity_id="SYN-1",
    legal_name="SYNTHETIC MUTATION ENTITY",
    entity_classes=("PAYMENT_INSTITUTION",),
)
INDEX = [ENTITY]
RETRIEVED = "2027-01-05"  # evidencia fresca para as_of <= 2027-02


def _src(register_id="EBA_PSD2_REGISTER", retrieved=RETRIEVED,
         source_as_of=RETRIEVED):
    return SourceAssertion(
        authority="test",
        register_id=register_id,
        source_url="test://mk",
        retrieved_at=retrieved,
        source_as_of=source_as_of,
        source_date_reliability="TRUSTED",
        raw_value="x",
        raw_snapshot_sha256="0" * 64,
        extractor_version="mk",
        observed_current=True,
    )


def _fact(root_key="EBA|PSD_PI|NL_DNB!F1", *, retrieved=RETRIEVED,
          source_as_of=RETRIEVED, source="EBA_PSD2_REGISTER",
          home="NL", intervals=None, effective_from=None,
          neg_class=None, reported_status=None, with_sources=True):
    f = {
        "corpus_id": ENTITY.entity_id,
        "fact_id": f"fact-{root_key}",
        "rule_id": "mk-rule",
        "root_key": root_key,
        "source": source,
        "root_home_jurisdiction": home,
    }
    if with_sources:
        f["source_assertions"] = [
            {
                "retrieved_at": retrieved,
                "source_as_of": source_as_of,
                "source_date_reliability": "TRUSTED",
            }
        ]
    if intervals is not None:
        f["status_intervals"] = intervals
    if effective_from is not None:
        f["effective_from"] = effective_from
    if neg_class is not None:
        f["negative_evidence_class"] = neg_class
    if reported_status is not None:
        f["reported_status"] = reported_status
    return f


def _assertion(aid, effect, basis="FREEDOM_TO_PROVIDE_SERVICES",
               root="EBA|PSD_PI|NL_DNB!F1", home="NL",
               effective_from="2020-01-01", effective_to=None,
               register_id="EBA_PSD2_REGISTER", sources=None,
               activity="PAYMENT_INITIATION_SERVICES",
               admissibility=None, interval_end=None,
               entity_class="PAYMENT_INSTITUTION",
               evidence_composition=None):
    return EntitlementAssertion(
        assertion_id=aid,
        register_id=register_id,
        entity_id=ENTITY.entity_id,
        entity_class=entity_class,
        activity=activity,
        jurisdiction="ES",
        legal_effect=effect,
        entry_mechanism="AUTHORISATION",
        territorial_basis=basis,
        legal_basis="mk",
        effective_from=effective_from,
        effective_to=effective_to,
        scope="mk",
        source_assertions=sources if sources is not None else (_src(),),
        interval_end=interval_end,
        admissibility=admissibility,
        negative_scope="ROUTE_CAPABILITY" if effect is LegalEffect.NOT_ENTITLED else None,
        negative_evidence_class=(
            "ENUMERATED_ABSENCE" if effect is LegalEffect.NOT_ENTITLED else None
        ),
        evidence_composition=evidence_composition,
        root_key=root,
        root_home_jurisdiction=home,
    )


def _assess(assertions, facts, as_of, activity="PAYMENT_INITIATION_SERVICES",
            territorial_basis=None, version="V3", contracts=CONTRACTS):
    return assess(
        ENTITY.entity_id,
        INDEX,
        activity=activity,
        jurisdiction="ES",
        as_of=as_of,
        assertions=assertions,
        contracts=contracts,
        semantics_version=version,
        reported_facts=facts,
        territorial_basis=territorial_basis,
    )


# -------------------------------------------------------------------
# temporal.py — mutantes: is_stale(None policy -> False), age>=max,
# response_freshness/suspect_source_as_of sin cobertura.
# -------------------------------------------------------------------


def test_is_stale_undefined_policy_is_fail_closed():
    """max_staleness_days=None => politica no definida => stale."""
    f = Freshness(date(2027, 1, 5), date(2027, 1, 5), "TRUSTED")
    assert is_stale(f, None, date(2027, 1, 6)) is True


def test_is_stale_boundary_age_equals_max_is_fresh():
    """La politica usa ``age > max``: en la frontera exacta sigue fresh."""
    f = Freshness(date(2027, 1, 5), None, "TRUSTED")
    assert is_stale(f, 30, date(2027, 2, 4)) is False  # age == 30
    assert is_stale(f, 30, date(2027, 2, 5)) is True   # age == 31


def test_is_stale_prefers_source_as_of_over_retrieved():
    f = Freshness(date(2027, 1, 5), date(2026, 1, 1), "TRUSTED")
    assert is_stale(f, 30, date(2027, 1, 5)) is True


def test_response_freshness_empty_and_min():
    assert response_freshness([]) is None
    a = Freshness(date(2027, 1, 5), None, "TRUSTED")
    b = Freshness(date(2027, 1, 1), date(2026, 12, 1), "TRUSTED")
    assert response_freshness([a, b]) == date(2026, 12, 1)


def test_suspect_source_as_of_truth_table():
    assert suspect_source_as_of("h1", "h2", "d1", "d1") is True
    assert suspect_source_as_of("h1", "h1", "d1", "d1") is False
    assert suspect_source_as_of("h1", "h2", "d1", "d2") is False
    assert suspect_source_as_of("h1", "h1", "d1", "d2") is False


# -------------------------------------------------------------------
# coverage.py — mutantes: _rule_applies (jurisdiccion True, fronteras
# valid_from/valid_to), razones de ScopeDecision, enumeracion fuera
# de scope fail-open.
# -------------------------------------------------------------------


def test_rule_applies_rejects_mismatched_dimensions():
    """_rule_applies: cada dimension declarada en la regla debe
    matchear — un 'return True' en cualquier guarda es fail-open."""
    rule = CoverageRule(
        rule_id="r1", scope="IN", entity_class=None, activities=None,
        jurisdictions=("ES",), territorial_bases=None,
        valid_from=None, valid_to=None, note="",
    )
    q = CoverageQuery(
        entity_class="PAYMENT_INSTITUTION", activity="PAYMENT_SERVICES",
        jurisdiction="FR", territorial_basis="DOMESTIC",
        effective_date="2027-01-10",
    )
    assert _rule_applies(rule, q) is False

    rule_tf = dataclasses.replace(rule, jurisdictions=None,
                                  territorial_bases=("BRANCH",))
    assert _rule_applies(rule_tf, q) is False


def test_rule_applies_jurisdiction_mismatch_is_not_in_scope():
    """Una regla con jurisdictions=[ES] no puede matchear jur=FR
    (mutante return True era fail-open)."""
    d = coverage(
        CONTRACTS["BDE_REGISTRO_SERVICIOS_PAGO"],
        CoverageQuery(
            entity_class="PAYMENT_INSTITUTION",
            activity="MONEY_REMITTANCE",
            jurisdiction="FR",
            territorial_basis="DOMESTIC",
            effective_date="2027-01-10",
        ),
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.matched_rule_id == "contract-jurisdiction-coverage"
    assert d.reason == "JURISDICTION_NOT_COVERED_BY_REGISTER"


def test_rule_applies_validity_window_boundaries():
    """valid_from/valid_to son inclusivos: una regla vigente en
    [vf,vt] aplica en los bordes y no fuera."""
    rule = dataclasses.replace(
        CONTRACTS["CNMV_MICA_CASP_LIST"].coverage_rules[0],
        valid_from="2027-01-01",
        valid_to="2027-12-31",
    )
    contract = dataclasses.replace(
        CONTRACTS["CNMV_MICA_CASP_LIST"], coverage_rules=(rule,)
    )

    def q(day):
        return coverage(
            contract,
            CoverageQuery(
                entity_class="CASP",
                activity="CRYPTO_ASSET_SERVICES",
                jurisdiction="ES",
                territorial_basis="DOMESTIC",
                effective_date=day,
            ),
        )

    assert q("2026-12-31").status is not ScopeStatus.IN_SCOPE
    assert q("2027-01-01").status is ScopeStatus.IN_SCOPE  # borde vf
    assert q("2027-12-31").status is ScopeStatus.IN_SCOPE  # borde vt
    assert q("2028-01-01").status is not ScopeStatus.IN_SCOPE


def test_coverage_decision_reasons_and_matched_rule():
    d = coverage(
        EBA,
        CoverageQuery(
            entity_class="CREDIT_INSTITUTION",
            activity="PAYMENT_SERVICES",
            jurisdiction="ES",
            territorial_basis="DOMESTIC",
            effective_date="2027-01-10",
        ),
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.matched_rule_id == "eba-psd2-out-credit-institutions"
    assert d.reason == "EXPLICIT_EXCLUSION"

    # Guard generica de clase excluida: FUND_MANAGER_SGIIC no cae en
    # ninguna regla OUT explicita (solo credit-institutions y crypto).
    d = coverage(
        EBA,
        CoverageQuery(
            entity_class="FUND_MANAGER_SGIIC",
            activity="PAYMENT_SERVICES",
            jurisdiction="ES",
            territorial_basis="DOMESTIC",
            effective_date="2027-01-10",
        ),
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.matched_rule_id == "contract-excluded-entity-classes"
    assert d.reason == "EXCLUDED_ENTITY_CLASS"

    d = coverage(
        EBA,
        CoverageQuery(
            entity_class="PAYMENT_INSTITUTION",
            activity="DEPOSIT_TAKING",
            jurisdiction="ES",
            territorial_basis="DOMESTIC",
            effective_date="2027-01-10",
        ),
    )
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.reason == "ACTIVITY_NOT_COVERED_BY_REGISTER"

    d = coverage(
        EBA,
        CoverageQuery(
            entity_class="PAYMENT_INSTITUTION",
            activity="MONEY_REMITTANCE",
            jurisdiction="ES",
            territorial_basis="BRANCH",
            effective_date="2027-01-10",
        ),
    )
    assert d.status is ScopeStatus.IN_SCOPE
    assert d.matched_rule_id == "eba-psd2-in-eea"
    assert d.reason == "COVERED_BY_RULE"


def test_enumeration_negative_rejected_when_not_in_scope():
    """mutante fail-open: decision no-IN_SCOPE debe devolver False."""
    d = coverage(
        EBA,
        CoverageQuery(
            entity_class="CREDIT_INSTITUTION",
            activity="PAYMENT_SERVICES",
            jurisdiction="ES",
            territorial_basis="DOMESTIC",
            effective_date="2027-01-10",
        ),
    )
    ok, why = can_produce_enumeration_negative(
        EBA, d, "EXACT",
        EnumerationSnapshot(
            enumeration_snapshot_sha256="a" * 64,
            enumeration_retrieved_at="2027-01-01",
            enumeration_source_as_of=None,
            coverage_rule_id="eba-psd2-in-eea",
            coverage_ruleset_version="1.0.0",
        ),
    )
    assert ok is False
    assert why.startswith("SCOPE_")


# -------------------------------------------------------------------
# semantics.py — _root_can_provide / _fact_freshness_ok / root states.
# -------------------------------------------------------------------


def test_root_can_provide_type_matrix():
    assert _root_can_provide("EBA|PSD_AISP|NL_DNB!F9", "ACCOUNT_INFORMATION_SERVICES")
    assert not _root_can_provide(
        "EBA|PSD_AISP|NL_DNB!F9", "PAYMENT_INITIATION_SERVICES"
    )
    assert not _root_can_provide("EBA|PSD_PI|X", "E_MONEY_ISSUANCE")
    assert _root_can_provide("EBA|PSD_EMI|X", "E_MONEY_ISSUANCE")
    assert _root_can_provide("EBA|PSD_PI|X", "MONEY_REMITTANCE")


def test_root_can_provide_unknown_or_malformed_is_conservative():
    """Tipo no resoluble => capaz de todo (conservador)."""
    assert _root_can_provide("BDE|PSD_BR|6935", "PAYMENT_INITIATION_SERVICES")
    assert _root_can_provide("NO_PIPES", "PAYMENT_INITIATION_SERVICES")
    assert _root_can_provide("A|B", "PAYMENT_INITIATION_SERVICES")


def test_fact_freshness_fail_closed_gates():
    as_of = date(2027, 1, 10)
    assert _fact_freshness_ok(_fact(with_sources=False), CONTRACTS, as_of) is False
    assert _fact_freshness_ok(
        _fact(source="NO_SUCH_REGISTER"), CONTRACTS, as_of
    ) is False


def test_fact_freshness_uses_negative_policy():
    """Los hechos usan la ventana NEGATIVA del contrato (EBA: 30d)."""
    as_of = date(2027, 1, 10)
    fresh = _fact(retrieved="2026-12-20", source_as_of="2026-12-20")  # 21d
    stale = _fact(retrieved="2026-11-20", source_as_of="2026-11-20")  # 51d
    assert _fact_freshness_ok(fresh, CONTRACTS, as_of) is True
    assert _fact_freshness_ok(stale, CONTRACTS, as_of) is False


def test_fact_freshness_source_as_of_dominates_retrieved():
    """source_as_of viejo + retrieved_at fresco => freshness_at es el
    viejo => stale (mata mutantes que ignoran source_as_of)."""
    fact = _fact(retrieved="2027-01-05", source_as_of="2026-06-01")
    assert _fact_freshness_ok(fact, CONTRACTS, date(2027, 1, 10)) is False


def test_root_states_withdrawal_without_intervals_closes():
    """EXPLICIT_WITHDRAWAL sin status_intervals cierra desde su
    effective_from (rama elif closed_at)."""
    facts = [_fact(effective_from="2024-06-01", neg_class="EXPLICIT_WITHDRAWAL")]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "CLOSED"


def test_root_states_withdrawal_boundary_inclusive():
    """effective_from <= as_of: el dia exacto ya esta cerrado."""
    facts = [_fact(effective_from="2027-01-10", neg_class="EXPLICIT_WITHDRAWAL")]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "CLOSED"
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 9))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "OPEN"


def test_root_states_entity_baja_is_unresolved_not_closed():
    for neg in ("ENTITY_BAJA", "UNRESOLVED_MOTIVO"):
        facts = [_fact(effective_from="2024-06-01", neg_class=neg)]
        states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
        assert states["EBA|PSD_PI|NL_DNB!F1"] == "UNRESOLVED", neg


def test_root_states_legacy_withdrawn_status_is_unresolved():
    """Pre-E4.1: reported_status WITHDRAWN sin negative_evidence_class
    => UNRESOLVED (no cierra limpiamente)."""
    facts = [
        _fact(effective_from="2024-06-01", reported_status="WITHDRAWN")
    ]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "UNRESOLVED"
    # ACTIVE reportado sin clase: no es evento de cierre.
    facts = [
        _fact(effective_from="2024-06-01", reported_status="ACTIVE")
    ]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "OPEN"


def test_root_states_intervals_exclusive_to_and_absent():
    """[from,to): abierto en from, cerrado en to; si toda la ventana es
    futura => ABSENT."""
    iv = [{"from": "2020-01-01", "to": "2025-06-01"}]
    facts = [_fact(intervals=iv)]
    s = _root_states_at(facts, CONTRACTS, date(2020, 1, 1))
    assert s["EBA|PSD_PI|NL_DNB!F1"] == "OPEN"      # from inclusivo
    s = _root_states_at(facts, CONTRACTS, date(2025, 6, 1))
    assert s["EBA|PSD_PI|NL_DNB!F1"] == "CLOSED"    # to exclusivo
    s = _root_states_at(facts, CONTRACTS, date(2019, 12, 31))
    assert s["EBA|PSD_PI|NL_DNB!F1"] == "ABSENT"    # pre-ventana


def test_root_states_continues_past_irrelevant_facts():
    """Un fact sin root_key, uno stale y uno sin effective_from no
    deben abortar el barrido (mutantes continue->break)."""
    facts = [
        {"fact_id": "no-root", "corpus_id": "x"},                 # sin root_key
        _fact(root_key="EBA|PSD_PI|OTHER", retrieved="2020-01-01",
              source_as_of="2020-01-01",
              effective_from="2020-02-01",
              neg_class="EXPLICIT_WITHDRAWAL"),                    # stale
        _fact(root_key="EBA|PSD_PI|NL_DNB!F1"),                    # sin eff
        _fact(root_key="EBA|PSD_PI|NL_DNB!F1",
              effective_from="2024-01-01", neg_class="EXPLICIT_WITHDRAWAL"),
    ]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert "EBA|PSD_PI|OTHER" in states  # conocido pese a stale
    assert states["EBA|PSD_PI|OTHER"] == "OPEN"
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "CLOSED"


def test_root_states_default_open_when_fact_has_no_closure():
    facts = [_fact(intervals=None)]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "OPEN"


def test_root_states_degenerate_interval_is_closed_not_absent():
    """Intervalo vacio [d,d): no cubre as_of y as_of >= min(from) =>
    CLOSED (mata el mutante '>' del chequeo de ventana pasada)."""
    facts = [_fact(intervals=[{"from": "2027-01-10", "to": "2027-01-10"}])]
    states = _root_states_at(facts, CONTRACTS, date(2027, 1, 10))
    assert states["EBA|PSD_PI|NL_DNB!F1"] == "CLOSED"


# -------------------------------------------------------------------
# _assertion_admissible — gates fail-closed y politicas pos/neg.
# -------------------------------------------------------------------


def _admissible(a, as_of="2027-01-10", contracts=CONTRACTS):
    diagnostics: list[str] = []
    ok = _assertion_admissible(
        a, entity=ENTITY, contracts=contracts, as_of=as_of,
        as_of_date=date.fromisoformat(as_of), diagnostics=diagnostics,
    )
    return ok, diagnostics


def test_admissible_rejects_missing_contract():
    a = _assertion("m1", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id="NO_SUCH_REGISTER")
    ok, diag = _admissible(a)
    assert ok is False
    assert "no_contract:NO_SUCH_REGISTER" in diag


def test_admissible_unknown_scope_without_evidence_rejects():
    """Scope UNKNOWN + sin source_assertions => inadmisible
    (mutante return True era fail-open)."""
    a = _assertion(
        "m2", LegalEffect.ENTITLED_TO_PROVIDE,
        register_id="ESMA_MICA_REGISTER",
        activity="CRYPTO_ASSET_SERVICES",
        entity_class="CREDIT_INSTITUTION",
        sources=(),
    )
    ok, diag = _admissible(a)
    assert ok is False
    assert "unknown_scope_no_evidence:m2" in diag


def test_admissible_unknown_scope_with_evidence_passes_gate():
    """UNKNOWN con evidencia no se rechaza por el gate de scope."""
    a = _assertion(
        "m3", LegalEffect.ENTITLED_TO_PROVIDE,
        register_id="ESMA_MICA_REGISTER",
        activity="CRYPTO_ASSET_SERVICES",
        entity_class="CREDIT_INSTITUTION",
        sources=(_src("ESMA_MICA_REGISTER"),),
    )
    ok, _ = _admissible(a)
    assert ok is True


def test_admissible_negative_uses_stricter_staleness():
    """Evidencia de 35d: fresh para positivo (45d), stale para
    negativo (30d) — mata los mutantes que ignoran legal_effect."""
    as_of = "2027-01-10"
    stale_35 = (_src(retrieved="2026-12-06", source_as_of="2026-12-06"),)
    pos = _assertion("m4", LegalEffect.ENTITLED_TO_PROVIDE, sources=stale_35)
    neg = _assertion("m5", LegalEffect.NOT_ENTITLED, sources=stale_35)
    assert _admissible(pos, as_of)[0] is True
    assert _admissible(neg, as_of)[0] is False


def test_admissible_all_required_missing_register_contract():
    a = _assertion(
        "m6", LegalEffect.ENTITLED_TO_PROVIDE,
        evidence_composition="ALL_REQUIRED",
        sources=(_src(), _src("UNREGISTERED_SOURCE")),
    )
    ok, diag = _admissible(a)
    assert ok is False
    assert "no_contract:UNREGISTERED_SOURCE" in diag


def test_admissible_all_required_out_of_scope_register():
    """Una fuente citada fuera de scope para la query tumba la
    asercion conjuntiva."""
    a = _assertion(
        "m7", LegalEffect.ENTITLED_TO_PROVIDE,
        entity_class="CREDIT_INSTITUTION",
        activity="DEPOSIT_TAKING",
        basis="BRANCH",
        register_id="EBA_CREDIT_INSTITUTIONS_REGISTER",
        evidence_composition="ALL_REQUIRED",
        sources=(
            _src("EBA_CREDIT_INSTITUTIONS_REGISTER"),
            _src("EBA_PSD2_REGISTER"),  # EBA PSD2 excluye credit inst.
        ),
    )
    ok, diag = _admissible(a)
    assert ok is False
    assert "out_of_source_scope:m7:EBA_PSD2_REGISTER" in diag


def test_admissible_all_required_stale_source_under_its_policy():
    """ALL_REQUIRED: cada fuente se evalua bajo SU politica negativa.
    BDE servicios neg=45d: una fuente BDE de 50d tumba un negativo."""
    a = _assertion(
        "m8", LegalEffect.NOT_ENTITLED,
        basis="BRANCH",
        evidence_composition="ALL_REQUIRED",
        sources=(
            _src(),
            _src("BDE_REGISTRO_SERVICIOS_PAGO",
                 retrieved="2026-11-20", source_as_of="2026-11-20"),
        ),
    )
    ok, diag = _admissible(a, "2027-01-10")
    assert ok is False
    assert "stale_required_source:m8:BDE_REGISTRO_SERVICIOS_PAGO" in diag


def test_admissible_all_required_negative_uses_reg_negative_policy():
    """Fuente requerida con 35d bajo BDE (neg 45 / pos 90): fresh para
    positivo, stale para negativo EBA(30)... probamos el registro con
    politica distinta: BDE neg=45 => 50d stale, EBA pos=45 => fresh."""
    srcs = (
        _src(),
        _src("BDE_REGISTRO_SERVICIOS_PAGO",
             retrieved="2026-11-21", source_as_of="2026-11-21"),  # 50d
    )
    neg = _assertion("m9", LegalEffect.NOT_ENTITLED, basis="BRANCH",
                     evidence_composition="ALL_REQUIRED", sources=srcs)
    pos = _assertion("m10", LegalEffect.ENTITLED_TO_PROVIDE, basis="BRANCH",
                     evidence_composition="ALL_REQUIRED", sources=srcs)
    ok_neg, diag = _admissible(neg, "2027-01-10")
    assert ok_neg is False  # BDE neg: 50 > 45 stale
    assert "stale_required_source" in "\n".join(diag)
    # Positivo: EBA pos=45 (m4 lo cubre) y BDE pos=90 => ambas fresh.
    assert _admissible(pos, "2027-01-10")[0] is True


# -------------------------------------------------------------------
# _assess_v3 — agregacion: raiz no-capaz, ABSENT, UNRESOLVED, rutas
# imposibles, razon de cierre, positivo futuro/expirado.
# -------------------------------------------------------------------


def test_v3_incapable_root_does_not_close_query():
    """Una raiz PSD_AISP cerrada no puede producir
    CONFIRMED_NOT_ENTITLED en una query PIS (mutante and->or en el
    filtro de raices aplicables)."""
    facts = [_fact(root_key="EBA|PSD_AISP|NL_DNB!F9",
                   effective_from="2024-01-01",
                   neg_class="EXPLICIT_WITHDRAWAL")]
    a = _assertion("v1", LegalEffect.NOT_ENTITLED,
                   root="EBA|PSD_AISP|NL_DNB!F9")
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is not AssessmentV2.CONFIRMED_NOT_ENTITLED


def test_v3_absent_root_does_not_close_query():
    """Raiz con intervalos solo futuros => ABSENT: no cuenta como
    raiz aplicable aunque sus rutas esten cerradas."""
    facts = [_fact(intervals=[{"from": "2030-01-01", "to": None}])]
    a1 = _assertion("v2a", LegalEffect.NOT_ENTITLED)
    a2 = _assertion("v2b", LegalEffect.NOT_ENTITLED, basis="BRANCH")
    r = _assess([a1, a2], facts, "2027-01-10")
    assert r.assessment is not AssessmentV2.CONFIRMED_NOT_ENTITLED


def test_v3_unresolved_root_blocks_confirmed_negative():
    """UNRESOLVED no es CLOSED: raiz baja + rutas cerradas =>
    INDETERMINATE, nunca CONFIRMED_NOT_ENTITLED."""
    facts = [
        _fact(root_key="EBA|PSD_PI|NL_DNB!F1",
              effective_from="2024-01-01", neg_class="ENTITY_BAJA"),
        _fact(root_key="EBA|PSD_PI|NL_DNB!F2",
              effective_from="2024-01-01", neg_class="EXPLICIT_WITHDRAWAL"),
    ]
    negs = [
        _assertion("v3a", LegalEffect.NOT_ENTITLED, root="EBA|PSD_PI|NL_DNB!F1"),
        _assertion("v3b", LegalEffect.NOT_ENTITLED, root="EBA|PSD_PI|NL_DNB!F1",
                   basis="BRANCH"),
    ]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.INDETERMINATE


def test_v3_explicit_basis_only_intersects_legal_routes():
    """Query PIS+FPS con raiz home=ES: FPS no es via legal para ese
    home => possible = {DOMESTIC} & {FPS} = vacio, y una ruta FPS
    cerrada no puede cerrar la raiz. (El mutante `possible = {tb}`
    ignoraba la interseccion y daria CONFIRMED_NOT_ENTITLED.)"""
    facts = [_fact(home="ES")]
    a = _assertion("v4", LegalEffect.NOT_ENTITLED,
                   basis="FREEDOM_TO_PROVIDE_SERVICES", home="ES")
    r = _assess([a], facts, "2027-01-10",
                territorial_basis="FREEDOM_TO_PROVIDE_SERVICES")
    assert r.assessment is AssessmentV2.INDETERMINATE


def test_v3_all_routes_closed_reason_when_not_withdrawal():
    """Cierre por rutas (sin retirada de raiz) => razon
    ALL_AVAILABLE_ROUTES_CLOSED, no ROOT_FAMILY_WITHDRAWN."""
    facts = [_fact()]
    negs = [
        _assertion("v5a", LegalEffect.NOT_ENTITLED),
        _assertion("v5b", LegalEffect.NOT_ENTITLED, basis="BRANCH"),
    ]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert r.reason is AssessmentReason.ALL_AVAILABLE_ROUTES_CLOSED


def test_v3_withdrawn_root_reason_is_root_family():
    facts = [_fact(effective_from="2024-01-01", neg_class="EXPLICIT_WITHDRAWAL")]
    r = _assess([], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert r.reason is AssessmentReason.ROOT_FAMILY_WITHDRAWN


def test_v3_mixed_withdrawal_and_route_closure_reason():
    """Raiz A retirada + raiz B con todas las rutas cerradas => la
    razon agregada es ALL_AVAILABLE_ROUTES_CLOSED (no toda la carga
    es retirada). Mata el mutante and->or en la seleccion de razon."""
    facts = [
        _fact(root_key="EBA|PSD_PI|NL_DNB!F1",
              effective_from="2024-01-01", neg_class="EXPLICIT_WITHDRAWAL"),
        _fact(root_key="EBA|PSD_PI|NL_DNB!F2"),
    ]
    negs = [
        _assertion("v6a", LegalEffect.NOT_ENTITLED, root="EBA|PSD_PI|NL_DNB!F2"),
        _assertion("v6b", LegalEffect.NOT_ENTITLED, root="EBA|PSD_PI|NL_DNB!F2",
                   basis="BRANCH"),
    ]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert r.reason is AssessmentReason.ALL_AVAILABLE_ROUTES_CLOSED


def test_v3_closed_route_with_unresolved_alternative_is_indeterminate():
    """FPS cerrada + BRANCH legalmente posible sin evidencia =>
    INDETERMINATE (no NOT_ENTITLED)."""
    facts = [_fact()]
    negs = [_assertion("v7", LegalEffect.NOT_ENTITLED)]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED


def test_v3_future_positive_on_open_root_is_indeterminate():
    """Positivo no admisible (effective_from > as_of) sobre raiz
    abierta: la ruta existira pero no era observable => INDETERMINATE
    TERRITORIAL, nunca NO_ENTITLEMENT."""
    facts = [_fact()]
    a = _assertion("v8", LegalEffect.ENTITLED_TO_PROVIDE,
                   effective_from="2028-01-01")
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED


def test_v3_future_positive_boundary_effective_from_equals_as_of():
    """effective_from == as_of: la ventana cubre; si es inadmisible
    (stale) no es 'futuro' (mata el mutante >=)."""
    facts = [_fact()]
    a = _assertion(
        "v9", LegalEffect.ENTITLED_TO_PROVIDE,
        effective_from="2027-01-10",
        sources=(_src(retrieved="2026-01-01", source_as_of="2026-01-01"),),
    )
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED


def test_v3_expired_positive_gives_entitlement_expired():
    """Positivo con ventana cerrada sobre raiz abierta =>
    NO_ENTITLEMENT_EVIDENCED / ENTITLEMENT_EXPIRED."""
    facts = [_fact()]
    a = _assertion("v10", LegalEffect.ENTITLED_TO_PROVIDE,
                   effective_from="2020-01-01", effective_to="2024-01-01",
                   interval_end="EXCLUSIVE")
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.ENTITLEMENT_EXPIRED


def test_v3_expired_positive_boundary_effective_to_equals_as_of():
    """EXCLUSIVE: effective_to == as_of ya esta cerrada => expirada.
    (mata el mutante < en la comparacion)."""
    facts = [_fact()]
    a = _assertion("v11", LegalEffect.ENTITLED_TO_PROVIDE,
                   effective_from="2020-01-01", effective_to="2027-01-10",
                   interval_end="EXCLUSIVE")
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.ENTITLEMENT_EXPIRED


def test_v3_expired_negative_does_not_fake_expired_positive():
    """Una NOT_ENTITLED con ventana cerrada no es 'positivo expirado':
    mata el mutante is->is not en la seleccion de expired_positive."""
    facts = [_fact()]
    a = _assertion("v12", LegalEffect.NOT_ENTITLED,
                   effective_from="2020-01-01", effective_to="2024-01-01",
                   interval_end="EXCLUSIVE")
    r = _assess([a], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.NO_ASSERTIONS_IN_SCOPE


def test_v3_route_conflict_reports_used_assertions():
    """El resultado de conflicto lleva las aserciones usadas
    (mata mutantes que vacian used=)."""
    facts = [_fact()]
    pos = _assertion("v13a", LegalEffect.ENTITLED_TO_PROVIDE)
    neg = _assertion("v13b", LegalEffect.NOT_ENTITLED)
    r = _assess([pos, neg], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.ROUTE_CONFLICT
    assert len(r.assertions) == 2
    assert (
        "route_conflict:EBA|PSD_PI|NL_DNB!F1:FREEDOM_TO_PROVIDE_SERVICES"
        in r.diagnostics
    )


def test_v3_result_serializes_query_fields():
    """entity_id/activity/jurisdiction/as_of se propagan al resultado
    (mata mutantes None en _result)."""
    facts = [_fact()]
    pos = _assertion("v14", LegalEffect.ENTITLED_TO_PROVIDE)
    r = _assess([pos], facts, "2027-01-10")
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED
    assert r.entity_id == "SYN-1"
    assert r.activity == "PAYMENT_INITIATION_SERVICES"
    assert r.jurisdiction == "ES"
    assert r.as_of == "2027-01-10"


def test_v3_result_serializes_negative_bridge_fields():
    """El dict de asercion expone negative_scope /
    negative_evidence_class (campos E4.1)."""
    facts = [_fact()]
    negs = [
        _assertion("v15a", LegalEffect.NOT_ENTITLED),
        _assertion("v15b", LegalEffect.NOT_ENTITLED, basis="BRANCH"),
    ]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert r.assertions[0]["negative_scope"] == "ROUTE_CAPABILITY"
    assert r.assertions[0]["negative_evidence_class"] == "ENUMERATED_ABSENCE"


# -------------------------------------------------------------------
# assess() V1/V2 — rama historica: mutantes en continue/expired/V2.
# -------------------------------------------------------------------


def test_v1_inadmissible_first_assertion_does_not_stop_scan():
    """Una asercion inadmisible no aborta el barrido: la siguiente
    admisible sigue produciendo entitlement (mutante continue->break)."""
    stale = _assertion(
        "w1", LegalEffect.ENTITLED_TO_PROVIDE,
        sources=(_src(retrieved="2020-01-01", source_as_of="2020-01-01"),),
    )
    fresh = _assertion("w2", LegalEffect.ENTITLED_TO_PROVIDE)
    r = _assess([stale, fresh], [], "2027-01-10", version="V1")
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED


def test_v1_expired_positive_reason_entitlement_expired():
    """Positivo expirado (to < as_of, ventana legacy inclusiva) =>
    NO_ENTITLEMENT con razon ENTITLEMENT_EXPIRED."""
    a = _assertion("w3", LegalEffect.ENTITLED_TO_PROVIDE,
                   effective_from="2020-01-01", effective_to="2024-01-01")
    r = _assess([a], [], "2027-01-10", version="V1")
    assert r.assessment is Assessment.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.ENTITLEMENT_EXPIRED


def test_v1_expired_negative_is_not_expired_positive():
    """Negativo con ventana cerrada no cuenta como positivo expirado
    (mutante and->or en la condicion)."""
    a = _assertion("w4", LegalEffect.NOT_ENTITLED,
                   effective_from="2020-01-01", effective_to="2024-01-01")
    r = _assess([a], [], "2027-01-10", version="V1")
    assert r.reason is not AssessmentReason.ENTITLEMENT_EXPIRED


def test_v2_withdrawn_fact_conflicts_with_positive():
    """V2/A7: positivo admisible + fact reportado WITHDRAWN =>
    INDETERMINATE, nunca positivo silencioso."""
    a = _assertion("w5", LegalEffect.ENTITLED_TO_PROVIDE)
    facts = [{
        "corpus_id": ENTITY.entity_id,
        "fact_id": "f-wd",
        "rule_id": "x",
        "reported_status": "WITHDRAWN",
    }]
    r = _assess([a], facts, "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.CONFLICTING_ASSERTIONS
    assert "conflicting_reported_fact:withdrawn" in r.diagnostics
    assert len(r.assertions) == 1


def test_v2_unknown_fps_assertions_give_territorial_reason():
    """V2: toda la evidencia admisible UNKNOWN y territorial FPS =>
    TERRITORIAL_ENTITLEMENT_UNRESOLVED."""
    a = _assertion("w6", LegalEffect.UNKNOWN)
    r = _assess([a], [], "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED
    assert len(r.assertions) == 1


def test_v2_unknown_mixed_basis_gives_uninterpretable():
    """UNKNOWN no-FPS: la razon territorial no aplica."""
    a = _assertion("w7", LegalEffect.UNKNOWN, basis="DOMESTIC", home="ES")
    r = _assess([a], [], "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.UNINTERPRETABLE_EVIDENCE


def test_v2_no_admissible_with_facts_reports_them():
    """V2: entidad con facts pero sin aserciones admisibles =>
    INDETERMINATE con la razon del hecho reportado."""
    facts = [{
        "corpus_id": ENTITY.entity_id,
        "fact_id": "f1",
        "rule_id": "eba-parent-status",
        "reported_status": "ACTIVE",
    }, {
        "corpus_id": ENTITY.entity_id,
        "fact_id": "f2",
        "rule_id": "eba-parent-status",
        "reported_status": "ACTIVE",
    }]
    r = _assess([], facts, "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.PARENT_STATUS_NOT_CHILD_ENTITLEMENT
    assert "reported_facts:f1,f2" in r.diagnostics


def test_reported_fact_reason_precedence():
    """Seleccion de razon V2 por contenido del hecho reportado."""
    base = {"corpus_id": "x", "fact_id": "f", "reported_status": "ACTIVE"}
    assert _reported_fact_reason(
        [dict(base, rule_id="eba-agent-parent-status")]
    ) is AssessmentReason.AGENT_DELEGATED_ROUTE_NO_INDEPENDENT_ENTITLEMENT
    assert _reported_fact_reason(
        [dict(base, rule_id="bde-limited-lp")]
    ) is AssessmentReason.TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP
    assert _reported_fact_reason(
        [dict(base, rule_id="eba-parent-status")]
    ) is AssessmentReason.PARENT_STATUS_NOT_CHILD_ENTITLEMENT
    assert _reported_fact_reason(
        [dict(base, rule_id="bde-insufficient-basis")]
    ) is AssessmentReason.INSUFFICIENT_LEGAL_BASIS
    assert _reported_fact_reason(
        [dict(base, rule_id="r", reported_status="WITHDRAWN")]
    ) is AssessmentReason.WITHDRAWAL_SEMANTICS_DEFERRED
    assert _reported_fact_reason(
        [dict(base, rule_id="r",
              reported_status="TERRITORIAL_ENTITLEMENT_DEFERRED")]
    ) is AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED


def test_effective_effect_at_closed_window_negative_is_unknown():
    """Negativo con ventana cerrada => ('UNKNOWN','WINDOW_CLOSED') —
    un negativo expirado no afirma nada."""
    a = _assertion("w8", LegalEffect.NOT_ENTITLED,
                   effective_from="2020-01-01", effective_to="2024-01-01")
    assert a.effective_effect_at(date(2027, 1, 10)) == (
        "UNKNOWN", "WINDOW_CLOSED"
    )
    a2 = _assertion("w9", LegalEffect.ENTITLED_TO_PROVIDE,
                    effective_from="2020-01-01", effective_to="2024-01-01")
    assert a2.effective_effect_at(date(2027, 1, 10)) == (
        "NOT_ENTITLED", "ENTITLEMENT_EXPIRED"
    )


# -------------------------------------------------------------------
# Batch 2 — triage fino de los supervivientes restantes.
#
# coverage.py: matched_rule_id / reason son campos contractuales del
# ScopeDecision (los consume can_produce_enumeration_negative).
# semantics.py: CoverageQuery debe propagar entity_class /
# territorial_basis / effective_date; freshness_at prefiere
# source_as_of; los emits V1/V2 llevan diagnostics y used=.
# -------------------------------------------------------------------

BDE_SERVICIOS = "BDE_REGISTRO_SERVICIOS_PAGO"  # pos 90 / neg 45


def _dated_contract(register_id="SYN_DATED"):
    """Contrato con regla IN fechada: effective_date=None debe romper
    la comparacion (mata mutantes as_of/effective_date -> None)."""
    return dataclasses.replace(
        EBA,
        register_id=register_id,
        coverage_rules=(
            CoverageRule("d-in", "IN", None, None, None, None,
                         "2020-01-01", None, ""),
        ),
    )


def test_coverage_activity_not_covered_reports_rule_id():
    """matched_rule_id='contract-activities-coverage' es contractual:
    can_produce_enumeration_negative lo coteja con el snapshot."""
    d = coverage(EBA, CoverageQuery(
        entity_class="PAYMENT_INSTITUTION",
        activity="DEPOSIT_TAKING",
        jurisdiction="ES",
        territorial_basis="FREEDOM_TO_PROVIDE_SERVICES",
        effective_date="2027-01-10",
    ))
    assert d.status is ScopeStatus.OUT_OF_SCOPE
    assert d.matched_rule_id == "contract-activities-coverage"
    assert d.reason == "ACTIVITY_NOT_COVERED_BY_REGISTER"


def test_coverage_no_rule_matches_is_unknown_with_reason():
    """Sin regla aplicable => UNKNOWN + NO_RULE_MATCHES (no afirma)."""
    d = coverage(CONTRACTS[BDE_SERVICIOS], CoverageQuery(
        entity_class="PAYMENT_INSTITUTION",
        activity="PAYMENT_INITIATION_SERVICES",
        jurisdiction="ES",
        territorial_basis=None,
        effective_date="2027-01-10",
    ))
    assert d.status is ScopeStatus.UNKNOWN
    assert d.matched_rule_id is None
    assert d.reason == "NO_RULE_MATCHES"


def test_admissible_entity_class_drives_out_rule():
    """CREDIT_INSTITUTION cae en eba-psd2-out-credit-institutions:
    entity_class=None en la query haria la regla invisible."""
    a = _assertion("ec1", LegalEffect.ENTITLED_TO_PROVIDE,
                   entity_class="CREDIT_INSTITUTION")
    ok, diag = _admissible(a)
    assert ok is False
    assert "out_of_source_scope:ec1" in diag


def test_admissible_territorial_basis_drives_out_rule():
    """FPS en el registro BdE-servicios cae en bde-psp-out-fps:
    territorial_basis=None escondiria la exclusion."""
    a = _assertion("tb1", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id=BDE_SERVICIOS,
                   basis="FREEDOM_TO_PROVIDE_SERVICES",
                   sources=(_src(BDE_SERVICIOS),))
    ok, diag = _admissible(a)
    assert ok is False
    assert "out_of_source_scope:tb1" in diag


def test_admissible_dated_rule_uses_effective_date():
    contract = _dated_contract()
    contracts = {**CONTRACTS, contract.register_id: contract}
    a = _assertion("dt1", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id=contract.register_id,
                   sources=(_src(contract.register_id),))
    ok, _ = _admissible(a, contracts=contracts)
    assert ok is True


def test_assess_v1_dated_rule_path():
    """as_of->None en el path V1/V2 de admisibilidad romperia la
    comparacion con valid_from."""
    contract = _dated_contract("SYN_DATED_V1")
    contracts = {**CONTRACTS, contract.register_id: contract}
    a = _assertion("dt2", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id=contract.register_id,
                   sources=(_src(contract.register_id),))
    r = _assess([a], [], "2027-01-10", version="V1", contracts=contracts)
    assert r.assessment is Assessment.CONFIRMED_AUTHORISED


def test_assess_v3_dated_rule_path():
    """as_of->None hacia _assess_v3 / su llamada a admisibilidad."""
    contract = _dated_contract("SYN_DATED_V3")
    contracts = {**CONTRACTS, contract.register_id: contract}
    a = _assertion("dt3", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id=contract.register_id,
                   sources=(_src(contract.register_id),))
    r = _assess([a], [], "2027-01-10", version="V3", contracts=contracts)
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED


def test_all_required_reg_entity_class_drives_out():
    """ALL_REQUIRED: la regla OUT de un registro secundario se aplica
    al entity_class de la asercion."""
    syn = dataclasses.replace(
        EBA, register_id="SYN_EC_OUT",
        coverage_rules=(
            CoverageRule("s-out", "OUT", "PAYMENT_INSTITUTION",
                         None, None, None, None, None, ""),
            CoverageRule("s-in", "IN", None, None, None,
                         None, None, None, ""),
        ),
    )
    contracts = {**CONTRACTS, syn.register_id: syn}
    a = _assertion("rc1", LegalEffect.ENTITLED_TO_PROVIDE,
                   sources=(_src(), _src(syn.register_id)),
                   evidence_composition="ALL_REQUIRED")
    ok, diag = _admissible(a, contracts=contracts)
    assert ok is False
    assert f"out_of_source_scope:rc1:{syn.register_id}" in diag


def test_all_required_reg_territorial_basis_drives_out():
    """BdE-servicios como registro requerido: tb=FPS => OUT."""
    a = _assertion("rc2", LegalEffect.ENTITLED_TO_PROVIDE,
                   sources=(_src(), _src(BDE_SERVICIOS)),
                   evidence_composition="ALL_REQUIRED")
    ok, diag = _admissible(a)
    assert ok is False
    assert f"out_of_source_scope:rc2:{BDE_SERVICIOS}" in diag


def test_all_required_reg_dated_rule_uses_effective_date():
    syn = _dated_contract("SYN_DATED_REG")
    contracts = {**CONTRACTS, syn.register_id: syn}
    a = _assertion("rc3", LegalEffect.ENTITLED_TO_PROVIDE,
                   sources=(_src(), _src(syn.register_id)),
                   evidence_composition="ALL_REQUIRED")
    ok, _ = _admissible(a, contracts=contracts)
    assert ok is True


def test_admissible_prefers_source_as_of_over_retrieved():
    """freshness_at = source_as_of ?? retrieved_at: una fuente con
    retrieved_at viejo pero source_as_of fresco NO esta stale."""
    a = _assertion("sa1", LegalEffect.ENTITLED_TO_PROVIDE,
                   sources=(_src(retrieved="2020-01-01",
                                 source_as_of="2027-01-05"),))
    ok, _ = _admissible(a)
    assert ok is True


def test_all_required_reg_prefers_source_as_of_over_retrieved():
    """ALL_REQUIRED: la frescura del registro requerido tambien usa
    source_as_of ?? retrieved_at (mutantes source_as_of->None en el
    bucle de registros)."""
    syn = dataclasses.replace(
        EBA, register_id="SYN_FRESH",
        coverage_rules=(
            CoverageRule("s-in", "IN", None, None, None,
                         None, None, None, ""),
        ),
    )
    contracts = {**CONTRACTS, syn.register_id: syn}
    a = _assertion(
        "sa2", LegalEffect.ENTITLED_TO_PROVIDE,
        sources=(
            _src(),
            _src(syn.register_id, retrieved="2020-01-01",
                 source_as_of="2027-01-05"),
        ),
        evidence_composition="ALL_REQUIRED",
    )
    ok, _ = _admissible(a, contracts=contracts)
    assert ok is True


def test_fact_freshness_falls_back_to_retrieved_at():
    """source_as_of ausente => la frescura se mide por retrieved_at
    (mutantes: retrieved_at=None rompe is_stale, 'or True' parsea
    un valor vacio)."""
    f = _fact(source_as_of=None)
    assert _fact_freshness_ok(f, CONTRACTS, date(2027, 1, 10)) is True


def test_latest_freshness_propagates_source_reliability():
    a = _assertion("lf1", LegalEffect.ENTITLED_TO_PROVIDE)
    assert a.latest_freshness().source_date_reliability == "TRUSTED"


def test_v3_routes_closed_root_does_not_hide_open_root():
    """Root A con todas sus rutas cerradas + root B abierta: el
    agregador no puede cortocircuitar a CONFIRMED_NOT_ENTITLED
    (mata continue->break en el cierre por rutas)."""
    facts = [
        _fact("EBA|PSD_PI|NL_DNB!A",
              intervals=[{"from": "2020-01-01", "to": None}]),
        _fact("EBA|PSD_PI|NL_DNB!B",
              intervals=[{"from": "2020-01-01", "to": None}]),
    ]
    negs = [
        _assertion("rr-a1", LegalEffect.NOT_ENTITLED,
                   root="EBA|PSD_PI|NL_DNB!A"),
        _assertion("rr-a2", LegalEffect.NOT_ENTITLED, basis="BRANCH",
                   root="EBA|PSD_PI|NL_DNB!A"),
    ]
    r = _assess(negs, facts, "2027-01-10")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED


def test_expired_positive_boundary_effective_to_equals_as_of():
    """V1/V2: un positivo con effective_to == as_of NO cuenta como
    expirado (legacy cierra solo con to < as_of)."""
    neg = _assertion("ex-n", LegalEffect.NOT_ENTITLED,
                     effective_from="2020-01-01", effective_to="2024-01-01")
    pos = _assertion("ex-p", LegalEffect.ENTITLED_TO_PROVIDE,
                     effective_from="2020-01-01", effective_to="2027-01-10",
                     sources=(_src(retrieved="2020-01-01",
                                   source_as_of="2020-01-01"),))
    r = _assess([neg, pos], [], "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED
    assert r.reason is AssessmentReason.NO_ASSERTIONS_IN_SCOPE


def test_v2_inadmissible_unknown_scope_is_uninterpretable():
    """matching no vacio + todo inadmisible por scope desconocido sin
    evidencia => INDETERMINATE / UNINTERPRETABLE_EVIDENCE."""
    a = _assertion("u1", LegalEffect.ENTITLED_TO_PROVIDE,
                   register_id="ESMA_MICA_REGISTER",
                   activity="CRYPTO_ASSET_SERVICES",
                   entity_class="CREDIT_INSTITUTION",
                   sources=())
    r = _assess([a], [], "2027-01-10", version="V2",
                activity="CRYPTO_ASSET_SERVICES")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.UNINTERPRETABLE_EVIDENCE


def test_not_found_result_carries_query_fields():
    """Resultado de identidad NOT_FOUND: activity/jurisdiction/as_of
    y el diagnostico identity: se propagan."""
    r = assess(
        "NO_SUCH_ID", INDEX,
        activity="PAYMENT_INITIATION_SERVICES", jurisdiction="ES",
        as_of="2027-01-10", assertions=[], contracts=CONTRACTS,
        semantics_version="V2",
    )
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.IDENTITY_NOT_FOUND
    assert r.entity_id is None
    assert r.activity == "PAYMENT_INITIATION_SERVICES"
    assert r.jurisdiction == "ES"
    assert r.as_of == "2027-01-10"
    assert r.diagnostics == ("identity:UNKNOWN_ENTITY_ID",)


def test_ambiguous_resolution_result_fields():
    """Resolucion no-EXACT: entity_id y campos de query viajan."""
    resolution = IdentityResolution(
        IdentityResolutionState.AMBIGUOUS, "SYN-1", "DUPLICATE_LEI"
    )
    r = assess(
        resolution, INDEX,
        activity="PAYMENT_INITIATION_SERVICES", jurisdiction="ES",
        as_of="2027-01-10", assertions=[], contracts=CONTRACTS,
        semantics_version="V2",
    )
    assert r.assessment is Assessment.INDETERMINATE
    assert r.reason is AssessmentReason.AMBIGUOUS_IDENTITY
    assert r.entity_id == "SYN-1"
    assert r.activity == "PAYMENT_INITIATION_SERVICES"
    assert r.jurisdiction == "ES"
    assert r.as_of == "2027-01-10"
    assert r.diagnostics == ("identity:DUPLICATE_LEI",)


def test_assess_accepts_index_entry_object():
    """entity_query como IdentityIndexEntry => resolucion EXACT."""
    facts = [_fact()]
    pos = _assertion("ep1", LegalEffect.ENTITLED_TO_PROVIDE)
    r = assess(
        ENTITY, INDEX,
        activity="PAYMENT_INITIATION_SERVICES", jurisdiction="ES",
        as_of="2027-01-10", assertions=[pos], contracts=CONTRACTS,
        semantics_version="V3", reported_facts=facts,
    )
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED
    assert r.entity_id == "SYN-1"


def test_v2_conflicting_legal_effects_reports_diagnostic():
    """Positivo + negativo admisibles => INDETERMINATE con el
    diagnostico contractual 'conflicting_legal_effects'."""
    pos = _assertion("cf-p", LegalEffect.ENTITLED_TO_PROVIDE)
    neg = _assertion("cf-n", LegalEffect.NOT_ENTITLED)
    r = _assess([pos, neg], [], "2027-01-10", version="V2")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert r.reason is AssessmentReason.CONFLICTING_ASSERTIONS
    assert "conflicting_legal_effects" in r.diagnostics
    assert len(r.assertions) == 2
