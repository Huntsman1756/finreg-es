"""Carga determinista de fixtures (identity index, aserciones, escenarios)."""
from __future__ import annotations

from pathlib import Path

from .canonical import strict_json_loads
from .identity import Identifier, IdentityIndexEntry
from .semantics import EntitlementAssertion, SourceAssertion
from .vocab import LegalEffect


def load_identity_index(path: Path) -> list[IdentityIndexEntry]:
    raw = strict_json_loads(path.read_text(encoding="utf-8"))
    entries = []
    for e in raw["entities"]:
        entries.append(
            IdentityIndexEntry(
                entity_id=e["entity_id"],
                legal_name=e["legal_name"],
                entity_classes=tuple(e["entity_classes"]),
                identifiers=tuple(
                    Identifier(
                        kind=i["kind"],
                        value=i["value"],
                        source_url=i["source_url"],
                        retrieved_at=i["retrieved_at"],
                    )
                    for i in e.get("identifiers", [])
                ),
                principal_entity_id=e.get("principal_entity_id"),
            )
        )
    return entries


def load_assertions(path: Path) -> list[EntitlementAssertion]:
    raw = strict_json_loads(path.read_text(encoding="utf-8"))
    out = []
    for a in raw["assertions"]:
        out.append(
            EntitlementAssertion(
                assertion_id=a["assertion_id"],
                register_id=a["register_id"],
                entity_id=a["entity_id"],
                entity_class=a["entity_class"],
                activity=a["activity"],
                jurisdiction=a["jurisdiction"],
                legal_effect=LegalEffect(a["legal_effect"]),
                entry_mechanism=a["entry_mechanism"],
                territorial_basis=a["territorial_basis"],
                legal_basis=a["legal_basis"],
                effective_from=a["effective_from"],
                effective_to=a.get("effective_to"),
                scope=a.get("scope", ""),
                principal_entity_id=a.get("principal_entity_id"),
                derived_by=a.get("derived_by"),
                source_assertions=tuple(
                    SourceAssertion(**s) for s in a["source_assertions"]
                ),
            )
        )
    return out
