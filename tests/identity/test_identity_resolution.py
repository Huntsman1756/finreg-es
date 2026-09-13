"""G0.2 — Tests del modelo de identidad."""
import pytest

from finreg_es.identity import (
    is_valid_lei,
    is_valid_nif,
    resolve_by_identifier,
    resolve_by_name,
    adopt_identifiers_from_source,
)
from finreg_es.vocab import IdentityResolutionState


def test_nif_checksum_accepts_valid_rejects_invalid():
    assert is_valid_nif("A12345676")
    assert is_valid_nif("B1234567F")
    assert is_valid_nif("12345678Z")
    assert not is_valid_nif("A12345671")
    assert not is_valid_nif("A1234567")
    assert not is_valid_nif("")


def test_lei_iso17442_validation():
    assert is_valid_lei("MERIDIANOBANK0000167")
    bad = "MERIDIANOBANK0000168"
    assert not is_valid_lei(bad)
    assert not is_valid_lei("TOOSHORT")


def test_exact_resolution_via_identifier(identity_index):
    r = resolve_by_identifier(identity_index, "NIF", "a12345676")
    assert r.state is IdentityResolutionState.EXACT
    assert r.entity_id == "ent-001"


def test_conflicting_identifiers(identity_index):
    r = resolve_by_identifier(identity_index, "LEI", "MERIDIANOBANK0000167")
    assert r.state is IdentityResolutionState.CONFLICTING_IDENTIFIERS
    assert set(r.candidates) == {"ent-001", "ent-010"}


def test_multiple_name_candidates_is_ambiguous_not_not_found(identity_index):
    r = resolve_by_name(identity_index, "Solvia Crypto Services S.A.")
    assert r.state is IdentityResolutionState.AMBIGUOUS
    assert r.reason == "MULTIPLE_NAME_CANDIDATES"
    assert set(r.candidates) == {"ent-006", "ent-007"}


def test_single_name_candidate_is_also_ambiguous_w6(identity_index):
    r = resolve_by_name(identity_index, "Payvista Europe UAB")
    assert r.state is IdentityResolutionState.AMBIGUOUS
    assert r.reason == "SINGLE_CANDIDATE_NAME_MATCH"
    assert r.candidates == ("ent-002",)


def test_name_not_found(identity_index):
    r = resolve_by_name(identity_index, "Entidad Que No Existe S.A.")
    assert r.state is IdentityResolutionState.NOT_FOUND


def test_lei_nullable_in_index(identity_index):
    ent005 = next(e for e in identity_index if e.entity_id == "ent-005")
    kinds = {i.kind for i in ent005.identifiers}
    assert "LEI" not in kinds


def test_identifier_adoption_from_identifier_bearing_source(identity_index):
    # La lista CNMV solo da denominacion (H2); ESMA porta identificadores (W6).
    r = adopt_identifiers_from_source(identity_index, "ESMA_MICA_ID", "Crypto Catalina S.L.")
    assert r.state is IdentityResolutionState.EXACT
    assert r.reason == "ADOPTED_FROM_IDENTIFIER_BEARING_SOURCE"
    assert r.entity_id == "ent-003"


def test_identifier_adoption_with_multiple_candidates_stays_ambiguous(identity_index):
    r = adopt_identifiers_from_source(identity_index, "ESMA_MICA_ID", "Solvia Crypto Services S.A.")
    assert r.state is IdentityResolutionState.AMBIGUOUS


def test_identifiers_normalized_deterministically(identity_index):
    r1 = resolve_by_identifier(identity_index, "NIF", "  A12345676 ")
    r2 = resolve_by_identifier(identity_index, "NIF", "A12345676")
    assert r1.state == r2.state == IdentityResolutionState.EXACT
