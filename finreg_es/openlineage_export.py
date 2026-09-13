"""POST-G0 — Piloto OpenLineage: exportador read-only FinReg -> OpenLineage 2.0.2.

El export NO es el modelo de linaje de FinReg: los 337 claims del
ledger G0.6 y las ``SourceAssertion`` siguen siendo la fuente de verdad.
Esto es una proyeccion de interoperabilidad a granularidad de artefacto:

    snapshots de autoridad
      -> job finreg.extraction   (runs g0.5-a-*)
      -> artefacto extraction-run
      -> job finreg.provenance   (ledger G0.6)
      -> claim ledger
      -> job finreg.derivation   (ruleset G0.7)
      -> derived assertions
      -> job finreg.assessment   (run g0.7-001)
      -> assessment run

Garantias: read-only sobre los artefactos congelados; sin red, sin
transporte, sin collector; salida canonica FINREG_CANONICAL_JSON_V1
(byte-identica en replay); runIds UUIDv5 estables derivados del run
FinReg (mismo input -> mismo UUID, nunca aleatorio).

``eventTime``: los pasos con ``executed_at`` registrado por el propio
artefacto (extraction, assessment) se emiten como ``RunEvent``
START+COMPLETE con ese instante. Los pasos sin tiempo de ejecucion
registrado (ledger G0.6, derived-assertions G0.7) NO se emiten como
RunEvent — no se conoce su instante de ejecucion real — sino como
``JobEvent`` estatico (spec 2.0.2: inputs/outputs sin ``run``). El
``eventTime`` de un JobEvent es ``lineage_observed_at``: el instante
declarado del export, fijado una vez en ``openlineage/pilot-manifest.json``
y reutilizado en todo replay (nunca ``datetime.now()``). El instante
historico de freeze del artefacto (``git log -1 --format=%cI``) viaja
aparte, como ``freeze_commit_time`` en el facet ``finreg_job_contract``.

Ver ``docs/openlineage-pilot.md`` para el mapping completo y
``schemas/openlineage/`` para spec vendored + custom facets.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .canonical import canonical_json, strict_json_loads
from .provenance import SOURCE_PROVENANCE

EXPORTER_VERSION = "FINREG_OL_EXPORT_V1"
PRODUCER = f"urn:finreg-es:openlineage-export:{EXPORTER_VERSION}"
OL_SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json"
JOBTYPE_FACET_SCHEMA_URL = (
    "https://openlineage.io/spec/facets/2-0-2/JobTypeJobFacet.json"
)

# OpenLineage identifica datasets por la pareja (namespace, name).
NS_SNAPSHOTS = "finreg://snapshots"   # capturas raw de autoridad
NS_ARTIFACTS = "finreg://artifacts"   # artefactos bajo control FinReg
JOB_NAMESPACE = "finreg-es.g0"
_FACET_URN_BASE = "urn:finreg-es:schema:openlineage:v1:"

PILOT_MANIFEST_PATH = "openlineage/pilot-manifest.json"
G05_RUNS_GLOB = "fixtures/g0.5/runs/*.json"
LEDGER_PATH = "fixtures/g0.6/claim-provenance-g0.5-a-003.json"
MANIFEST_PATH = "fixtures/g0.5/sources/manifest.json"
CORPUS_PATH = "fixtures/g0.5/corpus/entities.json"
GROUND_TRUTH_PATH = "fixtures/g0.5/corpus/ground-truth.json"
RULESET_PATH = "fixtures/g0.7/derivation-rules.json"
DERIVED_PATH = "fixtures/g0.7/derived-assertions-g0.5-a-003.json"
CASES_PATH = "fixtures/g0.7/assessment-cases.json"
ASSESSMENT_RUN_PATH = "fixtures/g0.7/runs/g0.7-001.json"

JOB_EXTRACTION = "finreg.extraction"
JOB_PROVENANCE = "finreg.provenance"
JOB_DERIVATION = "finreg.derivation"
JOB_ASSESSMENT = "finreg.assessment"


def _load(repo_root: Path, rel: str) -> dict[str, Any]:
    return strict_json_loads((repo_root / rel).read_text(encoding="utf-8"))


def _file_sha256(repo_root: Path, rel: str) -> str:
    return hashlib.sha256((repo_root / rel).read_bytes()).hexdigest()


def _freeze_time(repo_root: Path, rel: str) -> str:
    """Instante de freeze del artefacto: committer time de su ultimo commit."""
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%cI", "--", rel],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _run_uuid(job_name: str, finreg_run_id: str) -> str:
    """UUIDv5 estable: mismo (job, run FinReg) -> mismo runId en todo replay."""
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, f"urn:finreg-es:run:{job_name}:{finreg_run_id}"
        )
    )


def _facet_urn(name: str) -> str:
    return f"{_FACET_URN_BASE}{name}"


def _base_facet(name: str) -> dict[str, Any]:
    return {"_producer": PRODUCER, "_schemaURL": _facet_urn(name)}


def _snapshot_facet(
    item: dict[str, Any], source: str | None, retrieved_at: str
) -> dict[str, Any]:
    facet = {
        **_base_facet("finreg-snapshot"),
        "snapshot_file": item["snapshot_file"],
        "sha256": item["sha256"],
        "source_url": item["source_url"],
        "bytes": item["bytes"],
        # retrieved_at vive en el manifest a nivel captura, no por snapshot.
        "retrieved_at": retrieved_at,
        # source_as_of ausente se declara como null, nunca se rellena.
        "source_as_of": item.get("source_as_of"),
    }
    if item.get("hypothesis"):
        facet["hypothesis"] = item["hypothesis"]
    if item.get("embedded_payload_sha256"):
        facet["embedded_payload_sha256"] = item["embedded_payload_sha256"]
    if source is not None:
        prov = SOURCE_PROVENANCE[source]
        facet["source"] = source
        facet["register_id"] = prov["register_id"]
        facet["authority"] = prov["authority"]
    return facet


def _artifact_facet(
    kind: str,
    path: str | None = None,
    sha256: str | None = None,
    git_ref: str | None = None,
    artifact_version: str | None = None,
    result_sha256: str | None = None,
) -> dict[str, Any]:
    facet: dict[str, Any] = {**_base_facet("finreg-artifact"), "artifact_kind": kind}
    if path is not None:
        facet["path"] = path
    if sha256 is not None:
        facet["sha256"] = sha256
    if git_ref is not None:
        facet["git_ref"] = git_ref
    if artifact_version is not None:
        facet["artifact_version"] = artifact_version
    if result_sha256 is not None:
        facet["result_sha256"] = result_sha256
    return facet


def _dataset(
    name: str, facets: dict[str, Any], namespace: str = NS_ARTIFACTS
) -> dict[str, Any]:
    return {"namespace": namespace, "name": name, "facets": facets}


def _snapshot_dataset(
    item: dict[str, Any], source: str | None, retrieved_at: str
) -> dict[str, Any]:
    # name = sha256: la identidad del dataset es su contenido.
    return _dataset(
        item["sha256"],
        {"finreg_snapshot": _snapshot_facet(item, source, retrieved_at)},
        namespace=NS_SNAPSHOTS,
    )


def _job_facets() -> dict[str, Any]:
    return {
        "jobType": {
            "_producer": PRODUCER,
            "_schemaURL": JOBTYPE_FACET_SCHEMA_URL,
            "processingType": "BATCH",
            "integration": "FINREG",
            "jobType": "TASK",
        }
    }


def _run_contract(
    finreg_run_id: str,
    run_version: str,
    input_contract: dict[str, Any],
    executed_at: str,
    gate: str | None = None,
    code: dict[str, Any] | None = None,
    output_sha256: str | None = None,
    supersedes_run_id: str | None = None,
) -> dict[str, Any]:
    """FinregRunContractRunFacet — solo RunEvents con executed_at real."""
    facet: dict[str, Any] = {
        **_base_facet("finreg-run-contract"),
        "finreg_run_id": finreg_run_id,
        "finreg_run_version": run_version,
        "executed_at": executed_at,
        "input_contract": input_contract,
    }
    if gate is not None:
        facet["gate"] = gate
    if code is not None:
        facet["code"] = code
    if output_sha256 is not None:
        facet["output_sha256"] = output_sha256
    if supersedes_run_id is not None:
        facet["supersedes_run_id"] = supersedes_run_id
    return facet


def _job_contract(
    finreg_artifact_id: str,
    artifact_version: str,
    input_contract: dict[str, Any],
    freeze_commit_time: str,
    gate: str | None = None,
    output_sha256: str | None = None,
) -> dict[str, Any]:
    """FinregJobContractJobFacet — JobEvents: linaje estatico, sin
    conceptos de ejecucion (no run_id, no executed_at)."""
    facet: dict[str, Any] = {
        **_base_facet("finreg-job-contract"),
        "finreg_artifact_id": finreg_artifact_id,
        "finreg_artifact_version": artifact_version,
        "input_contract": input_contract,
        "freeze_commit_time": freeze_commit_time,
    }
    if gate is not None:
        facet["gate"] = gate
    if output_sha256 is not None:
        facet["output_sha256"] = output_sha256
    return facet


def _event(
    job_name: str,
    finreg_run_id: str,
    event_type: str,
    event_time: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, Any]:
    return {
        "eventTime": event_time,
        "eventType": event_type,
        "producer": PRODUCER,
        "schemaURL": OL_SCHEMA_URL,
        "job": {
            "namespace": JOB_NAMESPACE,
            "name": job_name,
            "facets": _job_facets(),
        },
        "run": {
            "runId": _run_uuid(job_name, finreg_run_id),
            "facets": {"finreg_run_contract": contract},
        },
        "inputs": sorted(inputs, key=lambda d: (d["namespace"], d["name"])),
        "outputs": sorted(
            outputs, key=lambda d: (d["namespace"], d["name"])
        ),
    }


def _emit(
    events: dict[str, dict[str, Any]],
    job_name: str,
    finreg_run_id: str,
    event_time: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    """Un run = 1 START + 1 COMPLETE (par exigido por la spec)."""
    for event_type in ("START", "COMPLETE"):
        filename = f"{job_name}.{finreg_run_id}.{event_type.lower()}.json"
        events[filename] = _event(
            job_name,
            finreg_run_id,
            event_type,
            event_time,
            inputs,
            outputs,
            contract,
        )


def _emit_jobevent(
    events: dict[str, dict[str, Any]],
    job_name: str,
    event_id: str,
    lineage_observed_at: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    contract: dict[str, Any],
) -> None:
    """JobEvent estatico: linaje del job sin ``run``.

    Se usa cuando no hay instante de ejecucion registrado: modelar un
    RunEvent requeriria un eventTime de ejecucion que no existe. El
    contrato FinReg viaja como job facet ``finreg_job_contract``;
    ``eventTime`` = ``lineage_observed_at`` (instante del export, fijado
    en el pilot manifest), distinto del ``freeze_commit_time`` historico.
    """
    events[f"{job_name}.{event_id}.jobevent.json"] = {
        "eventTime": lineage_observed_at,
        "producer": PRODUCER,
        "schemaURL": OL_SCHEMA_URL,
        "job": {
            "namespace": JOB_NAMESPACE,
            "name": job_name,
            "facets": {**_job_facets(), "finreg_job_contract": contract},
        },
        "inputs": sorted(inputs, key=lambda d: (d["namespace"], d["name"])),
        "outputs": sorted(outputs, key=lambda d: (d["namespace"], d["name"])),
    }


def build_events(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Construye el set completo de RunEvents desde los artefactos congelados.

    Devuelve ``{nombre_fichero: evento}``; la escritura canonica la hace
    ``export()``. Orden determinista por construccion de dict ordenado.
    """
    repo_root = repo_root.resolve()
    events: dict[str, dict[str, Any]] = {}
    lineage_observed_at = _load(repo_root, PILOT_MANIFEST_PATH)[
        "lineage_observed_at"
    ]

    manifest = _load(repo_root, MANIFEST_PATH)
    manifest_items = {s["snapshot_file"]: s for s in manifest["snapshots"]}
    manifest_ds = _dataset(
        f"manifest/{manifest['capture_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "source-manifest",
                path=MANIFEST_PATH,
                sha256=_file_sha256(repo_root, MANIFEST_PATH),
            )
        },
    )
    corpus = _load(repo_root, CORPUS_PATH)
    corpus_ds = _dataset(
        f"corpus/{corpus['corpus_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "entity-corpus",
                path=CORPUS_PATH,
                sha256=_file_sha256(repo_root, CORPUS_PATH),
            )
        },
    )
    ground_truth = _load(repo_root, GROUND_TRUTH_PATH)
    ground_truth_ds = _dataset(
        f"ground-truth/{ground_truth['ground_truth_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "ground-truth",
                path=GROUND_TRUTH_PATH,
                sha256=_file_sha256(repo_root, GROUND_TRUTH_PATH),
            )
        },
    )

    # ------------------------------------------------------------------
    # job finreg.extraction — un run por artefacto congelado g0.5-a-*
    for run_path in sorted(repo_root.glob(G05_RUNS_GLOB)):
        rel = run_path.relative_to(repo_root).as_posix()
        run_result = _load(repo_root, rel)
        meta = run_result["run"]
        file_to_source = {
            a["snapshot_file"]: a["source"] for a in run_result["attempts"]
        }
        snapshot_inputs = [
            _snapshot_dataset(
                manifest_items[snap],
                file_to_source.get(snap),
                manifest["retrieved_at"],
            )
            for snap in meta["source_snapshot_sha"]
        ]
        inputs = [
            *snapshot_inputs,
            corpus_ds,
            ground_truth_ds,
            _dataset(
                f"contracts/{meta['contracts_sha']}",
                {
                    "finreg_artifact": _artifact_facet(
                        "source-contracts", git_ref=meta["contracts_sha"]
                    )
                },
            ),
            _dataset(
                f"source-baseline/{meta['source_baseline_sha']}",
                {
                    "finreg_artifact": _artifact_facet(
                        "source-baseline", git_ref=meta["source_baseline_sha"]
                    )
                },
            ),
        ]
        output = _dataset(
            f"extraction-run/{meta['run_id']}",
            {
                "finreg_artifact": _artifact_facet(
                    "extraction-run",
                    path=rel,
                    sha256=_file_sha256(repo_root, rel),
                    artifact_version=meta["run_version"],
                    result_sha256=run_result["result_sha"],
                )
            },
        )
        contract = _run_contract(
            meta["run_id"],
            meta["run_version"],
            input_contract={
                "corpus_sha": meta["corpus_sha"],
                "corpus_manifest_sha256": meta["corpus_manifest_sha256"],
                "ground_truth_sha256": meta["ground_truth_sha256"],
                "source_baseline_sha": meta["source_baseline_sha"],
                "contracts_sha": meta["contracts_sha"],
                "source_snapshot_sha": meta["source_snapshot_sha"],
            },
            gate="G0.5-A",
            executed_at=meta["executed_at"],
            code={"sha256": meta["extractor_sha"], "commit": None},
            output_sha256=_file_sha256(repo_root, rel),
            supersedes_run_id=meta.get("supersedes_run_id"),
        )
        _emit(events, JOB_EXTRACTION, meta["run_id"], meta["executed_at"],
              inputs, [output], contract)

    # ------------------------------------------------------------------
    # job finreg.provenance — ledger G0.6 construido sobre el run sucesor
    ledger = _load(repo_root, LEDGER_PATH)
    ledger_meta = ledger["ledger"]
    source_run_rel = f"fixtures/g0.5/runs/{ledger_meta['run_id']}.json"
    source_run_ds = _dataset(
        f"extraction-run/{ledger_meta['run_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "extraction-run",
                path=source_run_rel,
                sha256=_file_sha256(repo_root, source_run_rel),
                result_sha256=ledger_meta["run_result_sha"],
            )
        },
    )
    ledger_ds = _dataset(
        f"claims/{ledger_meta['ledger_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "claim-ledger",
                path=LEDGER_PATH,
                sha256=_file_sha256(repo_root, LEDGER_PATH),
                artifact_version=ledger_meta["ledger_version"],
            )
        },
    )
    freeze_at = _freeze_time(repo_root, LEDGER_PATH)
    contract = _job_contract(
        ledger_meta["ledger_id"],
        ledger_meta["ledger_version"],
        input_contract={
            "extraction_run_id": ledger_meta["run_id"],
            "extraction_run_result_sha": ledger_meta["run_result_sha"],
            "source_manifest_sha256": _file_sha256(repo_root, MANIFEST_PATH),
        },
        gate="G0.6",
        output_sha256=_file_sha256(repo_root, LEDGER_PATH),
        freeze_commit_time=freeze_at,
    )
    # JobEvent, no RunEvent: el instante de ejecucion del ledger build no
    # esta registrado; solo se conoce el freeze del artefacto.
    _emit_jobevent(events, JOB_PROVENANCE, ledger_meta["ledger_id"],
                   lineage_observed_at, [source_run_ds, manifest_ds],
                   [ledger_ds], contract)

    # ------------------------------------------------------------------
    # job finreg.derivation — ruleset G0.7 sobre el claim ledger
    ruleset = _load(repo_root, RULESET_PATH)
    derived = _load(repo_root, DERIVED_PATH)
    derived_meta = derived["artifact"]
    derivation_run_id = Path(DERIVED_PATH).stem
    ruleset_ds = _dataset(
        f"ruleset/{ruleset['ruleset']['ruleset_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "derivation-ruleset",
                path=RULESET_PATH,
                sha256=_file_sha256(repo_root, RULESET_PATH),
                artifact_version=ruleset["ruleset"]["ruleset_version"],
            )
        },
    )
    derived_ds = _dataset(
        f"assertions/{derivation_run_id}",
        {
            "finreg_artifact": _artifact_facet(
                "derived-assertions",
                path=DERIVED_PATH,
                sha256=_file_sha256(repo_root, DERIVED_PATH),
                artifact_version=derived_meta["artifact_version"],
            )
        },
    )
    freeze_at = _freeze_time(repo_root, DERIVED_PATH)
    contract = _job_contract(
        derivation_run_id,
        derived_meta["derivation_version"],
        input_contract={
            "claims_ledger_sha256": derived_meta["claims_ledger_sha256"],
            "corpus_sha256": derived_meta["corpus_sha256"],
            "derivation_ruleset_sha256": derived_meta["derivation_ruleset_sha256"],
            "source_manifest_sha256": derived_meta["source_manifest_sha256"],
        },
        gate=ruleset["ruleset"]["gate"],
        output_sha256=_file_sha256(repo_root, DERIVED_PATH),
        freeze_commit_time=freeze_at,
    )
    # JobEvent, no RunEvent: la derivacion no registro instante de
    # ejecucion; solo el freeze del artefacto derivado.
    _emit_jobevent(events, JOB_DERIVATION, derivation_run_id,
                   lineage_observed_at,
                   [ledger_ds, ruleset_ds, corpus_ds, manifest_ds],
                   [derived_ds], contract)

    # ------------------------------------------------------------------
    # job finreg.assessment — run congelado g0.7-001
    assessment = _load(repo_root, ASSESSMENT_RUN_PATH)
    meta = assessment["run"]
    cases = _load(repo_root, CASES_PATH)
    cases_ds = _dataset(
        f"assessment-cases/{cases['cases_meta']['version']}",
        {
            "finreg_artifact": _artifact_facet(
                "assessment-cases",
                path=CASES_PATH,
                sha256=_file_sha256(repo_root, CASES_PATH),
                artifact_version=cases["cases_meta"]["version"],
            )
        },
    )
    assessment_ds = _dataset(
        f"assessment/{meta['run_id']}",
        {
            "finreg_artifact": _artifact_facet(
                "assessment-run",
                path=ASSESSMENT_RUN_PATH,
                sha256=_file_sha256(repo_root, ASSESSMENT_RUN_PATH),
                artifact_version=meta["run_version"],
                result_sha256=assessment["result_sha"],
            )
        },
    )
    contract = _run_contract(
        meta["run_id"],
        meta["run_version"],
        input_contract={
            "corpus_sha256": meta["corpus_sha256"],
            "claims_ledger_sha256": meta["claims_ledger_sha256"],
            "derivation_ruleset_sha256": meta["derivation_ruleset_sha256"],
            "assessment_cases_sha256": meta["assessment_cases_sha256"],
            "derived_assertions_sha256": meta["derived_assertions_sha256"],
        },
        gate=meta["gate"],
        executed_at=meta["executed_at"],
        code={"sha256": meta["code_sha"], "commit": meta["code_commit"]},
        output_sha256=_file_sha256(repo_root, ASSESSMENT_RUN_PATH),
    )
    _emit(events, JOB_ASSESSMENT, meta["run_id"], meta["executed_at"],
          [derived_ds, cases_ds, corpus_ds, ledger_ds, ruleset_ds],
          [assessment_ds], contract)

    return events


def export(repo_root: Path, out_dir: Path) -> list[Path]:
    """Escribe un fichero JSON canonico por evento. Crea ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, event in build_events(repo_root).items():
        path = out_dir / filename
        path.write_bytes(canonical_json(event).encode("utf-8"))
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("openlineage"))
    args = parser.parse_args(argv)
    written = export(args.repo_root.resolve(), args.out)
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
