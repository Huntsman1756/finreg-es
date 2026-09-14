"""G1-C — Replay determinista del artefacto MiCA y del run C6.

Fija la cadena congelada corpus -> ledger -> ruleset -> derivadas ->
assessment para los dos mecanismos MiCA (art.63 AUTHORISATION /
art.60 NOTIFICATION). El replay byte-identico del artefacto es lo que
detecta un input declarado que no coincide con el fichero vivo
(G1-C-F01: sha de ruleset stale en la primera congelacion).
"""
from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from pathlib import Path

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.derivation import build_g1c_artifact, derive_entitlements
from finreg_es.assessment_run import run_assessment


ROOT = Path(__file__).parents[2]
ARTIFACT_PATH = ROOT / "fixtures" / "g1" / "derived-assertions-g1-c-001.json"
RUN_PATH = ROOT / "fixtures" / "g1" / "runs" / "assessment-run-g1-c-003.json"
RULESET_PATH = ROOT / "fixtures" / "g1" / "derivation-rules.json"
LEDGER_PATH = ROOT / "fixtures" / "g1" / "claim-ledger-g1-c-001.json"
MANIFEST_PATH = ROOT / "fixtures" / "g1" / "sources" / "manifest-g1-c-run.json"
CORPUS_PATH = ROOT / "fixtures" / "g0.5" / "corpus" / "entities.json"


def _read(path: Path) -> dict:
    return strict_json_loads(path.read_text(encoding="utf-8"))


def _no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("network access forbidden during G1-C replay")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked)


def test_artifact_replays_byte_identical_from_committed_inputs():
    """Las derivadas G1-C se regeneran solo con inputs commiteados: el
    sha declarado de cada input congelado es el del fichero vivo."""
    rebuilt = canonical_json(build_g1c_artifact(ROOT)) + "\n"
    assert rebuilt == ARTIFACT_PATH.read_text(encoding="utf-8")
    declared = _read(ARTIFACT_PATH)["artifact"]
    assert declared["derivation_ruleset_sha256"] == hashlib.sha256(
        RULESET_PATH.read_bytes()
    ).hexdigest()


def test_run_002_replays_offline(monkeypatch):
    """El run de verificacion -002 (post-remediacion G1-C-F01) se
    reproduce sobre artefactos locales con integridad de inputs."""
    _no_network(monkeypatch)
    frozen = _read(RUN_PATH)
    meta = frozen["run"]
    replayed = run_assessment(
        ROOT,
        run_id=meta["run_id"],
        g1c=True,
        executed_at=meta["executed_at"],
        code_commit=meta["code_commit"],
    )
    assert replayed["cases"] == frozen["cases"]
    assert replayed["summary"] == frozen["summary"]
    meta_keys = {k for k in meta if k not in {"code_sha", "code_files"}}
    assert {k: replayed["run"][k] for k in meta_keys} == {
        k: meta[k] for k in meta_keys
    }
    assert all(meta["frozen_input_integrity"].values())

    recorded = frozen.pop("result_sha")
    recomputed = hashlib.sha256(
        canonical_json(frozen).encode("utf-8")
    ).hexdigest()
    assert recomputed == recorded


def test_mechanism_anchored_to_cnmv_category():
    """0 mecanismos inferidos del CSV ESMA: toda asercion MiCA cita el
    claim CNMV de categoria como evidencia corroborante, y solo las dos
    rutas domesticas probadas emiten (ruleset < ley)."""
    artifact = _read(ARTIFACT_PATH)
    mica = [a for a in artifact["assertions"] if a["rule_id"].startswith("mica-")]
    assert mica
    assert {a["rule_id"] for a in mica} == {
        "mica-art63-domestic-psc",
        "mica-art60-domestic-credit-institution",
    }
    for assertion in mica:
        assert any(
            s["register_id"] == "CNMV_PSC_REGISTER"
            for s in assertion["source_assertions"]
        ), assertion["assertion_id"]
        assert assertion["territorial_basis"] == "DOMESTIC"
        assert assertion["jurisdiction"] == "ES"


def test_no_positive_assertion_without_explicit_service():
    """La granularidad es (entity, crypto_service): ninguna asercion
    MiCA existe fuera de las letras a-j listadas en ac_serviceCode, y
    ninguna entidad recibe servicios por pertenencia a la clase."""
    artifact = _read(ARTIFACT_PATH)
    crypto_activities = {
        "CRYPTO_CUSTODY_ADMINISTRATION", "CRYPTO_TRADING_PLATFORM",
        "CRYPTO_EXCHANGE_FUNDS", "CRYPTO_EXCHANGE_CRYPTO",
        "CRYPTO_ORDER_EXECUTION", "CRYPTO_PLACING",
        "CRYPTO_ORDER_RECEPTION_TRANSMISSION", "CRYPTO_ADVICE",
        "CRYPTO_PORTFOLIO_MANAGEMENT", "CRYPTO_TRANSFER",
    }
    mica = [a for a in artifact["assertions"] if a["rule_id"].startswith("mica-")]
    assert all(a["activity"] in crypto_activities for a in mica)
    # BBVA lista a/e/j: i (portfolio management) nunca aparece.
    assert not any(
        a["entity_id"] == "G05-001" and a["activity"] == "CRYPTO_PORTFOLIO_MANAGEMENT"
        for a in artifact["assertions"]
    )


def test_territorial_rows_deferred_not_promoted():
    """ac_serviceCode_cou y las categorias LP/sucursal producen
    reported_facts TERRITORIAL_ENTITLEMENT_DEFERRED (G1-D), nunca una
    asercion territorial positiva."""
    artifact = _read(ARTIFACT_PATH)
    facts = artifact["reported_facts"]
    deferred = [f for f in facts if f["reported_status"] == "TERRITORIAL_ENTITLEMENT_DEFERRED"]
    assert deferred
    assert all(f["rule_id"] == "mica-passport-territorial-deferred" for f in deferred)
    assert not any(
        a["rule_id"].startswith("mica-")
        and a["territorial_basis"] != "DOMESTIC"
        for a in artifact["assertions"]
    )
    # Ninguna regla emite efecto negativo (politica congelada G0/G1).
    assert not any(
        a["legal_effect"] == "NOT_ENTITLED" for a in artifact["assertions"]
    )


def test_multi_role_entity_no_conflict():
    """PROSEGUR (G05-012): PI RDL 19/2018 via EBA + CASP MiCA art.63
    coexisten sobre el mismo entity_id — COMPATIBLE_MULTI_ROLE, 0
    findings de conflicto."""
    artifact = _read(ARTIFACT_PATH)
    prosegur = [a for a in artifact["assertions"] if a["entity_id"] == "G05-012"]
    activities = {a["activity"] for a in prosegur}
    assert "PAYMENT_SERVICES" in activities  # pata EBA PSD2
    assert activities & {
        "CRYPTO_CUSTODY_ADMINISTRATION", "CRYPTO_TRADING_PLATFORM",
        "CRYPTO_EXCHANGE_FUNDS", "CRYPTO_EXCHANGE_CRYPTO",
        "CRYPTO_ORDER_EXECUTION", "CRYPTO_PLACING",
        "CRYPTO_ORDER_RECEPTION_TRANSMISSION", "CRYPTO_ADVICE",
        "CRYPTO_PORTFOLIO_MANAGEMENT", "CRYPTO_TRANSFER",
    }
    assert not any(
        f["corpus_id"] == "G05-012" and "CONFLICT" in f["classification"]
        for f in artifact["findings"]
    )


def test_v2_convergence_two_legal_routes():
    """art.63 AUTHORISATION y art.60 NOTIFICATION convergen a
    CONFIRMED_ENTITLED bajo ASSESSMENT_SEMANTICS_V2 — sin recaer en la
    taxonomia V1 de CONFIRMED_AUTHORISED."""
    run = _read(RUN_PATH)
    cases = {c["case_id"]: c for c in run["cases"]}
    assert run["run"]["semantics_version"] == "ASSESSMENT_SEMANTICS_V2"
    assert run["summary"]["mismatches"] == []
    assert run["summary"]["reason_mismatches"] == []
    assert cases["G1C-01"]["assessment"] == "CONFIRMED_ENTITLED"
    assert cases["G1C-01"]["entry_mechanisms"] == ["AUTHORISATION"]
    assert cases["G1C-02"]["assessment"] == "CONFIRMED_ENTITLED"
    assert cases["G1C-02"]["entry_mechanisms"] == ["NOTIFICATION"]
    # Pasaporte MiCA: hecho reportado explica el INDETERMINATE, no crea
    # entitlement ni negativo.
    assert cases["G1C-06"]["assessment"] == "INDETERMINATE"
    assert cases["G1C-06"]["reason"] == "TERRITORIAL_ENTITLEMENT_UNRESOLVED"
    assert cases["G1C-06"]["matched_reported_fact_ids"]
    # Multi-role PROSEGUR: ambas patas CONFIRMED_ENTITLED, 0 conflicto.
    assert cases["G1C-07"]["assessment"] == "CONFIRMED_ENTITLED"
    assert cases["G1C-08"]["assessment"] == "CONFIRMED_ENTITLED"


# ------------------------------------------------------------------
# Hardening metamorfico: input requerido ausente => finding clasificado
# (G1-C: la abstencion debe ser auditable, nunca silenciosa).
# ------------------------------------------------------------------


def _derive_with_mutation(corpus_id: str, source: str, field: str, value):
    """Copia en memoria del ledger congelado con un claim mutado."""
    ledger = _read(LEDGER_PATH)
    ruleset = _read(RULESET_PATH)
    manifest = _read(MANIFEST_PATH)
    corpus = _read(CORPUS_PATH)
    for claim in ledger["claims"]:
        if (
            claim["corpus_id"] == corpus_id
            and claim["source"] == source
            and claim["field"] == field
        ):
            claim["normalized_value"] = value
            break
    else:
        raise KeyError((corpus_id, source, field))
    return derive_entitlements(
        ledger, ruleset, manifest, corpus,
        derivation_version="FINREG_G1_DERIVATION_V1", id_prefix="tst",
    )


def _entity(result, corpus_id):
    return {
        "assertions": [
            a for a in result["assertions"] if a["entity_id"] == corpus_id
        ],
        "findings": [
            f for f in result["findings"] if f["corpus_id"] == corpus_id
        ],
        "facts": [
            f for f in result.get("reported_facts", [])
            if f["corpus_id"] == corpus_id
        ],
    }


def test_missing_cnmv_service_date_is_audited_not_silent():
    """PSC domestico (BIT2ME) con services_from ausente: 0 asercion
    positiva, exactamente 1 REQUIRED_FIELD_MISSING nombrando el campo,
    y sin fallback a la fecha ESMA."""
    result = _derive_with_mutation(
        "G05-004", "CNMV_PSC_REGISTER", "services_from", None
    )
    entity = _entity(result, "G05-004")
    assert not any(
        a["rule_id"].startswith(("mica-art63", "mica-art60"))
        for a in entity["assertions"]
    )
    missing = [
        f for f in entity["findings"]
        if f["classification"] == "REQUIRED_FIELD_MISSING"
    ]
    assert len(missing) == 1
    assert missing[0]["rule_id"] == "mica-domestic-cnmv-service-date-missing"
    assert "cnmv_services_from" in missing[0]["detail"]
    assert not any(
        f["classification"] == "DATE_CONFLICT" for f in entity["findings"]
    )
    # Sin fallback: ninguna asercion toma la fecha ESMA (31/10/2025).
    assert not any(
        a.get("effective_from") == "2025-10-31" for a in entity["assertions"]
    )


def test_missing_cnmv_service_date_credit_institution():
    """Mismo comportamiento en la ruta art.60 (BBVA)."""
    result = _derive_with_mutation(
        "G05-001", "CNMV_PSC_REGISTER", "services_from", None
    )
    entity = _entity(result, "G05-001")
    assert not any(
        a["rule_id"].startswith(("mica-art63", "mica-art60"))
        for a in entity["assertions"]
    )
    missing = [
        f for f in entity["findings"]
        if f["classification"] == "REQUIRED_FIELD_MISSING"
    ]
    assert len(missing) == 1
    assert "cnmv_services_from" in missing[0]["detail"]


def test_missing_esma_date_blocks_agreement_check():
    """Fecha ESMA ausente con fecha CNMV presente: la concordancia no es
    verificable -> REQUIRED_FIELD_MISSING (la fecha CNMV sola no se
    promociona a asercion)."""
    result = _derive_with_mutation(
        "G05-004", "ESMA_MICA_REGISTER", "authorisation_notification_date", None
    )
    entity = _entity(result, "G05-004")
    assert not any(
        a["rule_id"].startswith(("mica-art63", "mica-art60"))
        for a in entity["assertions"]
    )
    missing = [
        f for f in entity["findings"]
        if f["classification"] == "REQUIRED_FIELD_MISSING"
    ]
    assert len(missing) == 1
    assert missing[0]["rule_id"] == "mica-domestic-esma-date-missing"


def test_date_conflict_excludes_missing_date_finding():
    """Fechas presentes y divergentes: solo DATE_CONFLICT, sin
    REQUIRED_FIELD_MISSING adicional (precedencia disjunta)."""
    result = _derive_with_mutation(
        "G05-004", "CNMV_PSC_REGISTER", "services_from", "01/01/2020"
    )
    entity = _entity(result, "G05-004")
    assert not any(
        a["rule_id"].startswith(("mica-art63", "mica-art60"))
        for a in entity["assertions"]
    )
    assert [
        f["classification"] for f in entity["findings"]
    ] == ["DATE_CONFLICT"]


def test_missing_date_rule_does_not_fire_on_lp_row():
    """Frontera C/D: la misma mutacion sobre una fila LP no dispara la
    residual domestica — sigue UNSUPPORTED_ART60_ENTITY_CLASS / defer
    G1-D, nunca una fecha domestica exigida."""
    ledger = _read(LEDGER_PATH)
    ruleset = _read(RULESET_PATH)
    manifest = _read(MANIFEST_PATH)
    corpus = _read(CORPUS_PATH)
    for claim in ledger["claims"]:
        if claim["corpus_id"] == "G05-004" and claim["source"] == "CNMV_PSC_REGISTER":
            if claim["field"] == "cnmv_category":
                claim["normalized_value"] = "PSC EN RÉGIMEN DE LP"
            elif claim["field"] == "services_from":
                claim["normalized_value"] = None
    result = derive_entitlements(
        ledger, ruleset, manifest, corpus,
        derivation_version="FINREG_G1_DERIVATION_V1", id_prefix="tst",
    )
    entity = _entity(result, "G05-004")
    assert not any(
        a["rule_id"].startswith(("mica-art63", "mica-art60"))
        for a in entity["assertions"]
    )
    assert not any(
        f["classification"] == "REQUIRED_FIELD_MISSING"
        for f in entity["findings"]
    )
    assert any(
        f["classification"] == "UNSUPPORTED_ART60_ENTITY_CLASS"
        for f in entity["findings"]
    )
