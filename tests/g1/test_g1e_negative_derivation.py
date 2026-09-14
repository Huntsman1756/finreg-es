"""G1-E (E4) — materializacion derivacional de evidencia negativa.

Tests binding del artefacto ``derived-assertions-g1-e-001.json``
(ledger/corpus de las 10 anclas E3-003 + ruleset V5). E4 materializa
hechos y aserciones; los veredictos globales pertenecen a E5 y no se
evaluan aqui.

Invariantes verificados por ancla:

- DENIZEN (E3-001): retirada de raiz EXPLICIT_WITHDRAWAL con
  effective_from=2020-07-23 e interval_end=EXCLUSIVE; intervalo
  domestico cerrado [2019-03-15, 2020-07-23); dos fuentes concordantes.
- MMG (E3-002): raiz ACTIVA; positivos FPS con
  effective_from=EVIDENCE_AS_OF — el vector actual nunca se
  retroproyecta al intervalo historico de la raiz.
- CERRO CATEDRAL (E3-004): positivo MONEY_REMITTANCE + negativo
  atomico PAYMENT_ACCOUNT_CASH_PLACEMENT en la misma via DOMESTIC.
- Mollie (E3-005): raiz PI cerrada + raiz EMI abierta — la retirada de
  una raiz no es entity-global.
- Fintonic (E3-006): candidatos negativos BLOQUEADOS por
  TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED + finding; cero
  NOT_ENTITLED admisibles.
- Wise (E3-008): negativos PIS en rutas FPS y BRANCH.
- Eupago (E3-009): negativo PIS en FPS + positivo PIS en BRANCH.
- THUNES (E3-010): raiz retirada; Services{ES} posterior no genera
  positivos.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
ARTIFACT = json.loads(
    (ROOT / "fixtures/g1/derived-assertions-g1-e-001.json").read_text(
        encoding="utf-8"
    )
)
EVIDENCE_AS_OF = "2026-09-14"


def _assertions(entity_id: str, **filters) -> list[dict]:
    out = []
    for a in ARTIFACT["assertions"]:
        if a["entity_id"] != entity_id:
            continue
        if all(a.get(k) == v for k, v in filters.items()):
            out.append(a)
    return out


def _facts(entity_id: str, **filters) -> list[dict]:
    return [
        f
        for f in ARTIFACT.get("reported_facts", [])
        if f["corpus_id"] == entity_id
        and all(f.get(k) == v for k, v in filters.items())
    ]


def _findings(entity_id: str, classification: str) -> list[dict]:
    return [
        f
        for f in ARTIFACT["findings"]
        if f["corpus_id"] == entity_id and f["classification"] == classification
    ]


def _route_negatives(entity_id: str, activity: str) -> list[dict]:
    return _assertions(
        entity_id,
        activity=activity,
        legal_effect="NOT_ENTITLED",
        negative_evidence_class="ENUMERATED_ABSENCE",
    )


# ---------------------------------------------------------------- DENIZEN


def test_denizen_root_withdrawal_exclusive_interval():
    """E3-001: retirada dual-source el mismo dia, scope ROOT_FAMILY."""
    facts = _facts(
        "E3-001",
        reported_status="WITHDRAWN",
        negative_evidence_class="EXPLICIT_WITHDRAWAL",
        negative_scope="ROOT_FAMILY",
    )
    assert len(facts) == 2  # EBA ENT_AUT + BdE renuncia
    for fact in facts:
        assert fact["effective_from"] == "2020-07-23"
        assert fact["interval_end"] == "EXCLUSIVE"
        # la retirada de raiz nunca inventa una base territorial
        assert "territorial_basis" not in fact


def test_denizen_domestic_closed_positive_interval():
    """El intervalo domestico [aut, retirada) se materializa cerrado:
    la ruta esta abierta el 22/07 y cerrada EN el 23/07."""
    positives = _assertions(
        "E3-001",
        activity="MONEY_REMITTANCE",
        legal_effect="ENTITLED_TO_PROVIDE",
        territorial_basis="DOMESTIC",
    )
    assert positives
    eba = [p for p in positives if p["rule_id"].startswith("eba-")]
    assert eba[0]["effective_from"] == "2019-03-15"
    assert eba[0]["effective_to"] == "2020-07-23"
    assert eba[0]["interval_end"] == "EXCLUSIVE"
    bde = [p for p in positives if p["rule_id"].startswith("bde-")]
    assert bde[0]["effective_from"] == "2011-06-09"
    assert bde[0]["effective_to"] == "2020-07-23"


def test_denizen_no_route_capability_negatives():
    """Una retirada de raiz no produce negativos ROUTE_CAPABILITY de
    rutas nunca observadas."""
    assert not _assertions(
        "E3-001", legal_effect="NOT_ENTITLED", negative_scope="ROUTE_CAPABILITY"
    )


# --------------------------------------------------------------------- MMG


def test_mmg_no_territorial_retroprojection():
    """E3-002: el Services{ES} actual no demuestra la ruta en 2018 —
    todo positivo FPS nace en EVIDENCE_AS_OF."""
    positives = _assertions(
        "E3-002",
        legal_effect="ENTITLED_TO_PROVIDE",
        territorial_basis="FREEDOM_TO_PROVIDE_SERVICES",
    )
    assert positives
    for p in positives:
        assert p["effective_from"] == EVIDENCE_AS_OF
        assert p["effective_to"] is None


def test_mmg_root_history_preserved_in_fact():
    """La secuencia ENT_AUT [2017,2019,2024] queda en el hecho de raiz
    con interval_end=EXCLUSIVE — bitemporalidad para E5."""
    facts = _facts("E3-002", reported_status="ACTIVE")
    assert len(facts) == 1
    intervals = facts[0]["status_intervals"]
    assert intervals == [
        {"from": "2017-05-30", "to": "2019-07-12"},
        {"from": "2024-07-12", "to": None},
    ]
    assert facts[0]["interval_end"] == "EXCLUSIVE"


# ---------------------------------------------------------- CERRO CATEDRAL


def test_cerro_catedral_atomic_contrast():
    """E3-004: positivo y negativo atomicos en la misma via DOMESTIC."""
    positives = _assertions(
        "E3-004",
        activity="MONEY_REMITTANCE",
        legal_effect="ENTITLED_TO_PROVIDE",
    )
    assert len(positives) == 1
    negatives = _route_negatives("E3-004", "PAYMENT_ACCOUNT_CASH_PLACEMENT")
    assert len(negatives) == 1
    neg = negatives[0]
    assert neg["territorial_basis"] == "DOMESTIC"
    assert neg["negative_scope"] == "ROUTE_CAPABILITY"
    assert neg["raw_capability_code"] == "1"
    assert neg["source_granularity"] == "ATOMIC"
    assert neg["effective_from"] == EVIDENCE_AS_OF
    assert neg["coverage_policy_id"] == "bde-domestic-pi-activities"


# ------------------------------------------------------------------ MOLLIE


def test_mollie_root_withdrawal_not_entity_global():
    """E3-005: PI cerrada (EXPLICIT_WITHDRAWAL) + EMI abierta en la
    misma fecha — la retirada de una raiz no cierra otra raiz."""
    closed = _facts(
        "E3-005",
        reported_status="WITHDRAWN",
        negative_evidence_class="EXPLICIT_WITHDRAWAL",
    )
    assert len(closed) == 1
    assert closed[0]["effective_from"] == "2025-02-03"
    assert closed[0]["negative_scope"] == "ROOT_FAMILY"
    emi_pos = _assertions(
        "E3-005",
        activity="E_MONEY_ISSUANCE",
        legal_effect="ENTITLED_TO_PROVIDE",
    )
    assert len(emi_pos) == 1
    assert emi_pos[0]["effective_from"] == EVIDENCE_AS_OF


# ---------------------------------------------------------------- FINTONIC


def test_fintonic_blocked_not_admissible():
    """E3-006: la continuidad del sucesor tras transformacion no esta
    demostrada — candidatos BLOQUEADOS + finding, 0 admisibles."""
    admissible_neg = [
        a
        for a in _assertions("E3-006", legal_effect="NOT_ENTITLED")
        if a.get("admissibility") == "ADMISSIBLE"
    ]
    assert admissible_neg == []
    blocked = _route_negatives("E3-006", "PAYMENT_INITIATION_SERVICES")
    assert len(blocked) == 1
    assert blocked[0]["admissibility"] == "BLOCKED"
    assert (
        blocked[0]["blocker"] == "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED"
    )
    assert blocked[0]["territorial_basis"] == "DOMESTIC"
    assert blocked[0]["entry_mechanism"] == "REGISTRATION"
    assert _findings("E3-006", "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED")
    baja = _facts(
        "E3-006",
        reported_status="WITHDRAWN",
        negative_evidence_class="ENTITY_BAJA",
    )
    assert len(baja) == 1
    assert baja[0]["effective_from"] == "2024-11-26"


def test_fintonic_aisp_ais_positive_stands():
    """El positivo AIS del sucesor AISP sigue vigente — el bloqueo es
    de la continuidad PIS, no de toda la entidad."""
    ais = _assertions(
        "E3-006",
        activity="ACCOUNT_INFORMATION_SERVICES",
        legal_effect="ENTITLED_TO_PROVIDE",
        entry_mechanism="REGISTRATION",
    )
    assert any(p["effective_to"] is None for p in ais)


# --------------------------------------------------------------------- WISE


def test_wise_pis_negative_on_two_routes():
    """E3-008: PIS ausente en FPS (parent) y en BRANCH (PSD_BR + BdE)."""
    negs = _route_negatives("E3-008", "PAYMENT_INITIATION_SERVICES")
    bases = {n["territorial_basis"] for n in negs}
    assert "FREEDOM_TO_PROVIDE_SERVICES" in bases
    assert "BRANCH" in bases
    assert len(negs) >= 2
    for n in negs:
        assert n["negative_scope"] == "ROUTE_CAPABILITY"
        assert n["admissibility"] == "ADMISSIBLE"
        assert n["effective_from"] == EVIDENCE_AS_OF


# ------------------------------------------------------------------- EUPAGO


def test_eupago_fps_negative_branch_positive():
    """E3-009: contraste con Wise — PIS cerrado en FPS, abierto en
    BRANCH (PSD_BR + sucursal BdE 6938 codigo 7)."""
    negs = _route_negatives("E3-009", "PAYMENT_INITIATION_SERVICES")
    assert {n["territorial_basis"] for n in negs} == {
        "FREEDOM_TO_PROVIDE_SERVICES"
    }
    pos = _assertions(
        "E3-009",
        activity="PAYMENT_INITIATION_SERVICES",
        legal_effect="ENTITLED_TO_PROVIDE",
    )
    assert pos
    assert all(p["territorial_basis"] == "BRANCH" for p in pos)
    raw_codes = {p["raw_capability_code"] for p in pos}
    assert raw_codes == {"PS_070", "7"}  # vector EBA + codigo BdE


# ------------------------------------------------------------------- THUNES


def test_thunes_withdrawn_no_positive_from_services():
    """E3-010: la raiz retirada no produce positivos aunque el
    snapshot aun declare Services{ES}."""
    assert _assertions("E3-010", legal_effect="ENTITLED_TO_PROVIDE") == []
    facts = _facts(
        "E3-010",
        reported_status="WITHDRAWN",
        negative_evidence_class="EXPLICIT_WITHDRAWAL",
        negative_scope="ROOT_FAMILY",
    )
    assert len(facts) == 1
    assert facts[0]["effective_from"] == "2026-08-27"


# ------------------------------------------------------------ BANKINTER


def test_bankinter_transformation_not_withdrawal():
    """E3-003: baja por transformacion = ENTITY_BAJA, nunca
    EXPLICIT_WITHDRAWAL — son clases distintas."""
    baja = _facts(
        "E3-003",
        reported_status="WITHDRAWN",
        negative_evidence_class="ENTITY_BAJA",
    )
    assert len(baja) == 1
    assert baja[0]["effective_from"] == "2019-02-22"
    withdrawal = _facts(
        "E3-003", negative_evidence_class="EXPLICIT_WITHDRAWAL"
    )
    assert len(withdrawal) == 1
    assert withdrawal[0]["effective_from"] == "2026-07-01"
    # en el as_of entre ambos, el intervalo EBA sigue abierto
    domestic = _assertions(
        "E3-003",
        legal_effect="ENTITLED_TO_PROVIDE",
        territorial_basis="DOMESTIC",
    )
    assert any(
        p["effective_from"] == "2019-03-15"
        and p["effective_to"] == "2026-07-01"
        and p.get("interval_end") == "EXCLUSIVE"
        for p in domestic
    )


# --------------------------------------------------------------- SIBS


def test_sibs_lps_absent_bde_no_negative():
    """E3-007: la ausencia de SIBS en los workbooks BdE no genera
    ningun hecho negativo BdE (LPS fuera del universo)."""
    bde_neg = [
        a
        for a in _assertions("E3-007", legal_effect="NOT_ENTITLED")
        if a["register_id"].startswith("BDE")
    ]
    assert bde_neg == []
    # el vector EBA si produce ausencias scoped de la ruta FPS
    fps_neg = _route_negatives("E3-007", "PAYMENT_INITIATION_SERVICES")
    assert len(fps_neg) == 1
    assert fps_neg[0]["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"


# ------------------------------------------------------- contrato global


def test_negative_contract_fields_complete():
    """Todo NOT_ENTITLED lleva el contrato E4 completo."""
    for a in ARTIFACT["assertions"]:
        if a["legal_effect"] != "NOT_ENTITLED":
            continue
        for field in (
            "negative_scope",
            "negative_evidence_class",
            "raw_capability_code",
            "source_granularity",
            "coverage_policy_id",
            "admissibility",
        ):
            assert a.get(field) is not None, (a["assertion_id"], field)
        assert a["negative_scope"] == "ROUTE_CAPABILITY"
        assert a["negative_evidence_class"] == "ENUMERATED_ABSENCE"
        assert a["source_granularity"] == "ATOMIC"
        assert a["entry_mechanism"] and a["territorial_basis"]


def test_root_facts_never_carry_territorial_basis():
    """Los hechos ROOT_FAMILY no inventan una base territorial."""
    for f in ARTIFACT.get("reported_facts", []):
        if f.get("negative_scope") == "ROOT_FAMILY":
            assert "territorial_basis" not in f
            assert f["negative_evidence_class"] in (
                "EXPLICIT_WITHDRAWAL",
                "ENTITY_BAJA",
            )


def test_no_global_assessment_materialized():
    """E4 no decide veredictos globales: el artefacto queda NOT_RUN y
    ninguna asercion lleva assessment."""
    assert ARTIFACT["artifact"]["assessment"] == "NOT_RUN"
    for a in ARTIFACT["assertions"]:
        assert "assessment" not in a


def test_bde_legacy_codes_never_decomposed():
    """Un codigo compuesto legacy nunca se descompone: ningun hecho
    emite raw_capability_code fuera de los mapas atomicos, y el
    universo de ausencias excluye codigos legacy."""
    atomic = {
        "PS_010", "PS_020", "PS_03A", "PS_03B", "PS_03C",
        "PS_04A", "PS_04B", "PS_04C", "PS_05A", "PS_05B",
        "PS_060", "PS_070", "PS_080", "ES_010",
        "1", "2", "3.A", "3.B", "3.C", "4.A", "4.B", "4.C",
        "5.A", "5.B", "6", "7", "8", "A", "B", "C",
    }
    for a in ARTIFACT["assertions"]:
        code = a.get("raw_capability_code")
        if code is not None:
            assert code in atomic, (a["assertion_id"], code)


def test_artifact_is_deterministic():
    """La regeneracion byte-identica del artefacto (OpenLineage)."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        subprocess.run(
            [
                "python", "-m", "finreg_es.derivation",
                "--g1e", "--out", str(out),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        assert out.read_bytes() == (
            ROOT / "fixtures/g1/derived-assertions-g1-e-001.json"
        ).read_bytes()
    finally:
        out.unlink(missing_ok=True)
