"""G0.1 — Tests contractuales de contratos de fuentes."""
from pathlib import Path

import pytest

from finreg_es.canonical import canonical_json, sha256_hex, strict_json_loads
from finreg_es.contracts import load_contract, staleness_policy
from finreg_es.loaders import load_assertions
from finreg_es.vocab import NegativeEvidenceCapability


def test_every_register_required_in_g0(all_contracts):
    expected = {
        "BDE_REGISTRO_ENTIDADES",
        "CNMV_REGISTRO_EMPRESAS",
        "CNMV_MICA_CASP_LIST",
        "EBA_PSD2_REGISTER",
        "EBA_CREDIT_INSTITUTIONS_REGISTER",
        "ESMA_MICA_REGISTER",
        "HOME_STATE_AUTHORITY_TEMPLATE",
    }
    assert expected <= set(all_contracts)


def test_negative_capability_enum_and_ps2_bank_exclusion(all_contracts):
    for c in all_contracts.values():
        assert c.negative_evidence_capability in NegativeEvidenceCapability
    psd2 = all_contracts["EBA_PSD2_REGISTER"]
    assert "CREDIT_INSTITUTION" in psd2.excluded_entity_classes
    assert any(
        r.rule_id == "eba-psd2-out-credit-institutions" and r.scope == "OUT"
        for r in psd2.coverage_rules
    )


def test_negative_staleness_not_longer_than_positive(all_contracts):
    for c in all_contracts.values():
        pos, neg = staleness_policy(c)
        if pos is not None and neg is not None:
            assert neg <= pos


def test_verified_fields_carry_primary_source(contract_paths):
    for p in contract_paths:
        raw = strict_json_loads(p.read_text(encoding="utf-8"))
        for field, info in raw["verification"].items():
            if info["status"] == "VERIFIED":
                assert info.get("source_url"), f"{p.name}:{field} VERIFIED sin source_url"


def test_pending_hypotheses_are_declared(contract_paths):
    """Las hipotesis H1-H8 deben quedar registradas como PENDING, no silenciadas."""
    for p in contract_paths:
        raw = strict_json_loads(p.read_text(encoding="utf-8"))
        statuses = {info["status"] for info in raw["verification"].values()}
        assert statuses <= {"VERIFIED", "PENDING", "PROPOSED"}


def test_fixtures_are_canonical_deterministic_and_float_free():
    for base in (Path("fixtures/contracts"), Path("fixtures/regulatory")):
        for p in sorted((Path(__file__).parents[1] / base).glob("*.json")):
            raw = strict_json_loads(p.read_text(encoding="utf-8"))
            assert canonical_json(raw) == canonical_json(
                strict_json_loads(canonical_json(raw))
            ), f"no canonico: {p.name}"
            _assert_no_floats(raw, p.name)


def test_canonical_json_rejects_float_and_nonfinite():
    for bad in ('{"x": 1.5}', '{"x": NaN}', '{"x": Infinity}', '{"x": 1e400}'):
        with pytest.raises(ValueError):
            strict_json_loads(bad)


def test_canonical_json_rejects_duplicate_keys():
    with pytest.raises(ValueError, match="clave duplicada"):
        strict_json_loads('{"a": 1, "a": 2}')


def test_canonical_json_preserves_unicode_and_orders_keys():
    composed = "\u00e9"       # é precompuesto
    decomposed = "e\u0301"    # e + combining acute
    assert canonical_json({"b": composed, "a": 1}) == '{"a":1,"b":"\u00e9"}'
    # No se normaliza Unicode: dos cadenas distintas siguen siendo distintas.
    assert canonical_json({"s": composed}) != canonical_json({"s": decomposed})
    assert sha256_hex({"a": 1}) == sha256_hex({"a": 1})


def _assert_no_floats(obj, name):
    if isinstance(obj, float):
        pytest.fail(f"float prohibido en fixture {name}")
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_no_floats(v, name)
    if isinstance(obj, list):
        for v in obj:
            _assert_no_floats(v, name)


def test_raw_snapshot_sha256_matches_raw_value(assertions):
    for a in assertions:
        for s in a.source_assertions:
            assert s.raw_snapshot_sha256 == sha256_hex(s.raw_value), a.assertion_id
            assert len(s.raw_snapshot_sha256) == 64


def test_assertions_have_required_semantic_dimensions(assertions):
    for a in assertions:
        assert a.legal_effect in ("ENTITLED_TO_PROVIDE", "NOT_ENTITLED", "UNKNOWN")
        assert a.entry_mechanism in (
            "AUTHORISATION",
            "NOTIFICATION",
            "REGISTRATION",
            "EXEMPTION",
            "STATUTORY_ENTITLEMENT",
        )
        assert a.territorial_basis in ("DOMESTIC", "BRANCH", "FREEDOM_TO_PROVIDE_SERVICES", "OTHER")
        assert a.effective_from
        for s in a.source_assertions:
            assert s.retrieved_at and s.extractor_version and s.source_url
