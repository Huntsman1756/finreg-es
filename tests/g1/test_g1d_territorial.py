"""G1-D — Replay del artefacto territorial y pruebas de frontera D4.

Fija la cadena congelada corpus G1-D -> ledger G1-D -> ruleset G1-D ->
derivadas -> run sobre los casos reales preregistrados (G1D-01..08).
Los casos metamorficos D3-09/10 se ejercen aqui como mutaciones del
ledger en memoria (no forman parte del run congelado).

Propiedades fijadas (gate D, congelado en D1/D2):

- entry_mechanism nunca muta por el procedimiento territorial
  (AUTHORISATION + art.28/art.65; jamas NOTIFICATION por pasaporte);
- effective_from es especifico de ruta y nunca cae a la fecha de
  autorizacion home ni a la fecha ESMA como fallback territorial;
- la asercion de sucursal PSD2 exige join exacto a parent ACTIVE +
  inscripcion BdE vigente + servicio exacto, e incluye la evidencia
  del parent y de BdE en source_assertions;
- agente y country-code-sin-ruta producen hecho/abstencion, 0
  entitlement;
- LIMITED_LP se abstiene siempre (sin fuente primaria);
- fechas territoriales ausentes/conflictivas producen findings
  clasificados, nunca una eleccion silenciosa.
"""
from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from pathlib import Path

from finreg_es.assessment_run import run_assessment
from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.derivation import (
    G1D_DERIVATION_VERSION,
    build_g1d_artifact,
    derive_entitlements,
)


ROOT = Path(__file__).parents[2]
G1 = ROOT / "fixtures" / "g1"
ARTIFACT_PATH = G1 / "derived-assertions-g1-d-001.json"
RUN_PATH = G1 / "runs" / "assessment-run-g1-d-001.json"
RULESET_PATH = G1 / "derivation-rules-g1-d.json"
LEDGER_PATH = G1 / "claim-ledger-g1-d-001.json"
MANIFEST_PATH = G1 / "sources" / "manifest-g1-d-run.json"
CORPUS_PATH = G1 / "corpus-g1-d.json"
BUILDER = ROOT / "tools" / "build_g1d_ledger.py"


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


def _assertions(entity_id: str, effect: str | None = None) -> list[dict]:
    out = [
        a
        for a in _artifact()["assertions"]
        if a["entity_id"] == entity_id
    ]
    if effect:
        out = [a for a in out if a["legal_effect"] == effect]
    return out


def _entitled(entity_id: str) -> list[dict]:
    return _assertions(entity_id, "ENTITLED_TO_PROVIDE")


def _derive_mutated(mutator):
    """Deriva el ledger G1-D congelado con una mutacion en memoria."""
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
        "facts": [
            f for f in result.get("reported_facts", [])
            if f["corpus_id"] == corpus_id
        ],
    }


# ------------------------------------------------------------------
# Replay / integridad
# ------------------------------------------------------------------


def test_artifact_replays_byte_identical_from_committed_inputs():
    """Las derivadas G1-D se regeneran solo con inputs commiteados."""
    rebuilt = canonical_json(build_g1d_artifact(ROOT)) + "\n"
    assert rebuilt == ARTIFACT_PATH.read_text(encoding="utf-8")
    declared = _read(ARTIFACT_PATH)["artifact"]
    assert declared["derivation_ruleset_sha256"] == hashlib.sha256(
        RULESET_PATH.read_bytes()
    ).hexdigest()
    assert declared["claims_ledger_sha256"] == hashlib.sha256(
        LEDGER_PATH.read_bytes()
    ).hexdigest()
    assert declared["corpus_sha256"] == hashlib.sha256(
        CORPUS_PATH.read_bytes()
    ).hexdigest()
    assert declared["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST_PATH.read_bytes()
    ).hexdigest()


def test_ledger_corpus_manifest_build_deterministic():
    """El builder G1-D reproduce byte-identicos los tres artefactos de
    entrada a partir de los snapshots congelados."""
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import build_g1d_ledger as builder

    assert canonical_json(builder.build_ledger()) + "\n" == (
        LEDGER_PATH.read_text(encoding="utf-8")
    )
    assert canonical_json(builder.build_corpus()) + "\n" == (
        CORPUS_PATH.read_text(encoding="utf-8")
    )
    assert canonical_json(builder.build_manifest()) + "\n" == (
        MANIFEST_PATH.read_text(encoding="utf-8")
    )


def test_ledger_claims_resolve_to_real_snapshot_records():
    """Cada claim G1D cita un registro real del snapshot: el
    raw_record_sha256 del claim es reproducible desde el propio claim
    solo si el builder lo derivo del registro (spot-check de cadena)."""
    ledger = _read(LEDGER_PATH)
    g1d = [c for c in ledger["claims"] if c["corpus_id"].startswith("G1D")]
    assert g1d
    for claim in g1d:
        assert claim["record_key"]
        assert claim["snapshot_sha256"]
        assert claim["raw_record_sha256"]
        assert claim["extractor_version"] == "G1D_TERRITORIAL_EXTRACT_V1"


def test_run_001_replays_offline(monkeypatch):
    """El run congelado G1-D se reproduce sin red y con integridad de
    inputs; los casos metamorficos quedan fuera del run."""
    _no_network(monkeypatch)
    frozen = _read(RUN_PATH)
    meta = frozen["run"]
    replayed = run_assessment(
        ROOT,
        run_id=meta["run_id"],
        g1d=True,
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
    assert meta["metamorphic_cases_excluded"] == ["G1D-09", "G1D-10"]

    recorded = frozen.pop("result_sha")
    recomputed = hashlib.sha256(
        canonical_json(frozen).encode("utf-8")
    ).hexdigest()
    assert recomputed == recorded


def test_all_real_cases_match_full_expectation():
    """Gate D3: assessment + reason + mechanism + territorial_basis +
    legal_basis coinciden en los 8 casos reales."""
    run = _read(RUN_PATH)
    assert run["summary"]["cases_total"] == 8
    assert run["summary"]["mismatches"] == []
    for case in run["cases"]:
        assert case["match"], case["case_id"]
        assert case["territorial_basis_match"], case["case_id"]
        assert case["legal_basis_match"], case["case_id"]
        assert case["entry_mechanism_match"], case["case_id"]


# ------------------------------------------------------------------
# Fechas efectivas por ruta
# ------------------------------------------------------------------


def test_effective_from_is_route_specific():
    """Cada ruta toma su fecha territorial juridica (D4)."""
    lp = _entitled("G1D-004")
    assert {a["effective_from"] for a in lp} == {"2025-05-03"}
    branch_mica = _entitled("G1D-005")
    assert {a["effective_from"] for a in branch_mica} == {"2025-12-10"}
    branch_psd2 = [
        a for a in _entitled("G1D-002") if a["territorial_basis"] == "BRANCH"
    ]
    assert {a["effective_from"] for a in branch_psd2} == {"2024-06-26"}
    wise_branch = [
        a for a in _entitled("G1D-007") if a["territorial_basis"] == "BRANCH"
    ]
    assert {a["effective_from"] for a in wise_branch} == {"2026-04-10"}


def test_fps_never_uses_home_authorisation_date():
    """Sin fecha juridica de pasaporte publicada, FPS usa
    EVIDENCE_AS_OF (2026-09-14): nunca la autorizacion home
    2018-07-02 como fecha territorial."""
    fps = [
        a for a in _entitled("G1D-001")
        if a["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"
    ]
    assert len(fps) == 1
    assert fps[0]["effective_from"] == "2026-09-14"
    assert fps[0]["effective_from"] != "2018-07-02"
    # La fecha home sigue citada como base, no como inicio territorial.
    assert "2018-07-02" in fps[0]["legal_basis"]


# ------------------------------------------------------------------
# Sucursal PSD2: join exacto + inscripcion BdE + scope exacto
# ------------------------------------------------------------------


def test_branch_assertion_carries_parent_and_bde_provenance():
    """La SourceAssertion[] de la sucursal incluye la fila EBA de la
    sucursal, la del parent y la inscripcion BdE."""
    for entity_id, register_count in (("G1D-002", 3), ("G1D-007", 3)):
        branch = [
            a for a in _entitled(entity_id)
            if a["territorial_basis"] == "BRANCH"
        ]
        assert len(branch) == 1
        registers = sorted(
            s["register_id"] for s in branch[0]["source_assertions"]
        )
        assert registers == [
            "BDE_REGISTRO_SERVICIOS_PAGO",
            "EBA_PSD2_REGISTER",
            "EBA_PSD2_REGISTER",
        ]
        assert len(branch[0]["source_assertions"]) == register_count
        parent_claims = [
            cid for cid in branch[0]["source_claim_ids"] if "PSD_PI:" in cid
        ]
        bde_claims = [
            cid
            for cid in branch[0]["source_claim_ids"]
            if "BDE_REGISTRO_SERVICIOS_PAGO" in cid
        ]
        assert parent_claims and bde_claims


def test_branch_requires_exact_parent_join():
    """Sin el registro del parent no hay positivo de sucursal aunque
    DER_CHI_ENT_AUT diga Active (metamorfico: claims del parent de
    Eupago eliminados)."""

    def drop_parent(claims):
        claims[:] = [
            c
            for c in claims
            if not (
                c["corpus_id"] == "G1D-002"
                and c["source"] == "EBA_PSD2_REGISTER"
                and c["record_key"].get("EntityType") == "PSD_PI"
            )
        ]

    result = _derive_mutated(drop_parent)
    entity = _entity(result, "G1D-002")
    assert not any(
        a["territorial_basis"] == "BRANCH"
        and a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in entity["assertions"]
    )
    assert any(
        f["rule_id"] == "eba-psd2-branch-es-parent-not-active"
        and f["classification"] == "DERIVED_PRECONDITION_NOT_MET"
        for f in entity["findings"]
    )


def test_branch_requires_active_bde_registration():
    """Sucursal EBA activa + parent activo sin inscripcion BdE
    demostrada: REQUIRED_FIELD_MISSING, 0 positivo (metamorfico)."""

    def drop_bde(claims):
        claims[:] = [
            c
            for c in claims
            if not (
                c["corpus_id"] == "G1D-002"
                and c["source"] == "BDE_REGISTRO_SERVICIOS_PAGO"
            )
        ]

    result = _derive_mutated(drop_bde)
    entity = _entity(result, "G1D-002")
    assert not any(
        a["territorial_basis"] == "BRANCH"
        and a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in entity["assertions"]
    )
    assert any(
        f["rule_id"] == "eba-psd2-branch-es-registration-missing"
        and f["classification"] == "REQUIRED_FIELD_MISSING"
        for f in entity["findings"]
    )


def test_exact_psd2_service_scope_preserved():
    """El scope conserva los codigos EBA exactos declarados para ES;
    activity publica sigue siendo PAYMENT_SERVICES."""
    fps = [
        a for a in _entitled("G1D-001")
        if a["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"
    ][0]
    for code in ("PS_03A", "PS_03B", "PS_03C", "PS_05A", "PS_05B",
                 "PS_070", "PS_080"):
        assert code in fps["scope"]
    assert fps["activity"] == "PAYMENT_SERVICES"
    branch = [
        a for a in _entitled("G1D-002") if a["territorial_basis"] == "BRANCH"
    ][0]
    for code in ("PS_060", "PS_070", "PS_080"):
        assert code in branch["scope"]


# ------------------------------------------------------------------
# Abstenciones preregistradas
# ------------------------------------------------------------------


def test_agent_produces_no_independent_entitlement():
    """PSD_AG: hecho delegado (parent ACTIVE explica el registro) y
    0 asercion de entitlement para el agente."""
    entitled = _entitled("G1D-003")
    assert entitled == []
    run = _read(RUN_PATH)
    case = next(c for c in run["cases"] if c["case_id"] == "G1D-03")
    assert case["assessment"] == "INDETERMINATE"
    assert (
        case["reason"] == "AGENT_DELEGATED_ROUTE_NO_INDEPENDENT_ENTITLEMENT"
    )
    assert case["matched_reported_fact_ids"]


def test_country_code_alone_produces_no_entitlement():
    """ac_serviceCode_cou=ES sin trigger CNMV: hecho reportado,
    0 asercion territorial (Bitpanda)."""
    assert _entitled("G1D-008") == []
    run = _read(RUN_PATH)
    case = next(c for c in run["cases"] if c["case_id"] == "G1D-08")
    assert case["assessment"] == "INDETERMINATE"
    assert case["reason"] == "TERRITORIAL_ENTITLEMENT_UNRESOLVED"


def test_limited_lp_abstains_without_primary_source():
    """LIMITED PSC EN REGIMEN DE LP: epigrafe sin filas ni fuente
    primaria -> abstencion clasificada, nunca promovida a LP."""
    assert _entitled("G1D-006") == []
    facts = _artifact()["reported_facts"]
    fact = next(f for f in facts if f["corpus_id"] == "G1D-006")
    assert fact["reported_status"] == "TERRITORIAL_ROUTE_UNRESOLVED"
    run = _read(RUN_PATH)
    case = next(c for c in run["cases"] if c["case_id"] == "G1D-06")
    assert case["assessment"] == "INDETERMINATE"
    assert case["reason"] == "TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP"


# ------------------------------------------------------------------
# Metamorficos D3-09/10 (mutaciones sobre ledger en memoria)
# ------------------------------------------------------------------


def test_missing_territorial_date_is_finding_not_fallback():
    """D3-09: services_from ausente en la fila CNMV LP -> 0 asercion,
    REQUIRED_FIELD_MISSING nombrando el campo; la fecha ESMA nunca es
    fallback territorial."""

    def mutate(claims):
        for c in claims:
            if (
                c["corpus_id"] == "G1D-004"
                and c["source"] == "CNMV_PSC_REGISTER"
                and c["field"] == "services_from"
            ):
                c["normalized_value"] = None

    result = _derive_mutated(mutate)
    entity = _entity(result, "G1D-004")
    assert not any(
        a["legal_effect"] == "ENTITLED_TO_PROVIDE" for a in entity["assertions"]
    )
    missing = [
        f for f in entity["findings"]
        if f["classification"] == "REQUIRED_FIELD_MISSING"
    ]
    assert missing
    assert any(
        f["rule_id"] == "mica-territorial-date-missing" for f in missing
    )
    # Sin fallback: ninguna asercion toma la fecha ESMA 02/04/2025.
    assert not any(
        a.get("effective_from") == "2025-04-02" for a in entity["assertions"]
    )


def test_conflicting_territorial_dates_abstain():
    """D3-10: segunda fecha territorial divergente de la misma
    semantica (doble alta BdE) -> DATE_CONFLICT + 0 asercion BRANCH;
    sin precedencia silenciosa."""

    def mutate(claims):
        dup = [
            dict(c)
            for c in claims
            if c["corpus_id"] == "G1D-002"
            and c["source"] == "BDE_REGISTRO_SERVICIOS_PAGO"
        ]
        for c in dup:
            c["claim_id"] = c["claim_id"] + "|dup"
            c["record_key"] = {"field": "CÓDIGO BE", "value": "6938-DUP"}
            if c["field"] == "fecha_alta":
                c["normalized_value"] = "01/01/2020"
                c["raw_value"] = "01/01/2020"
        claims.extend(dup)

    result = _derive_mutated(mutate)
    entity = _entity(result, "G1D-002")
    assert not any(
        a["territorial_basis"] == "BRANCH"
        and a["legal_effect"] == "ENTITLED_TO_PROVIDE"
        for a in entity["assertions"]
    )
    assert any(
        f["rule_id"] == "eba-psd2-branch-es-date-conflict"
        and f["classification"] == "DATE_CONFLICT"
        for f in entity["findings"]
    )


# ------------------------------------------------------------------
# Invariantes del modelo territorial
# ------------------------------------------------------------------


def test_wise_multi_route_compatible_not_conflict():
    """G1D-07: FPS y BRANCH coexisten como aserciones separadas
    (COMPATIBLE_MULTI_ROUTE); la deduplicacion no las colapsa."""
    bases = {a["territorial_basis"] for a in _entitled("G1D-007")}
    assert {"FREEDOM_TO_PROVIDE_SERVICES", "BRANCH"} <= bases
    run = _read(RUN_PATH)
    case = next(c for c in run["cases"] if c["case_id"] == "G1D-07")
    assert case["assessment"] == "CONFIRMED_ENTITLED"


def test_entry_mechanism_never_mutates_to_notification():
    """Ninguna asercion ENTITLED territorial tiene entry_mechanism
    NOTIFICATION: la comunicacion de pasaporte no cambia el mecanismo
    de base."""
    for a in _artifact()["assertions"]:
        if a["entity_id"].startswith("G1D") and a[
            "legal_effect"
        ] == "ENTITLED_TO_PROVIDE":
            assert a["entry_mechanism"] == "AUTHORISATION", a["rule_id"]


def test_no_domestic_from_territorial_routes():
    """0 LP -> DOMESTIC y 0 branch -> FPS: ninguna asercion G1D usa una
    base territorial distinta de la de su ruta."""
    for a in _artifact()["assertions"]:
        if not a["entity_id"].startswith("G1D"):
            continue
        if a["rule_id"].startswith("mica-lp") or a["rule_id"].endswith(
            "fps-es-entitled"
        ):
            assert a["territorial_basis"] == "FREEDOM_TO_PROVIDE_SERVICES"
        if a["rule_id"].endswith("branch-es-entitled"):
            assert a["territorial_basis"] == "BRANCH"
        assert a["territorial_basis"] != "DOMESTIC"


def test_no_negative_from_missing_evidence():
    """Gate D: 0 NOT_ENTITLED emitido por ausencia de evidencia o
    retirada territorial en G1-D."""
    for a in _artifact()["assertions"]:
        if a["entity_id"].startswith("G1D"):
            assert a["legal_effect"] != "NOT_ENTITLED"


def test_g1d_ruleset_keeps_g1c_rules_intact():
    """El delta es aditivo: todas las reglas G1-C estan presentes en el
    ruleset G1-D (salvo las dos renombradas/estrechadas documentadas:
    agent-branch-parent-status -> agent-only y los ajustes de
    passport-services/deferred)."""
    g1c = {r["rule_id"] for r in _read(G1 / "derivation-rules.json")["ruleset"]["rules"]}
    g1d = {r["rule_id"] for r in _read(RULESET_PATH)["ruleset"]["rules"]}
    renamed = {"eba-psd2-agent-branch-parent-status"}
    assert g1c - renamed <= g1d
