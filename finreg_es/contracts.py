"""G0.1 — Contratos de fuentes: carga y validacion estructural.

Un contrato declara hechos de la fuente (VERIFIED/PENDING) y politica
propia de FinReg (PROPOSED = decision deliberada y versionada).
El validador exige que todo campo VERIFIED tenga fuente primaria.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .canonical import strict_json_loads
from .vocab import (
    ENTITY_CLASSES,
    ACTIVITIES,
    NegativeEvidenceCapability,
    SourceDateReliability,
    TerritorialBasis,
    VerificationStatus,
)

REQUIRED_FIELDS = (
    "authority",
    "register_name",
    "official_url",
    "legal_basis",
    "entity_classes_covered",
    "excluded_entity_classes",
    "activities_covered",
    "jurisdictions",
    "territorial_regimes",
    "update_cadence",
    "max_positive_staleness_days",
    "max_negative_staleness_days",
    "supports_source_as_of",
    "negative_evidence_capability",
    "identity_fields",
    "raw_format",
    "supports_bulk_snapshot",
    "coverage_rules",
    "verification",
)


@dataclass(frozen=True)
class CoverageRule:
    rule_id: str
    scope: str  # IN | OUT
    entity_class: str | None
    activities: tuple[str, ...] | None  # None = todas las declaradas
    jurisdictions: tuple[str, ...] | None
    territorial_bases: tuple[str, ...] | None
    valid_from: str | None
    valid_to: str | None
    note: str


@dataclass(frozen=True)
class SourceContract:
    register_id: str
    authority: str
    register_name: str
    official_url: str
    legal_basis: str
    entity_classes_covered: tuple[str, ...]
    excluded_entity_classes: tuple[str, ...]
    activities_covered: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    territorial_regimes: tuple[str, ...]
    update_cadence: str
    max_positive_staleness_days: int | None
    max_negative_staleness_days: int | None
    supports_source_as_of: bool | None
    negative_evidence_capability: NegativeEvidenceCapability
    identity_fields: tuple[str, ...]
    raw_format: str
    supports_bulk_snapshot: bool | None
    coverage_rules: tuple[CoverageRule, ...]
    verification: dict


def load_contract(path: Path) -> SourceContract:
    raw = strict_json_loads(path.read_text(encoding="utf-8"))
    validate_contract_dict(raw)
    return SourceContract(
        register_id=raw["register_id"],
        authority=raw["authority"],
        register_name=raw["register_name"],
        official_url=raw["official_url"],
        legal_basis=raw["legal_basis"],
        entity_classes_covered=tuple(raw["entity_classes_covered"]),
        excluded_entity_classes=tuple(raw["excluded_entity_classes"]),
        activities_covered=tuple(raw["activities_covered"]),
        jurisdictions=tuple(raw["jurisdictions"]),
        territorial_regimes=tuple(raw["territorial_regimes"]),
        update_cadence=raw["update_cadence"],
        max_positive_staleness_days=raw["max_positive_staleness_days"],
        max_negative_staleness_days=raw["max_negative_staleness_days"],
        supports_source_as_of=raw["supports_source_as_of"],
        negative_evidence_capability=NegativeEvidenceCapability(
            raw["negative_evidence_capability"]
        ),
        identity_fields=tuple(raw["identity_fields"]),
        raw_format=raw["raw_format"],
        supports_bulk_snapshot=raw["supports_bulk_snapshot"],
        coverage_rules=tuple(
            CoverageRule(
                rule_id=r["rule_id"],
                scope=r["scope"],
                entity_class=r.get("entity_class"),
                activities=tuple(r["activities"]) if r.get("activities") else None,
                jurisdictions=tuple(r["jurisdictions"]) if r.get("jurisdictions") else None,
                territorial_bases=tuple(r["territorial_bases"])
                if r.get("territorial_bases")
                else None,
                valid_from=r.get("valid_from"),
                valid_to=r.get("valid_to"),
                note=r.get("note", ""),
            )
            for r in raw["coverage_rules"]
        ),
        verification=raw["verification"],
    )


def validate_contract_dict(raw: dict) -> None:
    missing = [f for f in REQUIRED_FIELDS if f not in raw]
    if missing:
        raise ValueError(f"contrato incompleto, faltan campos: {missing}")
    if "register_id" not in raw:
        raise ValueError("contrato sin register_id")
    if raw["negative_evidence_capability"] not in NegativeEvidenceCapability.__members__:
        raise ValueError("negative_evidence_capability fuera de vocabulario")
    unknown_classes = set(raw["entity_classes_covered"]) - set(ENTITY_CLASSES)
    unknown_excluded = set(raw["excluded_entity_classes"]) - set(ENTITY_CLASSES)
    if unknown_classes or unknown_excluded:
        raise ValueError(f"entity classes fuera de vocabulario: {unknown_classes | unknown_excluded}")
    unknown_activities = set(raw["activities_covered"]) - set(ACTIVITIES)
    if unknown_activities:
        raise ValueError(f"actividades fuera de vocabulario: {unknown_activities}")
    unknown_territorial = set(raw["territorial_regimes"]) - set(TerritorialBasis)
    if unknown_territorial:
        raise ValueError(f"regimenes territoriales fuera de vocabulario: {unknown_territorial}")
    if not raw["identity_fields"]:
        raise ValueError("identity_fields no puede estar vacio (minimo legal_name)")
    if "legal_name" not in raw["identity_fields"]:
        raise ValueError("legal_name es obligatorio en identity_fields")
    for key in ("max_positive_staleness_days", "max_negative_staleness_days"):
        v = raw[key]
        if v is not None and (not isinstance(v, int) or v <= 0):
            raise ValueError(f"{key} debe ser int positivo o null (politica no definida)")
    for rid, rule in enumerate(raw["coverage_rules"]):
        if rule["scope"] not in ("IN", "OUT"):
            raise ValueError(f"coverage_rules[{rid}].scope fuera de vocabulario")
        if rule.get("entity_class") is not None and rule["entity_class"] not in ENTITY_CLASSES:
            raise ValueError(f"coverage_rules[{rid}].entity_class fuera de vocabulario")
        for key in ("activities", "jurisdictions", "territorial_bases"):
            if rule.get(key) is not None and not rule[key]:
                raise ValueError(f"coverage_rules[{rid}].{key} vacio: usar null")
    if raw["supports_source_as_of"] is True and raw["verification"].get(
        "supports_source_as_of", {}
    ).get("status") not in (VerificationStatus.VERIFIED,):
        raise ValueError(
            "supports_source_as_of=true exige verificacion VERIFIED de la fuente"
        )
    # Todo hecho marcado VERIFIED exige URL de fuente primaria.
    for field, info in raw["verification"].items():
        if info.get("status") == VerificationStatus.VERIFIED and not info.get("source_url"):
            raise ValueError(f"verificacion VERIFIED de '{field}' sin source_url")


# Alias fuente->contrato: algunos extractos congelados citan un
# register_id de vista (provenance) distinto del register_id del
# contrato que la gobierna. G1-D-F02: la composicion ALL_REQUIRED
# consulta el contrato de cada fuente citada en source_assertions,
# por lo que la vista CNMV_PSC_REGISTER (extract estructurado del
# listado MiCA) debe resolver a su contrato CNMV_MICA_CASP_LIST.
SOURCE_CONTRACT_ALIASES: dict[str, str] = {
    "CNMV_PSC_REGISTER": "CNMV_MICA_CASP_LIST",
}


def staleness_policy(contract: SourceContract) -> tuple[int | None, int | None]:
    """Politica de staleness del perfil del registro (positivo, negativo).

    Los negativos caducan estrictamente antes que los positivos.
    """
    pos = contract.max_positive_staleness_days
    neg = contract.max_negative_staleness_days
    if pos is not None and neg is not None and neg > pos:
        raise ValueError(
            f"{contract.register_id}: max_negative_staleness debe ser <= max_positive_staleness"
        )
    return pos, neg
