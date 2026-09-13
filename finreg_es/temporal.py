"""Temporalidad: separacion retrieved_at / source_as_of / effective_* / observed_current.

freshness_at = source_as_of ?? retrieved_at
response_freshness = min(freshness_at de los claims necesarios)

La caducidad (staleness) se mide sobre freshness_at de la evidencia mas
recente que sostiene el claim, nunca sobre la fecha de efecto juridico.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Freshness:
    """Frescura de un claim de fuente."""

    retrieved_at: date
    source_as_of: date | None
    source_date_reliability: str  # TRUSTED | SUSPECT | UNAVAILABLE

    @property
    def freshness_at(self) -> date:
        return self.source_as_of if self.source_as_of is not None else self.retrieved_at


def is_stale(freshness: Freshness, max_staleness_days: int | None, as_of: date) -> bool:
    """True si la frescura excede la politica del registro.

    ``max_staleness_days=None`` significa "politica no definida": tratamos
    la evidencia como caducada (conservador) hasta que el contrato fije
    un valor.
    """
    if max_staleness_days is None:
        return True
    age = (as_of - freshness.freshness_at).days
    return age > max_staleness_days


def response_freshness(freshness_list: list[Freshness]) -> date | None:
    """min(freshness_at) de los claims necesarios para la respuesta."""
    if not freshness_list:
        return None
    return min(f.freshness_at for f in freshness_list)


def suspect_source_as_of(
    content_hash_t1: str,
    content_hash_t2: str,
    source_as_of_t1: str | None,
    source_as_of_t2: str | None,
) -> bool:
    """Regla congelada de fiabilidad de fecha de fuente.

    ``content_hash(t1) != content_hash(t2) AND source_as_of(t1) ==
    source_as_of(t2)`` => ``SUSPECT``: la fuente cambio el contenido sin
    mover su fecha declarada. Puede ser una correccion editorial, no un
    error: se marca, no se descarta. Dos observaciones distintas con
    ``source_as_of`` distinto son una revision legitima, no sospecha.
    """
    return content_hash_t1 != content_hash_t2 and source_as_of_t1 == source_as_of_t2
