"""Post-G0 — Contratos JSON Schema v1 de los artefactos.

Los esquemas de ``schemas/v1/`` son el contrato estructural publico de
los artefactos: validan forma, no semantica regulatoria (que vive en
coverage.py/derivation.py/semantics.py y en los tests). Versionados e
inmutables: una ampliacion compatible se estudia expresamente; una
ruptura va a ``schemas/v2/``.

``jsonschema`` es dependencia de tooling (extra ``tooling`` en
pyproject): el runtime core sigue stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


ROOT = Path(__file__).parents[2]
SCHEMA_V1 = ROOT / "schemas" / "v1"


def _registry() -> Registry:
    resources = []
    for path in sorted(SCHEMA_V1.rglob("*.schema.json")):
        uri = path.relative_to(SCHEMA_V1).as_posix()
        doc = json.loads(path.read_text(encoding="utf-8"))
        resources.append((uri, Resource.from_contents(doc, default_specification=DRAFT202012)))
    return Registry().with_resources(resources)


REGISTRY = _registry()


def _validator(schema_name: str):
    doc = json.loads(
        (SCHEMA_V1 / f"{schema_name}.schema.json").read_text(encoding="utf-8")
    )
    return jsonschema.Draft202012Validator(doc, registry=REGISTRY)


# Superficie contractual: glob -> schema. Todo JSON de fixtures debe
# validar contra un esquema o aparecer explicitamente en UNSCOPED.
ARTIFACT_MAP = {
    "fixtures/contracts/*.json": "source-contract",
    "fixtures/g0.5/corpus/entities.json": "entity-corpus",
    "fixtures/g0.5/corpus/ground-truth.json": "ground-truth",
    "fixtures/g0.5/sources/manifest.json": "source-manifest",
    "fixtures/g0.5/runs/*.json": "extraction-run",
    "fixtures/g0.6/claim-provenance-*.json": "claim-ledger",
    "fixtures/g0.7/derivation-rules.json": "derivation-ruleset",
    "fixtures/g0.7/derived-assertions-*.json": "derived-assertions",
    "fixtures/g0.7/assessment-cases.json": "assessment-cases",
    "fixtures/g0.7/runs/*.json": "assessment-run",
    "fixtures/g0.7/audit/*.json": "run-audit",
}

# Artefactos historicos de analisis / fixtures sinteticos fuera del
# contrato v1 (documentado en el ADR; pueden entrar en una v1.1).
UNSCOPED = {
    "fixtures/g0.5/audit/g0.5-b-corpus-audit.json",
    "fixtures/g0.5/audit/g0.5-b-preregistration-resolution.json",
    "fixtures/g0.5/audit/gleif-lei-lookups-2026-09-13.json",
    "fixtures/g0.6/verification-report.json",
    "fixtures/g0.6/temporal/suspect-source-as-of.json",
    "fixtures/regulatory/assertions.json",
    "fixtures/regulatory/identity-index.json",
    "fixtures/regulatory/scenarios.json",
}

# Capturas raw de autoridad: contenido controlado por BdE/CNMV/EBA/ESMA,
# no por FinReg — jamas se les impone rigidez de contrato.
UNSCOPED_GLOBS = ["fixtures/g0.5/sources/raw/*.json"]


def _covered_files() -> dict[Path, str]:
    out = {}
    for pattern, schema in ARTIFACT_MAP.items():
        for path in sorted(ROOT.glob(pattern)):
            out[path.relative_to(ROOT)] = schema
    return out


def test_every_fixture_json_is_scoped_or_declared():
    """Ningun JSON de fixtures escapa del contrato sin declaracion."""
    all_json = {
        p.relative_to(ROOT)
        for p in (ROOT / "fixtures").rglob("*.json")
    }
    covered = set(_covered_files())
    unscoped = {Path(p) for p in UNSCOPED}
    for pattern in UNSCOPED_GLOBS:
        unscoped |= {p.relative_to(ROOT) for p in ROOT.glob(pattern)}
    assert all_json == covered | unscoped


@pytest.mark.parametrize(
    "path,schema_name",
    sorted(_covered_files().items(), key=lambda kv: str(kv[0])),
    ids=lambda v: str(v),
)
def test_frozen_artifact_validates_and_bytes_unchanged(path, schema_name):
    """Artefacto congelado: valida contra su schema versionado y la
    validacion no toca ni un byte (validacion != canonicalizacion)."""
    raw = (ROOT / path).read_bytes()
    before = hashlib.sha256(raw).hexdigest()
    doc = json.loads(raw.decode("utf-8"))
    _validator(schema_name).validate(doc)
    assert hashlib.sha256(raw).hexdigest() == before


def _mutate(schema_name: str, doc: dict, mutate) -> dict:
    import copy
    mutated = copy.deepcopy(doc)
    mutate(mutated)
    return mutated


def _first_artifact(schema_name: str) -> dict:
    for pattern, name in ARTIFACT_MAP.items():
        if name == schema_name:
            path = sorted(ROOT.glob(pattern))[0]
            return json.loads(path.read_text(encoding="utf-8"))
    raise KeyError(schema_name)


@pytest.mark.parametrize("schema_name", sorted(set(ARTIFACT_MAP.values())))
def test_negative_missing_required_property_fails(schema_name):
    schema = json.loads(
        (SCHEMA_V1 / f"{schema_name}.schema.json").read_text(encoding="utf-8")
    )
    required_key = schema["required"][0]
    doc = _mutate(
        schema_name,
        _first_artifact(schema_name),
        lambda d: d.pop(required_key),
    )
    assert not _validator(schema_name).is_valid(doc)


@pytest.mark.parametrize("schema_name", sorted(set(ARTIFACT_MAP.values())))
def test_negative_unknown_property_fails_on_closed_contract(schema_name):
    doc = _mutate(
        schema_name,
        _first_artifact(schema_name),
        lambda d: d.__setitem__("unexpected_extra_field", 1),
    )
    assert not _validator(schema_name).is_valid(doc)


def test_negative_wrong_enum_fails():
    doc = _first_artifact("assessment-cases")
    doc["cases"][0]["expected_assessment"] = "NOT_A_REAL_ASSESSMENT"
    assert not _validator("assessment-cases").is_valid(doc)


def test_negative_wrong_primitive_type_fails():
    doc = _first_artifact("claim-ledger")
    doc["claims"][0]["snapshot_sha256"] = 12345
    assert not _validator("claim-ledger").is_valid(doc)


def test_negative_bad_sha256_pattern_fails():
    doc = _first_artifact("assessment-run")
    doc["run"]["code_sha"] = "zz" * 32
    assert not _validator("assessment-run").is_valid(doc)


def test_schemas_do_not_encode_regulatory_semantics():
    """Guardrail: ningun schema contiene la logica fail-closed (if/then
    sobre efectos legales, joins de identidad, negativos por ausencia).
    La semantica vive en el runtime, no en la capa contractual."""
    forbidden = {"if", "then", "else", "dependencies", "dependentRequired",
                 "format"}
    for path in SCHEMA_V1.rglob("*.schema.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))

        def walk(node):
            if isinstance(node, dict):
                assert not (forbidden & node.keys()), (
                    f"{path.name}: conditional/format composition "
                    f"{forbidden & node.keys()}"
                )
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(doc)


def test_runtime_core_has_no_jsonschema_dependency():
    """finreg_es sigue stdlib-only: jsonschema no aparece en el core."""
    for path in (ROOT / "finreg_es").rglob("*.py"):
        assert "jsonschema" not in path.read_text(encoding="utf-8"), path
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    deps_section = pyproject.split("[project.optional-dependencies]")[0]
    assert "jsonschema" not in deps_section
