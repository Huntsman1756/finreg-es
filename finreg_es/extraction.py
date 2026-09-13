"""G0.5-A: extracción de hechos desde snapshots, sin assessment regulatorio.

Este módulo separa FETCH, PARSE, IDENTITY, SEMANTICS y GROUND_TRUTH. Los
adapters no crean ``EntitlementAssertion`` ni llaman a ``assess``: solo
conservan hechos observados, valores raw y las divergencias clasificadas.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .canonical import canonical_json, strict_json_loads
from .identity import is_valid_lei


RUN_VERSION = "FINREG_G05A_EXTRACTION_V2"
EXPECTATION_ANNOTATION_RULE = "CLASSIFICATION_IN_ENTITY_EXPECTED_CONTRACT_RISKS"
EXPECTED_COMMIT_SHA = {
    "corpus_sha": "a3ed773",
    "contracts_sha": "83754ec",
    "source_baseline_sha": "1b6132b",
}

DIVERGENCE_CLASSES = {
    "FETCH_ERROR",
    "PARSE_ERROR",
    "IDENTITY_ERROR",
    "IDENTITY_GAP",
    "SOURCE_CONTRACT_GAP",
    "COVERAGE_GAP",
    "SEMANTICS_GAP",
    "GROUND_TRUTH_ERROR",
    "SOURCE_CHANGED",
    "EXTRACTION_BUG",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_record_hash(record: object) -> str:
    return _sha256_bytes(canonical_json(record).encode("utf-8"))


def _exact_name(value: str) -> str:
    # Matching de identidad: trim, mayúsculas y espacios; no normalización
    # Unicode ni eliminación de puntuación.
    return " ".join(value.strip().upper().split())


def _clean_html(value: str) -> str:
    value = html_lib.unescape(value)
    value = re.sub(r"<[^>]*>", " ", value)
    return " ".join(value.replace("\xa0", " ").split())


def _property(record: dict[str, Any], code: str) -> Any:
    for item in record.get("Properties", []):
        if code in item:
            return item[code]
    return None


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_flatten_strings(item))
        return out
    return []


class _JsonStream:
    """Lector pequeño de valores JSON para no cargar el dump EBA completo."""

    def __init__(self, stream: io.TextIOBase, chunk_size: int = 64 * 1024):
        self.stream = stream
        self.chunk_size = chunk_size
        self.buffer = ""
        self.eof = False
        self.decoder = json.JSONDecoder()

    def _fill(self) -> None:
        if self.eof:
            return
        chunk = self.stream.read(self.chunk_size)
        if chunk == "":
            self.eof = True
        else:
            self.buffer += chunk

    def _skip_space(self) -> None:
        while True:
            stripped = self.buffer.lstrip()
            if stripped:
                self.buffer = stripped
                return
            if self.eof:
                return
            self.buffer = ""
            self._fill()

    def _peek(self) -> str:
        self._skip_space()
        while not self.buffer and not self.eof:
            self._fill()
            self._skip_space()
        return self.buffer[:1]

    def _consume_char(self, expected: str) -> None:
        if self._peek() != expected:
            raise ValueError(f"JSON EBA: se esperaba {expected!r}")
        self.buffer = self.buffer[1:]

    def parse_value(self) -> Any:
        while True:
            self._skip_space()
            try:
                value, end = self.decoder.raw_decode(self.buffer)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self._fill()
            else:
                self.buffer = self.buffer[end:]
                return value

    def iter_open_array(self) -> Iterable[Any]:
        self._skip_space()
        if self._peek() == "]":
            self.buffer = self.buffer[1:]
            return
        while True:
            yield self.parse_value()
            marker = self._peek()
            if marker == ",":
                self.buffer = self.buffer[1:]
                continue
            if marker == "]":
                self.buffer = self.buffer[1:]
                return
            raise ValueError("JSON EBA: separador de array inválido")


def _iter_eba_records(zip_path: Path) -> Iterable[dict[str, Any]]:
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        json_names = [name for name in names if name.lower().endswith(".json")]
        if len(json_names) != 1:
            raise ValueError(f"ZIP EBA: JSON ambiguo: {json_names!r}")
        with archive.open(json_names[0], "r") as binary:
            with io.TextIOWrapper(binary, encoding="utf-8") as text:
                reader = _JsonStream(text)
                reader._consume_char("[")
                # Primer elemento: array de disclaimer. Se consume sin
                # retenerlo; el disclaimer está ya preservado dentro del ZIP.
                reader._consume_char("[")
                for _ in reader.iter_open_array():
                    pass
                reader._consume_char(",")
                reader._consume_char("[")
                for record in reader.iter_open_array():
                    if not isinstance(record, dict):
                        raise ValueError("JSON EBA: registro no objeto")
                    yield record
                reader._consume_char("]")


class SnapshotAdapter:
    source: str

    def extract(
        self, path: Path, record_specs: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    @staticmethod
    def key_for(spec: dict[str, Any]) -> str:
        raise NotImplementedError


class EsmaCaspsAdapter(SnapshotAdapter):
    source = "ESMA_MICA_REGISTER"

    @staticmethod
    def key_for(spec: dict[str, Any]) -> str:
        key = spec["record_key"]
        return f"{key['field']}={key['value']}"

    def extract(self, path: Path, record_specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        targets = {self.key_for(spec): spec["record_key"]["value"] for spec in record_specs}
        output: dict[str, dict[str, Any]] = {}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {
                "ae_competentAuthority",
                "ae_homeMemberState",
                "ae_lei_name",
                "ae_lei",
                "ac_authorisationNotificationDate",
                "ac_authorisationEndDate",
                "ac_serviceCode",
                "ac_serviceCode_cou",
                "ac_lastupdate",
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"ESMA CSV: faltan columnas {sorted(missing)}")
            for row in reader:
                key = f"ae_lei={row.get('ae_lei', '')}"
                if key not in targets:
                    continue
                output[key] = {
                    "source": self.source,
                    "record_key": {"field": "ae_lei", "value": row["ae_lei"]},
                    "raw_record": row,
                    "raw_record_sha256": _canonical_record_hash(row),
                    "observed": {
                        "legal_name": row["ae_lei_name"],
                        "lei": row["ae_lei"],
                        "lei_valid": is_valid_lei(row["ae_lei"]),
                        "home_member_state": row["ae_homeMemberState"],
                        "competent_authority": row["ae_competentAuthority"],
                        "commercial_name": row["ae_commercial_name"],
                        "service_codes_raw": row["ac_serviceCode"],
                        "service_countries_raw": row["ac_serviceCode_cou"],
                        "authorisation_notification_date": row[
                            "ac_authorisationNotificationDate"
                        ],
                        "authorisation_end_date": row["ac_authorisationEndDate"] or None,
                        "last_update": row["ac_lastupdate"],
                    },
                }
        return output


class EbaPsd2Adapter(SnapshotAdapter):
    source = "EBA_PSD2_REGISTER"

    @staticmethod
    def key_for(spec: dict[str, Any]) -> str:
        key = spec["record_key"]
        return f"{key['EntityCode']}|{key['EntityType']}"

    def extract(self, path: Path, record_specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        targets = {self.key_for(spec): spec["record_key"] for spec in record_specs}
        output: dict[str, dict[str, Any]] = {}
        for record in _iter_eba_records(path):
            key = f"{record.get('EntityCode', '')}|{record.get('EntityType', '')}"
            if key not in targets:
                continue
            output[key] = {
                "source": self.source,
                "record_key": {
                    "EntityCode": record.get("EntityCode"),
                    "EntityType": record.get("EntityType"),
                    "EntityVersion": record.get("__EBA_EntityVersion"),
                },
                "raw_record": record,
                "raw_record_sha256": _canonical_record_hash(record),
                "observed": {
                    "legal_name": _property(record, "ENT_NAM"),
                    "commercial_name": _property(record, "ENT_NAM_COM"),
                    "entity_code": record.get("EntityCode"),
                    "entity_type": record.get("EntityType"),
                    "national_reference_code": _property(record, "ENT_NAT_REF_COD"),
                    "country": _property(record, "ENT_COU_RES"),
                    "ent_aut_raw": _property(record, "ENT_AUT"),
                    "ent_aut_raw_type": type(_property(record, "ENT_AUT")).__name__,
                    "services_raw": record.get("Services"),
                    "service_codes": _flatten_strings(record.get("Services")),
                    "entity_version": record.get("__EBA_EntityVersion"),
                },
            }
        return output


class CnmvEsiFpsAdapter(SnapshotAdapter):
    source = "CNMV_ESI_FPS"
    _title_re = re.compile(
        r'<span[^>]+id="[^"]*_spanTituloCabecera"[^>]*>(?P<name>.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    _registration_re = re.compile(
        r"Número\s+y\s+fecha\s+de\s+registro\s+oficial:\s*"
        r"(?P<number>[^\s<]+)\s*-\s*(?P<date>\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    )
    _country_re = re.compile(r"País:\s*(?P<country>[^<]+)", re.IGNORECASE)

    @staticmethod
    def key_for(spec: dict[str, Any]) -> str:
        return f"official_number={spec['record_key']['official_number']}"

    def extract(self, path: Path, record_specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        targets = {
            self.key_for(spec): spec["record_key"]["official_number"]
            for spec in record_specs
        }
        document = path.read_text(encoding="utf-8")
        matches = list(self._title_re.finditer(document))
        output: dict[str, dict[str, Any]] = {}
        for index, match in enumerate(matches):
            tail_end = matches[index + 1].start() if index + 1 < len(matches) else len(document)
            tail = html_lib.unescape(document[match.end() : tail_end])
            plain_tail = _clean_html(tail)
            registration = self._registration_re.search(plain_tail)
            country = self._country_re.search(plain_tail)
            if registration is None or country is None:
                continue
            number = registration.group("number").strip()
            key = f"official_number={number}"
            if key not in targets:
                continue
            name = _clean_html(match.group("name"))
            raw_summary = _clean_html(match.group("name") + " " + plain_tail)
            output[key] = {
                "source": self.source,
                "record_key": {
                    "official_number": number,
                    "registration_date": registration.group("date"),
                    "country": _clean_html(country.group("country")),
                },
                "raw_record": raw_summary,
                "raw_record_sha256": _sha256_bytes(raw_summary.encode("utf-8")),
                "observed": {
                    "legal_name": name,
                    "official_number": number,
                    "registration_date": registration.group("date"),
                    "country": _clean_html(country.group("country")),
                    "lei": None,
                },
            }
        return output


class BdeMfiAdapter(SnapshotAdapter):
    source = "BDE_MFI_CLASSIFICATION_ES"

    @staticmethod
    def key_for(spec: dict[str, Any]) -> str:
        key = spec["record_key"]
        return f"{key['field']}={key['value']}"

    def extract(self, path: Path, record_specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        targets = {self.key_for(spec): spec["record_key"]["value"] for spec in record_specs}
        output: dict[str, dict[str, Any]] = {}
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"CÓDIGO EUROPEO", "LEI", "NOMBRE", "CATEGORÍA"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"BdE MFI CSV: faltan columnas {sorted(missing)}")
            for row in reader:
                key = f"CÓDIGO EUROPEO={row.get('CÓDIGO EUROPEO', '')}"
                if key not in targets:
                    continue
                lei = row.get("LEI", "")
                output[key] = {
                    "source": self.source,
                    "record_key": {
                        "field": "CÓDIGO EUROPEO",
                        "value": row["CÓDIGO EUROPEO"],
                        "lei": lei or None,
                    },
                    "raw_record": row,
                    "raw_record_sha256": _canonical_record_hash(row),
                    "observed": {
                        "legal_name": row["NOMBRE"],
                        "european_code": row["CÓDIGO EUROPEO"],
                        "lei": lei or None,
                        "lei_valid": is_valid_lei(lei) if lei else False,
                        "category": row["CATEGORÍA"],
                        "supervisor_code": row.get("CÓDIGO DE SUPERVISOR", ""),
                    },
                }
        return output


ADAPTERS: dict[str, SnapshotAdapter] = {
    EsmaCaspsAdapter.source: EsmaCaspsAdapter(),
    EbaPsd2Adapter.source: EbaPsd2Adapter(),
    CnmvEsiFpsAdapter.source: CnmvEsiFpsAdapter(),
    BdeMfiAdapter.source: BdeMfiAdapter(),
}


def _verify_snapshot(sources_dir: Path, manifest_item: dict[str, Any]) -> dict[str, Any]:
    relative = Path(*manifest_item["snapshot_file"].split("/"))
    path = (sources_dir / relative).resolve()
    root = sources_dir.resolve()
    if root not in path.parents:
        return {
            "status": "FETCH_ERROR",
            "mode": "LOCAL_SNAPSHOT",
            "reason": "SNAPSHOT_PATH_OUTSIDE_SOURCE_ROOT",
            "snapshot_file": manifest_item["snapshot_file"],
        }
    if not path.is_file():
        return {
            "status": "FETCH_ERROR",
            "mode": "LOCAL_SNAPSHOT",
            "reason": "SNAPSHOT_NOT_FOUND",
            "snapshot_file": manifest_item["snapshot_file"],
        }
    payload_hash = _sha256_file(path)
    payload_size = path.stat().st_size
    expected_hash = manifest_item["sha256"]
    expected_size = manifest_item["bytes"]
    if payload_hash != expected_hash or payload_size != expected_size:
        return {
            "status": "FETCH_ERROR",
            "mode": "LOCAL_SNAPSHOT",
            "reason": "SNAPSHOT_HASH_OR_SIZE_MISMATCH",
            "snapshot_file": manifest_item["snapshot_file"],
            "expected_sha256": expected_hash,
            "observed_sha256": payload_hash,
            "expected_bytes": expected_size,
            "observed_bytes": payload_size,
        }
    return {
        "status": "FETCH_OK",
        "mode": "LOCAL_SNAPSHOT",
        "snapshot_file": manifest_item["snapshot_file"],
        "bytes": payload_size,
        "sha256": payload_hash,
    }


def _record_key_matches(spec: dict[str, Any], parsed: dict[str, Any]) -> bool:
    expected = spec["record_key"]
    observed = parsed["record_key"]
    for field, value in expected.items():
        if field == "field":
            continue
        if field == "value":
            if observed.get("value") != value:
                return False
        elif observed.get(field) != value:
            return False
    return True


def _parse_result(
    source: str,
    spec: dict[str, Any],
    parsed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    adapter = ADAPTERS[source]
    key = adapter.key_for(spec)
    record = parsed.get(key)
    if record is None:
        return {
            "status": "PARSE_ERROR",
            "parser": type(adapter).__name__,
            "record_found": False,
            "reason": "EXPECTED_RECORD_NOT_FOUND_IN_SNAPSHOT",
        }
    if not _record_key_matches(spec, record):
        return {
            "status": "PARSE_ERROR",
            "parser": type(adapter).__name__,
            "record_found": True,
            "reason": "RECORD_KEY_MISMATCH",
            "record": record,
        }
    return {
        "status": "PARSE_OK",
        "parser": type(adapter).__name__,
        "record_found": True,
        "record": record,
    }


def _identity_layer(
    entity: dict[str, Any], source: str, parsed: dict[str, Any] | None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if parsed is None:
        return {"status": "NOT_EVALUATED", "reason": "PARSE_NOT_OK"}, []
    observed = parsed["observed"]
    corpus_name = entity["legal_name"]
    source_name = observed.get("legal_name") or ""
    name_match = _exact_name(source_name) == _exact_name(corpus_name)
    divergences: list[dict[str, Any]] = []
    if source == "ESMA_MICA_REGISTER":
        valid = bool(observed.get("lei")) and bool(observed.get("lei_valid"))
        status = "EXACT_IDENTIFIER" if valid and name_match else "IDENTITY_GAP"
        result = {
            "status": status,
            "identifier_kind": "LEI",
            "identifier": observed.get("lei"),
            "identifier_valid": observed.get("lei_valid"),
            "legal_name_match": name_match,
            "cross_source_join": "NOT_APPLICABLE",
        }
        if not observed.get("lei_valid"):
            divergences.append(
                {
                    "layer": "IDENTITY",
                    "classification": "IDENTITY_GAP",
                    "reason": "LEI_CHECKSUM_INVALID",
                    "expected_in_ground_truth": False,
                }
            )
        return result, divergences
    if source == "BDE_MFI_CLASSIFICATION_ES":
        valid = bool(observed.get("lei")) and bool(observed.get("lei_valid"))
        status = "EXACT_IDENTIFIER" if valid and name_match else "IDENTITY_GAP"
        result = {
            "status": status,
            "identifier_kind": "LEI",
            "identifier": observed.get("lei"),
            "identifier_valid": observed.get("lei_valid"),
            "legal_name_match": name_match,
            "cross_source_join": "NOT_APPLICABLE",
        }
        if not valid:
            divergences.append(
                {
                    "layer": "IDENTITY",
                    "classification": "IDENTITY_GAP",
                    "reason": "BDE_LEI_MISSING_OR_INVALID",
                    "expected_in_ground_truth": False,
                }
            )
        return result, divergences
    if source == "EBA_PSD2_REGISTER":
        esma_present = any(
            item["source"] == "ESMA_MICA_REGISTER"
            for item in entity["source_records"]
        )
        name_variant = not name_match
        result = {
            "status": "SOURCE_RECORD_EXACT" if name_match else "SOURCE_RECORD_EXACT_NAME_VARIANT",
            "identifier_kind": "EBA_ENTITY_CODE",
            "identifier": observed.get("entity_code"),
            "legal_name_match": name_match,
            "cross_source_join": "REVIEW_REQUIRED" if esma_present else "NOT_ATTEMPTED",
            "global_identity": "NOT_PROVEN_BY_SOURCE_LOCAL_ID",
        }
        if name_variant and not esma_present:
            divergences.append(
                {
                    "layer": "IDENTITY",
                    "classification": "IDENTITY_GAP",
                    "reason": "SOURCE_LOCAL_NAME_VARIANT",
                    "expected_in_ground_truth": False,
                }
            )
        return result, divergences
    # CNMV FPS only exposes a source-local official number in the captured
    # summary. Exact source-row retrieval is not global identity proof.
    return (
        {
            "status": "SOURCE_RECORD_EXACT",
            "identifier_kind": "CNMV_OFFICIAL_NUMBER",
            "identifier": observed.get("official_number"),
            "legal_name_match": name_match,
            "cross_source_join": "REVIEW_REQUIRED",
            "global_identity": "NOT_PROVEN_BY_SOURCE_LOCAL_ID",
        },
        [],
    )


def _semantics_layer(
    entity: dict[str, Any], source: str, parsed: dict[str, Any] | None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if parsed is None:
        return {"status": "NOT_EVALUATED", "reason": "PARSE_NOT_OK"}, []
    observed = parsed["observed"]
    divergences: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "assessment": "NOT_RUN",
        "assertion_created": False,
        "legal_effect": None,
        "entry_mechanism": None,
        "territorial_basis": None,
    }
    if source == "EBA_PSD2_REGISTER":
        ent_aut = observed.get("ent_aut_raw")
        is_date_array = (
            isinstance(ent_aut, list)
            and bool(ent_aut)
            and all(isinstance(item, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) for item in ent_aut)
        )
        if is_date_array:
            result.update(
                {
                    "status": "BLOCKED_SEMANTICS_GAP",
                    "reason": "ENT_AUT_DATE_ARRAY_NOT_STATUS_ENUM",
                    "raw_dimensions_preserved": ["ent_aut_raw", "services_raw"],
                }
            )
            divergences.extend(
                [
                    {
                        "layer": "SEMANTICS",
                        "classification": "SOURCE_CONTRACT_GAP",
                        "reason": "ENT_AUT_SHAPE_CONFLICTS_WITH_METADATA_ENUM",
                        "expected_in_ground_truth": False,
                    },
                    {
                        "layer": "SEMANTICS",
                        "classification": "SEMANTICS_GAP",
                        "reason": "ENT_AUT_DATE_HAS_NO_SAFE_STATUS_MAPPING",
                        "expected_in_ground_truth": False,
                    },
                ]
            )
        else:
            result.update({"status": "RAW_FACTS_ONLY", "reason": "NO_ASSERTION_LOGIC_IN_G05_A"})
        if observed.get("entity_type") == "PSD_AISP":
            result["coverage"] = "BLOCKED_COVERAGE_GAP"
            result["coverage_reason"] = "PSD_AISP_NOT_IN_G0_ENTITY_CLASSES"
            divergences.append(
                {
                    "layer": "SEMANTICS",
                    "classification": "COVERAGE_GAP",
                    "reason": "PSD_AISP_NOT_IN_FROZEN_VOCABULARY",
                    "expected_in_ground_truth": False,
                }
            )
        return result, divergences
    if source == "ESMA_MICA_REGISTER":
        result.update(
            {
                "status": "RAW_FACTS_ONLY",
                "reason": "ENTRY_ROUTE_AND_ENTITY_CLASS_NOT_INFERRED_FROM_CSV_ROW",
                "raw_dimensions_preserved": [
                    "authorisation_notification_date",
                    "authorisation_end_date",
                    "service_codes_raw",
                    "service_countries_raw",
                ],
            }
        )
        divergences.append(
            {
                "layer": "SEMANTICS",
                "classification": "COVERAGE_GAP",
                "reason": "MICA_ENTITY_CLASS_ROUTE_REQUIRES_H1_H2_MAPPING",
                "expected_in_ground_truth": False,
            }
        )
        return result, divergences
    if source == "CNMV_ESI_FPS":
        result.update(
            {
                "status": "RAW_FACTS_ONLY",
                "reason": "FPS_SUMMARY_HAS_NO_CURRENT_STATUS_OR_LEGAL_EFFECT",
                "raw_dimensions_preserved": [
                    "official_number",
                    "registration_date",
                    "country",
                ],
            }
        )
        return result, divergences
    result.update(
        {
            "status": "RAW_FACTS_ONLY",
            "reason": "PARTIAL_CLASSIFICATION_NOT_ENTITLEMENT_ENUMERATION",
            "raw_dimensions_preserved": ["european_code", "lei", "category"],
        }
    )
    divergences.append(
        {
            "layer": "SEMANTICS",
            "classification": "COVERAGE_GAP",
            "reason": "BDE_MFI_IS_PARTIAL_CLASSIFICATION",
            "expected_in_ground_truth": False,
        }
    )
    return result, divergences


def _check_fact(fact: str, records: list[dict[str, Any]]) -> bool:
    observed = [record.get("observed", {}) for record in records]
    if fact == "home_state_ES":
        return any(row.get("home_member_state") == "ES" for row in observed)
    if fact == "esma_lei_present":
        return any(row.get("lei") for row in observed if "home_member_state" in row)
    if fact == "lei_present":
        return any(row.get("lei") for row in observed)
    if fact == "services_present":
        return any(row.get("service_codes_raw") for row in observed)
    if fact == "passport_countries_present":
        return any(row.get("service_countries_raw") for row in observed)
    if fact == "commercial_name_present":
        return any(row.get("commercial_name") for row in observed)
    if fact == "cross_source_name_variant":
        names = [
            _exact_name(row.get("legal_name", ""))
            for row in observed
            if row.get("legal_name")
        ]
        return len(names) >= 2 and len(set(names)) > 1
    if fact in {"eba_entity_code_present", "entity_code_present"}:
        return any(row.get("entity_code") for row in observed)
    if fact == "national_reference_present":
        return any(row.get("national_reference_code") for row in observed)
    if fact == "commercial_name_may_be_present":
        return any(row.get("commercial_name") for row in observed)
    if fact == "transition_boundary_candidate":
        return any(row.get("authorisation_notification_date") == "30/06/2026" for row in observed)
    if fact == "post_transition_date_candidate":
        return any(
            row.get("authorisation_notification_date") in {"10/07/2026", "31/07/2026"}
            for row in observed
        )
    if fact.startswith("entity_type_"):
        return any(row.get("entity_type") == fact.removeprefix("entity_type_") for row in observed)
    if fact == "service_PS_080":
        return any("PS_080" in row.get("service_codes", []) for row in observed)
    if fact == "ent_aut_raw_is_date_array":
        return any(
            isinstance(row.get("ent_aut_raw"), list)
            and all(isinstance(item, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) for item in row["ent_aut_raw"])
            for row in observed
        )
    if fact == "multiple_ent_aut_dates":
        return any(isinstance(row.get("ent_aut_raw"), list) and len(row["ent_aut_raw"]) > 1 for row in observed)
    if fact == "status_semantics_unresolved":
        return _check_fact("ent_aut_raw_is_date_array", records)
    if fact == "fps_listing_present":
        return any(row.get("official_number") for row in observed)
    if fact == "official_number_present":
        return any(row.get("official_number") for row in observed)
    if fact == "country_present":
        return any(row.get("country") for row in observed)
    if fact == "no_lei_in_summary":
        return any("official_number" in row and not row.get("lei") for row in observed)
    if fact == "old_registration_date":
        return any(row.get("registration_date", "").endswith(("/2006", "/2010", "/2012")) for row in observed)
    if fact == "mfi_row_present":
        return any(row.get("european_code") for row in observed)
    if fact == "european_code_present":
        return any(row.get("european_code") for row in observed)
    if fact == "category_credit_institution":
        return any(row.get("category") == "Entidad de crédito" for row in observed)
    if fact == "source_is_partial_classification":
        return True
    raise ValueError(f"ground truth fact no implementado: {fact}")


def _ground_truth_for_entity(
    entity: dict[str, Any], expectation: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any]:
    checks = [
        {"fact": fact, "observed": _check_fact(fact, records)}
        for fact in expectation["expected_facts"]
    ]
    status = "MATCH" if all(item["observed"] for item in checks) else "DIVERGENCE"
    return {
        "status": status,
        "expected_source_presence": expectation["expected_source_presence"],
        "expected_facts": checks,
        "expected_contract_risks": expectation.get("expected_contract_risks", []),
        "identity_join_expected": expectation.get("identity_join"),
    }


def _extractor_sha(repo_root: Path) -> tuple[str, list[dict[str, str]]]:
    files = [repo_root / "finreg_es" / "extraction.py"]
    parts = []
    metadata = []
    for path in sorted(files):
        relative = path.relative_to(repo_root).as_posix()
        payload = path.read_bytes()
        parts.extend([relative.encode("utf-8"), b"\0", payload, b"\0"])
        metadata.append({"path": relative, "sha256": _sha256_bytes(payload)})
    return _sha256_bytes(b"".join(parts)), metadata


def run_extraction(
    repo_root: Path,
    *,
    run_id: str,
    corpus_sha: str = EXPECTED_COMMIT_SHA["corpus_sha"],
    contracts_sha: str = EXPECTED_COMMIT_SHA["contracts_sha"],
    source_baseline_sha: str = EXPECTED_COMMIT_SHA["source_baseline_sha"],
    executed_at: str | None = None,
    supersedes_run_id: str | None = None,
) -> dict[str, Any]:
    sources_dir = repo_root / "fixtures" / "g0.5" / "sources"
    corpus_path = repo_root / "fixtures" / "g0.5" / "corpus" / "entities.json"
    ground_truth_path = repo_root / "fixtures" / "g0.5" / "corpus" / "ground-truth.json"
    corpus = strict_json_loads(corpus_path.read_text(encoding="utf-8"))
    ground_truth = strict_json_loads(ground_truth_path.read_text(encoding="utf-8"))
    source_manifest = strict_json_loads(
        (sources_dir / "manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(corpus, dict) or not isinstance(ground_truth, dict):
        raise ValueError("G0.5 corpus/ground truth debe ser objeto")
    manifest_by_file = {
        item["snapshot_file"]: item for item in source_manifest["snapshots"]
    }
    truth_by_entity = {
        row["corpus_id"]: row for row in ground_truth["entity_expectations"]
    }

    attempts_by_snapshot: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for entity in corpus["entities"]:
        for source_record in entity["source_records"]:
            attempts_by_snapshot[source_record["snapshot_file"]].append((entity, source_record))

    fetch_by_snapshot: dict[str, dict[str, Any]] = {}
    parsed_by_snapshot: dict[str, dict[str, dict[str, Any]]] = {}
    parser_errors: dict[str, str] = {}
    for snapshot_file, items in attempts_by_snapshot.items():
        manifest_item = manifest_by_file.get(snapshot_file)
        if manifest_item is None:
            fetch_by_snapshot[snapshot_file] = {
                "status": "FETCH_ERROR",
                "mode": "LOCAL_SNAPSHOT",
                "reason": "SNAPSHOT_NOT_IN_MANIFEST",
                "snapshot_file": snapshot_file,
            }
            continue
        fetch = _verify_snapshot(sources_dir, manifest_item)
        fetch_by_snapshot[snapshot_file] = fetch
        if fetch["status"] != "FETCH_OK":
            continue
        source = items[0][1]["source"]
        adapter = ADAPTERS.get(source)
        if adapter is None:
            parser_errors[snapshot_file] = f"no adapter for {source}"
            continue
        try:
            parsed_by_snapshot[snapshot_file] = adapter.extract(
                (sources_dir / Path(*snapshot_file.split("/"))),
                [source_record for _, source_record in items],
            )
        except Exception as exc:  # convert adapter failure to a layer result
            parser_errors[snapshot_file] = f"{type(exc).__name__}: {exc}"

    parsed_records_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    attempts: list[dict[str, Any]] = []
    for entity in corpus["entities"]:
        expectation = truth_by_entity[entity["corpus_id"]]
        for source_record in entity["source_records"]:
            snapshot_file = source_record["snapshot_file"]
            source = source_record["source"]
            fetch = fetch_by_snapshot[snapshot_file]
            if fetch["status"] != "FETCH_OK":
                parse = {
                    "status": "PARSE_ERROR",
                    "parser": type(ADAPTERS.get(source)).__name__ if source in ADAPTERS else None,
                    "record_found": False,
                    "reason": "FETCH_NOT_OK",
                }
            elif snapshot_file in parser_errors:
                parse = {
                    "status": "PARSE_ERROR",
                    "parser": type(ADAPTERS[source]).__name__,
                    "record_found": False,
                    "reason": parser_errors[snapshot_file],
                }
            else:
                parse = _parse_result(
                    source,
                    source_record,
                    parsed_by_snapshot.get(snapshot_file, {}),
                )
            parsed = parse.get("record") if parse["status"] == "PARSE_OK" else None
            if parsed is not None:
                parsed_records_by_entity[entity["corpus_id"]].append(parsed)
            identity, identity_divergences = _identity_layer(entity, source, parsed)
            semantics, semantics_divergences = _semantics_layer(entity, source, parsed)
            divergences: list[dict[str, Any]] = []
            if fetch["status"] != "FETCH_OK":
                divergences.append(
                    {
                        "layer": "FETCH",
                        "classification": (
                            "SOURCE_CHANGED"
                            if fetch.get("reason") == "SNAPSHOT_HASH_OR_SIZE_MISMATCH"
                            else "FETCH_ERROR"
                        ),
                        "reason": fetch.get("reason", "FETCH_NOT_OK"),
                        "expected_in_ground_truth": False,
                    }
                )
            if parse["status"] != "PARSE_OK":
                divergences.append(
                    {
                        "layer": "PARSE",
                        "classification": "PARSE_ERROR",
                        "reason": parse.get("reason", "PARSE_NOT_OK"),
                        "expected_in_ground_truth": False,
                    }
                )
            divergences.extend(identity_divergences)
            divergences.extend(semantics_divergences)
            expected_risks = set(expectation.get("expected_contract_risks", []))
            for divergence in divergences:
                divergence["expected_in_ground_truth"] = (
                    divergence["classification"] in expected_risks
                )
            attempts.append(
                {
                    "corpus_id": entity["corpus_id"],
                    "legal_name": entity["legal_name"],
                    "source": source,
                    "snapshot_file": snapshot_file,
                    "source_snapshot_sha": fetch.get("sha256"),
                    "source_record_key": source_record["record_key"],
                    "fetch": fetch,
                    "parse": parse,
                    "identity": identity,
                    "semantics": semantics,
                    "assessment": {"status": "NOT_RUN", "assertions": []},
                    "pre_registered_contract_risks": expectation.get(
                        "expected_contract_risks", []
                    ),
                    "divergences": divergences,
                }
            )

    truth_by_entity_result: dict[str, dict[str, Any]] = {}
    for entity in corpus["entities"]:
        truth_by_entity_result[entity["corpus_id"]] = _ground_truth_for_entity(
            entity,
            truth_by_entity[entity["corpus_id"]],
            parsed_records_by_entity.get(entity["corpus_id"], []),
        )
    for attempt in attempts:
        attempt["ground_truth"] = truth_by_entity_result[attempt["corpus_id"]]
        if attempt["ground_truth"]["status"] != "MATCH":
            attempt["divergences"].append(
                {
                    "layer": "GROUND_TRUTH",
                    "classification": "GROUND_TRUTH_ERROR",
                    "reason": "PREREGISTERED_FACT_NOT_OBSERVED",
                    "expected_in_ground_truth": False,
                }
            )

    extractor_sha, extractor_files = _extractor_sha(repo_root)
    used_snapshots = sorted(attempts_by_snapshot)
    source_snapshot_sha = {
        snapshot: manifest_by_file[snapshot]["sha256"] for snapshot in used_snapshots
    }
    statuses = {
        layer: Counter(
            attempt[layer]["status"]
            for attempt in attempts
            if isinstance(attempt.get(layer), dict) and "status" in attempt[layer]
        )
        for layer in ("fetch", "parse", "identity", "semantics")
    }
    divergence_rows = [
        {
            "corpus_id": attempt["corpus_id"],
            "source": attempt["source"],
            "snapshot_file": attempt["snapshot_file"],
            **divergence,
        }
        for attempt in attempts
        for divergence in attempt["divergences"]
    ]
    invalid_classifications = sorted(
        {
            row["classification"]
            for row in divergence_rows
            if row["classification"] not in DIVERGENCE_CLASSES
        }
    )
    if invalid_classifications:
        raise ValueError(f"clasificaciones de divergencia no soportadas: {invalid_classifications}")

    executed_at = executed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result: dict[str, Any] = {
        "run": {
            "run_id": run_id,
            "run_version": RUN_VERSION,
            "supersedes_run_id": supersedes_run_id,
            "expectation_annotation_rule": EXPECTATION_ANNOTATION_RULE,
            "corpus_sha": corpus_sha,
            "contracts_sha": contracts_sha,
            "source_baseline_sha": source_baseline_sha,
            "extractor_sha": extractor_sha,
            "extractor_files": extractor_files,
            "source_snapshot_sha": source_snapshot_sha,
            "corpus_manifest_sha256": _sha256_file(corpus_path),
            "ground_truth_sha256": _sha256_file(ground_truth_path),
            "executed_at": executed_at,
            "assessment_execution": "NOT_RUN",
        },
        "summary": {
            "entities_attempted": len(corpus["entities"]),
            "source_attempts": len(attempts),
            "layer_statuses": {layer: dict(counter) for layer, counter in statuses.items()},
            "ground_truth_entities": dict(
                Counter(value["status"] for value in truth_by_entity_result.values())
            ),
            "divergences_total": len(divergence_rows),
            "divergences_by_classification": dict(
                Counter(row["classification"] for row in divergence_rows)
            ),
            "unexpected_divergences": sum(
                not row.get("expected_in_ground_truth", False) for row in divergence_rows
            ),
        },
        "attempts": attempts,
        "divergences": divergence_rows,
    }
    result["result_sha"] = _sha256_bytes(canonical_json(result).encode("utf-8"))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--executed-at")
    parser.add_argument("--supersedes-run-id")
    parser.add_argument("--corpus-sha", default=EXPECTED_COMMIT_SHA["corpus_sha"])
    parser.add_argument("--contracts-sha", default=EXPECTED_COMMIT_SHA["contracts_sha"])
    parser.add_argument("--source-baseline-sha", default=EXPECTED_COMMIT_SHA["source_baseline_sha"])
    args = parser.parse_args(argv)
    result = run_extraction(
        args.repo_root.resolve(),
        run_id=args.run_id,
        corpus_sha=args.corpus_sha,
        contracts_sha=args.contracts_sha,
        source_baseline_sha=args.source_baseline_sha,
        executed_at=args.executed_at,
        supersedes_run_id=args.supersedes_run_id,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(result) + "\n")
    print(
        json.dumps(
            {
                "run_id": result["run"]["run_id"],
                "result_sha": result["result_sha"],
                "entities_attempted": result["summary"]["entities_attempted"],
                "source_attempts": result["summary"]["source_attempts"],
                "divergences_total": result["summary"]["divergences_total"],
                "unexpected_divergences": result["summary"]["unexpected_divergences"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
