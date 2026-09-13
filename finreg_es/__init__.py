"""FinReg Espana — G0: contratos, identidad, cobertura y semantica."""
from .contracts import SourceContract, load_contract, validate_contract_dict
from .vocab import (
    ACTIVITIES,
    ENTITY_CLASSES,
    Assessment,
    AssessmentReason,
    EntryMechanism,
    IdentityResolutionState,
    LegalEffect,
    NegativeEvidenceCapability,
    SourceDateReliability,
    TerritorialBasis,
)

__all__ = [
    "SourceContract",
    "load_contract",
    "validate_contract_dict",
    "ACTIVITIES",
    "ENTITY_CLASSES",
    "Assessment",
    "AssessmentReason",
    "EntryMechanism",
    "IdentityResolutionState",
    "LegalEffect",
    "NegativeEvidenceCapability",
    "SourceDateReliability",
    "TerritorialBasis",
]
