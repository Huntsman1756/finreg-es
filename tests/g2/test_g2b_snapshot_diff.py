"""G2-B — casos preregistrados B01-B12 (docs/g2-snapshot-history-contract.md §11).

El differ no conoce semantica juridica: solo records canonicalizados,
comparabilidad y admisibilidad de removals.
"""
from __future__ import annotations

import pytest

from finreg_es.snapshot_diff import (
    ObservationRef,
    compare_observations,
    diff_records,
    diff_value,
)

NORM = "FINREG_G2_EBA_NORMALIZATION_V1"


def _obs(
    sha: str,
    retrieved: str = "2026-09-14",
    as_of: str | None = "2026-09-14",
    completeness: str = "complete",
    norm: str = NORM,
    series: str = "eba-psd2-register|full",
) -> ObservationRef:
    return ObservationRef(
        register_id="eba-psd2-register",
        series_key=series,
        snapshot_file=f"raw/{sha}.zip",
        content_sha256=sha,
        retrieved_at=retrieved,
        source_as_of=as_of,
        completeness=completeness,
        normalization_version=norm,
    )


L = {"k1": {"a": 1, "s": ["x", "y"]}, "k2": {"a": 2}}
R = {"k1": {"a": 1, "s": ["x", "y"]}, "k2": {"a": 3}}


def test_b01_same_content_id_zero_diff_no_record_diff():
    """B01: misma observacion repetida -> 0 diff (short-circuit)."""
    left = _obs("AAA", retrieved="2026-09-13")
    right = _obs("AAA", retrieved="2026-09-14")
    result = compare_observations(left, right, {}, {"ignored": {"x": 1}})
    assert result["changes"] == {"added": [], "removed": [], "changed": []}
    assert result["comparison"]["identical_content"] is True
    assert result["comparison"]["comparable"] is True


def test_b02_set_reorder_zero_diff_after_normalization():
    """B02: reordenacion de sets => 0 cambios (los sets salen ordenados
    de la normalizacion; el differ compara canonicalizados)."""
    left = {"k": {"s": ["a", "b", "c"]}}
    right = {"k": {"s": ["a", "b", "c"]}}
    assert diff_records(left, right)["changed"] == []


def test_b03_same_as_of_revision():
    """B03: mismo source_as_of + contenido distinto -> SAME_AS_OF_REVISION."""
    left = _obs("AAA", as_of="2026-09-13")
    right = _obs("BBB", as_of="2026-09-13")
    result = compare_observations(left, right, L, R)
    c = result["comparison"]
    assert c["succession_state"] == "SAME_AS_OF_REVISION"
    assert any(
        f["classification"] == "SAME_AS_OF_REVISION" for f in c["findings"]
    )


def test_b04_record_added():
    """B04: record anadido -> added."""
    result = compare_observations(
        _obs("AAA"), _obs("BBB"), L, {**L, "k3": {"a": 9}}
    )
    assert result["changes"]["added"] == ["k3"]


def test_b05_absent_in_partial_capture_not_removal():
    """B05: record ausente en captura parcial -> NO_REMOVAL_ADMISSIBLE."""
    left = _obs("AAA", completeness="complete")
    right = _obs("BBB", completeness="partial")
    result = compare_observations(left, right, L, {"k1": L["k1"]})
    c = result["comparison"]
    assert result["changes"]["removed"] == ["k2"]
    assert c["removal_admissible"] is False
    assert any(
        f["classification"] == "NO_REMOVAL_ADMISSIBLE" for f in c["findings"]
    )


def test_b06_absent_between_complete_captures_is_structural_removal():
    """B06: record ausente entre capturas completas -> STRUCTURAL_REMOVAL
    admisible (nunca conclusion juridica)."""
    result = compare_observations(_obs("AAA"), _obs("BBB"), L, {"k1": L["k1"]})
    c = result["comparison"]
    assert result["changes"]["removed"] == ["k2"]
    assert c["removal_admissible"] is True
    assert not any(
        f["classification"] == "NO_REMOVAL_ADMISSIBLE" for f in c["findings"]
    )


def test_b07_normalization_mismatch_not_comparable():
    """B07: extractor v1 x v2 -> NON_COMPARABLE_NORMALIZATION_VERSION."""
    left = _obs("AAA", norm="FINREG_G2_EBA_NORMALIZATION_V1")
    right = _obs("BBB", norm="FINREG_G2_EBA_NORMALIZATION_V2")
    result = compare_observations(left, right, L, R)
    c = result["comparison"]
    assert c["comparable"] is False
    assert result["changes"] == {"added": [], "removed": [], "changed": []}
    assert any(
        f["classification"] == "NON_COMPARABLE_NORMALIZATION_VERSION"
        for f in c["findings"]
    )


def test_b08_b09_no_legal_dates_in_structural_output():
    """B08/B09: el differ emite el cambio con su intervalo de observacion
    (observation_ids), nunca una fecha juridica fabricada."""
    result = compare_observations(
        _obs("AAA", retrieved="2026-05-01"),
        _obs("BBB", retrieved="2026-06-01"),
        L,
        R,
    )
    c = result["comparison"]
    assert "2026-05-01" in c["left_observation_id"]
    assert "2026-06-01" in c["right_observation_id"]
    for ch in result["changes"]["changed"]:
        assert "effective_from" not in ch
        assert "effective_at" not in ch


def test_b10_null_vs_missing_are_distinct_events():
    """B10: field presente->null (changed) != field removed (removed)."""
    left = {"k": {"f": 1}}
    null_side = {"k": {"f": None}}
    missing_side = {"k": {}}
    c_null = diff_records(left, null_side)["changed"]
    c_missing = diff_records(left, missing_side)["changed"]
    assert c_null == [
        {"record_key": "k", "kind": "changed", "path": ("f",), "old": 1, "new": None}
    ]
    assert c_missing == [
        {"record_key": "k", "kind": "removed", "path": ("f",), "old": 1}
    ]


def test_b11_source_as_of_regression_finding():
    """B11: source_as_of retrocede -> SOURCE_AS_OF_REGRESSION."""
    left = _obs("AAA", as_of="2026-09-14")
    right = _obs("BBB", as_of="2026-09-10")
    result = compare_observations(left, right, L, R)
    c = result["comparison"]
    assert c["succession_state"] == "SOURCE_AS_OF_REGRESSION"
    assert any(
        f["classification"] == "SOURCE_AS_OF_REGRESSION" for f in c["findings"]
    )


def test_b12_ordered_field_reorder_is_change():
    """B12: reordenar un campo declared-ordered si cuenta (la
    normalizacion conserva el orden en campos ordered)."""
    left = {"k": {"ordered": [1, 2, 3]}}
    right = {"k": {"ordered": [3, 2, 1]}}
    changes = diff_records(left, right)["changed"]
    assert len(changes) == 1
    assert changes[0]["kind"] == "changed"


def test_series_mismatch_is_invocation_error():
    """Contrato §2: diff entre series distintas es error, no resultado."""
    with pytest.raises(ValueError, match="series distintas"):
        compare_observations(
            _obs("AAA", series="eba-psd2|full"),
            _obs("BBB", series="bde-servicios-pago|full"),
            L,
            R,
        )


def test_nested_keyed_records_diff_recursively():
    """Contrato §6: nested keyed records se componen por clave."""
    left = {"k": {"services": {"ES": ["PS_01"], "FR": ["PS_03"]}}}
    right = {"k": {"services": {"ES": ["PS_01", "PS_02"], "FR": ["PS_03"]}}}
    changes = diff_records(left, right)["changed"]
    assert changes == [
        {
            "record_key": "k",
            "kind": "changed",
            "path": ("services", "ES"),
            "old": ["PS_01"],
            "new": ["PS_01", "PS_02"],
        }
    ]


def test_diff_value_scalar_and_missing():
    assert diff_value(("a",), 1, 2)[0]["kind"] == "changed"
    assert diff_value(("a",), 1, 1) == []
