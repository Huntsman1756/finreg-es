"""G2-C1 — clasificacion de cambios estructurales en candidatos a evento
regulatorio (docs/g2-c0-change-event-contract.md).

La capa interpreta cambios observados por G2-B; nunca reconstruye un
evento que el diff no observo. Casos preregistrados del catalogo EBA
PSD2 (series eba-psd2-register|*); el par real produjo 0/0/0, asi que
la demostracion del catalogo corre sobre el slice sintetico decidido
en el blocker del task (.tasks/g2-c1.yaml).
"""
from __future__ import annotations

import json
from pathlib import Path

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.change_events import (
    FINREG_G2C_EVENT_RULES_V1,
    classify_changes,
)

ROOT = Path(__file__).parents[2]
REAL_COMPARISON = (
    ROOT / "fixtures/g2/comparisons/eba-psd2-20260913-vs-20260914.json"
)
# Primer par real con Type-B/C del corpus longitudinal (task g2-c1,
# desbloqueado por g2-acquire-next 2026-09-15).
REAL_COMPARISON_0915 = (
    ROOT / "fixtures/g2/comparisons/eba-psd2-20260914-vs-20260915.json"
)

LEFT_ID = "eba-psd2-register|2026-09-13|aaaabbbbccccdddd"
RIGHT_ID = "eba-psd2-register|2026-09-14T19:36:43Z|eeeeffff00001111"


def _comparison(
    changes: dict,
    *,
    comparable: bool = True,
    removal_admissible: bool = True,
    findings: list | None = None,
    series: str = "eba-psd2-register|full",
) -> dict:
    """Salida de compare_observations sintetica (forma G2-B)."""
    return {
        "comparison": {
            "left_observation_id": LEFT_ID,
            "right_observation_id": RIGHT_ID,
            "series_key": series,
            "succession_state": "NORMAL_SUCCESSION",
            "normalization_version": "FINREG_G2_EBA_NORMALIZATION_V1",
            "completeness": {
                "left": "complete" if removal_admissible else "partial",
                "right": "complete",
            },
            "comparable": comparable,
            "identical_content": False,
            "removal_admissible": removal_admissible,
            "findings": findings or [],
        },
        "changes": changes,
    }


def _changes(added=(), removed=(), changed=()):
    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "changed": list(changed),
    }


def _only(result):
    assert len(result["candidates"]) == 1
    return result["candidates"][0]


# --- Catalogo EBA PSD2 preregistrado ---------------------------------


def test_c01_ent_aut_withdrawal_append_is_root_withdrawal_candidate():
    """ENT_AUT + fecha en posicion par => el intervalo abierto se cierra:
    ROOT_WITHDRAWAL_CANDIDATE con effective_from de la fuente (B08)."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:FR_ACPR!384558",
                        "kind": "changed",
                        "path": ("properties", "ENT_AUT"),
                        "old": ["2023-03-23"],
                        "new": ["2023-03-23", "2026-08-27"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "ROOT_WITHDRAWAL_CANDIDATE"
    assert c["record_key"] == "PSD_PI:FR_ACPR!384558"
    assert c["field_path"] == ["properties", "ENT_AUT"]
    assert c["admissibility"] == "SUPPORTED"
    assert c["effective_basis"] == "SOURCE_DECLARED"
    assert c["effective_from"] == "2026-08-27"
    assert c["old_value"] == ["2023-03-23"]
    assert c["new_value"] == ["2023-03-23", "2026-08-27"]


def test_c02_ent_aut_odd_append_is_reauthorisation_candidate():
    """ENT_AUT + fecha en posicion impar => nueva autorizacion publicada."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:X",
                        "kind": "changed",
                        "path": ("properties", "ENT_AUT"),
                        "old": ["2019-01-01", "2020-06-01"],
                        "new": ["2019-01-01", "2020-06-01", "2026-09-11"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "ROOT_REAUTHORISATION_CANDIDATE"
    assert c["effective_from"] == "2026-09-11"
    assert c["effective_basis"] == "SOURCE_DECLARED"
    assert c["admissibility"] == "SUPPORTED"


def test_c03_services_es_plus_code_is_capability_appeared():
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("services", "ES"),
                        "old": ["PS_01"],
                        "new": ["PS_01", "PS_070"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "CAPABILITY_APPEARED_CANDIDATE"
    assert c["added_codes"] == ["PS_070"]
    assert c["admissibility"] == "SUPPORTED"
    assert c["effective_basis"] == "EVIDENCE_AS_OF"
    # Sin fecha juridica publicada: nunca se fabrica effective_from.
    assert "effective_from" not in c


def test_c04_services_es_minus_code_is_capability_disappeared():
    """- PS_xx => CAPABILITY_DISAPPEARED; NUNCA negativo juridico."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("services", "ES"),
                        "old": ["PS_01", "PS_070"],
                        "new": ["PS_01"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "CAPABILITY_DISAPPEARED_CANDIDATE"
    assert c["removed_codes"] == ["PS_070"]
    assert "effective_from" not in c
    # candidato != asercion: no efecto juridico en el artefacto.
    assert "legal_effect" not in c
    assert "entitlement" not in c


def test_c05_record_added_is_entity_record_appeared():
    """record added => ENTITY_RECORD_APPEARED; presencia != entitlement."""
    result = classify_changes(
        _comparison(_changes(added=["PSD_PI:NEW_1"]))
    )
    c = _only(result)
    assert c["candidate_type"] == "ENTITY_RECORD_APPEARED"
    assert c["admissibility"] == "SUPPORTED"
    assert c["effective_basis"] == "EVIDENCE_AS_OF"
    assert "effective_from" not in c
    assert "field_path" not in c or c.get("field_path") == []


def test_c06_record_removed_admissible_is_disappeared_never_withdrawal():
    """record removed entre capturas completas => ENTITY_RECORD_DISAPPEARED;
    nunca withdrawal por si solo (anti-regla congelada)."""
    result = classify_changes(
        _comparison(_changes(removed=["PSD_PI:GONE_1"]))
    )
    c = _only(result)
    assert c["candidate_type"] == "ENTITY_RECORD_DISAPPEARED"
    assert c["admissibility"] == "SUPPORTED"
    assert c["effective_basis"] == "EVIDENCE_AS_OF"
    assert c["candidate_type"] != "ROOT_WITHDRAWAL_CANDIDATE"


def test_c07_record_removed_partial_capture_is_blocked():
    """removed en captura parcial => BLOCKED + NO_REMOVAL_ADMISSIBLE
    (finding heredado de G2-B)."""
    result = classify_changes(
        _comparison(
            _changes(removed=["PSD_PI:GONE_1"]),
            removal_admissible=False,
            findings=[
                {
                    "classification": "NO_REMOVAL_ADMISSIBLE",
                    "detail": "slice no completo",
                }
            ],
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "ENTITY_RECORD_DISAPPEARED"
    assert c["admissibility"] == "BLOCKED"
    assert c["blocker"] == "NO_REMOVAL_ADMISSIBLE"
    assert c["effective_basis"] == "UNKNOWN"


def test_c08_changes_outside_catalog_are_unclassified_blocked():
    """Fail-closed bilateral: sin regla preregistrada no se inventa un
    evento regulatorio NI se declara NOT_REGULATORY."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("services", "FR"),
                        "old": ["PS_01"],
                        "new": ["PS_01", "PS_02"],
                    },
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("properties", "ENT_NAM"),
                        "old": "Old Name",
                        "new": "New Name",
                    },
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("ca_owner_id",),
                        "old": "A",
                        "new": "B",
                    },
                ]
            )
        )
    )
    assert len(result["candidates"]) == 3
    for c in result["candidates"]:
        assert c["candidate_type"] == "UNCLASSIFIED_STRUCTURAL_CHANGE"
        assert c["admissibility"] == "BLOCKED"
        assert c["blocker"] == "NO_PREREGISTERED_RULE"


def test_c09_ent_aut_rewrite_is_not_an_append_event():
    """ENT_AUT modificado sin append estricto (prefijo distinto, lista
    encogida o campo desaparecido) => UNCLASSIFIED, nunca retirada."""
    cases = [
        # prefijo reescrito
        {"old": ["2020-01-01", "2020-06-01"], "new": ["2020-01-01", "2021-01-01"], "kind": "changed"},
        # la lista encoge
        {"old": ["2020-01-01", "2020-06-01"], "new": ["2020-01-01"], "kind": "changed"},
        # campo desaparecido: removed nunca implica retirada
        {"old": ["2020-01-01"], "kind": "removed"},
        # valor no-lista
        {"old": "NO", "new": ["2020-01-01"], "kind": "changed"},
    ]
    for ch in cases:
        change = {
            "record_key": "PSD_PI:E1",
            "path": ("properties", "ENT_AUT"),
            **ch,
        }
        result = classify_changes(_comparison(_changes(changed=[change])))
        c = _only(result)
        assert c["candidate_type"] == "UNCLASSIFIED_STRUCTURAL_CHANGE"
        assert c["admissibility"] == "BLOCKED"
        assert "effective_from" not in c


def test_c10_observation_bounds_and_no_fabricated_dates():
    """Cada candidato cota el cambio a (observed_after, observed_by]
    desde los retrieved_at de las observaciones (contrato §7)."""
    result = classify_changes(
        _comparison(_changes(added=["PSD_PI:N1"], removed=["PSD_PI:G1"]))
    )
    for c in result["candidates"]:
        assert c["left_observation_id"] == LEFT_ID
        assert c["right_observation_id"] == RIGHT_ID
        assert c["observed_after"] == "2026-09-13"
        assert c["observed_by"] == "2026-09-14T19:36:43Z"
        assert "effective_from" not in c  # EVIDENCE_AS_OF


def test_c11_real_frozen_comparison_produces_zero_candidates():
    """Replay sobre el artefacto real congelado: 0/0/0 => 0 candidatos.
    Es un resultado legitimo: la capa se ejecuta y no hay nada que
    clasificar."""
    doc = strict_json_loads(REAL_COMPARISON.read_text(encoding="utf-8"))
    result = classify_changes(doc)
    assert result["candidates"] == []
    assert result["summary"]["input"] == {"added": 0, "removed": 0, "changed": 0}
    assert result["summary"]["candidates"] == 0


def test_real_pair_0915_first_type_bc_classifies_candidates():
    """Replay sobre el primer Type-B/C real del corpus (task g2-c1):
    EBA 20260914 -> 20260915, added=67 removed=0 changed=312.

    Resultado por contrato:
    - 67 records added => ENTITY_RECORD_APPEARED (SUPPORTED,
      EVIDENCE_AS_OF; presencia != entitlement).
    - 312 changed en paths fuera del catalogo (ENT_ADD, ENT_NAM,
      ENT_POS_COD, ENT_TOW_CIT_RES, DER_CHI_ENT_AUT — ninguno es
      ENT_AUT ni services.ES) => UNCLASSIFIED_STRUCTURAL_CHANGE,
      BLOCKED + NO_PREREGISTERED_RULE. Fail-closed: ni evento
      inventado ni NOT_REGULATORY inventado.
    - La fuente no publica fecha juridica: cero effective_from
      fabricados; el cambio queda acotado a (observed_after,
      observed_by].
    """
    doc = strict_json_loads(REAL_COMPARISON_0915.read_text(encoding="utf-8"))
    result = classify_changes(doc)
    assert result["summary"] == {
        "input": {"added": 67, "removed": 0, "changed": 312},
        "candidates": 379,
        "supported": 67,
        "blocked": 312,
    }

    appeared = [
        c for c in result["candidates"]
        if c["candidate_type"] == "ENTITY_RECORD_APPEARED"
    ]
    assert len(appeared) == 67
    for c in appeared:
        assert c["admissibility"] == "SUPPORTED"
        assert c["effective_basis"] == "EVIDENCE_AS_OF"
        assert "effective_from" not in c
        assert "entitlement" not in c

    unclassified = [
        c for c in result["candidates"]
        if c["candidate_type"] == "UNCLASSIFIED_STRUCTURAL_CHANGE"
    ]
    assert len(unclassified) == 312
    non_catalog_paths = {
        ("properties", "DER_CHI_ENT_AUT"),
        ("properties", "ENT_ADD"),
        ("properties", "ENT_NAM"),
        ("properties", "ENT_POS_COD"),
        ("properties", "ENT_TOW_CIT_RES"),
    }
    for c in unclassified:
        assert c["admissibility"] == "BLOCKED"
        assert c["blocker"] == "NO_PREREGISTERED_RULE"
        assert c["effective_basis"] == "UNKNOWN"
        assert tuple(c["field_path"]) in non_catalog_paths

    # Sin cambios en ENT_AUT / services.ES: cero candidatos de
    # retirada, reautorizacion o capability.
    types = {c["candidate_type"] for c in result["candidates"]}
    assert types == {
        "ENTITY_RECORD_APPEARED",
        "UNCLASSIFIED_STRUCTURAL_CHANGE",
    }

    # Intervalo de observacion bilateral; nunca fecha juridica.
    for c in result["candidates"]:
        assert c["observed_after"] == "2026-09-14T19:36:43Z"
        assert c["observed_by"] == "2026-09-15T02:35:43Z"
        assert "effective_from" not in c


def test_c12_non_comparable_yields_zero_candidates():
    """NON_COMPARABLE_* nunca produce candidatos: los cambios no son
    observables bajo una normalizacion comun (contrato §4)."""
    result = classify_changes(
        _comparison(
            _changes(
                added=["PSD_PI:N1"],
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("services", "ES"),
                        "old": ["PS_01"],
                        "new": ["PS_01", "PS_02"],
                    }
                ],
            ),
            comparable=False,
            findings=[
                {
                    "classification": "NON_COMPARABLE_NORMALIZATION_VERSION",
                    "detail": "v1 vs v2",
                }
            ],
        )
    )
    assert result["candidates"] == []
    assert any(
        f["classification"] == "NON_COMPARABLE_NORMALIZATION_VERSION"
        for f in result["comparison_findings"]
    )


def test_c13_ent_aut_multi_append_emits_one_candidate_per_date():
    """old=[a1] -> new=[a1,w1,a2]: dos transiciones en el log ENT_AUT,
    un candidato por fecha anadida, en orden cronologico."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("properties", "ENT_AUT"),
                        "old": ["2020-01-01"],
                        "new": ["2020-01-01", "2026-09-10", "2026-09-11"],
                    }
                ]
            )
        )
    )
    assert [c["candidate_type"] for c in result["candidates"]] == [
        "ROOT_WITHDRAWAL_CANDIDATE",
        "ROOT_REAUTHORISATION_CANDIDATE",
    ]
    assert [c["effective_from"] for c in result["candidates"]] == [
        "2026-09-10",
        "2026-09-11",
    ]


def test_c14_ent_aut_field_appeared_counts_as_append_from_empty():
    """ENT_AUT ausente -> [d1] equivale a anadir en posicion impar
    (nueva fecha de autorizacion declarada por la fuente)."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_AG:AG1",
                        "kind": "added",
                        "path": ("properties", "ENT_AUT"),
                        "new": ["2026-09-12"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "ROOT_REAUTHORISATION_CANDIDATE"
    assert c["effective_from"] == "2026-09-12"


def test_c15_services_es_field_removed_is_capability_disappeared():
    """services.ES desaparece entero => todos sus codigos son '-'."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "removed",
                        "path": ("services", "ES"),
                        "old": ["PS_01", "PS_070"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "CAPABILITY_DISAPPEARED_CANDIDATE"
    assert c["removed_codes"] == ["PS_01", "PS_070"]


def test_c16_deterministic_output():
    """Mismos inputs => mismos bytes canonicos."""
    comp = _comparison(
        _changes(
            added=["PSD_PI:N1"],
            changed=[
                {
                    "record_key": "PSD_PI:E1",
                    "kind": "changed",
                    "path": ["properties", "ENT_AUT"],
                    "old": ["2020-01-01"],
                    "new": ["2020-01-01", "2026-09-10"],
                }
            ],
        )
    )
    a = classify_changes(comp)
    b = classify_changes(json.loads(canonical_json(comp)))
    assert canonical_json(a) == canonical_json(b)


def test_c17_unknown_series_has_no_preregistered_rules():
    """Sin catalogo preregistrado para la serie => todo queda
    UNCLASSIFIED/BLOCKED (fail-closed, nunca crash)."""
    result = classify_changes(
        _comparison(
            _changes(
                added=["K1"],
                changed=[
                    {
                        "record_key": "K2",
                        "kind": "changed",
                        "path": ("services", "ES"),
                        "old": ["PS_01"],
                        "new": [],
                    }
                ],
            ),
            series="cnmv-algun-registro|full",
        )
    )
    assert result["candidates"]
    for c in result["candidates"]:
        assert c["candidate_type"] == "UNCLASSIFIED_STRUCTURAL_CHANGE"
        assert c["admissibility"] == "BLOCKED"


def test_json_loaded_paths_are_accepted():
    """Los artefactos JSON traen path como lista; se acepta igual que la
    tupla del differ en memoria."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ["services", "ES"],
                        "old": ["PS_01"],
                        "new": ["PS_01", "PS_02"],
                    }
                ]
            )
        )
    )
    assert _only(result)["candidate_type"] == "CAPABILITY_APPEARED_CANDIDATE"


def test_scalar_and_set_service_values_are_sets():
    """services.ES admite str o lista en la normalizacion EBA; el delta
    se calcula sobre el conjunto de codigos."""
    result = classify_changes(
        _comparison(
            _changes(
                changed=[
                    {
                        "record_key": "PSD_PI:E1",
                        "kind": "changed",
                        "path": ("services", "ES"),
                        "old": "PS_01",
                        "new": ["PS_01", "PS_070"],
                    }
                ]
            )
        )
    )
    c = _only(result)
    assert c["candidate_type"] == "CAPABILITY_APPEARED_CANDIDATE"
    assert c["added_codes"] == ["PS_070"]
