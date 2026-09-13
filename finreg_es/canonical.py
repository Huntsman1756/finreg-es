"""FINREG_CANONICAL_JSON_V1 — canonicalizacion determinista y hashing.

IMPORTANTE: este modulo **no** implementa RFC 8785 / JCS y **no afirma**
compatibilidad con RFC 8785. Es un perfil propio, suficiente para el
subconjunto de datos de FinReg G0 y verificado por tests.

ALLOWED
  object, array, string, integer, boolean, null
FORBIDDEN
  float, NaN, Infinity, duplicate keys
DATES/TIMESTAMPS
  strings ISO-8601
SERIALIZATION
  UTF-8, orden determinista de claves, sin whitespace insignificante,
  preservacion exacta de Unicode (sin normalizacion NFC/NFKC)

Si en el futuro se necesita interoperabilidad JCS real, se implementara y
testeara RFC 8785 completo por separado; no se reutilizara este modulo
bajo el nombre JCS.
"""
from __future__ import annotations

import hashlib
import json

_MAX_SAFE_INT = 2**53 - 1


def canonical_json(obj: object) -> str:
    """Serializa ``obj`` de forma canonica bajo FINREG_CANONICAL_JSON_V1."""
    _assert_allowed_types(obj)
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_hex(obj: object) -> str:
    """SHA-256 hex del contenido canonico de ``obj``."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def strict_json_loads(text: str) -> object:
    """Carga JSON rechazando floats, NaN/Infinity y claves duplicadas.

    ``json.loads`` estandar acepta floats, NaN/Infinity y silenciosamente
    conserva la ultima de las claves duplicadas; los tres casos rompen la
    garantia de determinismo de FINREG_CANONICAL_JSON_V1.
    """

    def _object_pairs_hook(pairs: list[tuple[str, object]]) -> dict:
        seen = set()
        for key, _ in pairs:
            if key in seen:
                raise ValueError(f"clave duplicada en JSON: {key!r}")
            seen.add(key)
        return dict(pairs)

    def _reject_float(value: str) -> object:
        raise ValueError(f"float prohibido en datos G0: {value!r}")

    def _reject_constant(value: str) -> object:
        raise ValueError(f"constante no finita prohibida en datos G0: {value!r}")

    return json.loads(
        text,
        object_pairs_hook=_object_pairs_hook,
        parse_float=_reject_float,
        parse_constant=_reject_constant,
    )


def _assert_allowed_types(obj: object) -> None:
    if obj is None or isinstance(obj, (str, bool)):
        return
    if isinstance(obj, int):
        if not (-_MAX_SAFE_INT - 1 <= obj <= _MAX_SAFE_INT):
            raise ValueError(f"integer fuera del rango seguro: {obj}")
        return
    if isinstance(obj, float):
        raise ValueError("floats prohibidos en FINREG_CANONICAL_JSON_V1 (usar enteros)")
    if isinstance(obj, list):
        for item in obj:
            _assert_allowed_types(item)
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                raise ValueError("claves no-string prohibidas en FINREG_CANONICAL_JSON_V1")
            _assert_allowed_types(value)
        return
    raise TypeError(f"tipo no soportado en FINREG_CANONICAL_JSON_V1: {type(obj)!r}")
