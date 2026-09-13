"""G0.2 — Modelo de identidad: resolucion determinista, sin fuzzy joins.

Reglas congeladas:
  - EXACT exige >= 1 identificador verificado que resuelva a un unico
    entity_id sin conflicto. Un match solo por denominacion (aun con un
    unico candidato) es AMBIGUOUS con razon SINGLE_CANDIDATE_NAME_MATCH;
    solo puede convertirse en EXACT adoptando identificadores desde una
    fuente portadora de identificadores con candidato unico (W6).
  - Multiples candidatos por nombre -> AMBIGUOUS.
  - Un identificador resuelto a >= 2 entity_ids -> CONFLICTING_IDENTIFIERS.
  - Nada encontrado -> NOT_FOUND.
Los identificadores se normalizan de forma determinista (trim, mayusculas,
checksum NIF/LEI como validacion, nunca como matching difuso).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from .vocab import IdentityResolutionState

_LEI_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_NIF_CONTROL_NUMBERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIF_CONTROL_LETTERS = "JABCDEFGHI"
_NIF_LETTER_CONTROL_REQUIRED = set("KPQSNWR")


def normalize_identifier(kind: str, value: str) -> str:
    """Normalizacion determinista (trim + mayusculas). Sin fuzzy matching."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"identificador {kind} vacio")
    return value.strip().upper()


def is_valid_nif(nif: str) -> bool:
    """Checksum de NIF/CIF espanol (validacion determinista, no matching)."""
    if not isinstance(nif, str) or not nif.strip():
        return False
    v = normalize_identifier("NIF", nif)
    if len(v) != 9:
        return False
    body, control = v[:8], v[8]
    # DNI: 8 digitos + letra modulo 23.
    if body.isdigit():
        return _NIF_CONTROL_NUMBERS[int(body) % 23] == control
    first, digits = body[0], body[1:]
    if first in "XYZ":
        if not digits.isdigit():
            return False
        return _NIF_CONTROL_NUMBERS[int(str("XYZ".index(first)) + digits) % 23] == control
    if first.isalpha() and first.isupper() and digits.isdigit():
        # CIF: posiciones impares (1,3,5,7) se duplican con suma de digitos;
        # pares (2,4,6) se suman tal cual.
        odd = 0
        for d in digits[0::2]:
            twice = 2 * int(d)
            odd += twice - 9 if twice > 9 else twice
        even = sum(int(d) for d in digits[1::2])
        total = odd + even
        expected_letter = _NIF_CONTROL_LETTERS[total % 10]
        if first in _NIF_LETTER_CONTROL_REQUIRED:
            return control == expected_letter
        return control == expected_letter or control == str(total % 10)
    return False


@lru_cache(maxsize=None)
def _lei_check_digits(base18: str) -> str:
    converted = "".join(str(_LEI_ALPHABET.index(c)) for c in base18) + "00"
    return f"{98 - (int(converted) % 97):02d}"


LEI_DIAGNOSTIC_VERSION = "FINREG_LEI_DIAGNOSTIC_V2"
LEI_DIAGNOSTICS = (
    "VALID",
    "MISSING",
    "INVALID_LENGTH",
    "INVALID_CHARSET",
    "INVALID_CHECK_DIGITS",
)


def lei_diagnostic(lei: str | None) -> str:
    """Diagnostico ISO 17442 versionado (FINREG_LEI_DIAGNOSTIC_V2).

    Separa los defectos que la validez booleana mezclaba: ausencia,
    longitud, alfabeto y digitos de control. El orden es el de
    evaluabilidad: el checksum solo se computa cuando longitud y
    alfabeto permiten interpretar el valor. Nunca repara el valor.
    """
    if not isinstance(lei, str) or not lei.strip():
        return "MISSING"
    v = normalize_identifier("LEI", lei)
    if len(v) != 20:
        return "INVALID_LENGTH"
    if any(c not in _LEI_ALPHABET for c in v):
        return "INVALID_CHARSET"
    if _lei_check_digits(v[:18]) != v[18:]:
        return "INVALID_CHECK_DIGITS"
    return "VALID"


def is_valid_lei(lei: str) -> bool:
    """Formato ISO 17442 (20 caracteres alfanumericos, mod 97-10).

    Capa agregada booleana sobre ``lei_diagnostic``.
    """
    return lei_diagnostic(lei) == "VALID"


@dataclass(frozen=True)
class Identifier:
    kind: str  # NIF | LEI | BDE_REGISTRY_ID | CNMV_REGISTRY_ID | HOME_STATE_ID
    value: str
    source_url: str
    retrieved_at: str  # ISO date

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", normalize_identifier(self.kind, self.value))


@dataclass(frozen=True)
class IdentityIndexEntry:
    entity_id: str
    legal_name: str
    entity_classes: tuple[str, ...]
    identifiers: tuple[Identifier, ...] = field(default_factory=tuple)
    principal_entity_id: str | None = None  # para agentes


@dataclass(frozen=True)
class IdentityResolution:
    state: IdentityResolutionState
    entity_id: str | None
    reason: str
    candidates: tuple[str, ...] = ()


def _identifier_matches(id1: Identifier, kind: str, value: str) -> bool:
    return id1.kind == kind and id1.value == normalize_identifier(kind, value)


def resolve_by_identifier(
    index: list[IdentityIndexEntry], kind: str, value: str
) -> IdentityResolution:
    """Resolucion exacta por identificador (determinista)."""
    target = normalize_identifier(kind, value)
    matches = [
        e.entity_id
        for e in index
        if any(_identifier_matches(i, kind, target) for i in e.identifiers)
    ]
    if len(matches) == 1:
        return IdentityResolution(
            IdentityResolutionState.EXACT, matches[0], "IDENTIFIER_UNIQUE", matches
        )
    if len(matches) > 1:
        return IdentityResolution(
            IdentityResolutionState.CONFLICTING_IDENTIFIERS,
            None,
            "IDENTIFIER_MAPS_TO_MULTIPLE_ENTITIES",
            tuple(matches),
        )
    return IdentityResolution(
        IdentityResolutionState.NOT_FOUND, None, "NO_IDENTIFIER_MATCH"
    )


def resolve_by_name(index: list[IdentityIndexEntry], name: str) -> IdentityResolution:
    """Resolucion por denominacion: nunca produce EXACT (W6).

    Un unico candidato devuelve AMBIGUOUS con razon
    SINGLE_CANDIDATE_NAME_MATCH: la denominacion sola no demuestra
    identidad; exige adopcion de identificadores desde fuente portadora.
    """
    target = " ".join(name.strip().upper().split())
    matches = [
        e.entity_id
        for e in index
        if " ".join(e.legal_name.upper().split()) == target
    ]
    if len(matches) == 1:
        return IdentityResolution(
            IdentityResolutionState.AMBIGUOUS,
            None,
            "SINGLE_CANDIDATE_NAME_MATCH",
            tuple(matches),
        )
    if len(matches) > 1:
        return IdentityResolution(
            IdentityResolutionState.AMBIGUOUS,
            None,
            "MULTIPLE_NAME_CANDIDATES",
            tuple(matches),
        )
    return IdentityResolution(IdentityResolutionState.NOT_FOUND, None, "NO_NAME_MATCH")


def adopt_identifiers_from_source(
    index: list[IdentityIndexEntry],
    source_register_id: str,
    name: str,
) -> IdentityResolution:
    """Adopcion conservadora de identificadores (W6/CNMV-MiCA).

    Dada una denominacion en una fuente SIN identificadores (p. ej. lista
    MiCA de CNMV), busca en ``source_register_id`` (p. ej. ESMA MiCA) una
    entidad cuyo legal_name coincida exactamente y que porte
    identificadores. Si hay exactamente un candidato, devuelve EXACT con
    los identificadores adoptados (razon ADOPTED_FROM_IDENTIFIER_BEARING_SOURCE).
    Si hay varios, AMBIGUOUS.
    """
    target = " ".join(name.strip().upper().split())
    matches = [
        e
        for e in index
        if source_register_id in [i.kind for i in e.identifiers]
        and " ".join(e.legal_name.upper().split()) == target
        and e.identifiers
    ]
    if len(matches) == 1:
        return IdentityResolution(
            IdentityResolutionState.EXACT,
            matches[0].entity_id,
            "ADOPTED_FROM_IDENTIFIER_BEARING_SOURCE",
            (matches[0].entity_id,),
        )
    if len(matches) > 1:
        return IdentityResolution(
            IdentityResolutionState.AMBIGUOUS,
            None,
            "MULTIPLE_NAME_CANDIDATES",
            tuple(e.entity_id for e in matches),
        )
    return IdentityResolution(IdentityResolutionState.NOT_FOUND, None, "NO_NAME_MATCH")
