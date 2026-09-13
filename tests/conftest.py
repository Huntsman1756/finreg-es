from pathlib import Path

import pytest

from finreg_es.canonical import strict_json_loads
from finreg_es.contracts import load_contract, staleness_policy, validate_contract_dict
from finreg_es.loaders import load_assertions, load_identity_index

ROOT = Path(__file__).parents[1]
CONTRACTS_DIR = ROOT / "fixtures" / "contracts"
REGULATORY_DIR = ROOT / "fixtures" / "regulatory"


@pytest.fixture(scope="session")
def contract_paths() -> list[Path]:
    return sorted(CONTRACTS_DIR.glob("*.json"))


@pytest.fixture(scope="session")
def all_contracts(contract_paths) -> dict[str, object]:
    out = {}
    for p in contract_paths:
        c = load_contract(p)
        out[c.register_id] = c
    return out


@pytest.fixture(scope="session")
def identity_index():
    return load_identity_index(REGULATORY_DIR / "identity-index.json")


@pytest.fixture(scope="session")
def assertions():
    return load_assertions(REGULATORY_DIR / "assertions.json")


@pytest.fixture(scope="session")
def scenarios():
    return strict_json_loads((REGULATORY_DIR / "scenarios.json").read_text(encoding="utf-8"))


def test_contract_files_exist(contract_paths):
    assert len(contract_paths) >= 6


def test_contract_dicts_validate(contract_paths):
    for p in contract_paths:
        validate_contract_dict(strict_json_loads(p.read_text(encoding="utf-8")))
