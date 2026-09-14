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

from .contracts import (
    SOURCE_CONTRACT_ALIASES,
    SourceContract,
    staleness_policy,
)
from .coverage import CoverageQuery, ScopeStatus, coverage
from .identity import IdentityIndexEntry, IdentityResolution, IdentityResolutionState
from .temporal import Freshness, is_stale
from .vocab import (
    Assessment,
    AssessmentReason,
    AssessmentV2,
    LegalEffect,
    TerritorialBasis,
)


# ASSESSMENT_SEMANTICS_V2 (G1-A7): el resultado publico describe el
# entitlement, no el mecanismo. La traduccion ocurre en la frontera de
# emision: la logica interna sigue razonando en terminos V1.
_V1_TO_V2_ASSESSMENT = {
    Assessment.CONFIRMED_AUTHORISED: AssessmentV2.CONFIRMED_ENTITLED,
    Assessment.NO_ENTITLEMENT_EVIDENCED: AssessmentV2.NO_ENTITLEMENT_EVIDENCED,
    Assessment.CONFIRMED_NOT_AUTHORISED: AssessmentV2.CONFIRMED_NOT_ENTITLED,
    Assessment.INDETERMINATE: AssessmentV2.INDETERMINATE,
}


def _reported_fact_reason(facts: list[dict]) -> AssessmentReason:
    """Razon V2 para una entidad sin aserciones admisibles que tiene
    reported_facts (politica A7: el hecho reportado bloquea o explica,
    nunca eleva ni crea un negativo)."""
    # G1-D: el agente opera por cuenta del principal — ruta delegada,
    # nunca entitlement propio. Va antes que el generico parent-status.
    if any("agent-parent-status" in f["rule_id"] for f in facts):
        return AssessmentReason.AGENT_DELEGATED_ROUTE_NO_INDEPENDENT_ENTITLEMENT
    if any("limited-lp" in f["rule_id"] for f in facts):
        return AssessmentReason.TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP
    if any("parent-status" in f["rule_id"] for f in facts):
        return AssessmentReason.PARENT_STATUS_NOT_CHILD_ENTITLEMENT
    if any("insufficient-basis" in f["rule_id"] for f in facts):
        return AssessmentReason.INSUFFICIENT_LEGAL_BASIS
    if any(f["reported_status"] == "WITHDRAWN" for f in facts):
        return AssessmentReason.WITHDRAWAL_SEMANTICS_DEFERRED
    if any(
        f["reported_status"] == "TERRITORIAL_ENTITLEMENT_DEFERRED" for f in facts
    ):
        return AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED
    return AssessmentReason.MALFORMED_STATUS_SEQUENCE


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
    # G1-A: procedencia probatoria y estado temporal reportado (política
    # A5). None en artefactos G0 — retrocompatible.
    evidence_basis: str | None = None
    reported_status: str | None = None
    status_intervals: tuple | None = None
    # G1-D-F02: composicion de evidencia. "ALL_REQUIRED" = la asercion
    # es conjuntiva: cada registro citado en source_assertions debe
    # tener contrato, estar en scope y ser fresh bajo su propia
    # politica; la frescura de una fuente nunca compensa otra.
    # None = semantica historica (contrato de register_id + freshness
    # de la evidencia mas reciente).
    evidence_composition: str | None = None
    # G1-E (E4.1): puente del contrato negativo E4 al dataclass.
    # interval_end="EXCLUSIVE" => la ventana [from,to) cierra EN
    # effective_to (semanticas ENT_AUT); default = semantica legacy
    # inclusiva de G0/G1-A..D. root_key/root_home_jurisdiction atan la
    # asercion a su raiz de autorizacion para la agregacion V3.
    interval_end: str | None = None
    negative_scope: str | None = None
    negative_evidence_class: str | None = None
    raw_capability_code: str | None = None
    source_granularity: str | None = None
    coverage_policy_id: str | None = None
    admissibility: str | None = None
    blocker: str | None = None
    root_key: str | None = None
    root_home_jurisdiction: str | None = None

    def _window_closed(self, as_of: date) -> bool:
        if self.effective_to is None:
            return False
        end = date.fromisoformat(self.effective_to)
        # G1-E: interval_end EXCLUSIVE => [from,to), cerrada en `to`.
        if self.interval_end == "EXCLUSIVE":
            return end <= as_of
        return end < as_of

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
        if self._window_closed(as_of):
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
        if self._window_closed(as_of):
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
    assessment: Assessment | AssessmentV2
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
    semantics_version: str = "V1",
    reported_facts: list[dict] | None = None,
) -> AssessmentResult:
    """Motor de assessment.

    ``semantics_version="V1"`` (default) reproduce la semantica G0
    congelada — replay byte-identico. ``"V2"`` (G1+) emite la taxonomia
    CONFIRMED_ENTITLED/CONFIRMED_NOT_ENTITLED y consume
    ``reported_facts`` como evidencia contextual que bloquea o explica
    (politica A7: nunca elevan el resultado ni crean un negativo).
    """
    v2 = semantics_version == "V2"
    # ASSESSMENT_SEMANTICS_V3 (G1-E, E5): agregacion route-aware sobre
    # los hechos E4 materializados (negative_scope ROOT_FAMILY /
    # ROUTE_CAPABILITY, root_key, interval_end=EXCLUSIVE). V1/V2 quedan
    # congelados — V3 solo se invoca para los artefactos g1-e.
    v3 = semantics_version == "V3"
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

    entity_facts = [
        f for f in (reported_facts or [])
        if f.get("corpus_id") == entity.entity_id
    ]

    def emit(assessment, reason, used=None):
        if v2 or v3:
            assessment = _V1_TO_V2_ASSESSMENT[assessment]
            if reason is AssessmentReason.SUPPORTED_BY_ACTIVE_ASSERTIONS:
                reason = AssessmentReason.ACTIVE_ENTITLEMENT_EVIDENCED
        return _result(
            resolution, entity, activity, jurisdiction, as_of,
            assessment, reason, diagnostics,
            assertions=used or [], evaluations=evaluations,
        )

    if v3:
        return _assess_v3(
            entity,
            activity,
            as_of,
            as_of_date,
            matching,
            entity_facts,
            contracts,
            territorial_basis,
            emit,
            diagnostics,
        )

    # Admisibilidad: scope de fuente + ventana temporal + evidencia fresca.
    admissible: list[EntitlementAssertion] = []
    for a in matching:
        if not _assertion_admissible(
            a, entity, contracts, as_of, as_of_date, diagnostics
        ):
            continue
        admissible.append(a)

    if not admissible:
        # V2/A7: un reported_fact sobre la entidad bloquea o explica —
        # WITHDRAWN no es NO_ENTITLEMENT_EVIDENCED (hay evidencia
        # material) ni CONFIRMED_NOT_ENTITLED (lectura juridica = G1-E).
        if v2 and entity_facts:
            diagnostics.append(
                "reported_facts:" + ",".join(f["fact_id"] for f in entity_facts)
            )
            return emit(
                Assessment.INDETERMINATE,
                _reported_fact_reason(entity_facts),
            )
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
        # V2: un hecho reportado WITHDRAWN contradice una asercion
        # positiva admisible -> conflicto, nunca positivo silencioso.
        if v2 and any(f["reported_status"] == "WITHDRAWN" for f in entity_facts):
            diagnostics.append("conflicting_reported_fact:withdrawn")
            return emit(
                Assessment.INDETERMINATE,
                AssessmentReason.CONFLICTING_ASSERTIONS,
                used=admissible,
            )
        return emit(
            Assessment.CONFIRMED_AUTHORISED,
            AssessmentReason.SUPPORTED_BY_ACTIVE_ASSERTIONS,
            used=entitled,
        )
    # Solo UNKNOWN interpretable pero fresco: indeterminado.
    # V2: si toda la evidencia UNKNOWN es territorial (pasaporte/FPS),
    # la razon explicita que el entitlement territorial esta en G1-D.
    if v2 and all(
        a.territorial_basis == TerritorialBasis.FREEDOM_TO_PROVIDE_SERVICES
        for a in unknown
    ):
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED,
            used=unknown,
        )
    return emit(
        Assessment.INDETERMINATE,
        AssessmentReason.UNINTERPRETABLE_EVIDENCE,
        used=unknown,
    )


def _assertion_admissible(
    a: EntitlementAssertion,
    entity,
    contracts: dict,
    as_of: str,
    as_of_date: date,
    diagnostics: list[str],
) -> bool:
    """Gate de admisibilidad por asercion (compartido V2/V3).

    Misma semantica congelada: contrato + scope + principal + ventana
    temporal + freshness + composicion conjuntiva ALL_REQUIRED.
    """
    contract = contracts.get(a.register_id)
    if contract is None:
        diagnostics.append(f"no_contract:{a.register_id}")
        return False
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
        return False
    if decision.status is ScopeStatus.UNKNOWN and not a.source_assertions:
        diagnostics.append(f"unknown_scope_no_evidence:{a.assertion_id}")
        return False
    # W1: un agente presta por cuenta de su principal; su asercion
    # exige principal_entity_id identificado.
    if "PSP_AGENT" in entity.entity_classes and a.principal_entity_id is None:
        diagnostics.append(f"agent_missing_principal:{a.assertion_id}")
        return False
    if not a.covers(as_of_date):
        diagnostics.append(f"not_in_effect:{a.assertion_id}")
        return False
    fresh = a.latest_freshness()
    pos_stale, neg_stale = staleness_policy(contract)
    max_stale = (
        neg_stale if a.legal_effect is LegalEffect.NOT_ENTITLED else pos_stale
    )
    if is_stale(fresh, max_stale, as_of_date):
        diagnostics.append(f"stale_evidence:{a.assertion_id}")
        return False
    # G1-D-F02: asercion conjuntiva — cada fuente requerida debe
    # tener contrato, estar en scope y ser fresh bajo SU contrato.
    if a.evidence_composition == "ALL_REQUIRED":
        for register in sorted(
            {s.register_id for s in a.source_assertions}
        ):
            # Vistas de registro resuelven al contrato que las
            # gobierna (p. ej. CNMV_PSC_REGISTER -> CNMV_MICA_CASP_LIST).
            reg_contract = contracts.get(
                SOURCE_CONTRACT_ALIASES.get(register, register)
            )
            if reg_contract is None:
                diagnostics.append(f"no_contract:{register}")
                return False
            reg_decision = coverage(
                reg_contract,
                CoverageQuery(
                    entity_class=a.entity_class,
                    activity=a.activity,
                    jurisdiction=a.jurisdiction,
                    territorial_basis=a.territorial_basis,
                    effective_date=as_of,
                ),
            )
            if reg_decision.status is ScopeStatus.OUT_OF_SCOPE:
                diagnostics.append(
                    f"out_of_source_scope:{a.assertion_id}:{register}"
                )
                return False
            reg_fresh = max(
                (
                    Freshness(
                        retrieved_at=date.fromisoformat(s.retrieved_at),
                        source_as_of=(
                            date.fromisoformat(s.source_as_of)
                            if s.source_as_of
                            else None
                        ),
                        source_date_reliability=s.source_date_reliability,
                    )
                    for s in a.source_assertions
                    if s.register_id == register
                ),
                key=lambda f: f.freshness_at,
            )
            reg_pos, reg_neg = staleness_policy(reg_contract)
            reg_max_stale = (
                reg_neg
                if a.legal_effect is LegalEffect.NOT_ENTITLED
                else reg_pos
            )
            if is_stale(reg_fresh, reg_max_stale, as_of_date):
                diagnostics.append(
                    f"stale_required_source:{a.assertion_id}:{register}"
                )
                return False
    return True


# ---------------------------------------------------------------------
# ASSESSMENT_SEMANTICS_V3 (G1-E, E5) — agregacion route-aware.
#
# El modelo E4 separa:
#   ROOT_FAMILY       retirada/baja de una raiz de autorizacion
#                     (root_key). Cierra toda la familia que desciende
#                     de ella; nunca inventa una base territorial.
#   ROUTE_CAPABILITY  ausencia enumerada de una actividad atomica en
#                     una ruta demostrada (root_key + territorial_basis).
#
# El veredicto global compone raices y rutas; una retirada de raiz no
# es entity-global (Mollie: PI cerrada + EMI abierta).
# ---------------------------------------------------------------------

# Tipo de raiz -> actividades que la raiz puede sostener legalmente.
# Un PSD_AISP nunca sustenta PIS (registro != autorizacion); un PI no
# emite dinero electronico. Raices sin tipo resoluble (UNKNOWN) se
# tratan como capaces de todo — conservador.
_PI_ACTIVITIES = {
    "PAYMENT_ACCOUNT_CASH_PLACEMENT",
    "PAYMENT_ACCOUNT_CASH_WITHDRAWAL",
    "PAYMENT_DIRECT_DEBIT_EXECUTION",
    "PAYMENT_CARD_TRANSACTION_EXECUTION",
    "PAYMENT_CREDIT_TRANSFER_EXECUTION",
    "PAYMENT_DIRECT_DEBIT_EXECUTION_CREDIT_LINE",
    "PAYMENT_CARD_TRANSACTION_EXECUTION_CREDIT_LINE",
    "PAYMENT_CREDIT_TRANSFER_EXECUTION_CREDIT_LINE",
    "PAYMENT_INSTRUMENT_ISSUING",
    "PAYMENT_TRANSACTION_ACQUIRING",
    "MONEY_REMITTANCE",
    "PAYMENT_INITIATION_SERVICES",
    "ACCOUNT_INFORMATION_SERVICES",
    "PAYMENT_SERVICES",
}
_ROOT_TYPE_ACTIVITIES = {
    "PSD_PI": _PI_ACTIVITIES,
    "PSD_EMI": _PI_ACTIVITIES | {"E_MONEY_ISSUANCE"},
    "PSD_AISP": {"ACCOUNT_INFORMATION_SERVICES"},
}


def _root_can_provide(root_key: str, activity: str) -> bool:
    """True si la clase de la raiz puede sostener legalmente la
    actividad consultada (raices no aplicables no cuentan para el
    cierre global)."""
    parts = root_key.split("|")
    root_type = parts[1] if len(parts) >= 3 else "UNKNOWN"
    supported = _ROOT_TYPE_ACTIVITIES.get(root_type)
    if supported is None:
        return True
    return activity in supported


def _root_possible_routes(home: str | None) -> set[str]:
    """Vias legalmente disponibles para una raiz segun su home."""
    if home == "ES":
        return {TerritorialBasis.DOMESTIC}
    return {
        TerritorialBasis.FREEDOM_TO_PROVIDE_SERVICES,
        TerritorialBasis.BRANCH,
    }


def _fact_freshness_ok(fact: dict, contracts: dict, as_of_date: date) -> bool:
    """Politica de staleness del contrato aplicada a un reported_fact.

    Solo hechos con provenance (E4.1) son evaluables; un hecho sin
    source_assertions no puede cerrar nada en V3.
    """
    sources = fact.get("source_assertions") or []
    if not sources:
        return False
    contract = contracts.get(fact.get("source") or "")
    if contract is None:
        return False
    _, neg_stale = staleness_policy(contract)
    fresh = max(
        Freshness(
            retrieved_at=date.fromisoformat(s["retrieved_at"]),
            source_as_of=(
                date.fromisoformat(s["source_as_of"]) if s["source_as_of"] else None
            ),
            source_date_reliability=s["source_date_reliability"],
        )
        for s in sources
    )
    return not is_stale(fresh, neg_stale, as_of_date)


def _root_states_at(
    entity_facts: list[dict],
    contracts: dict,
    as_of_date: date,
) -> dict[str, str]:
    """Estado bitemporal de cada raiz en ``as_of``.

    Los intervalos ENT_AUT [from,to) son la fuente temporal; un hecho
    EXPLICIT_WITHDRAWAL sin intervalos cierra desde su effective_from.
    ENTITY_BAJA / UNRESOLVED_MOTIVO NO cierran: dejan la raiz
    UNRESOLVED (salvo que una retirada posterior la cierre limpiamente
    — la retirada explicita resuelve la ambiguedad).

    Devuelve root_key -> OPEN | CLOSED | UNRESOLVED | ABSENT.
    """
    intervals: dict[str, list[dict]] = {}
    withdrawals: dict[str, list[str]] = {}
    unresolved_events: dict[str, list[str]] = {}
    known: set[str] = set()
    for fact in entity_facts:
        root_key = fact.get("root_key")
        if not root_key:
            continue
        known.add(root_key)
        if not _fact_freshness_ok(fact, contracts, as_of_date):
            continue
        for interval in fact.get("status_intervals") or []:
            intervals.setdefault(root_key, []).append(interval)
        eff = fact.get("effective_from")
        if not eff:
            continue
        neg_class = fact.get("negative_evidence_class")
        if neg_class == "EXPLICIT_WITHDRAWAL":
            withdrawals.setdefault(root_key, []).append(eff)
        elif neg_class in ("ENTITY_BAJA", "UNRESOLVED_MOTIVO") or (
            neg_class is None and fact.get("reported_status") == "WITHDRAWN"
        ):
            # Baja/transformacion (o retirada sin clase, pre-E4.1):
            # no cierra la raiz, la deja UNRESOLVED.
            unresolved_events.setdefault(root_key, []).append(eff)

    states: dict[str, str] = {}
    for root_key in known:
        spans = intervals.get(root_key, [])
        closed_at = [
            d for d in withdrawals.get(root_key, [])
            if date.fromisoformat(d) <= as_of_date
        ]
        if spans:
            open_now = any(
                date.fromisoformat(s["from"]) <= as_of_date
                and (
                    s["to"] is None or as_of_date < date.fromisoformat(s["to"])
                )
                for s in spans
            )
            if open_now:
                states[root_key] = "OPEN"
            elif as_of_date >= min(
                date.fromisoformat(s["from"]) for s in spans
            ):
                states[root_key] = "CLOSED"
            else:
                states[root_key] = "ABSENT"
        elif closed_at:
            states[root_key] = "CLOSED"
        elif unresolved_events.get(root_key):
            states[root_key] = "UNRESOLVED"
        else:
            # Hecho de raiz presente sin cierre efectivo en as_of.
            states[root_key] = "OPEN"
    return states


def _assess_v3(
    entity,
    activity: str,
    as_of: str,
    as_of_date: date,
    matching: list[EntitlementAssertion],
    entity_facts: list[dict],
    contracts: dict,
    territorial_basis: str | None,
    emit,
    diagnostics: list[str],
) -> AssessmentResult:
    """Agregacion route-aware (G1-E, E5).

    1. admisibilidad por asercion (mismo gate V2) — las aserciones
       ``admissibility=BLOCKED`` no cierran rutas: informan como
       evidencia bloqueada.
    2. estado de cada raiz en as_of via intervalos [from,to).
    3. rutas agrupadas por (root_key, territorial_basis): positivo +
       negativo admisibles en la misma ruta = ROUTE_CONFLICT.
    4. cualquier ruta abierta => CONFIRMED_ENTITLED.
    5. CONFIRMED_NOT_ENTITLED solo si toda raiz aplicable esta cerrada
       (retirada) o tiene todas sus vias legalmente posibles cerradas
       por ausencias enumeradas.
    6. evidencia bloqueada / raiz irresoluble / conflicto sin ruta
       abierta => INDETERMINATE.
    """
    blocked = [a for a in matching if a.admissibility == "BLOCKED"]
    for a in blocked:
        diagnostics.append(f"blocked_evidence:{a.assertion_id}")

    admissible = [
        a
        for a in matching
        if a.admissibility != "BLOCKED"
        and _assertion_admissible(
            a, entity, contracts, as_of, as_of_date, diagnostics
        )
    ]

    # Rutas observadas: (root_key, territorial_basis). Las aserciones
    # sin root_key forman su propio ambito por registro (legacy).
    open_routes: dict[tuple, list[EntitlementAssertion]] = {}
    closed_routes: dict[tuple, list[EntitlementAssertion]] = {}
    for a in admissible:
        key = (a.root_key or f"UNSCOPED|{a.register_id}", a.territorial_basis)
        if a.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE:
            open_routes.setdefault(key, []).append(a)
        elif a.legal_effect is LegalEffect.NOT_ENTITLED:
            closed_routes.setdefault(key, []).append(a)

    conflicts = sorted(set(open_routes) & set(closed_routes))
    clean_open = [k for k in open_routes if k not in conflicts]
    for key in conflicts:
        diagnostics.append(f"route_conflict:{key[0]}:{key[1]}")

    # (4) ruta abierta limpia => entitlement confirmado.
    if clean_open:
        used = [a for k in clean_open for a in open_routes[k]]
        return emit(
            Assessment.CONFIRMED_AUTHORISED,
            AssessmentReason.SUPPORTED_BY_ACTIVE_ASSERTIONS,
            used=used,
        )

    # (3) conflicto de ruta sin otra ruta abierta => indeterminado.
    if conflicts:
        used = [
            a
            for k in conflicts
            for a in open_routes[k] + closed_routes[k]
        ]
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.ROUTE_CONFLICT,
            used=used,
        )

    root_states = _root_states_at(entity_facts, contracts, as_of_date)

    # Raices aplicables: las de los hechos de la entidad + las de las
    # aserciones que matchean; la raiz debe poder sostener la actividad
    # consultada (un AISP nunca cierra una query de PIS).
    entity_roots: dict[str, str | None] = {}
    for fact in entity_facts:
        if fact.get("root_key"):
            entity_roots.setdefault(
                fact["root_key"], fact.get("root_home_jurisdiction")
            )
    for a in matching:
        if a.root_key:
            entity_roots.setdefault(a.root_key, a.root_home_jurisdiction)
    applicable = {
        rk: home
        for rk, home in entity_roots.items()
        if _root_can_provide(rk, activity)
        and root_states.get(rk, "OPEN") != "ABSENT"
    }

    if applicable:
        all_closed = True
        withdrawal_driven = False
        for root_key, home in applicable.items():
            if root_states.get(root_key) == "CLOSED":
                withdrawal_driven = True
                continue
            if root_states.get(root_key) == "UNRESOLVED":
                all_closed = False
                continue
            possible = _root_possible_routes(home)
            if territorial_basis is not None:
                possible &= {territorial_basis}
            if possible and all(
                (root_key, str(route)) in closed_routes for route in possible
            ):
                continue
            all_closed = False
        if all_closed:
            used = [a for v in closed_routes.values() for a in v]
            reason = (
                AssessmentReason.ROOT_FAMILY_WITHDRAWN
                if withdrawal_driven
                and all(
                    root_states.get(rk) == "CLOSED"
                    for rk in applicable
                )
                else AssessmentReason.ALL_AVAILABLE_ROUTES_CLOSED
            )
            return emit(
                Assessment.CONFIRMED_NOT_AUTHORISED,
                reason,
                used=used,
            )

    # (9) evidencia negativa bloqueada que matchea la query =>
    # indeterminado, nunca CONFIRMED_NOT_ENTITLED (Fintonic).
    if blocked:
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.NEGATIVE_EVIDENCE_BLOCKED,
            used=blocked,
        )

    # Sin cierre completo: abstenciones ordenadas.
    open_root_keys = {
        rk for rk, state in root_states.items() if state == "OPEN"
    }
    matching_on_open_roots = [
        a for a in matching if a.root_key in open_root_keys
    ]
    future_positive = any(
        a.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE
        and date.fromisoformat(a.effective_from) > as_of_date
        for a in matching_on_open_roots
    )
    if future_positive:
        # La ruta existe en evidencia vigente pero no era observable en
        # as_of (MMG @2018): territorialidad historica irresoluble.
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED,
        )
    expired_positive = any(
        a.legal_effect is LegalEffect.ENTITLED_TO_PROVIDE
        and a.effective_to is not None
        and date.fromisoformat(a.effective_to) <= as_of_date
        for a in matching_on_open_roots
    )
    if expired_positive:
        return emit(
            Assessment.NO_ENTITLEMENT_EVIDENCED,
            AssessmentReason.ENTITLEMENT_EXPIRED,
        )
    if closed_routes:
        # Al menos una via cerrada pero queda otra legalmente posible
        # sin resolver: la agregacion no puede abstenerse como
        # NO_ENTITLEMENT_EVIDENCED.
        return emit(
            Assessment.INDETERMINATE,
            AssessmentReason.TERRITORIAL_ENTITLEMENT_UNRESOLVED,
        )
    return emit(
        Assessment.NO_ENTITLEMENT_EVIDENCED,
        AssessmentReason.NO_ASSERTIONS_IN_SCOPE,
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
                "root_key": a.root_key,
                "negative_scope": a.negative_scope,
                "negative_evidence_class": a.negative_evidence_class,
                "admissibility": a.admissibility,
                "evidence": [asdict(sa) for sa in a.source_assertions],
            }
            for a in used
        ),
        assertion_evaluations=evaluations,
        response_freshness=min(freshness_dates).isoformat() if freshness_dates else None,
        diagnostics=tuple(diagnostics),
    )
