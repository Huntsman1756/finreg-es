"""POST-G0 — Piloto OpenLineage: validacion del export de linaje.

El export ``openlineage/*.json`` es una proyeccion read-only de los
artefactos congelados G0.5/G0.6/G0.7 a OpenLineage 2.0.2:

- cada evento valida contra la spec oficial vendored
  (``schemas/openlineage/OpenLineage-2.0.2.schema.json``) con
  FormatChecker activo (uuid, date-time, uri se verifican de verdad);
- cada custom facet ``finreg_*`` valida contra su schema versionado en
  ``schemas/openlineage/facets/v1/``;
- replay determinista: regenerar produce bytes identicos (canonical
  FINREG_CANONICAL_JSON_V1) y runIds UUIDv5 estables;
- guardarrail: 0 semantica regulatoria migrada a OpenLineage;
- el exportador es stdlib-only, sin red y read-only sobre fixtures.

``jsonschema`` es dependencia de tooling, nunca runtime.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from finreg_es.canonical import canonical_json, strict_json_loads
from finreg_es.openlineage_export import (
    EXPORTER_VERSION,
    JOB_NAMESPACE,
    NS_ARTIFACTS,
    NS_SNAPSHOTS,
    OL_SCHEMA_URL,
    PRODUCER,
    build_events,
    export,
)

ROOT = Path(__file__).parents[2]
OL_DIR = ROOT / "schemas" / "openlineage"
FACETS_DIR = OL_DIR / "facets" / "v1"
EXPORT_DIR = ROOT / "openlineage"

OL_SPEC_PATH = OL_DIR / "OpenLineage-2.0.2.schema.json"
JOBTYPE_PATH = OL_DIR / "JobTypeJobFacet-2.0.2.schema.json"

# Pin del vendor: si alguien sustituye la spec, el hash lo delata.
OL_SPEC_SHA256 = "69f68bee00b9beac88a87059c0102410e7bb05f3f43c46d02a0409831eceb0d2"
JOBTYPE_SHA256 = "0716fc27d8f4ac450e64bfd25de002523f313d03e510bbc90d212d3af6259d1c"

FACET_SCHEMA_BY_KEY = {
    "finreg_snapshot": "finreg-snapshot-facet.schema.json",
    "finreg_artifact": "finreg-artifact-facet.schema.json",
    "finreg_run_contract": "finreg-run-contract-run-facet.schema.json",
    "finreg_job_contract": "finreg-job-contract-job-facet.schema.json",
}

PILOT_MANIFEST = ROOT / "openlineage" / "pilot-manifest.json"

# Claves cuya presencia indicaria fuga de semantica regulatoria a OL.
FORBIDDEN_SEMANTIC_KEYS = {
    "legal_effect",
    "entry_mechanism",
    "territorial_basis",
    "expected_assessment",
    "expected_reason",
    "coverage",
    "case_id",
    "claim_id",
    "assertion_id",
    "entity_class",
    "activity",
    "jurisdiction",
    "effective_from",
    "effective_to",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> Registry:
    resources = [
        (
            "https://openlineage.io/spec/2-0-2/OpenLineage.json",
            Resource.from_contents(
                _load(OL_SPEC_PATH), default_specification=DRAFT202012
            ),
        ),
        (
            "https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json",
            Resource.from_contents(
                _load(JOBTYPE_PATH), default_specification=DRAFT202012
            ),
        ),
    ]
    # facets finreg por $id (URN): resuelve los $ref al schema comun
    for path in sorted(FACETS_DIR.glob("*.schema.json")):
        doc = _load(path)
        resources.append(
            (doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
        )
    return Registry().with_resources(resources)


REGISTRY = _registry()


def _ol_validator():
    return jsonschema.Draft202012Validator(
        _load(OL_SPEC_PATH),
        registry=REGISTRY,
        format_checker=jsonschema.FormatChecker(),
    )


def _facet_validator(schema_file: str):
    return jsonschema.Draft202012Validator(
        _load(FACETS_DIR / schema_file),
        registry=REGISTRY,
        format_checker=jsonschema.FormatChecker(),
    )


def _event_files() -> list[Path]:
    return sorted(
        p for p in EXPORT_DIR.glob("*.json") if p.name != "pilot-manifest.json"
    )


def test_vendored_spec_is_pinned():
    """La spec vendored es exactamente OpenLineage 2.0.2 oficial."""
    assert hashlib.sha256(OL_SPEC_PATH.read_bytes()).hexdigest() == OL_SPEC_SHA256
    assert hashlib.sha256(JOBTYPE_PATH.read_bytes()).hexdigest() == JOBTYPE_SHA256
    assert _load(OL_SPEC_PATH)["$id"] == OL_SCHEMA_URL


@pytest.mark.parametrize("path", _event_files(), ids=lambda p: p.name)
def test_event_validates_against_official_spec(path):
    _ol_validator().validate(_load(path))


@pytest.mark.parametrize("path", _event_files(), ids=lambda p: p.name)
def test_custom_facets_validate(path):
    event = _load(path)
    errors = []
    for location, container in (
        ("run", event.get("run", {}).get("facets", {})),
        ("job", event["job"].get("facets", {})),
    ):
        for key, facet in container.items():
            if key in FACET_SCHEMA_BY_KEY:
                errors.extend(
                    _facet_validator(FACET_SCHEMA_BY_KEY[key]).iter_errors(facet)
                )
            else:
                # facets estandar (jobType) validan contra su schema oficial
                assert key == "jobType"
                jobtype_doc = _load(JOBTYPE_PATH)
                jsonschema.Draft202012Validator(
                    jobtype_doc, registry=REGISTRY
                ).validate({"jobType": facet})
    for side in ("inputs", "outputs"):
        for ds in event.get(side, []):
            for key, facet in ds.get("facets", {}).items():
                assert key in FACET_SCHEMA_BY_KEY, (path.name, key)
                errors.extend(
                    _facet_validator(FACET_SCHEMA_BY_KEY[key]).iter_errors(facet)
                )
    assert not errors, [e.message for e in errors]


def test_replay_is_byte_identical():
    """Regenerar el export produce exactamente los mismos bytes."""
    regenerated = build_events(ROOT)
    on_disk = {p.name: p.read_bytes() for p in _event_files()}
    assert set(regenerated) == set(on_disk)
    for name, event in regenerated.items():
        assert canonical_json(event).encode("utf-8") == on_disk[name], name


def test_export_writes_only_inside_out_dir(tmp_path):
    written = export(ROOT, tmp_path)
    assert len(written) == len(_event_files())
    for path in written:
        assert path.parent == tmp_path
        assert path.read_bytes() == canonical_json(
            strict_json_loads(path.read_text(encoding="utf-8"))
        ).encode("utf-8")


def test_run_ids_are_stable_uuid5():
    events = build_events(ROOT)
    by_run = {}
    for event in events.values():
        if "run" not in event:
            continue  # JobEvent: sin run por diseno
        run_id = event["run"]["runId"]
        parsed = uuid.UUID(run_id)
        assert parsed.version == 5
        key = (event["job"]["name"], run_id)
        by_run.setdefault(key, set()).add(event["eventType"])
    # cada run FinReg produce exactamente START + COMPLETE
    assert all(types == {"START", "COMPLETE"} for types in by_run.values())
    # 4 RunEvents con run: 3 extraction + 1 assessment
    assert len(by_run) == 4


def test_jobevents_carry_no_run():
    """provenance/derivation son JobEvents: linaje sin run, porque no hay
    instante de ejecucion registrado."""
    events = build_events(ROOT)
    observed_at = _load(PILOT_MANIFEST)["lineage_observed_at"]
    jobevents = [e for e in events.values() if "run" not in e]
    assert len(jobevents) == 2
    for event in jobevents:
        assert "eventType" not in event
        assert "run" not in event
        contract = event["job"]["facets"]["finreg_job_contract"]
        # sin conceptos de ejecucion en un facet de job
        assert "finreg_run_contract" not in event["job"]["facets"]
        assert "finreg_run_id" not in contract
        assert "executed_at" not in contract
        # eventTime = instante del export (manifest), distinto del freeze
        assert event["eventTime"] == observed_at
        assert contract["freeze_commit_time"] != observed_at


def test_pilot_manifest_is_part_of_replay_contract(monkeypatch):
    """``lineage_observed_at`` es un input del piloto: si cambia, el
    replay produce bytes distintos en exactamente los JobEvents — el
    manifest queda dentro del contrato de reproduccion."""
    import finreg_es.openlineage_export as olx

    base = build_events(ROOT)
    original_load = olx._load

    def drifted_load(root, rel):
        doc = original_load(root, rel)
        if rel == olx.PILOT_MANIFEST_PATH:
            doc = {**doc, "lineage_observed_at": "2000-01-01T00:00:00Z"}
        return doc

    monkeypatch.setattr(olx, "_load", drifted_load)
    drifted = build_events(ROOT)
    changed = {
        name
        for name in drifted
        if canonical_json(drifted[name]) != canonical_json(base[name])
    }
    assert changed == {n for n in drifted if n.endswith(".jobevent.json")}


def test_event_pairs_share_run_and_job():
    """START y COMPLETE de un mismo run referencian el mismo runId/job."""
    events = build_events(ROOT)
    starts = {
        e["run"]["runId"]: e
        for e in events.values()
        if e.get("eventType") == "START"
    }
    for event in events.values():
        if event.get("eventType") == "COMPLETE":
            start = starts[event["run"]["runId"]]
            assert start["job"] == event["job"]
            assert start["inputs"] == event["inputs"]
            assert start["outputs"] == event["outputs"]


def _contract(event: dict) -> dict:
    """El contrato FinReg viaja como run facet (RunEvent,
    ``finreg_run_contract``) o job facet (JobEvent,
    ``finreg_job_contract``) segun el carrier."""
    if "run" in event:
        return event["run"]["facets"]["finreg_run_contract"]
    return event["job"]["facets"]["finreg_job_contract"]


def test_lineage_graph_edges_match_recorded_contracts():
    """Las aristas del grafo OL reflejan los pins sha256 registrados por
    los propios artefactos FinReg (nada inventado)."""
    events = build_events(ROOT)
    complete = [
        e for e in events.values() if e.get("eventType") == "COMPLETE"
    ] + [e for e in events.values() if "run" not in e]
    by_job = {e["job"]["name"]: e for e in complete}

    def out_names(event):
        return {(d["namespace"], d["name"]) for d in event["outputs"]}

    def in_names(event):
        return {(d["namespace"], d["name"]) for d in event["inputs"]}

    def artifact_sha(event, ds_name):
        for ds in event["inputs"] + event["outputs"]:
            if ds["name"] == ds_name:
                return ds["facets"]["finreg_artifact"]["sha256"]
        raise KeyError(ds_name)

    # extraction 003 -> provenance: run_result_sha registrado en el ledger
    prov = by_job["finreg.provenance"]
    ext3_name = "extraction-run/g0.5-a-2026-09-13-003"
    assert (NS_ARTIFACTS, ext3_name) in in_names(prov)
    assert (
        _contract(prov)["input_contract"]["extraction_run_result_sha"]
        == "6c59c36ddf48116d826eb79b12c4824d5d12a0be3d8fa2cd6ac3e311e23dc12b"
    )

    # provenance -> derivation/assessment: claims_ledger_sha256 = file sha
    claims_name = "claims/g0.6-claim-provenance-g0.5-a-2026-09-13-003"
    assert (NS_ARTIFACTS, claims_name) in out_names(prov)
    ledger_sha = artifact_sha(prov, claims_name)
    for job in ("finreg.derivation", "finreg.assessment"):
        ev = by_job[job]
        assert (NS_ARTIFACTS, claims_name) in in_names(ev)
        assert (
            _contract(ev)["input_contract"]["claims_ledger_sha256"]
            == ledger_sha
        )

    # derivation -> assessment: derived_assertions_sha256 = file sha
    assertions_name = "assertions/derived-assertions-g0.5-a-003"
    deriv = by_job["finreg.derivation"]
    assert (NS_ARTIFACTS, assertions_name) in out_names(deriv)
    assertions_sha = artifact_sha(deriv, assertions_name)
    assert (
        _contract(by_job["finreg.assessment"])["input_contract"][
            "derived_assertions_sha256"
        ]
        == assertions_sha
    )

    # snapshots: solo los 4 consumidos por el run, con sha del manifest
    manifest = _load(ROOT / "fixtures" / "g0.5" / "sources" / "manifest.json")
    manifest_sha = {s["snapshot_file"]: s["sha256"] for s in manifest["snapshots"]}
    ext_events = {
        _contract(e)["finreg_run_id"]: e
        for e in complete
        if e["job"]["name"] == "finreg.extraction"
    }
    assert set(ext_events) == {
        "g0.5-a-2026-09-13-001",
        "g0.5-a-2026-09-13-002",
        "g0.5-a-2026-09-13-003",
    }
    for run_id, ev in ext_events.items():
        snap_facets = [
            d["facets"]["finreg_snapshot"]
            for d in ev["inputs"]
            if "finreg_snapshot" in d["facets"]
        ]
        assert len(snap_facets) == 4
        for facet in snap_facets:
            assert manifest_sha[facet["snapshot_file"]] == facet["sha256"]
            assert facet["authority"] and facet["register_id"]


def test_no_regulatory_semantics_in_events():
    """Guardarrail: el export no migra vocabulario regulatorio."""

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in FORBIDDEN_SEMANTIC_KEYS, key
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for event in build_events(ROOT).values():
        walk(event)


def test_exporter_is_stdlib_and_offline():
    """El exportador no importa red ni dependencias externas."""
    import ast

    tree = ast.parse(
        (ROOT / "finreg_es" / "openlineage_export.py").read_text(
            encoding="utf-8"
        )
    )
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            imported.add("finreg_es")
    forbidden = {"urllib", "requests", "socket", "http",
                 "jsonschema", "openlineage"}
    assert not (imported & forbidden), imported & forbidden


def test_namespaces_and_producer():
    events = build_events(ROOT)
    seen: dict[tuple[str, str], dict] = {}
    for event in events.values():
        assert event["producer"] == PRODUCER
        assert event["producer"].endswith(EXPORTER_VERSION)
        assert event["schemaURL"] == OL_SCHEMA_URL
        assert event["job"]["namespace"] == JOB_NAMESPACE
        for ds in event.get("inputs", []) + event.get("outputs", []):
            assert ds["namespace"] in {NS_SNAPSHOTS, NS_ARTIFACTS}
            assert ds["name"] and "finreg://" not in ds["name"]
            seen.setdefault((ds["namespace"], ds["name"]), ds)
    # la pareja (namespace, name) es la identidad; el sha256 declarado
    # para un mismo path es consistente en todos los eventos
    path_sha: dict[str, str] = {}
    for event in events.values():
        for ds in event.get("inputs", []) + event.get("outputs", []):
            facet = ds["facets"].get("finreg_artifact")
            if facet and "path" in facet:
                path_sha.setdefault(facet["path"], facet["sha256"])
                assert path_sha[facet["path"]] == facet["sha256"]
