"""G2-B — differential oracle: nuestro differ vs dictdiffer (scan §decision).

Invariante comprobada: el conjunto de record_keys tocadas por nuestro
differ (added + removed + changed) coincide con el conjunto de claves
de primer nivel que dictdiffer reporta como modificadas. Solo cubre la
parte generica del modelo de records; las reglas de comparabilidad y
completitud del contrato son propias y no se oraculizan.
"""
from __future__ import annotations

import pytest

dictdiffer = pytest.importorskip("dictdiffer")
hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from finreg_es.snapshot_diff import diff_records

_keys = st.from_regex(r"[a-z]{1,4}", fullmatch=True)
_scalars = st.none() | st.booleans() | st.integers(-10**4, 10**4) | st.text(
    alphabet="abcXYZ019", max_size=6
)
_values = st.recursive(
    _scalars,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(_keys, children, max_size=4),
    max_leaves=8,
)
_records = st.dictionaries(_keys, _values, max_size=5)
_record_sets = st.dictionaries(_keys, _records, max_size=6)


def _dictdiffer_touched_keys(left: dict, right: dict) -> set:
    touched = set()
    for action, path, values in dictdiffer.diff(left, right):
        segments = path.split(".") if isinstance(path, str) and path else (
            list(path) if isinstance(path, (list, tuple)) else []
        )
        if action in ("add", "remove") and not segments:
            touched.update(k for k, _ in values)
        elif segments:
            touched.add(segments[0])
    return touched


@settings(max_examples=400, derandomize=True, deadline=None)
@given(left=_record_sets, right=_record_sets)
def test_diff_records_agrees_with_dictdiffer_on_touched_keys(left, right):
    ours = diff_records(left, right)
    our_touched = (
        set(ours["added"])
        | set(ours["removed"])
        | {c["record_key"] for c in ours["changed"]}
    )
    assert our_touched == _dictdiffer_touched_keys(left, right)


@settings(max_examples=200, derandomize=True, deadline=None)
@given(left=_record_sets, right=_record_sets)
def test_diff_records_deterministic_and_symmetric_inverse(left, right):
    """Mismo input => mismos cambios; el inverso intercambia old/new."""
    a = diff_records(left, right)
    b = diff_records(left, right)
    assert a == b
    inv = diff_records(right, left)
    assert inv["added"] == a["removed"]
    assert inv["removed"] == a["added"]
    inv_changed = {
        (c["record_key"], c["path"]): (c.get("old", "<M>"), c.get("new", "<M>"))
        for c in inv["changed"]
    }
    for c in a["changed"]:
        assert inv_changed[(c["record_key"], c["path"])] == (
            c.get("new", "<M>"),
            c.get("old", "<M>"),
        )
