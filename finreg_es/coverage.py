"""G0.3 — Matriz de cobertura: coverage(register, entity_class, activity,
jurisdiction, territorial_basis, effective_date).

Evaluacion congelada de reglas:
  1. Primera regla OUT cuyo patron matchea -> OUT_OF_SCOPE (exclusiones
     explicitas ganan; bloquean inferencias negativas Y positivas).
  2. Regla IN matcheando -> IN_SCOPE.
  3. Sin regla aplicable -> UNKNOWN.

Un negativo (CONFIRMED_NOT_AUTHORISED) exige: capability de la fuente,
IN_SCOPE, entidad identificada exactamente, snapshot completo de
enumeracion (si el negativo deriva de enumeracion) y vigencia temporal
cubierta. En cualquier otro caso: NO_ENTITLEMENT_EVIDENCED o
INDETERMINATE — nunca negativo automatico desde NOT_FOUND.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import SourceContract
from .vocab import ScopeStatus


@dataclass(frozen=True)
class CoverageQuery:
    entity_class: str
    activity: str
    jurisdiction: str
    territorial_basis: str
    effective_date: str  # ISO date


@dataclass(frozen=True)
class ScopeDecision:
    status: ScopeStatus
    matched_rule_id: str | None
    reason: str


def _rule_applies(rule, query: CoverageQuery) -> bool:
    if rule.entity_class is not None and rule.entity_class != query.entity_class:
        return False
    if rule.activities is not None and query.activity not in rule.activities:
        return False
    if rule.jurisdictions is not None and query.jurisdiction not in rule.jurisdictions:
        return False
    if rule.territorial_bases is not None and query.territorial_basis not in rule.territorial_bases:
        return False
    if rule.valid_from is not None and query.effective_date < rule.valid_from:
        return False
    if rule.valid_to is not None and query.effective_date > rule.valid_to:
        return False
    return True


def coverage(contract: SourceContract, query: CoverageQuery) -> ScopeDecision:
    # 1) Reglas explicitas OUT (exclusiones del contrato ganan).
    outs = [r for r in contract.coverage_rules if r.scope == "OUT" and _rule_applies(r, query)]
    if outs:
        return ScopeDecision(ScopeStatus.OUT_OF_SCOPE, outs[0].rule_id, "EXPLICIT_EXCLUSION")
    # 2) Guardas genericas fail-closed sobre las declaraciones del contrato.
    if query.entity_class in contract.excluded_entity_classes:
        return ScopeDecision(
            ScopeStatus.OUT_OF_SCOPE,
            "contract-excluded-entity-classes",
            "EXCLUDED_ENTITY_CLASS",
        )
    if query.activity not in contract.activities_covered:
        return ScopeDecision(
            ScopeStatus.OUT_OF_SCOPE,
            "contract-activities-coverage",
            "ACTIVITY_NOT_COVERED_BY_REGISTER",
        )
    if "EEA" not in contract.jurisdictions and query.jurisdiction not in contract.jurisdictions:
        return ScopeDecision(
            ScopeStatus.OUT_OF_SCOPE,
            "contract-jurisdiction-coverage",
            "JURISDICTION_NOT_COVERED_BY_REGISTER",
        )
    # 3) Reglas IN.
    ins = [r for r in contract.coverage_rules if r.scope == "IN" and _rule_applies(r, query)]
    if ins:
        return ScopeDecision(ScopeStatus.IN_SCOPE, ins[0].rule_id, "COVERED_BY_RULE")
    # 4) Sin regla aplicable: UNKNOWN (bloquea negativos, no afirma nada).
    return ScopeDecision(ScopeStatus.UNKNOWN, None, "NO_RULE_MATCHES")


@dataclass(frozen=True)
class EnumerationSnapshot:
    """Prerequisitos de un negativo derivado de enumeracion (G0.3/B)."""

    enumeration_snapshot_sha256: str
    enumeration_retrieved_at: str
    enumeration_source_as_of: str | None
    coverage_rule_id: str
    coverage_ruleset_version: str


NEGATIVE_CAPABILITY_SUPPORTS_ENUMERATION = {"COMPLETE_ENUMERATION"}


def can_produce_enumeration_negative(
    contract: SourceContract,
    decision: ScopeDecision,
    entity_identity_state: str,  # IdentityResolutionState
    snapshot: EnumerationSnapshot | None,
) -> tuple[bool, str]:
    """Puerta de produccion de negativos por enumeracion completa."""
    if entity_identity_state != "EXACT":
        return False, "IDENTITY_NOT_EXACT"
    if decision.status is not ScopeStatus.IN_SCOPE:
        return False, f"SCOPE_{decision.status}"
    if contract.negative_evidence_capability not in NEGATIVE_CAPABILITY_SUPPORTS_ENUMERATION:
        return False, "SOURCE_CAPABILITY_DOES_NOT_ALLOW_ENUMERATION_NEGATIVE"
    if snapshot is None:
        return False, "MISSING_ENUMERATION_SNAPSHOT"
    if snapshot.coverage_rule_id != decision.matched_rule_id:
        return False, "COVERAGE_RULE_MISMATCH"
    return True, "ENUMERATION_NEGATIVE_ALLOWED"
