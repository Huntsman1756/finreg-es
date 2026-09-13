"""G0.4 — Semantica regulatoria y motor de assessment.

Atomo: REGULATORY_ENTITLEMENT_ASSERTION con tres dimensiones separadas
(legal_effect, entry_mechanism, territorial_basis). Los atributos
regulatorios pertenecen a la asercion, nunca a la entidad.

Motor: query (entity_id, activity, jurisdiction, as_of) ->
0..N aserciones admisibles -> Assessment. Reglas congeladas:
  - gate de identidad: sin EXACT no hay conclusion regulatoria
    (INDETERMINATE + razon de identidad); nunca negativo.
  - aserciones con scope OUT_OF_SOURCE_SCOPE o agente sin principal
    son inadmisibles y contaminan el diagnostico.
  - vigencia: effective_from/effective_to filtran; evidence staleness
    se mide sobre freshness_at de la source_assertion mas reciente.
  - conflicto de efectos legales admisibles -> INDETERMINATE (C2).
  - ausencia de evidencia -> NO_ENTITLEMENT_EVIDENCED, jamas
    CONFIRMED_NOT_AUTHORISED (nunca NOT_FOUND => negativo).
  - negativo explicito solo -> CONFIRMED_NOT_AUTHORISED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from .contracts import SourceContract, staleness_policy
from .coverage import CoverageQuery, ScopeStatus, coverage
from .identity import IdentityIndexEntry, IdentityResolution, IdentityResolutionState
from .temporal import Freshness, is_stale
from .vocab import (
    Assessment,
    AssessmentReason,
    LegalEffect,
)


@dataclass(frozen=True)
class SourceAssertion:
    authority: str
    register_id: str
    source_url: str
    retrieved_at: str
    source_as_of: str | None
    source_date_reliability: str
    raw_value: str
    raw_snapshot_sha256: str
    extractor_version: str
    observed_current: bool


@dataclass(frozen=True)
class EntitlementAssertion:
    assertion_id: str
    register_id: str  # registro que sustenta la asercion
    entity_id: str
    entity_class: str
    activity: str
    jurisdiction: str
    legal_effect: LegalEffect
    entry_mechanism: str
    territorial_basis: str
    legal_basis: str
    effective_from: str
    effective_to: str | None
    scope: str
    source_assertions: tuple[SourceAssertion, ...]
    derived_by: dict | None = None  # {rule_id, ruleset_version, effective_from}
    principal_entity_id: str | None = None  # obligatorio para agentes

    def latest_freshness(self) -> Freshness:
        claims = [
            Freshness(
                retrieved_at=date.fromisoformat(s.retrieved_at),
                source_as_of=date.fromisoformat(s.source_as_of) if s.source_as_of else None,
                source_date_reliability=s.source_date_reliability,
            )
            for s in self.source_assertions
        ]
        best = max(claims, key=lambda f: f.freshness_at)
        return best

    def covers(self, as_of: date) -> bool:
        if date.fromisoformat(self.effective_from) > as_of:
            return False
        if self.effective_to is not None and date.fromisoformat(self.effective_to) < as_of:
            return False
        return True

    def effective_effect_at(self, as_of: date) -> tuple[str, str]:
        """Efecto legal EFECTIVO de la asercion en ``as_of`` (nivel asercion).

        C4: una asercion con ventana cerrada cuya fuente decia
        ENTITLED_TO_PROVIDE puede concluir, a nivel de asercion,
        ``NOT_ENTITLED`` con razon ``ENTITLEMENT_EXPIRED``. Esa conclusion
        NO es evidencia negativa explicita y NO se agrega nunca como
        ``CONFIRMED_NOT_AUTHORISED``: podria existir otra via vigente de
        habilitacion.
        """
        if date.fromisoformat(self.effective_from) > as_of:
            return "UNKNOWN", "NOT_YET_EFFECTIVE"
        if self.effective_to is not None and date.fromisoformat(self.effective_to) < as_of:
            if self.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE:
                return "NOT_ENTITLED", "ENTITLEMENT_EXPIRED"
            return "UNKNOWN", "WINDOW_CLOSED"
        return str(self.legal_effect), "IN_EFFECT"


@dataclass(frozen=True)
class AssessmentResult:
    entity_id: str | None
    activity: str
    jurisdiction: str
    as_of: str
    identity_resolution: IdentityResolutionState
    assessment: Assessment
    reason: AssessmentReason
    assertions: tuple[dict, ...] = field(default_factory=tuple)
    assertion_evaluations: tuple[dict, ...] = field(default_factory=tuple)
    response_freshness: str | None = None
    diagnostics: tuple[str, ...] = ()


def assess(
    entity_query: IdentityResolution | IdentityIndexEntry,
    index: list[IdentityIndexEntry],
    activity: str,
    jurisdiction: str,
    as_of: str,
    assertions: list[EntitlementAssertion],
    contracts: dict[str, SourceContract],
    territorial_basis: str | None = None,
) -> AssessmentResult:
    """Motor de assessment (G0.7 dentro de G0.4: semantica congelada)."""
    as_of_date = date.fromisoformat(as_of)

    # Gate de identidad (C1): separado de la conclusion regulatoria.
    if isinstance(entity_query, IdentityResolution):
        resolution = entity_query
    elif isinstance(entity_query, str):
        entity = next((e for e in index if e.entity_id == entity_query), None)
        if entity is None:
            resolution = IdentityResolution(
                IdentityResolutionState.NOT_FOUND, None, "UNKNOWN_ENTITY_ID"
            )
            return AssessmentResult(
                entity_id=None,
                activity=activity,
                jurisdiction=jurisdiction,
                as_of=as_of,
                identity_resolution=resolution.state,
                assessment=Assessment.INDETERMINATE,
                reason=AssessmentReason.IDENTITY_NOT_FOUND,
                diagnostics=(f"identity:{resolution.reason}",),
            )
        resolution = IdentityResolution(
            IdentityResolutionState.EXACT, entity_query, "ENTITY_ID_PROVIDED"
        )
    else:
        resolution = IdentityResolution(
            IdentityResolutionState.EXACT, entity_query.entity_id, "ENTITY_PROVIDED"
        )
    if resolution.state is not IdentityResolutionState.EXACT:
        reason_map = {
            IdentityResolutionState.AMBIGUOUS: AssessmentReason.AMBIGUOUS_IDENTITY,
            IdentityResolutionState.NOT_FOUND: AssessmentReason.IDENTITY_NOT_FOUND,
            IdentityResolutionState.CONFLICTING_IDENTIFIERS: AssessmentReason.CONFLICTING_IDENTIFIERS,
        }
        return AssessmentResult(
            entity_id=resolution.entity_id,
            activity=activity,
            jurisdiction=jurisdiction,
            as_of=as_of,
            identity_resolution=resolution.state,
            assessment=Assessment.INDETERMINATE,
            reason=reason_map[resolution.state],
            diagnostics=(f"identity:{resolution.reason}",),
        )

    entity = next(e for e in index if e.entity_id == resolution.entity_id)
    diagnostics: list[str] = []

    # Evaluaciones a nivel de asercion (C4). Exponen el efecto EFECTIVO en
    # as_of, p. ej. NOT_ENTITLED/ENTITLEMENT_EXPIRED para una autorizacion
    # con ventana cerrada. NO son admisibilidad ni conclusion agregada: un
    # NOT_ENTITLED derivado de expiracion jamas alimenta
    # CONFIRMED_NOT_AUTHORISED (podria existir otra via vigente).
    matching = [
        a
        for a in assertions
        if a.entity_id == entity.entity_id
        and a.activity == activity
        and a.jurisdiction == jurisdiction
        and (territorial_basis is None or a.territorial_basis == territorial_basis)
    ]
    evaluations = tuple(_evaluation(a, as_of_date) for a in matching)

    def emit(assessment, reason, used=None):
        return _result(
            resolution, entity, activity, jurisdiction, as_of,
            assessment, reason, diagnostics,
            assertions=used or [], evaluations=evaluations,
        )

    # Admisibilidad: scope de fuente + ventana temporal + evidencia fresca.
    admissible: list[EntitlementAssertion] = []
    for a in matching:
        contract = contracts.get(a.register_id)
        if contract is None:
            diagnostics.append(f"no_contract:{a.register_id}")
            continue
        decision = coverage(
            contract,
            CoverageQuery(
                entity_class=a.entity_class,
                activity=a.activity,
                jurisdiction=a.jurisdiction,
                territorial_basis=a.territorial_basis,
                effective_date=as_of,
            ),
        )
        if decision.status is ScopeStatus.OUT_OF_SCOPE:
            diagnostics.append(f"out_of_source_scope:{a.assertion_id}")
            continue
        if decision.status is ScopeStatus.UNKNOWN and not a.source_assertions:
            diagnostics.append(f"unknown_scope_no_evidence:{a.assertion_id}")
            continue
        # W1: un agente presta por cuenta de su principal; su asercion
        # exige principal_entity_id identificado.
        if "PSP_AGENT" in entity.entity_classes and a.principal_entity_id is None:
            diagnostics.append(f"agent_missing_principal:{a.assertion_id}")
            continue
        if not a.covers(as_of_date):
            diagnostics.append(f"not_in_effect:{a.assertion_id}")
            continue
        fresh = a.latest_freshness()
        pos_stale, neg_stale = staleness_policy(contract)
        max_stale = (
            neg_stale if a.legal_effect is LegalEffect.NOT_ENTITLED else pos_stale
        )
        if is_stale(fresh, max_stale, as_of_date):
            diagnostics.append(f"stale_evidence:{a.assertion_id}")
            continue
        admissible.append(a)

    if not admissible:
        if not matching:
            return emit(
                Assessment.NO_ENTITLEMENT_EVIDENCED,
                AssessmentReason.NO_ASSERTIONS_IN_SCOPE,
            )
        if any(d.startswith("agent_missing_principal") for d in diagnostics):
            return emit(
                Assessment.INDETERMINATE,
                AssessmentReason.AGENT_ASSERTION_MISSING_PRINCIPAL,
            )
        if any(d.startswith("out_of_source_scope") for d in diagnostics):
            return emit(
                Assessment.NO_ENTITLEMENT_EVIDENCED,
                AssessmentReason.ASSERTION_OUT_OF_SOURCE_SCOPE,
            )
        if any(d.startswith("not_in_effect") for d in diagnostics):
            expired_positive = any(
                a.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE
                and a.effective_to is not None
                and date.fromisoformat(a.effective_to) < as_of_date
                for a in matching
            )
            return emit(
                Assessment.NO_ENTITLEMENT_EVIDENCED,
                AssessmentReason.ENTITLEMENT_EXPIRED
                if expired_positive
                else AssessmentReason.NO_ASSERTIONS_IN_SCOPE,
            )
        if any(d.startswith("stale_evidence") for d in diagnostics):
            return emit(Assessment.INDETERMINATE, AssessmentReason.ALL_EVIDENCE_STALE)
        return emit(Assessment.INDETERMINATE, AssessmentReason.UNINTERPRETABLE_EVIDENCE)

    entitled = [a for a in admissible if a.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE]
    not_entitled = [a for a in admissible if a.legal_effect is LegalEffect.NOT_ENTITLED]
    unknown = [a for a in admissible if a.legal_effect is LegalEffect.UNKNOWN]

    # Conflicto conservador (C2): efectos opuestos admisibles => INDETERMINATE.
    if entitled and not_entitled:
        diagnostics.append("conflicting_legal_effects")
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.CONFLICTING_ASSERTIONS,
            used=admissible,
        )
    if not_entitled and not entitled:
        return emit(
            Assessment.CONFIRMED_NOT_AUTHORISED,
            AssessmentReason.EXPLICIT_NEGATIVE_EVIDENCE,
            used=not_entitled,
        )
    if entitled:
        return emit(
            Assessment.CONFIRMED_AUTHORISED,
            AssessmentReason.SUPPORTED_BY_ACTIVE_ASSERTIONS,
            used=entitled,
        )
    # Solo UNKNOWN interpretable pero fresco: indeterminado.
    return emit(
        Assessment.INDETERMINATE,
        AssessmentReason.UNINTERPRETABLE_EVIDENCE,
        used=unknown,
    )


def _evaluation(assertion: EntitlementAssertion, as_of: date) -> dict:
    """Evaluacion a nivel de asercion. Conserva el SOURCE_ASSERTION completo:
    una asercion expirada no soporta el assessment pero su evidencia no se
    pierde (ni su raw_snapshot_sha256)."""
    effect, reason = assertion.effective_effect_at(as_of)
    return {
        "assertion_id": assertion.assertion_id,
        "register_id": assertion.register_id,
        "source_legal_effect": str(assertion.legal_effect),
        "effective_legal_effect_at_as_of": effect,
        "reason": reason,
        "legal_basis": assertion.legal_basis,
        "effective_from": assertion.effective_from,
        "effective_to": assertion.effective_to,
        "evidence": [asdict(sa) for sa in assertion.source_assertions],
    }


def _result(
    resolution, entity, activity, jurisdiction, as_of,
    assessment: Assessment, reason: AssessmentReason,
    diagnostics: list[str],
    assertions: list[EntitlementAssertion] | None = None,
    evaluations: tuple[dict, ...] = (),
) -> AssessmentResult:
    used = assertions or []
    freshness_dates = [a.latest_freshness().freshness_at for a in used]
    return AssessmentResult(
        entity_id=resolution.entity_id or entity.entity_id,
        activity=activity,
        jurisdiction=jurisdiction,
        as_of=as_of,
        identity_resolution=resolution.state,
        assessment=assessment,
        reason=reason,
        assertions=tuple(
            {
                "assertion_id": a.assertion_id,
                "legal_effect": str(a.legal_effect),
                "entry_mechanism": a.entry_mechanism,
                "territorial_basis": a.territorial_basis,
                "legal_basis": a.legal_basis,
                "effective_from": a.effective_from,
                "effective_to": a.effective_to,
                "derived_by": a.derived_by,
                "evidence": [asdict(sa) for sa in a.source_assertions],
            }
            for a in used
        ),
        assertion_evaluations=evaluations,
        response_freshness=min(freshness_dates).isoformat() if freshness_dates else None,
        diagnostics=tuple(diagnostics),
    )
