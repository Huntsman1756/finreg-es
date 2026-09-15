"""Genera ``fixtures/g2/e0/bitemporal-cases.json`` (G2-E0, task
``g2-e0-select-cases``).

Preregistro de casos bitemporales REALES para G2-E (AssessmentQuery
con ``valid_at`` x ``known_at``). Cero codigo de produccion: este
script solo inspecciona el corpus congelado y emite el fixture de
casos; la evaluacion usa la maquinaria existente
(``ASSESSMENT_SEMANTICS_V3`` + regla anti-retroproyeccion del contrato
G2-A sec.8) como ORACULO DE VERIFICACION — las expectativas vienen
declaradas en ``CASES`` y el build falla si el motor congelado las
contradice (verify-before-freeze, no derive-after-freeze).

Semantica preregistrada de la query bitemporal:

- ``valid_at`` alimenta ``as_of`` del motor congelado: ``covers()``,
  ``effective_effect_at()``, ``status_intervals [from,to)`` y la
  frescura se evaluan en tiempo juridico.
- ``known_at`` filtra la evidencia observable: un artefacto
  (asercion derivada o reported_fact) es observable en K si y solo si
  TODAS sus ``source_assertions`` tienen ``retrieved_at <= K`` — un
  producto derivado no puede ser mas cognoscible que su input menos
  observado (contrato sec.8: solo claims con ``retrieved_at <= K``).
- ``known_at`` NUNCA modifica ``effective_from``/``effective_to`` ni
  los intervalos; ``source_as_of`` nunca se usa como tiempo de
  observacion (``retrieved_at`` es transaction time).
- K es una fecha; un ``retrieved_at`` con hora es observable si su
  fecha calendario es ``<= K``.

Universo de evidencia: la cadena G1-E congelada
(``derived-assertions-g1-e-002.json`` + ``corpus-g1-e-001.json`` +
``claim-ledger-g1-e-001.json``). El par G2 EBA 14/09->15/09 alimenta
los findings E0-F01/E0-F02 (los 67 added son todos PSD_AG sin
ENT_AUT propia ni services.ES: el caso known_at preferido del
case_mix es NON_REPRESENTABLE y se documenta, no se fuerza).
"""
import copy
import hashlib
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finreg_es.canonical import canonical_json, sha256_hex, strict_json_loads
from finreg_es.contracts import load_contract
from finreg_es.derivation import to_entitlement_assertions, to_identity_index
from finreg_es.semantics import assess

ARTIFACT_PATH = ROOT / "fixtures/g1/derived-assertions-g1-e-002.json"
CORPUS_PATH = ROOT / "fixtures/g1/corpus-g1-e-001.json"
LEDGER_PATH = ROOT / "fixtures/g1/claim-ledger-g1-e-001.json"
COMPARISON_PATH = (
    ROOT / "fixtures/g2/comparisons/eba-psd2-20260914-vs-20260915.json"
)
EVENTS_PATH = ROOT / "fixtures/g2/events/eba-psd2-20260914-vs-20260915.json"
CONTRACTS_DIR = ROOT / "fixtures/contracts"
OUT = ROOT / "fixtures/g2/e0/bitemporal-cases.json"


# ------------------------------------------------------------------
# Casos preregistrados. expected_* se declara ANTES de evaluar; el
# build verifica (motor V3 congelado + filtro K) y aborta si diverge.
# ------------------------------------------------------------------
CASES = [
    {
        "case_id": "E0-01",
        "kind": "valid_at_interval_boundary",
        "axis": "valid_at",
        "entity_id": "E3-001",
        "legal_name": "DENIZEN GLOBAL FINANCIAL, S.A.",
        "root_key": "EBA|PSD_PI|ES_BE!6822",
        "activity": "MONEY_REMITTANCE",
        "jurisdiction": "ES",
        "territorial_basis": None,
        "rationale": (
            "Frontera exclusiva del intervalo ENT_AUT real "
            "[2019-03-15,2020-07-23): el assessment cambia al cruzar "
            "la fecha de retirada con known_at fijo. Doble K (13/14) "
            "demuestra que el veredicto no depende de la observacion "
            "BdE: EBA sola ya sostiene ambos lados de la frontera."
        ),
        "probes": [
            {"valid_at": "2020-07-22", "known_at": "2026-09-13",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2020-07-22", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2020-07-23", "known_at": "2026-09-13",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
            {"valid_at": "2020-07-23", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
            {"valid_at": "2026-09-14", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
        ],
    },
    {
        "case_id": "E0-02",
        "kind": "valid_at_interval",
        "axis": "valid_at",
        "entity_id": "E3-002",
        "legal_name": "MMG Corporation s.r.o.",
        "root_key": "EBA|PSD_PI|CZ_CNB!29142024",
        "activity": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
        "jurisdiction": "ES",
        "territorial_basis": None,
        "rationale": (
            "Intervalos raiz reales [2017-05-30,2019-07-12) + "
            "[2024-07-12,~): cruzar el gap de retirada/reautorizacion "
            "con known_at fijo reproduce INDETERMINATE territorial "
            "(raiz abierta, ruta ES no observada historicamente), "
            "NOT_ENTITLED (raiz cerrada en el gap) y ENTITLED "
            "(reautorizada + Services{ES} observados, "
            "effective_from=EVIDENCE_AS_OF)."
        ),
        "probes": [
            {"valid_at": "2018-06-01", "known_at": "2026-09-14",
             "expected_assessment": "INDETERMINATE",
             "expected_reason": "TERRITORIAL_ENTITLEMENT_UNRESOLVED"},
            {"valid_at": "2020-01-01", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
            {"valid_at": "2026-09-14", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
        ],
    },
    {
        "case_id": "E0-03",
        "kind": "known_at_observation",
        "axis": "known_at",
        "entity_id": "E3-001",
        "legal_name": "DENIZEN GLOBAL FINANCIAL, S.A.",
        "root_key": "EBA|PSD_PI|ES_BE!6822",
        "activity": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
        "jurisdiction": "ES",
        "territorial_basis": None,
        "rationale": (
            "Mismo valid_at, distinto known_at: la ventana probatoria "
            "BdE [2011-06-09,2020-07-23) solo era observable desde "
            "K=2026-09-14 (retrieved_at real del xlsx BdE); la "
            "evidencia EBA (retrieved 2026-09-13) cubre solo "
            "[2019-03-15,2020-07-23). En 2015 el veredicto cambia "
            "unicamente porque el claim BdE aun no habia sido "
            "observado — la respuesta a questions_falsables.1."
        ),
        "probes": [
            {"valid_at": "2015-06-01", "known_at": "2026-09-13",
             "expected_assessment": "NO_ENTITLEMENT_EVIDENCED",
             "expected_reason": "NO_ASSERTIONS_IN_SCOPE"},
            {"valid_at": "2015-06-01", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2020-07-22", "known_at": "2026-09-13",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2020-07-22", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
        ],
    },
    {
        "case_id": "E0-04",
        "kind": "known_at_observation",
        "axis": "known_at",
        "entity_id": "E3-010",
        "legal_name": "THUNES FINANCIAL SERVICES",
        "root_key": "EBA|PSD_PI|FR_ACPR!384558",
        "activity": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
        "jurisdiction": "ES",
        "territorial_basis": None,
        "rationale": (
            "Conocimiento retroactivo (contrato sec.8, segundo "
            "ejemplo): la retirada raiz 2026-08-27 fue observada el "
            "2026-09-13. Con K anterior a esa observacion la entidad "
            "no tiene evidencia alguna; con K posterior el veredicto "
            "en valid_at=2026-09-01 ya es NOT_ENTITLED — la "
            "observacion llego despues del hecho que describe."
        ),
        "probes": [
            {"valid_at": "2026-09-01", "known_at": "2026-09-12",
             "expected_assessment": "NO_ENTITLEMENT_EVIDENCED",
             "expected_reason": "NO_ASSERTIONS_IN_SCOPE"},
            {"valid_at": "2026-09-01", "known_at": "2026-09-13",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
            {"valid_at": "2026-09-01", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_NOT_ENTITLED",
             "expected_reason": "ROOT_FAMILY_WITHDRAWN"},
        ],
    },
    {
        "case_id": "E0-05",
        "kind": "control",
        "axis": "known_at",
        "entity_id": "E3-002",
        "legal_name": "MMG Corporation s.r.o.",
        "root_key": "EBA|PSD_PI|CZ_CNB!29142024",
        "activity": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
        "jurisdiction": "ES",
        "territorial_basis": None,
        "rationale": (
            "Control: mover known_at dentro del rango de observaciones "
            "disponibles (todas EBA retrieved 2026-09-13 para esta "
            "entidad) no cambia el assessment. La observacion EBA del "
            "15/09 existe en el corpus pero aun no ha entrado a la "
            "cadena de derivacion — K=2026-09-15 es observablemente "
            "equivalente a K=2026-09-14 para esta evidencia."
        ),
        "probes": [
            {"valid_at": "2026-09-14", "known_at": "2026-09-13",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2026-09-14", "known_at": "2026-09-14",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
            {"valid_at": "2026-09-14", "known_at": "2026-09-15",
             "expected_assessment": "CONFIRMED_ENTITLED",
             "expected_reason": "ACTIVE_ENTITLEMENT_EVIDENCED"},
        ],
    },
]

# Findings fail-closed del case_mix (ver doc). No son casos: son
# resultados de inspeccion del corpus que el preregistro exige
# declarar antes de implementar G2-E.
FINDINGS = [
    {
        "finding_id": "E0-F01",
        "classification": "NON_REPRESENTABLE_IN_CURRENT_CORPUS",
        "subject": "case_mix.known_at preferido (record added con ENT_AUT interpretable)",
        "detail": (
            "Los 67 records added del par EBA 20260914->20260915 son "
            "TODOS EntityType=PSD_AG (agentes). Inspeccion del "
            "snapshot congelado eba-psd2-202609150000.zip "
            "(sha256 a582908cfa99f3ab…): 0/67 tienen "
            "properties.ENT_AUT propia, 0/67 tienen services.ES; sus "
            "campos son identidad/direccion del agente + "
            "DER_CHI_ENT_AUT (estado heredado del parent). Ningun "
            "record added declara effective_from juridico propio — "
            "su unico ancla temporal es la observacion "
            "(EVIDENCE_AS_OF), y 'presencia != entitlement' "
            "(catalogo G2-C0). El caso known_at preferido del "
            "case_mix no es representable: se documenta aqui "
            "(fail-closed) y el eje known_at se cubre con E0-03/E0-04 "
            "sobre retrieved_at reales divergentes del corpus G1-E."
        ),
        "evidence": {
            "added_total": 67,
            "added_entity_types": {"PSD_AG": 67},
            "added_with_ENT_AUT": 0,
            "added_with_services_ES": 0,
            "source_comparison": (
                "fixtures/g2/comparisons/"
                "eba-psd2-20260914-vs-20260915.json"
            ),
            "source_snapshot": (
                "fixtures/g2/sources/raw/eba-psd2-202609150000.zip"
            ),
        },
    },
    {
        "finding_id": "E0-F02",
        "classification": "CATALOG_EXTENSION_CANDIDATE",
        "subject": "DER_CHI_ENT_AUT Active<->Inactive en records PSD_AG",
        "detail": (
            "Entre los 312 changed del par hay 278 transiciones en "
            "properties.DER_CHI_ENT_AUT (todas en PSD_AG): 276 "
            "Active->Inactive y 2 Inactive->Active "
            "(PSD_AG:ES_BE!006842!60607076Y, "
            "PSD_AG:ES_BE!006842!Y1928881T). Concentracion por "
            "parent: PSD_EPI ES_BE!6904 (140), PSD_PI ES_BE!6842 "
            "(105), PSD_PI FR_ACPR!54167 (23), PSD_PI "
            "CZ_CNB!01993143 (5), PSD_PI ES_BE!6828 (4), PSD_PI "
            "ES_BE!6813 (1); ninguno esta en el corpus G1-E. "
            "DER_CHI_ENT_AUT tiene semantica congelada en G1-D "
            "(estado Active/Inactive heredado del parent): el bulk "
            "de desactivacion de agentes de ES_BE!6904 es un "
            "candidato relevante para una extension preregistrada "
            "futura del catalogo G2-C0. NO es requisito de E0 ni "
            "clasificacion retroactiva: los 312 changed permanecen "
            "UNCLASSIFIED_STRUCTURAL_CHANGE/BLOCKED en el artefacto "
            "de eventos congelado."
        ),
        "evidence": {
            "der_chi_ent_aut_changed": 278,
            "transitions": {"Active->Inactive": 276, "Inactive->Active": 2},
            "inactive_to_active_record_keys": [
                "PSD_AG:ES_BE!006842!60607076Y",
                "PSD_AG:ES_BE!006842!Y1928881T",
            ],
            "parents": {
                "PSD_EPI:ES_BE!6904": 140,
                "PSD_PI:ES_BE!6842": 105,
                "PSD_PI:FR_ACPR!54167": 23,
                "PSD_PI:CZ_CNB!01993143": 5,
                "PSD_PI:ES_BE!6828": 4,
                "PSD_PI:ES_BE!6813": 1,
            },
            "parent_in_g1e_corpus": False,
        },
    },
]


def _kdate(value: str) -> date:
    """Fecha calendario de un retrieved_at/K (date o datetime ISO)."""
    return date.fromisoformat(str(value)[:10])


def _observable(item: dict, known_at: str) -> bool:
    """Un artefacto derivado es observable en K sii TODAS sus
    source_assertions tienen retrieved_at <= K (fecha)."""
    sources = item.get("source_assertions") or []
    return bool(sources) and all(
        _kdate(s["retrieved_at"]) <= _kdate(known_at) for s in sources
    )


def _filtered_artifact(doc: dict, known_at: str) -> dict:
    filtered = copy.deepcopy(doc)
    filtered["assertions"] = [
        a for a in doc["assertions"] if _observable(a, known_at)
    ]
    filtered["reported_facts"] = [
        f
        for f in doc.get("reported_facts", [])
        if _observable(f, known_at)
    ]
    return filtered


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    artifact = strict_json_loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    contracts = {
        c.register_id: c
        for c in (
            load_contract(p) for p in sorted(CONTRACTS_DIR.glob("*.json"))
        )
    }
    index = to_identity_index(artifact)

    cases_out: list[dict] = []
    divergences: list[str] = []
    for case in CASES:
        universe_assertions = [
            a
            for a in artifact["assertions"]
            if a["entity_id"] == case["entity_id"]
            and a["activity"] == case["activity"]
            and a["jurisdiction"] == case["jurisdiction"]
            and (
                case["territorial_basis"] is None
                or a["territorial_basis"] == case["territorial_basis"]
            )
        ]
        universe_facts = [
            f
            for f in artifact.get("reported_facts", [])
            if f.get("corpus_id") == case["entity_id"]
        ]

        probes_out: list[dict] = []
        for probe in case["probes"]:
            valid_at = probe["valid_at"]
            known_at = probe["known_at"]
            filtered = _filtered_artifact(artifact, known_at)
            result = assess(
                case["entity_id"],
                index,
                activity=case["activity"],
                jurisdiction=case["jurisdiction"],
                as_of=valid_at,
                assertions=to_entitlement_assertions(filtered),
                contracts=contracts,
                semantics_version="V3",
                reported_facts=filtered.get("reported_facts", []),
                territorial_basis=case["territorial_basis"],
            )
            assessment = str(result.assessment)
            reason = str(result.reason)
            if (
                assessment != probe["expected_assessment"]
                or reason != probe["expected_reason"]
            ):
                divergences.append(
                    f"{case['case_id']} ({valid_at},{known_at}): "
                    f"esperado {probe['expected_assessment']}/"
                    f"{probe['expected_reason']} != "
                    f"{assessment}/{reason}"
                )
            usable_assertions = sorted(
                a["assertion_id"]
                for a in universe_assertions
                if _observable(a, known_at)
            )
            usable_facts = sorted(
                f["fact_id"]
                for f in universe_facts
                if _observable(f, known_at)
            )
            probes_out.append(
                {
                    "valid_at": valid_at,
                    "known_at": known_at,
                    "expected_assessment": probe["expected_assessment"],
                    "expected_reason": probe["expected_reason"],
                    "usable_assertion_ids": usable_assertions,
                    "usable_fact_ids": usable_facts,
                    "excluded_after_K_assertion_ids": sorted(
                        a["assertion_id"]
                        for a in universe_assertions
                        if not _observable(a, known_at)
                    ),
                    "excluded_after_K_fact_ids": sorted(
                        f["fact_id"]
                        for f in universe_facts
                        if not _observable(f, known_at)
                    ),
                    "used_assertion_ids": [
                        a["assertion_id"] for a in result.assertions
                    ],
                    "diagnostics": list(result.diagnostics),
                }
            )
        cases_out.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "axis": case["axis"],
                "entity_id": case["entity_id"],
                "legal_name": case["legal_name"],
                "root_key": case["root_key"],
                "query": {
                    "activity": case["activity"],
                    "jurisdiction": case["jurisdiction"],
                    "territorial_basis": case["territorial_basis"],
                },
                "rationale": case["rationale"],
                "evidence_universe": {
                    "assertion_ids": sorted(
                        a["assertion_id"] for a in universe_assertions
                    ),
                    "fact_ids": sorted(
                        f["fact_id"] for f in universe_facts
                    ),
                    "retrieved_at_values": sorted(
                        {
                            s["retrieved_at"]
                            for item in (
                                list(universe_assertions)
                                + list(universe_facts)
                            )
                            for s in item.get("source_assertions", [])
                        }
                    ),
                },
                "probes": probes_out,
            }
        )

    if divergences:
        for line in divergences:
            print(f"DIVERGENCE {line}", file=sys.stderr)
        raise SystemExit(
            "expectativas preregistradas divergen del oraculo V3+K — "
            "STOP: auditar, no ajustar"
        )

    doc = {
        "artifact": "g2-e0-bitemporal-cases",
        "cases_meta": {
            "version": "FINREG_G2_E0_CASES_V1",
            "gate": "G2-E0",
            "task": "g2-e0-select-cases",
            "semantics_version": "ASSESSMENT_SEMANTICS_V3",
            "unit": (
                "entity_id x activity x jurisdiction x "
                "(valid_at, known_at) [x territorial_basis]"
            ),
            "valid_at_semantics": (
                "alimenta as_of del motor congelado: covers(), "
                "effective_effect_at(), status_intervals [from,to) y "
                "staleness se evaluan en tiempo juridico"
            ),
            "known_at_semantics": (
                "filtro de evidencia observable (contrato G2-A sec.8): "
                "una asercion/reported_fact es observable sii TODAS "
                "sus source_assertions tienen retrieved_at <= K; "
                "nunca modifica effective_from/effective_to ni los "
                "intervalos; source_as_of nunca es tiempo de "
                "observacion"
            ),
            "known_at_granularity": (
                "K es fecha; un retrieved_at con hora es observable "
                "si su fecha calendario es <= K"
            ),
            "entity_id_semantics": (
                "corpus_id E3-xxx de "
                "fixtures/g1/corpus-g1-e-001.json (corpus E3 "
                "preregistrado, anclas reales)"
            ),
            "match_definition": (
                "expected_assessment/expected_reason congelados por "
                "(valid_at, known_at); usable/excluded_after_K se "
                "derivan mecanicamente de retrieved_at sobre el "
                "universo de evidencia del caso"
            ),
            "oracle_used_to_freeze": (
                "replay offline: finreg_es.derivation."
                "to_entitlement_assertions + assess(V3) sobre el "
                "artefacto -002 filtrado por la regla K — verificado "
                "por build, nunca ajustado tras el resultado"
            ),
        },
        "inputs": {
            "derived_assertions": {
                "file": "fixtures/g1/derived-assertions-g1-e-002.json",
                "sha256": _sha256_file(ARTIFACT_PATH),
                "role": "universo de evidencia (aserciones + reported_facts)",
            },
            "corpus": {
                "file": "fixtures/g1/corpus-g1-e-001.json",
                "sha256": _sha256_file(CORPUS_PATH),
                "role": "entidades/anclas reales E3 (0 sinteticas)",
            },
            "claim_ledger": {
                "file": "fixtures/g1/claim-ledger-g1-e-001.json",
                "sha256": _sha256_file(LEDGER_PATH),
                "role": "provenance de claims (retrieved_at por claim)",
            },
            "g2_comparison": {
                "file": "fixtures/g2/comparisons/"
                "eba-psd2-20260914-vs-20260915.json",
                "sha256": _sha256_file(COMPARISON_PATH),
                "role": "par real que alimenta E0-F01/E0-F02",
            },
            "g2_events": {
                "file": "fixtures/g2/events/"
                "eba-psd2-20260914-vs-20260915.json",
                "sha256": _sha256_file(EVENTS_PATH),
                "role": "candidatos G2-C1 congelados del mismo par",
            },
        },
        "cases": cases_out,
        "findings": FINDINGS,
    }
    doc["artifact_sha256"] = sha256_hex(doc)
    return doc


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    OUT.write_bytes(canonical_json(doc).encode("utf-8"))
    n_probes = sum(len(c["probes"]) for c in doc["cases"])
    print(
        f"{OUT.relative_to(ROOT)}  cases={len(doc['cases'])} "
        f"probes={n_probes}  sha256={doc['artifact_sha256'][:16]}…"
    )
