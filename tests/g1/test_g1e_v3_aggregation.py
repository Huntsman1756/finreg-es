"""G1-E (E5) — ASSESSMENT_SEMANTICS_V3: agregacion route-aware.

Binding tests del contrato V3 sobre la materializacion E4.1
(``derived-assertions-g1-e-002.json``). V1/V2 quedan congeladas: esta
suite nunca invoca el run g1e con otra semantica ni muta artefactos
anteriores.

Invariantes fijados:

- interval_end=EXCLUSIVE: la ventana [from,to) cierra EN ``to``.
- root_key: una retirada ROOT_FAMILY cierra solo su raiz (Mollie
  PI cerrada + EMI abierta).
- ROUTE_CAPABILITY: una ausencia enumerada cierra solo su
  (root_key, territorial_basis) — nunca contamina otra via.
- admissibility=BLOCKED: la evidencia negativa bloqueada informa
  (INDETERMINATE), jamas cierra una ruta.
- root state bitemporal: status_intervals [from,to) en el as_of
  solicitado; reported_status actual no sustituye al historico.
- CONFIRMED_NOT_ENTITLED solo cuando toda raiz aplicable esta cerrada
  o todas sus vias legalmente posibles lo estan.
"""
from __future__ import annotations

import copy
import hashlib
import socket
import urllib.request
from datetime import date
from pathlib import Path

from finreg_es.assessment_run import run_assessment
from finreg_es.canonical import strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.derivation import (
    build_g1e_v2_artifact,
    to_entitlement_assertions,
    to_identity_index,
)
from finreg_es.semantics import EntitlementAssertion, assess
from finreg_es.vocab import AssessmentV2, LegalEffect


ROOT = Path(__file__).parents[2]
G1 = ROOT / "fixtures" / "g1"
ARTIFACT_V1_PATH = G1 / "derived-assertions-g1-e-001.json"
ARTIFACT_PATH = G1 / "derived-assertions-g1-e-002.json"
RULESET_PATH = G1 / "derivation-rules-g1-e-002.json"
LEDGER_PATH = G1 / "claim-ledger-g1-e-001.json"
CORPUS_PATH = G1 / "corpus-g1-e-001.json"
MANIFEST_PATH = G1 / "sources" / "manifest-g1-e-run.json"
RUN_PATH = G1 / "runs" / "assessment-run-g1-e-001.json"
CASES_PATH = G1 / "assessment-cases-g1-e.json"
CONTRACTS_DIR = ROOT / "fixtures" / "contracts"


def _read(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access forbidden during G1-E replay")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)


def _artifact() -> dict:
    return _read(ARTIFACT_PATH)


def _contracts() -> dict:
    return {
        c.register_id: c
        for c in (load_contract(p) for p in sorted(CONTRACTS_DIR.glob("*.json")))
    }


def _assess(entity_id, activity, as_of, territorial_basis=None,
            artifact=None):
    artifact = artifact or _artifact()
    return assess(
        entity_id,
        to_identity_index(artifact),
        activity=activity,
        jurisdiction="ES",
        as_of=as_of,
        assertions=to_entitlement_assertions(artifact),
        contracts=_contracts(),
        semantics_version="V3",
        reported_facts=artifact.get("reported_facts", []),
        territorial_basis=territorial_basis,
    )


# ------------------------------------------------------------------
# Cadena congelada: -001 preservado, -002 determinista, run replayable
# ------------------------------------------------------------------


def test_artifact_001_preserved_untouched():
    """La materializacion E4 historica no se muta: el byte debe seguir
    siendo el publicado con el commit E4."""
    raw = ARTIFACT_V1_PATH.read_bytes()
    assert len(raw) > 0
    doc = strict_json_loads(raw.decode("utf-8"))
    # -001 no conoce root_key ni provenance en facts (semantica E4).
    assert all("root_key" not in f for f in doc.get("reported_facts", []))
    assert all("root_key" not in a for a in doc["assertions"])


def test_artifact_002_regenerates_byte_identical():
    rebuilt = build_g1e_v2_artifact(ROOT)
    frozen = _artifact()
    assert rebuilt == frozen


def test_run_001_replays_offline(monkeypatch):
    _no_network(monkeypatch)
    frozen = _read(RUN_PATH)
    meta = frozen["run"]
    replayed = run_assessment(
        ROOT,
        run_id=meta["run_id"],
        g1e=True,
        executed_at=meta["executed_at"],
        code_commit=meta["code_commit"],
    )
    assert replayed["cases"] == frozen["cases"]
    assert replayed["summary"] == frozen["summary"]
    assert replayed["summary"]["mismatches"] == []
    assert replayed["run"]["semantics_version"] == "ASSESSMENT_SEMANTICS_V3"


def test_no_negative_umbrella_payment_services():
    """El umbrella negativo queda fuera de V3: el corpus no prueba el
    universo completo de constituyentes por clase."""
    for a in _artifact()["assertions"]:
        if a["activity"] == "PAYMENT_SERVICES":
            assert a["legal_effect"] != "NOT_ENTITLED"


# ------------------------------------------------------------------
# interval_end=EXCLUSIVE — frontera [from,to)
# ------------------------------------------------------------------


def _assertion(effective_from="2020-01-01", effective_to="2020-07-23",
               interval_end=None, legal_effect=LegalEffect.ENTITLED_TO_PROVIDE):
    return EntitlementAssertion(
        assertion_id="t",
        register_id="R",
        entity_id="E",
        entity_class="PAYMENT_INSTITUTION",
        activity="MONEY_REMITTANCE",
        jurisdiction="ES",
        legal_effect=legal_effect,
        entry_mechanism="AUTHORISATION",
        territorial_basis="DOMESTIC",
        legal_basis="x",
        effective_from=effective_from,
        effective_to=effective_to,
        scope="x",
        source_assertions=(),
        interval_end=interval_end,
    )


def test_exclusive_interval_closes_on_end_date():
    a = _assertion(interval_end="EXCLUSIVE")
    assert a.covers(date(2020, 7, 22))
    assert not a.covers(date(2020, 7, 23))
    assert a.effective_effect_at(date(2020, 7, 23)) == (
        "NOT_ENTITLED", "ENTITLEMENT_EXPIRED")


def test_legacy_interval_remains_inclusive():
    """Artefactos sin interval_end conservan la semantica G0/G1-D:
    la ventana cierra solo cuando effective_to < as_of."""
    a = _assertion(interval_end=None)
    assert a.covers(date(2020, 7, 23))
    assert not a.covers(date(2020, 7, 24))


# ------------------------------------------------------------------
# Bridge E4.1: los campos negativos llegan intactos al dataclass
# ------------------------------------------------------------------


def test_bridge_preserves_e4_fields():
    by_id = {a.assertion_id: a for a in to_entitlement_assertions(_artifact())}
    blocked = [a for a in by_id.values() if a.admissibility == "BLOCKED"]
    assert blocked, "Fintonic debe materializar negativos BLOCKED"
    b = blocked[0]
    assert b.negative_scope == "ROUTE_CAPABILITY"
    assert b.negative_evidence_class == "ENUMERATED_ABSENCE"
    assert b.blocker == "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED"
    assert b.root_key == "EBA|PSD_AISP|ES_BE!6935"
    assert b.source_granularity and b.coverage_policy_id
    enum_abs = next(
        a for a in by_id.values()
        if a.negative_evidence_class == "ENUMERATED_ABSENCE"
        and a.admissibility == "ADMISSIBLE"
    )
    # El codigo raw del servicio ausente se conserva como provenance.
    assert enum_abs.raw_capability_code is not None
    assert enum_abs.effective_from == "2026-09-14"  # EVIDENCE_AS_OF
    exclusive = next(a for a in by_id.values() if a.interval_end == "EXCLUSIVE")
    assert exclusive.effective_to is not None


def test_root_facts_carry_provenance():
    facts = _artifact()["reported_facts"]
    root_facts = [f for f in facts if f.get("root_key")]
    assert root_facts
    for f in root_facts:
        assert f["source_assertions"], f["fact_id"]
        assert f["source_claim_ids"], f["fact_id"]
        assert f["root_home_jurisdiction"]


# ------------------------------------------------------------------
# Root state bitemporal + scoping por raiz
# ------------------------------------------------------------------


def test_mmg_bitemporal_root():
    """La misma raiz: OPEN@2018, CLOSED@2020, OPEN@2026 — y el
    positivo territorial vigente no se retroproyecta a 2018."""
    assert _assess("E3-002", "PAYMENT_CREDIT_TRANSFER_EXECUTION",
                   "2018-06-01").assessment is AssessmentV2.INDETERMINATE
    r2020 = _assess("E3-002", "PAYMENT_CREDIT_TRANSFER_EXECUTION",
                    "2020-01-01")
    assert r2020.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert str(r2020.reason) == "ROOT_FAMILY_WITHDRAWN"
    assert _assess("E3-002", "PAYMENT_CREDIT_TRANSFER_EXECUTION",
                   "2026-09-14").assessment is AssessmentV2.CONFIRMED_ENTITLED


def test_denizen_exclusive_boundary():
    assert _assess("E3-001", "MONEY_REMITTANCE",
                   "2020-07-22").assessment is AssessmentV2.CONFIRMED_ENTITLED
    r = _assess("E3-001", "MONEY_REMITTANCE", "2020-07-23")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert str(r.reason) == "ROOT_FAMILY_WITHDRAWN"


def test_mollie_pi_withdrawal_not_entity_global():
    """La retirada de la raiz PI no cierra la raiz EMI."""
    r = _assess("E3-005", "PAYMENT_CREDIT_TRANSFER_EXECUTION",
                "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED
    assert all(
        a["root_key"] == "EBA|PSD_EMI|NL_DNB!F0038"
        for a in r.assertions
    )
    # Y antes de la transicion: ninguna via observable.
    r2024 = _assess("E3-005", "MONEY_REMITTANCE", "2024-01-01")
    assert r2024.assessment is AssessmentV2.NO_ENTITLEMENT_EVIDENCED


def test_bankinter_baja_then_withdrawal():
    assert _assess("E3-003", "PAYMENT_INSTRUMENT_ISSUING",
                   "2020-06-01").assessment is AssessmentV2.CONFIRMED_ENTITLED
    r = _assess("E3-003", "PAYMENT_INSTRUMENT_ISSUING", "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED


def test_thunes_codes_after_withdrawal_no_positives():
    r = _assess("E3-010", "PAYMENT_CREDIT_TRANSFER_EXECUTION",
                "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert str(r.reason) == "ROOT_FAMILY_WITHDRAWN"


# ------------------------------------------------------------------
# Agregacion por rutas — el par adversarial Wise/Eupago
# ------------------------------------------------------------------


def test_wise_pis_all_routes_closed():
    r = _assess("E3-008", "PAYMENT_INITIATION_SERVICES", "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert str(r.reason) == "ALL_AVAILABLE_ROUTES_CLOSED"


def test_wise_other_activity_not_contaminated():
    assert _assess("E3-008", "MONEY_REMITTANCE",
                   "2026-09-14").assessment is AssessmentV2.CONFIRMED_ENTITLED


def test_eupago_pis_branch_open():
    r = _assess("E3-009", "PAYMENT_INITIATION_SERVICES", "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED
    assert all(
        a["territorial_basis"] == "BRANCH" for a in r.assertions
    )


def test_eupago_explicit_route_queries():
    fps = _assess("E3-009", "PAYMENT_INITIATION_SERVICES", "2026-09-14",
                  territorial_basis="FREEDOM_TO_PROVIDE_SERVICES")
    assert fps.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert str(fps.reason) == "ALL_AVAILABLE_ROUTES_CLOSED"
    branch = _assess("E3-009", "PAYMENT_INITIATION_SERVICES",
                     "2026-09-14", territorial_basis="BRANCH")
    assert branch.assessment is AssessmentV2.CONFIRMED_ENTITLED


def test_wise_explicit_branch_query_closed():
    r = _assess("E3-008", "PAYMENT_INITIATION_SERVICES", "2026-09-14",
                territorial_basis="BRANCH")
    assert r.assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED


def test_cerro_atomic_negative_and_positive_same_route():
    assert _assess("E3-004", "PAYMENT_ACCOUNT_CASH_PLACEMENT",
                   "2026-09-14").assessment is AssessmentV2.CONFIRMED_NOT_ENTITLED
    assert _assess("E3-004", "MONEY_REMITTANCE",
                   "2026-09-14").assessment is AssessmentV2.CONFIRMED_ENTITLED


# ------------------------------------------------------------------
# Evidencia bloqueada y conflicto intra-ruta
# ------------------------------------------------------------------


def test_fintonic_blocked_negative_is_indeterminate():
    r = _assess("E3-006", "PAYMENT_INITIATION_SERVICES", "2026-09-14")
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert str(r.reason) == "NEGATIVE_EVIDENCE_BLOCKED"
    assert all(a["admissibility"] == "BLOCKED" for a in r.assertions)


def test_fintonic_ais_entitled_via_aisp_root():
    r = _assess("E3-006", "ACCOUNT_INFORMATION_SERVICES", "2026-09-14")
    assert r.assessment is AssessmentV2.CONFIRMED_ENTITLED
    assert all(
        a["root_key"] == "EBA|PSD_AISP|ES_BE!6935" for a in r.assertions
    )


def test_same_route_conflict_is_indeterminate():
    """Metamorfico: un NOT_ENTITLED admisible en una ruta con positivo
    vigente produce ROUTE_CONFLICT, nunca una resolucion silenciosa."""
    artifact = copy.deepcopy(_artifact())
    positives = [
        a for a in artifact["assertions"]
        if a["entity_id"] == "E3-009"
        and a["activity"] == "PAYMENT_INITIATION_SERVICES"
        and a["territorial_basis"] == "BRANCH"
    ]
    conflict = copy.deepcopy(positives[0])
    conflict["assertion_id"] = "g1e-asm-MUT"
    conflict["legal_effect"] = "NOT_ENTITLED"
    conflict["negative_scope"] = "ROUTE_CAPABILITY"
    conflict["negative_evidence_class"] = "ENUMERATED_ABSENCE"
    conflict["admissibility"] = "ADMISSIBLE"
    artifact["assertions"].append(conflict)
    r = _assess("E3-009", "PAYMENT_INITIATION_SERVICES", "2026-09-14",
                territorial_basis="BRANCH", artifact=artifact)
    assert r.assessment is AssessmentV2.INDETERMINATE
    assert str(r.reason) == "ROUTE_CONFLICT"
    assert any(d.startswith("route_conflict:") for d in r.diagnostics)


def test_root_fact_without_provenance_cannot_close():
    """Metamorfico: un fact de retirada sin source_assertions no puede
    cerrar la raiz — freshness no comprobable => hecho inutilizable."""
    artifact = copy.deepcopy(_artifact())
    for f in artifact["reported_facts"]:
        if f.get("corpus_id") == "E3-001":
            f.pop("source_assertions", None)
            f.pop("source_claim_ids", None)
    r = _assess("E3-001", "MONEY_REMITTANCE", "2020-07-23",
                artifact=artifact)
    assert r.assessment is not AssessmentV2.CONFIRMED_NOT_ENTITLED
