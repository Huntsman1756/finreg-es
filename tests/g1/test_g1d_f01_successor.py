"""G1-D-F01/F02/F03 — Remediacion sucesora -002.

El commit 9ab782e (ruleset -001) quedo publicado con findings de
auditoria D5 que impiden cerrar G1-D. La cadena -001 permanece
congelada como registro historico; esta suite fija la cadena sucesora:

- F01: el mecanismo home MiCA se prueba por fuente primaria del NCA de
  origen (BaFin Unternehmensdatenbank: Art. 59 Abs. 1a = autorizacion
  art. 63 / Abs. 1b = entidad financiera art. 60; Finanstilsynet:
  remarks expresos). La categoria CNMV LP/sucursal decide la ruta
  territorial, NUNCA el mecanismo. IG Europe y 360 Treasury son
  NOTIFICATION (art. 60), no AUTHORISATION (art. 63).
- F02: aserciones conjuntivas declaran evidence_composition
  ALL_REQUIRED — cada fuente citada exige contrato + scope + freshness
  bajo su propia politica.
- F03: metrica dual — probe_satisfaction (semantica relajada
  post-preregistro) y strict_exact_set (igualdad exacta; G1D-02
  diverge porque Eupago emite BRANCH+FPS).
"""
from __future__ import annotations

import copy
import hashlib
import json
import socket
import urllib.request
from pathlib import Path

from finreg_es.assessment_run import run_assessment
from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.derivation import (
    G1D_DERIVATION_VERSION,
    build_g1d_v2_artifact,
    derive_entitlements,
    to_entitlement_assertions,
    to_identity_index,
)
from finreg_es.contracts import load_contract
from finreg_es.semantics import assess


ROOT = Path(__file__).parents[2]
G1 = ROOT / "fixtures" / "g1"
ARTIFACT_PATH = G1 / "derived-assertions-g1-d-002.json"
RUN_PATH = G1 / "runs" / "assessment-run-g1-d-002.json"
RULESET_PATH = G1 / "derivation-rules-g1-d-002.json"
LEDGER_PATH = G1 / "claim-ledger-g1-d-002.json"
MANIFEST_PATH = G1 / "sources" / "manifest-g1-d-run-002.json"
CORPUS_PATH = G1 / "corpus-g1-d-002.json"
CASES_PATH = G1 / "assessment-cases-g1-d-002.json"


def _read(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access forbidden during G1-D replay")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)


def _artifact() -> dict:
    return _read(ARTIFACT_PATH)


def _entitled(entity_id: str) -> list[dict]:
    return [
        a
        for a in _artifact()["assertions"]
        if a["entity_id"] == entity_id
        and a["legal_effect"] == "ENTITLED_TO_PROVIDE"
    ]


def _derive_v2_mutated(mutator):
    ledger = _read(LEDGER_PATH)
    mutator(ledger["claims"])
    return derive_entitlements(
        ledger,
        _read(RULESET_PATH),
        _read(MANIFEST_PATH),
        _read(CORPUS_PATH),
        derivation_version=G1D_DERIVATION_VERSION,
        id_prefix="tst",
    )


def _entity(result, corpus_id):
    return {
        "assertions": [
            a for a in result["assertions"] if a["entity_id"] == corpus_id
        ],
        "findings": [
            f for f in result["findings"] if f["corpus_id"] == corpus_id
        ],
    }


def _assess_with(assertions_doc, entity_id, activity, as_of):
    """assess() sobre el artefacto -002 (posiblemente mutado)."""
    index = to_identity_index(assertions_doc)
    assertions = to_entitlement_assertions(assertions_doc)
    contracts = {
        c.register_id: c
        for c in (
            load_contract(p)
            for p in sorted((ROOT / "fixtures/contracts").glob("*.json"))
        )
    }
    return assess(
        entity_id,
        index,
        activity=activity,
        jurisdiction="ES",
        as_of=as_of,
        assertions=assertions,
        contracts=contracts,
        semantics_version="V2",
        reported_facts=assertions_doc.get("reported_facts", []),
    )


# ------------------------------------------------------------------
# Replay / integridad de la cadena sucesora
# ------------------------------------------------------------------


def test_artifact_002_replays_byte_identical():
    rebuilt = canonical_json(build_g1d_v2_artifact(ROOT)) + "\n"
    assert rebuilt == ARTIFACT_PATH.read_text(encoding="utf-8")
    declared = _read(ARTIFACT_PATH)["artifact"]
    assert declared["derivation_ruleset_sha256"] == hashlib.sha256(
        RULESET_PATH.read_bytes()
    ).hexdigest()
    assert declared["claims_ledger_sha256"] == hashlib.sha256(
        LEDGER_PATH.read_bytes()
    ).hexdigest()


def test_ledger_corpus_manifest_002_build_deterministic():
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import build_g1d_ledger as builder

    assert canonical_json(builder.build_ledger_v2()) + "\n" == (
        LEDGER_PATH.read_text(encoding="utf-8")
    )
    assert canonical_json(builder.build_corpus_v2()) + "\n" == (
        CORPUS_PATH.read_text(encoding="utf-8")
    )
    assert canonical_json(builder.build_manifest_v2()) + "\n" == (
        MANIFEST_PATH.read_text(encoding="utf-8")
    )


def test_historical_chain_001_untouched():
    """Los artefactos -001 siguen congelados: el ruleset historico sigue
    emitiendo AUTHORISATION para las rutas MiCA (la expectativa
    preregistrada falsada se conserva como historia)."""
    v1 = _read(G1 / "derivation-rules-g1-d.json")
    mica = {
        r["rule_id"]: r
        for r in v1["ruleset"]["rules"]
        if r["rule_id"] in ("mica-lp-es-entitled", "mica-branch-es-entitled")
    }
    for rule in mica.values():
        assert rule["emit_per"]["emit"]["entry_mechanism"] == "AUTHORISATION"
        assert "art. 63" in rule["emit_per"]["emit"]["legal_basis"]


def test_run_002_replays_offline(monkeypatch):
    _no_network(monkeypatch)
    frozen = _read(RUN_PATH)
    meta = frozen["run"]
    replayed = run_assessment(
        ROOT,
        run_id=meta["run_id"],
        g1d2=True,
        executed_at=meta["executed_at"],
        code_commit=meta["code_commit"],
    )
    assert replayed["cases"] == frozen["cases"]
    assert replayed["summary"] == frozen["summary"]


# ------------------------------------------------------------------
# F01 — mecanismo home MiCA probado por fuente primaria
# ------------------------------------------------------------------


def test_ig_europe_is_notification_branch_art60():
    """G1D-005: Finanstilsynet 199254 declara art. 60(3); BaFin 148759
    cita Art. 59 Abs. 1b -> NOTIFICATION + BRANCH, nunca AUTHORISATION."""
    for a in _entitled("G1D-005"):
        assert a["entry_mechanism"] == "NOTIFICATION"
        assert a["territorial_basis"] == "BRANCH"
        assert "art. 60(3)" in a["legal_basis"]
        assert "art. 59(7)" in a["legal_basis"]
        assert "art. 65" in a["legal_basis"]
        assert "art. 63" not in a["legal_basis"]
        assert a["effective_from"] == "2025-12-10"


def test_360t_is_notification_lp_art60():
    """G1D-004: BaFin 118252 cita el permiso cripto como Art. 59 Abs.
    1b MiCA-R (via art. 60, entidad financiera) -> NOTIFICATION + FPS.
    El registro CNMV LP por si solo nunca prueba art. 63."""
    for a in _entitled("G1D-004"):
        assert a["entry_mechanism"] == "NOTIFICATION"
        assert a["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"
        assert "art. 60(3)" in a["legal_basis"]
        assert "art. 65" in a["legal_basis"]
        assert a["effective_from"] == "2025-05-03"


def test_mica_assertions_carry_home_mechanism_provenance():
    """La SourceAssertion[] territorial incluye ESMA + CNMV + la fuente
    primaria del mecanismo (BaFin/Finanstilsynet)."""
    for entity_id in ("G1D-004", "G1D-005"):
        for a in _entitled(entity_id):
            registers = {s["register_id"] for s in a["source_assertions"]}
            assert {
                "ESMA_MICA_REGISTER",
                "CNMV_PSC_REGISTER",
                "BAFIN_UNTERNEHMENSDATENBANK",
            } <= registers


def test_all_required_declared_on_conjunctive_assertions():
    """F02: las aserciones conjuntivas declaran ALL_REQUIRED."""
    for entity_id in ("G1D-002", "G1D-004", "G1D-005", "G1D-007"):
        for a in _entitled(entity_id):
            if a["territorial_basis"] == "BRANCH" or a[
                "rule_id"
            ].startswith("mica"):
                assert a["evidence_composition"] == "ALL_REQUIRED"


def test_unproven_home_mechanism_abstains():
    """Sin fuente primaria del NCA home, la categoria CNMV LP no
    produce positivo: HOME_MECHANISM_UNPROVEN + 0 asercion
    (metamorfico: claims BaFin/FT de 360T eliminados)."""

    def drop_home_sources(claims):
        claims[:] = [
            c
            for c in claims
            if not (
                c["corpus_id"] == "G1D-004"
                and c["source"]
                in ("BAFIN_UNTERNEHMENSDATENBANK", "FINANSTILSYNET_REGISTRY")
            )
        ]

    result = _derive_v2_mutated(drop_home_sources)
    entity = _entity(result, "G1D-004")
    assert not any(
        a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in entity["assertions"]
    )
    assert any(
        f["classification"] == "HOME_MECHANISM_UNPROVEN"
        for f in entity["findings"]
    )


def test_conflicting_home_mechanism_abstains():
    """Senales home conflictivas (BaFin 1a vs Finanstilsynet 60(3)):
    HOME_MECHANISM_CONFLICT + 0 positivo — nunca resolucion silenciosa
    (metamorfico: la ruta BaFin de IG Europe muta a Abs. 1a)."""

    def force_conflict(claims):
        for c in claims:
            if (
                c["corpus_id"] == "G1D-005"
                and c["source"] == "BAFIN_UNTERNEHMENSDATENBANK"
                and c["field"] == "mica_home_route"
            ):
                c["normalized_value"] = "ART_59_1A"
                c["raw_value"] = "ART_59_1A"

    result = _derive_v2_mutated(force_conflict)
    entity = _entity(result, "G1D-005")
    assert not any(
        a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in entity["assertions"]
    )
    assert any(
        f["classification"] == "HOME_MECHANISM_CONFLICT"
        for f in entity["findings"]
    )


# ------------------------------------------------------------------
# F02 — admisibilidad conjuntiva por fuente requerida
# ------------------------------------------------------------------


def _stale_source(doc, entity_id, register_id, stale_as_of="2020-01-01"):
    """Envejece la evidencia de UNA fuente en las aserciones de una
    entidad (source_as_of viejo = stale bajo su contrato)."""
    doc = copy.deepcopy(doc)
    for a in doc["assertions"]:
        if a["entity_id"] != entity_id:
            continue
        for s in a["source_assertions"]:
            if s["register_id"] == register_id:
                s["source_as_of"] = stale_as_of
                s["retrieved_at"] = stale_as_of
    return doc


def test_stale_cnmv_blocks_mica_assertion_despite_fresh_esma():
    """CNMV stale + ESMA fresh: sin ALL_REQUIRED la frescura de ESMA
    enmascaraba la de CNMV (latest_freshness = max). Con composicion
    conjuntiva la asercion territorial se bloquea."""
    doc = _stale_source(_artifact(), "G1D-005", "CNMV_PSC_REGISTER")
    result = _assess_with(
        doc, "G1D-005", "CRYPTO_CUSTODY_ADMINISTRATION", "2026-09-15"
    )
    assert not any(
        a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in result.assertions
    )
    assert any(
        "stale_required_source" in d and "CNMV_PSC_REGISTER" in d
        for d in result.diagnostics
    )


def test_stale_bde_blocks_branch_assertion_despite_fresh_eba():
    """BdE stale + EBA fresh: la sucursal PSD2 pierde su trigger
    territorial; el positivo BRANCH no se emite (FPS por EBA, si lo
    hay, no rescata la ruta de establecimiento)."""
    doc = _stale_source(_artifact(), "G1D-002", "BDE_REGISTRO_SERVICIOS_PAGO")
    result = _assess_with(doc, "G1D-002", "PAYMENT_SERVICES", "2026-09-15")
    assert not any(
        a["territorial_basis"] == "BRANCH"
        for a in result.assertions
    )
    assert any(
        "stale_required_source" in d and "BDE_REGISTRO_SERVICIOS_PAGO" in d
        for d in result.diagnostics
    )


# ------------------------------------------------------------------
# F03 — metrica dual del run sucesor
# ------------------------------------------------------------------


def test_run_002_publishes_dual_metrics():
    """probe_satisfaction = 8/8 (semantica historica del run); la
    lectura estricta de conjuntos diverge en G1D-02 (Eupago emite
    BRANCH+FPS frente a BRANCH preregistrado)."""
    run = _read(RUN_PATH)
    metrics = run["summary"]["match_metrics"]
    assert metrics["probe_satisfaction"]["matches"] == 8
    assert metrics["probe_satisfaction"]["mismatches"] == []
    assert metrics["strict_exact_set"]["divergences"] == ["G1D-02"]
    case = next(c for c in run["cases"] if c["case_id"] == "G1D-02")
    assert case["match"] is True
    assert case["strict_exact_set_match"] is False
    assert case["strict_divergences"] == ["territorial_basis_set"]
