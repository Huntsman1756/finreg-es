"""Vocabulario regulatorio congelado de G0 (FinReg Espana).

Los enums de este modulo son el vocabulario canonico. Ningun otro
modulo puede introducir terminos fuera de este vocabulario; toda
extension pasa por una nueva version de ruleset/vocabulario.
"""
from __future__ import annotations

from enum import StrEnum


class LegalEffect(StrEnum):
    ENTITLED_TO_PROVIDE = "ENTITLED_TO_PROVIDE"
    NOT_ENTITLED = "NOT_ENTITLED"
    UNKNOWN = "UNKNOWN"


class EntryMechanism(StrEnum):
    AUTHORISATION = "AUTHORISATION"
    NOTIFICATION = "NOTIFICATION"
    REGISTRATION = "REGISTRATION"
    EXEMPTION = "EXEMPTION"
    STATUTORY_ENTITLEMENT = "STATUTORY_ENTITLEMENT"


class TerritorialBasis(StrEnum):
    DOMESTIC = "DOMESTIC"
    BRANCH = "BRANCH"
    FREEDOM_TO_PROVIDE_SERVICES = "FREEDOM_TO_PROVIDE_SERVICES"
    OTHER = "OTHER"


class Assessment(StrEnum):
    """ASSESSMENT_SEMANTICS_V1 — congelada con los artefactos G0."""
    CONFIRMED_AUTHORISED = "CONFIRMED_AUTHORISED"
    NO_ENTITLEMENT_EVIDENCED = "NO_ENTITLEMENT_EVIDENCED"
    CONFIRMED_NOT_AUTHORISED = "CONFIRMED_NOT_AUTHORISED"
    INDETERMINATE = "INDETERMINATE"


class AssessmentV2(StrEnum):
    """ASSESSMENT_SEMANTICS_V2 (G1+): el resultado público responde si la
    entidad puede prestar la actividad; ``entry_mechanism`` explica por
    qué (AUTHORISATION | REGISTRATION | NOTIFICATION | …). Un AISP
    registrado es CONFIRMED_ENTITLED, nunca "authorised"."""
    CONFIRMED_ENTITLED = "CONFIRMED_ENTITLED"
    NO_ENTITLEMENT_EVIDENCED = "NO_ENTITLEMENT_EVIDENCED"
    CONFIRMED_NOT_ENTITLED = "CONFIRMED_NOT_ENTITLED"
    INDETERMINATE = "INDETERMINATE"


class IdentityResolutionState(StrEnum):
    EXACT = "EXACT"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"
    CONFLICTING_IDENTIFIERS = "CONFLICTING_IDENTIFIERS"


class NegativeEvidenceCapability(StrEnum):
    COMPLETE_ENUMERATION = "COMPLETE_ENUMERATION"
    EXPLICIT_NEGATIVE_ONLY = "EXPLICIT_NEGATIVE_ONLY"
    NO_NEGATIVE_INFERENCE = "NO_NEGATIVE_INFERENCE"


class NegativeEvidenceClass(StrEnum):
    """Clase de evidencia negativa por hecho/asercion (G1-E, E1).

    Distinto de ``NegativeEvidenceCapability`` (propiedad poblacional
    del contrato de fuente): esto clasifica cada hecho negativo
    materializado. ``NONE`` no se emite — marca la ausencia de
    evidencia negativa en expectativas/corpus.
    """
    NONE = "NONE"
    EXPLICIT_WITHDRAWAL = "EXPLICIT_WITHDRAWAL"
    EXPIRY = "EXPIRY"
    ENUMERATED_ABSENCE = "ENUMERATED_ABSENCE"
    ENTITY_BAJA = "ENTITY_BAJA"


class NegativeScope(StrEnum):
    """Ambito de un hecho negativo (G1-E, E4).

    Una retirada de raiz cierra la familia de rutas que descienden
    mecanicamente de esa autorizacion, sin inventar una base
    territorial nunca observada. Una ausencia enumerada es
    especifica de (actividad, route_key).
    """
    ROOT_FAMILY = "ROOT_FAMILY"
    ROUTE_CAPABILITY = "ROUTE_CAPABILITY"


class SourceDateReliability(StrEnum):
    TRUSTED = "TRUSTED"
    SUSPECT = "SUSPECT"
    UNAVAILABLE = "UNAVAILABLE"


class ScopeStatus(StrEnum):
    IN_SCOPE = "IN_SCOPE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    PROPOSED = "PROPOSED"


class AssessmentReason(StrEnum):
    # Gates de identidad (C1: no son conclusiones regulatorias)
    IDENTITY_NOT_FOUND = "IDENTITY_NOT_FOUND"
    AMBIGUOUS_IDENTITY = "AMBIGUOUS_IDENTITY"
    CONFLICTING_IDENTIFIERS = "CONFLICTING_IDENTIFIERS"
    # Gates de evidencia
    NO_ASSERTIONS_IN_SCOPE = "NO_ASSERTIONS_IN_SCOPE"
    ALL_EVIDENCE_STALE = "ALL_EVIDENCE_STALE"
    ENTITLEMENT_EXPIRED = "ENTITLEMENT_EXPIRED"
    CONFLICTING_ASSERTIONS = "CONFLICTING_ASSERTIONS"
    UNINTERPRETABLE_EVIDENCE = "UNINTERPRETABLE_EVIDENCE"
    ASSERTION_OUT_OF_SOURCE_SCOPE = "ASSERTION_OUT_OF_SOURCE_SCOPE"
    AGENT_ASSERTION_MISSING_PRINCIPAL = "AGENT_ASSERTION_MISSING_PRINCIPAL"
    # Conclusión
    SUPPORTED_BY_ACTIVE_ASSERTIONS = "SUPPORTED_BY_ACTIVE_ASSERTIONS"
    EXPLICIT_NEGATIVE_EVIDENCE = "EXPLICIT_NEGATIVE_EVIDENCE"
    # ASSESSMENT_SEMANTICS_V2 (G1-A7 preregistrado)
    ACTIVE_ENTITLEMENT_EVIDENCED = "ACTIVE_ENTITLEMENT_EVIDENCED"
    WITHDRAWAL_SEMANTICS_DEFERRED = "WITHDRAWAL_SEMANTICS_DEFERRED"
    MALFORMED_STATUS_SEQUENCE = "MALFORMED_STATUS_SEQUENCE"
    TERRITORIAL_ENTITLEMENT_UNRESOLVED = "TERRITORIAL_ENTITLEMENT_UNRESOLVED"
    PARENT_STATUS_NOT_CHILD_ENTITLEMENT = "PARENT_STATUS_NOT_CHILD_ENTITLEMENT"
    INSUFFICIENT_LEGAL_BASIS = "INSUFFICIENT_LEGAL_BASIS"
    # G1-D: ruta delegada y categoria territorial sin fuente primaria
    AGENT_DELEGATED_ROUTE_NO_INDEPENDENT_ENTITLEMENT = (
        "AGENT_DELEGATED_ROUTE_NO_INDEPENDENT_ENTITLEMENT"
    )
    TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP = (
        "TERRITORIAL_ROUTE_UNRESOLVED_LIMITED_LP"
    )


# Actividades canónicas (conjunto mínimo congelado para G0; extender
# requiere nueva version de vocabulario documentada).
ACTIVITIES = (
    "DEPOSIT_TAKING",
    "LENDING",
    "PAYMENT_SERVICES",
    "E_MONEY_ISSUANCE",
    "INVESTMENT_SERVICES",
    "INVESTMENT_ADVICE_NON_MIFID",
    "FUND_MANAGEMENT",
    "CRYPTO_ASSET_SERVICES",
    # G1: resolución H9-A — Annex 2019/410 Tables 2/3/5 distinguen
    # registration de authorisation; AISP presta sólo servicios de
    # información de cuentas (art. 33 PSD2).
    "ACCOUNT_INFORMATION_SERVICES",
    # G1-C: servicios MiCA art. 3(16) letras a-j, granularidad por
    # servicio (la vía art. 60/63 se decide por entity x service).
    "CRYPTO_CUSTODY_ADMINISTRATION",
    "CRYPTO_TRADING_PLATFORM",
    "CRYPTO_EXCHANGE_FUNDS",
    "CRYPTO_EXCHANGE_CRYPTO",
    "CRYPTO_ORDER_EXECUTION",
    "CRYPTO_PLACING",
    "CRYPTO_ORDER_RECEPTION_TRANSMISSION",
    "CRYPTO_ADVICE",
    "CRYPTO_PORTFOLIO_MANAGEMENT",
    "CRYPTO_TRANSFER",
    # G1-E (E2): servicios PSD2 Annex I granulares. Namespace canonico
    # semantico, desacoplado del esquema de cada fuente; el codigo raw
    # (PS_03C, "3.C", "7", …) queda en raw_capability_code/provenance.
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
)

# Clases de entidad (conjunto mínimo congelado para G0).
ENTITY_CLASSES = (
    "CREDIT_INSTITUTION",
    "PAYMENT_INSTITUTION",
    "E_MONEY_INSTITUTION",
    "INVESTMENT_FIRM_ESI",
    "FINANCIAL_ADVISER_EAF",
    "FUND_MANAGER_SGIIC",
    "CASP",
    "PSP_AGENT",
    # G1: tipos EBA PSD2 registrados (no autorizados) — Annex 2019/410
    # Tables 2/3/5 exigen "date of registration", no "of authorisation".
    "EXEMPTED_PAYMENT_INSTITUTION",
    "EXEMPTED_E_MONEY_INSTITUTION",
    "ACCOUNT_INFORMATION_SERVICE_PROVIDER",
)

# Estados reportados por la capa de registro (G1-A). No son efectos
# jurídicos: un status WITHDRAWN es un hecho reportado; su lectura
# jurídica (negativo, expiración) pertenece a G1-E.
REPORTED_STATUSES = (
    "ACTIVE",
    "WITHDRAWN",
    "UNKNOWN",
    "TERRITORIAL_ENTITLEMENT_DEFERRED",
    # G1-D: categoria territorial observada sin definicion por fuente
    # primaria (p. ej. LIMITED PSC EN REGIMEN DE LP) — abstencion.
    "TERRITORIAL_ROUTE_UNRESOLVED",
)

# Procedencia probatoria de una aserción (G1-A, política A5):
# T2 EBA = reporte oficial NCA→EBA, no constitutivo.
EVIDENCE_BASES = ("NCA_REPORTED_VIA_EBA", "NCA_PRIMARY", "STATISTICAL")
