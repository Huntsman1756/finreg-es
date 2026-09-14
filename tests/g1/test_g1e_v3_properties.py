"""G1-E (E6-A) — Hypothesis property probe sobre ASSESSMENT_SEMANTICS_V3.

OSS scan failure-driven: el fallo a detectar es "la agregacion
route-aware viola sus invariantes bajo combinaciones no escritas a
mano". Hypothesis genera (root x route x efecto x ventana x
admissibility x hechos de raiz) y reduce el contraejemplo minimo.

Propiedades fijadas (oraculo = condiciones necesarias, no re-
implementacion del motor):

  P1  el motor nunca explota y siempre emite un AssessmentV2 valido.
  P2  CONFIRMED_ENTITLED => existe asercion usada ENTITLED.
  P3  CONFIRMED_NOT_ENTITLED => ninguna asercion usada es ENTITLED.
  P4  determinismo: misma entrada => mismo resultado.
  P5  metamorfico: bloquear TODOS los negativos (admissibility=
      BLOCKED) nunca produce CONFIRMED_NOT_ENTITLED cuando no hay
      hechos de raiz que lo sostengan.
  P6  metamorfico: un negativo admisible en una ruta distinta de la
      ruta abierta nunca convierte ENTITLED en otra cosa.
  P7  covers()/effective_effect_at(): EXCLUSIVE cierra EN `to`;
      legacy solo cuando `to` < as_of; monotonia temporal.

Configuracion: derandomize + database=None => ejemplos fijos, suite
offline-determinista; hypothesis vive solo en el extra ``tooling``
(el runtime core sigue stdlib-only).
"""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from finreg_es.canonical import strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.identity import IdentityIndexEntry
from finreg_es.semantics import (
    EntitlementAssertion,
    SourceAssertion,
    assess,
)
from finreg_es.vocab import AssessmentV2, LegalEffect


ROOT = Path(__file__).parents[2]
CONTRACTS = {
    c.register_id: c
    for c in (
        load_contract(p)
        for p in sorted((ROOT / "fixtures" / "contracts").glob("*.json"))
    )
}

ENTITY = IdentityIndexEntry(
    entity_id="SYN-1",
    legal_name="SYNTHETIC PROPERTY ENTITY",
    entity_classes=("PAYMENT_INSTITUTION",),
)
INDEX = [ENTITY]

# Evidencia fechada por encima del rango de probes: freshness nunca es
# la variable bajo test (ventanas EBA 45d/30d => probes <= 2027-01-31).
RETRIEVED = "2027-01-05"
SOURCE = SourceAssertion(
    authority="European Banking Authority (EBA)",
    register_id="EBA_PSD2_REGISTER",
    source_url="test://property-probe",
    retrieved_at=RETRIEVED,
    source_as_of=RETRIEVED,
    source_date_reliability="TRUSTED",
    raw_value="synthetic",
    raw_snapshot_sha256="0" * 64,
    extractor_version="g1e-property-probe",
    observed_current=True,
)

BASES = ("FREEDOM_TO_PROVIDE_SERVICES", "BRANCH")
HOME = "NL"  # home != ES => vias legalmente posibles = {FPS, BRANCH}


def _assertion(
    aid: str,
    effect: LegalEffect,
    basis: str,
    root: str,
    effective_from: str,
    effective_to: str | None = None,
    interval_end: str | None = None,
    admissibility: str | None = None,
    negative_class: str | None = None,
    activity: str = "MONEY_REMITTANCE",
) -> EntitlementAssertion:
    return EntitlementAssertion(
        assertion_id=aid,
        register_id="EBA_PSD2_REGISTER",
        entity_id=ENTITY.entity_id,
        entity_class="PAYMENT_INSTITUTION",
        activity=activity,
        jurisdiction="ES",
        legal_effect=effect,
        entry_mechanism="AUTHORISATION",
        territorial_basis=basis,
        legal_basis="synthetic probe",
        effective_from=effective_from,
        effective_to=effective_to,
        scope="synthetic",
        source_assertions=(SOURCE,),
        interval_end=interval_end,
        admissibility=admissibility,
        negative_scope="ROUTE_CAPABILITY" if negative_class else None,
        negative_evidence_class=negative_class,
        root_key=root,
        root_home_jurisdiction=HOME,
    )


def _root_fact(root: str, intervals, effective_from=None,
               neg_class=None, with_provenance=True) -> dict:
    fact = {
        "fact_id": f"fact-{root.split('|')[-1]}",
        "corpus_id": ENTITY.entity_id,
        "source": "EBA_PSD2_REGISTER",
        "rule_id": "eba-psd2-root-status-fact",
        "reported_status": "WITHDRAWN" if neg_class else "ACTIVE",
        "status_intervals": intervals,
        "root_key": root,
        "root_home_jurisdiction": HOME,
        "negative_scope": "ROOT_FAMILY",
    }
    if effective_from:
        fact["effective_from"] = effective_from
    if neg_class:
        fact["negative_evidence_class"] = neg_class
    if with_provenance:
        fact["source_claim_ids"] = ["claim-1"]
        fact["source_assertions"] = [
            {
                "authority": SOURCE.authority,
                "register_id": SOURCE.register_id,
                "source_url": SOURCE.source_url,
                "retrieved_at": SOURCE.retrieved_at,
                "source_as_of": SOURCE.source_as_of,
                "source_date_reliability": SOURCE.source_date_reliability,
                "raw_value": SOURCE.raw_value,
                "raw_snapshot_sha256": SOURCE.raw_snapshot_sha256,
                "extractor_version": SOURCE.extractor_version,
                "observed_current": SOURCE.observed_current,
            }
        ]
    return fact


def _run(assertions, facts=None, as_of="2026-09-14", territorial_basis=None):
    return assess(
        ENTITY.entity_id,
        INDEX,
        activity="MONEY_REMITTANCE",
        jurisdiction="ES",
        as_of=as_of,
        assertions=assertions,
        contracts=CONTRACTS,
        semantics_version="V3",
        reported_facts=facts or [],
        territorial_basis=territorial_basis,
    )


# ------------------------------------------------------------------
# P7 — frontera de intervalo (property sobre covers/effective_effect_at)
# ------------------------------------------------------------------


@given(
    start=st.dates(min_value=date(2010, 1, 1), max_value=date(2026, 1, 1)),
    delta=st.integers(min_value=0, max_value=4000),
    probe=st.dates(min_value=date(2010, 1, 1), max_value=date(2030, 12, 31)),
    interval_end=st.sampled_from([None, "EXCLUSIVE"]),
)
@settings(derandomize=True, database=None, deadline=None, max_examples=200)
def test_interval_boundary_property(start, delta, probe, interval_end):
    end = date.fromordinal(start.toordinal() + delta)
    a = _assertion(
        "p",
        LegalEffect.ENTITLED_TO_PROVIDE,
        "DOMESTIC",
        "EBA|PSD_PI|NL_DNB!T1",
        effective_from=start.isoformat(),
        effective_to=end.isoformat(),
        interval_end=interval_end,
    )
    covers = a.covers(probe)
    in_window = start <= probe
    if interval_end == "EXCLUSIVE":
        assert covers == (in_window and probe < end)
    else:
        # Semantica legacy: la ventana sigue abierta el propio dia `to`.
        assert covers == (in_window and probe <= end)
    # Monotonia: cerrada una vez, cerrada siempre.
    if not covers and probe >= end and interval_end == "EXCLUSIVE":
        assert not a.covers(date.fromordinal(probe.toordinal() + 1))


# ------------------------------------------------------------------
# P1-P4 — invariantes sobre bundles sinteticos
# ------------------------------------------------------------------

_route_assertion = st.builds(
    lambda i, basis, effect, adm, frm, to, excl: _assertion(
        f"a{i}",
        effect,
        basis,
        "EBA|PSD_PI|NL_DNB!T1",
        effective_from=frm.isoformat(),
        effective_to=to.isoformat() if to else None,
        interval_end="EXCLUSIVE" if excl else None,
        admissibility=adm,
        negative_class=(
            "ENUMERATED_ABSENCE" if effect is LegalEffect.NOT_ENTITLED else None
        ),
    ),
    i=st.integers(min_value=0, max_value=999),
    basis=st.sampled_from(BASES),
    effect=st.sampled_from([LegalEffect.ENTITLED_TO_PROVIDE,
                            LegalEffect.NOT_ENTITLED]),
    adm=st.sampled_from([None, "ADMISSIBLE", "BLOCKED"]),
    frm=st.dates(min_value=date(2020, 1, 1), max_value=date(2026, 9, 14)),
    to=st.one_of(
        st.none(),
        st.dates(min_value=date(2020, 1, 1), max_value=date(2027, 12, 31)),
    ),
    excl=st.booleans(),
)

_as_of = st.dates(min_value=date(2020, 1, 1), max_value=date(2027, 1, 31))


@given(
    bundle=st.lists(_route_assertion, min_size=0, max_size=6),
    as_of=_as_of,
)
@settings(derandomize=True, database=None, deadline=None, max_examples=300)
def test_aggregation_invariants(bundle, as_of):
    # assertion_id unico dentro del bundle.
    for i, a in enumerate(bundle):
        object.__setattr__(a, "assertion_id", f"a{i}")
    result = _run(bundle, as_of=as_of.isoformat())

    assert result.assessment in set(AssessmentV2)
    assert result.identity_resolution.value == "EXACT"

    used_effects = {a["legal_effect"] for a in result.assertions}
    if result.assessment is AssessmentV2.CONFIRMED_ENTITLED:
        assert "ENTITLED_TO_PROVIDE" in used_effects
    if result.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED:
        assert "ENTITLED_TO_PROVIDE" not in used_effects

    # P4: determinismo.
    again = _run(bundle, as_of=as_of.isoformat())
    assert again.assessment == result.assessment
    assert again.reason == result.reason


# ------------------------------------------------------------------
# P5 — bloquear los negativos nunca sostiene CONFIRMED_NOT_ENTITLED
# ------------------------------------------------------------------


@given(
    bundle=st.lists(_route_assertion, min_size=0, max_size=6),
    as_of=_as_of,
)
@settings(derandomize=True, database=None, deadline=None, max_examples=300)
def test_blocked_negatives_cannot_close_routes(bundle, as_of):
    for i, a in enumerate(bundle):
        object.__setattr__(a, "assertion_id", f"a{i}")
    blocked_bundle = [
        (
            a
            if a.legal_effect is not LegalEffect.NOT_ENTITLED
            else copy.copy(a).__class__(
                **{**a.__dict__, "admissibility": "BLOCKED"}
            )
        )
        for a in bundle
    ]
    result = _run(blocked_bundle, as_of=as_of.isoformat())
    # Sin hechos de raiz no puede haber CONFIRMED_NOT_ENTITLED si todos
    # los negativos estan bloqueados.
    assert result.assessment is not AssessmentV2.CONFIRMED_NOT_ENTITLED


# ------------------------------------------------------------------
# P6 — un negativo en otra ruta nunca cierra una ruta abierta
# ------------------------------------------------------------------


@given(
    neg_basis=st.sampled_from(BASES),
    as_of=st.dates(min_value=date(2026, 9, 14), max_value=date(2027, 1, 31)),
)
@settings(derandomize=True, database=None, deadline=None, max_examples=50)
def test_cross_route_negative_never_closes_open_route(neg_basis, as_of):
    open_basis = "BRANCH" if neg_basis == "FREEDOM_TO_PROVIDE_SERVICES" else (
        "FREEDOM_TO_PROVIDE_SERVICES"
    )
    bundle = [
        _assertion("pos", LegalEffect.ENTITLED_TO_PROVIDE, open_basis,
                   "EBA|PSD_PI|NL_DNB!T1", effective_from="2024-01-01"),
        _assertion("neg", LegalEffect.NOT_ENTITLED, neg_basis,
                   "EBA|PSD_PI|NL_DNB!T1", effective_from="2026-09-14",
                   admissibility="ADMISSIBLE",
                   negative_class="ENUMERATED_ABSENCE"),
    ]
    result = _run(bundle, as_of=as_of.isoformat())
    assert result.assessment is AssessmentV2.CONFIRMED_ENTITLED


# ------------------------------------------------------------------
# Raices: retirada scoped, freshness gate, reautorizacion
# ------------------------------------------------------------------


@given(
    probe=st.dates(min_value=date(2017, 1, 1), max_value=date(2027, 1, 31)),
)
@settings(derandomize=True, database=None, deadline=None, max_examples=300)
def test_bitemporal_root_state_mmg_shape(probe):
    """Secuencia [2017-05-30,2019-07-12) + [2024-07-12,inf): el estado
    de la raiz en ``probe`` sigue los intervalos, no el status actual."""
    root = "EBA|PSD_PI|CZ_CNB!T2"
    facts = [
        _root_fact(root, [
            {"from": "2017-05-30", "to": "2019-07-12"},
            {"from": "2024-07-12", "to": None},
        ]),
    ]
    # Sin positivos ni negativos: solo el estado de raiz decide.
    result = _run([], facts=facts, as_of=probe.isoformat())
    in_gap = date(2019, 7, 12) <= probe < date(2024, 7, 12)
    if in_gap:
        assert result.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    else:
        assert result.assessment is not AssessmentV2.CONFIRMED_NOT_ENTITLED


@given(
    probe=st.dates(min_value=date(2020, 1, 1), max_value=date(2027, 1, 31)),
    with_provenance=st.booleans(),
)
@settings(derandomize=True, database=None, deadline=None, max_examples=200)
def test_withdrawal_fact_requires_provenance(probe, with_provenance):
    """Un hecho de retirada sin source_assertions no puede cerrar la
    raiz: freshness no comprobable => inutilizable."""
    root = "EBA|PSD_PI|NL_DNB!T3"
    facts = [
        _root_fact(
            root,
            [{"from": "2019-01-01", "to": "2021-06-01"}],
            effective_from="2021-06-01",
            neg_class="EXPLICIT_WITHDRAWAL",
            with_provenance=with_provenance,
        ),
    ]
    result = _run([], facts=facts, as_of=probe.isoformat())
    closed = probe >= date(2021, 6, 1) and with_provenance
    assert (result.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED) == closed


@given(
    probe=st.dates(min_value=date(2020, 1, 1), max_value=date(2027, 1, 31)),
)
@settings(derandomize=True, database=None, deadline=None, max_examples=200)
def test_pi_withdrawal_never_closes_emi_root(probe):
    """Mollie metamorfico: la retirada de una raiz es inerte para la
    hermana — la raiz EMI abierta sustenta ENTITLED en cualquier fecha
    en que su via tenga positivo vigente."""
    bundle = [
        _assertion("emi-pos", LegalEffect.ENTITLED_TO_PROVIDE,
                   "FREEDOM_TO_PROVIDE_SERVICES",
                   "EBA|PSD_EMI|NL_DNB!T4", effective_from="2025-02-03"),
    ]
    facts = [
        _root_fact(
            "EBA|PSD_PI|NL_DNB!T4",
            [{"from": "2019-02-19", "to": "2025-02-03"}],
            effective_from="2025-02-03",
            neg_class="EXPLICIT_WITHDRAWAL",
        ),
        _root_fact(
            "EBA|PSD_EMI|NL_DNB!T4",
            [{"from": "2025-02-03", "to": None}],
        ),
    ]
    result = _run(bundle, facts=facts, as_of=probe.isoformat())
    if probe >= date(2025, 2, 3):
        assert result.assessment is AssessmentV2.CONFIRMED_ENTITLED
    else:
        # La raiz EMI aun no existia: ABSENT nunca sostiene ENTITLED
        # sin evidencia vigente.
        assert result.assessment is not AssessmentV2.CONFIRMED_ENTITLED
