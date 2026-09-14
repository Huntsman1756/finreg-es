"""Genera ``fixtures/g1/derivation-rules-g1-e-001.json`` (V5, G1-E/E4).

Delta estrictamente derivacional — la agregacion global (CONFIRMED_*)
pertenece a E5 y no aparece aqui. El ruleset materializa:

- actividades PSD2 granulares positivas (por codigo, con
  raw_capability_code + source_granularity);
- ENUMERATED_ABSENCE por (actividad, route_key) sobre vectores cuyo
  slice contractual declara completitud scoped
  (CAPABILITY_VECTOR_COMPLETE_WHEN_RECORD_PRESENT), nunca sobre la
  poblacion del registro;
- EXPLICIT_WITHDRAWAL como hecho de familia/raiz
  (negative_scope=ROOT_FAMILY, sin inventar territorial_basis);
- ENTITY_BAJA como hecho societario (transformacion/escision/fusion),
  nunca retirada de autorizacion;
- interval_end=EXCLUSIVE en los hechos/aserciones derivados de
  ENT_AUT y de fechas BdE (los intervalos [autorizacion, retirada)
  cierran EN la fecha de cese);
- evidencia negativa bloqueada (admissibility=BLOCKED + blocker) cuando
  la continuidad del sucesor tras una transformacion no esta
  demostrada — finding, no NOT_ENTITLED admisible.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "fixtures/g1/derivation-rules-g1-e-001.json"

# Mapas codigo raw -> actividad canonica (E2, congelado en
# docs/g1-e-negative-semantics.md). El codigo queda en
# raw_capability_code; nunca se translitera al namespace canonico.
EBA_CODE_MAP = {
    "PS_010": "PAYMENT_ACCOUNT_CASH_PLACEMENT",
    "PS_020": "PAYMENT_ACCOUNT_CASH_WITHDRAWAL",
    "PS_03A": "PAYMENT_DIRECT_DEBIT_EXECUTION",
    "PS_03B": "PAYMENT_CARD_TRANSACTION_EXECUTION",
    "PS_03C": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
    "PS_04A": "PAYMENT_DIRECT_DEBIT_EXECUTION_CREDIT_LINE",
    "PS_04B": "PAYMENT_CARD_TRANSACTION_EXECUTION_CREDIT_LINE",
    "PS_04C": "PAYMENT_CREDIT_TRANSFER_EXECUTION_CREDIT_LINE",
    "PS_05A": "PAYMENT_INSTRUMENT_ISSUING",
    "PS_05B": "PAYMENT_TRANSACTION_ACQUIRING",
    "PS_060": "MONEY_REMITTANCE",
    "PS_070": "PAYMENT_INITIATION_SERVICES",
    "PS_080": "ACCOUNT_INFORMATION_SERVICES",
    "ES_010": "E_MONEY_ISSUANCE",
}
BDE_CODE_MAP = {
    "1": "PAYMENT_ACCOUNT_CASH_PLACEMENT",
    "2": "PAYMENT_ACCOUNT_CASH_WITHDRAWAL",
    "3.A": "PAYMENT_DIRECT_DEBIT_EXECUTION",
    "3.B": "PAYMENT_CARD_TRANSACTION_EXECUTION",
    "3.C": "PAYMENT_CREDIT_TRANSFER_EXECUTION",
    "4.A": "PAYMENT_DIRECT_DEBIT_EXECUTION_CREDIT_LINE",
    "4.B": "PAYMENT_CARD_TRANSACTION_EXECUTION_CREDIT_LINE",
    "4.C": "PAYMENT_CREDIT_TRANSFER_EXECUTION_CREDIT_LINE",
    "5.A": "PAYMENT_INSTRUMENT_ISSUING",
    "5.B": "PAYMENT_TRANSACTION_ACQUIRING",
    "6": "MONEY_REMITTANCE",
    "7": "PAYMENT_INITIATION_SERVICES",
    "8": "ACCOUNT_INFORMATION_SERVICES",
    "A": "E_MONEY_ISSUANCE",
    "B": "E_MONEY_ISSUANCE",
    "C": "E_MONEY_ISSUANCE",
}

EBA_PS_UNIVERSE = [
    "PS_010", "PS_020",
    "PS_03A", "PS_03B", "PS_03C",
    "PS_04A", "PS_04B", "PS_04C",
    "PS_05A", "PS_05B",
    "PS_060", "PS_070", "PS_080",
]
EBA_EMI_UNIVERSE = EBA_PS_UNIVERSE + ["ES_010"]

# Universos BdE por familia, con guardas de codigos legacy (Ley
# 16/2009): un "5" bare o "3.1..4.3" no son el codigo atomico RDL
# 19/2018 — su presencia bloquea el negativo de la familia, nunca lo
# confirma.
BDE_UNIVERSES = [
    ("base", ["1", "2", "6", "7", "8"], []),
    ("f3", ["3.A", "3.B", "3.C"], ["3.1", "3.2", "3.3"]),
    ("f4", ["4.A", "4.B", "4.C"], ["4.1", "4.2", "4.3"]),
    ("f5", ["5.A", "5.B"], ["5"]),
]

EBA_TYPE_CLASS = {
    "PSD_PI": "PAYMENT_INSTITUTION",
    "PSD_EMI": "E_MONEY_INSTITUTION",
    "PSD_AISP": "ACCOUNT_INFORMATION_SERVICE_PROVIDER",
}
EBA_TYPE_MECH = {
    "PSD_PI": "AUTHORISATION",
    "PSD_EMI": "AUTHORISATION",
    "PSD_AISP": "REGISTRATION",
}
BDE_TYPE_CLASS = {
    "TEEP": "PAYMENT_INSTITUTION",
    "TEEFEP": "PAYMENT_INSTITUTION",
    "TEEFPH": "PAYMENT_INSTITUTION",
    "TEEDE": "E_MONEY_INSTITUTION",
    "TEPSIC": "ACCOUNT_INFORMATION_SERVICE_PROVIDER",
    "TESEPC": "PAYMENT_INSTITUTION",
    "TESEDC": "E_MONEY_INSTITUTION",
}
BDE_TYPE_MECH = {
    "TEEP": "AUTHORISATION",
    "TEEFEP": "AUTHORISATION",
    "TEEFPH": "AUTHORISATION",
    "TEEDE": "AUTHORISATION",
    "TEPSIC": "REGISTRATION",
    "TESEPC": "AUTHORISATION",
    "TESEDC": "AUTHORISATION",
}
BDE_DOMESTIC_TYPES = ["TEEP", "TEEFEP", "TEEFPH", "TEPSIC"]
BDE_BRANCH_TYPES = ["TESEPC", "TESEDC"]
BAJA_CLASS_MAP = {
    "WITHDRAWAL": "EXPLICIT_WITHDRAWAL",
    "TRANSFORMATION": "ENTITY_BAJA",
    "UNRESOLVED_MOTIVO": "ENTITY_BAJA",
}

_EVIDENCE_AS_OF = {"derivation": "EVIDENCE_AS_OF"}
_NULL = {"derivation": "CONSTANT_NULL"}
_EBA_LAST_AUTH = {"derivation": "EBA_ENT_AUT_LAST_AUTH"}
_LAST_WD = {"derivation": "FIELD_COPY", "field": "eba_ent_aut_last_withdrawal"}
_FECHA_ALTA = {"derivation": "FIELD_DDMMYYYY", "field": "fecha_alta"}
_FECHA_BAJA = {"derivation": "FIELD_DDMMYYYY", "field": "fecha_baja"}
_BRANCH_ALTA = {"derivation": "FIELD_DDMMYYYY", "field": "bde_branch_fecha_alta"}


def _base(
    rule_id: str,
    source: str,
    conditions: list[dict],
    *,
    required: list[str] | None = None,
    coverage: list[str] | None = None,
    rationale: str = "",
    limitations: list[str] | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "required_source_contract": source,
        "match": {"source": source, "conditions": conditions},
        "required_fields": required or [],
        "coverage_preconditions": coverage or [],
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": rationale,
        "known_limitations": limitations or [],
    }


def _emit_positive(
    *,
    code_map: dict,
    entity_class: dict,
    mechanism: dict,
    territorial_basis: str,
    effective_from: dict,
    effective_to: dict,
    legal_basis: str,
    scope: str,
    extra: dict | None = None,
) -> dict:
    emit = {
        "activity_from": {"field": "$ITEM", "map": code_map},
        "jurisdiction": "ES",
        "legal_effect": "ENTITLED_TO_PROVIDE",
        "territorial_basis": territorial_basis,
        "legal_basis": legal_basis,
        "scope": scope,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "raw_capability_code": "$ITEM",
        "source_granularity": "ATOMIC",
    }
    if "field" in entity_class:
        emit["entity_class_from"] = {"field": entity_class["field"], "map": entity_class["map"]}
    else:
        emit["entity_class"] = entity_class["value"]
    if "field" in mechanism:
        emit["entry_mechanism_from"] = {"field": mechanism["field"], "map": mechanism["map"]}
    else:
        emit["entry_mechanism"] = mechanism["value"]
    emit.update(extra or {})
    return emit


def _emit_absence(
    *,
    code_map: dict,
    entity_class: dict,
    mechanism: dict,
    territorial_basis: str,
    coverage_policy_id: str,
    legal_basis: str,
    scope: str,
    extra: dict | None = None,
) -> dict:
    emit = _emit_positive(
        code_map=code_map,
        entity_class=entity_class,
        mechanism=mechanism,
        territorial_basis=territorial_basis,
        effective_from=_EVIDENCE_AS_OF,
        effective_to=_NULL,
        legal_basis=legal_basis,
        scope=scope,
    )
    emit["legal_effect"] = "NOT_ENTITLED"
    emit["negative_scope"] = "ROUTE_CAPABILITY"
    emit["negative_evidence_class"] = "ENUMERATED_ABSENCE"
    emit["coverage_policy_id"] = coverage_policy_id
    emit.update(extra or {})
    return emit


def _rules() -> list[dict]:
    rules: list[dict] = []

    eba_conds_active_root = [
        {"field": "entity_type", "op": "IN", "value": ["PSD_PI", "PSD_EMI"]},
        {"field": "eba_ent_aut_status", "op": "EQ", "value": "ACTIVE"},
        {"field": "eba_es_services", "op": "NOT_NULL"},
    ]

    # --- EBA: positivos granulares FPS (LPS declarada, snapshot actual)
    r = _base(
        "eba-psd2-fps-es-service-entitled",
        "EBA_PSD2_REGISTER",
        eba_conds_active_root,
        required=["entity_code", "eba_es_services_str", "eba_home_nca"],
        coverage=["eba-psd2-in-eea"],
        rationale=(
            "Servicio atomico Annex I declarado para ES en Services{ES} "
            "de una raiz PI/EMI activa: positivo granular de la ruta "
            "FPS. La fecha territorial es EVIDENCE_AS_OF (sin fecha "
            "historica publicada el vector nunca se retroproyecta)."
        ),
        limitations=[
            "el vector solo atestigua el snapshot actual; el inicio "
            "historico de la ruta LPS no es reconstruible"
        ],
    )
    r["emit_per"] = {
        "iterate": {"field": "eba_es_services_str", "mode": "SPLIT", "separator": "|"},
        "emit": _emit_positive(
            code_map=EBA_CODE_MAP,
            entity_class={"field": "entity_type", "map": EBA_TYPE_CLASS},
            mechanism={"value": "AUTHORISATION"},
            territorial_basis="FREEDOM_TO_PROVIDE_SERVICES",
            effective_from=_EVIDENCE_AS_OF,
            effective_to=_NULL,
            legal_basis=(
                "PSD2 (UE) 2015/2366 art. 28 + art. 18: LPS passportada "
                "{eba_home_nca}->ES; servicio atomico declarado en "
                "Services{ES} (capa NCA-reportada T2)"
            ),
            scope="un servicio atomico Annex I declarado para ES en el snapshot",
            extra={"evidence_basis": "NCA_REPORTED_VIA_EBA"},
        ),
    }
    rules.append(r)

    # --- EBA: ENUMERATED_ABSENCE FPS (vector completo, scoped)
    for entity_type, cls, universe, suffix in (
        ("PSD_PI", "PAYMENT_INSTITUTION", EBA_PS_UNIVERSE, "pi"),
        ("PSD_EMI", "E_MONEY_INSTITUTION", EBA_EMI_UNIVERSE, "emi"),
    ):
        r = _base(
            f"eba-psd2-fps-es-service-absent-{suffix}",
            "EBA_PSD2_REGISTER",
            [
                {"field": "entity_type", "op": "EQ", "value": entity_type},
                {"field": "eba_ent_aut_status", "op": "EQ", "value": "ACTIVE"},
                {"field": "eba_es_services", "op": "NOT_NULL"},
            ],
            required=["entity_code", "eba_es_services"],
            coverage=["eba-psd2-in-eea"],
            rationale=(
                "Slice eba-fps-services-vector: el spec EBA congelado "
                "define Services{ES} como la lista completa Annex I del "
                "registro presente (CAPABILITY_VECTOR_COMPLETE_WHEN_"
                "RECORD_PRESENT). Un codigo atomico ausente del vector "
                "de una raiz activa es ENUMERATED_ABSENCE de esa ruta — "
                "propiedad scoped del vector, nunca poblacional."
            ),
            limitations=[
                "ausencia solo atestiguada en el snapshot actual "
                "(effective_from=EVIDENCE_AS_OF)"
            ],
        )
        r["emit_per"] = {
            "iterate": {
                "field": "eba_es_services",
                "mode": "ABSENT_FROM_SET",
                "universe": universe,
            },
            "emit": _emit_absence(
                code_map=EBA_CODE_MAP,
                entity_class={"value": cls},
                mechanism={"value": "AUTHORISATION"},
                territorial_basis="FREEDOM_TO_PROVIDE_SERVICES",
                coverage_policy_id="eba-fps-services-vector",
                legal_basis=(
                    "PSD2 (UE) 2015/2366: codigo Annex I ausente del "
                    "vector Services{ES} completo de una raiz activa"
                ),
                scope="un servicio atomico Annex I no declarado para ES",
                extra={
                    "evidence_basis": "NCA_REPORTED_VIA_EBA",
                    "admissibility": "ADMISSIBLE",
                },
            ),
        }
        rules.append(r)

    # --- EBA: ruta BRANCH (PSD_BR activa + parent activo + BdE vigente)
    branch_conds = [
        {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
        {"field": "eba_child_status", "op": "EQ", "value": "ACTIVE"},
        {"field": "eba_parent_status", "op": "EQ", "value": "ACTIVE"},
        {"field": "bde_branch_registered", "op": "EQ", "value": "TRUE"},
        {"field": "eba_es_services", "op": "NOT_NULL"},
    ]
    r = _base(
        "eba-psd2-branch-es-service-entitled",
        "EBA_PSD2_REGISTER",
        branch_conds,
        required=["entity_code", "eba_es_services_str", "bde_branch_fecha_alta"],
        coverage=["eba-psd2-in-eea", "bde-ce-in-branch"],
        rationale=(
            "Sucursal PSD2 ES conjuntiva: PSD_BR Active + parent "
            "ENT_AUT ACTIVE + inscripcion BdE vigente. La fecha "
            "territorial es el alta BdE (trigger juridico de la ruta "
            "de establecimiento, art. 28 PSD2)."
        ),
    )
    r["emit_per"] = {
        "iterate": {"field": "eba_es_services_str", "mode": "SPLIT", "separator": "|"},
        "emit": _emit_positive(
            code_map=EBA_CODE_MAP,
            entity_class={"field": "eba_parent_entity_type", "map": EBA_TYPE_CLASS},
            mechanism={"value": "AUTHORISATION"},
            territorial_basis="BRANCH",
            effective_from=_BRANCH_ALTA,
            effective_to=_NULL,
            legal_basis=(
                "PSD2 (UE) 2015/2366 art. 28: sucursal ES de {eba_parent_nca} "
                "inscrita en BdE {bde_branch_fecha_alta}; servicio atomico "
                "declarado en la fila PSD_BR"
            ),
            scope="un servicio atomico Annex I de la sucursal ES",
            extra={
                "evidence_basis": "NCA_REPORTED_VIA_EBA",
                "evidence_composition": "ALL_REQUIRED",
            },
        ),
    }
    rules.append(r)

    r = _base(
        "eba-psd2-branch-es-service-absent",
        "EBA_PSD2_REGISTER",
        branch_conds,
        required=["entity_code", "eba_es_services"],
        coverage=["eba-psd2-in-eea", "bde-ce-in-branch"],
        rationale=(
            "Slice eba-branch-services-vector: misma completitud scoped "
            "del vector Services{ES} aplicada a la fila PSD_BR "
            "corroborada por la inscripcion BdE vigente."
        ),
    )
    r["emit_per"] = {
        "iterate": {
            "field": "eba_es_services",
            "mode": "ABSENT_FROM_SET",
            "universe": EBA_PS_UNIVERSE,
        },
        "emit": _emit_absence(
            code_map=EBA_CODE_MAP,
            entity_class={"field": "eba_parent_entity_type", "map": EBA_TYPE_CLASS},
            mechanism={"value": "AUTHORISATION"},
            territorial_basis="BRANCH",
            coverage_policy_id="eba-branch-services-vector",
            legal_basis=(
                "PSD2 (UE) 2015/2366: codigo Annex I ausente del vector "
                "Services{ES} completo de la sucursal EBA"
            ),
            scope="un servicio atomico Annex I no declarado por la sucursal",
            extra={
                "evidence_basis": "NCA_REPORTED_VIA_EBA",
                "evidence_composition": "ALL_REQUIRED",
                "admissibility": "ADMISSIBLE",
            },
        ),
    }
    rules.append(r)

    # --- EBA: AISP (raiz registrada, ruta DOMESTIC)
    aisp_conds = [
        {"field": "entity_type", "op": "EQ", "value": "PSD_AISP"},
        {"field": "eba_ent_aut_status", "op": "EQ", "value": "ACTIVE"},
        {"field": "eba_es_services", "op": "NOT_NULL"},
    ]
    r = _base(
        "eba-psd2-aisp-service-entitled",
        "EBA_PSD2_REGISTER",
        aisp_conds,
        required=["entity_code", "eba_es_services_str"],
        coverage=["eba-psd2-in-eea"],
        rationale=(
            "Servicio atomico declarado por un AISP registrado y "
            "activo: positivo granular DOMESTIC/REGISTRATION."
        ),
    )
    r["emit_per"] = {
        "iterate": {"field": "eba_es_services_str", "mode": "SPLIT", "separator": "|"},
        "emit": _emit_positive(
            code_map=EBA_CODE_MAP,
            entity_class={"value": "ACCOUNT_INFORMATION_SERVICE_PROVIDER"},
            mechanism={"value": "REGISTRATION"},
            territorial_basis="DOMESTIC",
            effective_from=_EVIDENCE_AS_OF,
            effective_to=_NULL,
            legal_basis=(
                "PSD2 (UE) 2015/2366 art. 33: registro AISP; servicio "
                "atomico declarado en el registro EBA"
            ),
            scope="un servicio atomico declarado por el AISP",
            extra={"evidence_basis": "NCA_REPORTED_VIA_EBA"},
        ),
    }
    rules.append(r)

    for variant, extra_cond, extra_emit, suffix in (
        (
            "admissible",
            [{"field": "bde_entity_baja_kind", "op": "NULL"}],
            {"admissibility": "ADMISSIBLE"},
            "",
        ),
        (
            "blocked",
            [{"field": "bde_entity_baja_kind", "op": "EQ", "value": "TRANSFORMATION"}],
            {
                "admissibility": "BLOCKED",
                "blocker": "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED",
            },
            "-blocked",
        ),
    ):
        r = _base(
            f"eba-psd2-aisp-service-absent{suffix}",
            "EBA_PSD2_REGISTER",
            aisp_conds + extra_cond,
            required=["entity_code", "eba_es_services"],
            coverage=["eba-psd2-in-eea"],
            rationale=(
                "Slice eba-aisp-services-vector. "
                + (
                    "El registro BdE del sujeto cierra por "
                    "transformacion: la continuidad de capacidades del "
                    "sucesor no esta demostrada, asi que la ausencia se "
                    "materializa BLOQUEADA (evidencia negativa "
                    "candidata, jamas NOT_ENTITLED admisible)."
                    if variant == "blocked"
                    else "Codigo ausente del vector completo del AISP."
                )
            ),
        )
        r["emit_per"] = {
            "iterate": {
                "field": "eba_es_services",
                "mode": "ABSENT_FROM_SET",
                "universe": EBA_PS_UNIVERSE,
            },
            "emit": _emit_absence(
                code_map=EBA_CODE_MAP,
                entity_class={"value": "ACCOUNT_INFORMATION_SERVICE_PROVIDER"},
                mechanism={"value": "REGISTRATION"},
                territorial_basis="DOMESTIC",
                coverage_policy_id="eba-aisp-services-vector",
                legal_basis=(
                    "PSD2 (UE) 2015/2366 art. 33: codigo Annex I ausente "
                    "del vector completo del registro AISP"
                ),
                scope="un servicio atomico no declarado por el AISP",
                extra={"evidence_basis": "NCA_REPORTED_VIA_EBA", **extra_emit},
            ),
        }
        rules.append(r)

    # --- EBA: positivo domestico cerrado (raiz ES retirada)
    r = _base(
        "eba-psd2-domestic-closed-service-entitled",
        "EBA_PSD2_REGISTER",
        [
            {"field": "entity_type", "op": "IN", "value": list(EBA_TYPE_CLASS)},
            {"field": "eba_ent_aut_status", "op": "EQ", "value": "WITHDRAWN"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "eba_es_services", "op": "NOT_NULL"},
        ],
        required=["entity_code", "eba_es_services_str", "eba_ent_aut_last_withdrawal"],
        coverage=["eba-psd2-in-eea"],
        rationale=(
            "Raiz ES retirada: el intervalo DOMESTIC [autorizacion, "
            "retirada) SI es reconstruible — la ruta domestica ES la "
            "autorizacion raiz, sin retroproyeccion territorial. "
            "interval_end=EXCLUSIVE: cerrada EN la fecha de retirada."
        ),
        limitations=[
            "solo raices ES: una raiz extranjera retirada no prueba el "
            "intervalo de la ruta LPS (NO_HISTORICALLY_OBSERVED)"
        ],
    )
    r["emit_per"] = {
        "iterate": {"field": "eba_es_services_str", "mode": "SPLIT", "separator": "|"},
        "emit": _emit_positive(
            code_map=EBA_CODE_MAP,
            entity_class={"field": "entity_type", "map": EBA_TYPE_CLASS},
            mechanism={"field": "entity_type", "map": EBA_TYPE_MECH},
            territorial_basis="DOMESTIC",
            effective_from=_EBA_LAST_AUTH,
            effective_to=_LAST_WD,
            legal_basis=(
                "PSD2 (UE) 2015/2366: autorizacion/registration nacional "
                "vigente en [ENT_AUT_auth, ENT_AUT_retirada); cierre "
                "exclusivo en la fecha de retirada"
            ),
            scope="un servicio atomico Annex I declarado para ES",
            extra={
                "evidence_basis": "NCA_REPORTED_VIA_EBA",
                "interval_end": "EXCLUSIVE",
            },
        ),
    }
    rules.append(r)

    # --- EBA: hechos de raiz (status + retirada)
    r = _base(
        "eba-psd2-root-status-fact",
        "EBA_PSD2_REGISTER",
        [{"field": "entity_type", "op": "IN", "value": list(EBA_TYPE_CLASS)}],
        rationale=(
            "Hecho de estado de la raiz: la secuencia ENT_AUT completa "
            "se preserva bitemporalmente con interval_end=EXCLUSIVE."
        ),
    )
    r["emit_status_fact"] = {
        "reported_status_from": {"field": "eba_ent_aut_status"},
        "interval_end": "EXCLUSIVE",
        "detail": (
            "Secuencia ENT_AUT completa; intervalos [autorizacion, "
            "retirada) — la raiz esta cerrada EN la fecha de retirada."
        ),
    }
    rules.append(r)

    for types, mech, suffix in (
        (["PSD_PI", "PSD_EMI"], "AUTHORISATION", ""),
        (["PSD_AISP"], "REGISTRATION", "-aisp"),
    ):
        r = _base(
            f"eba-psd2-root-withdrawal{suffix}",
            "EBA_PSD2_REGISTER",
            [
                {"field": "entity_type", "op": "IN", "value": types},
                {"field": "eba_ent_aut_status", "op": "EQ", "value": "WITHDRAWN"},
            ],
            rationale=(
                "Retirada explicita de la raiz: hecho negativo de "
                "familia (ROOT_FAMILY). Cierra mecanicamente las rutas "
                "descendientes pero NO inventa una base territorial "
                "nunca observada — effective_from = ultima retirada."
            ),
        )
        r["emit_status_fact"] = {
            "reported_status": "WITHDRAWN",
            "negative_scope": "ROOT_FAMILY",
            "negative_evidence_class": "EXPLICIT_WITHDRAWAL",
            "effective_from_field": "eba_ent_aut_last_withdrawal",
            "interval_end": "EXCLUSIVE",
            "entry_mechanism": mech,
            "detail": (
                "ENT_AUT par: retirada explicita de la autorizacion/"
                "registro raiz. No es un negativo territorial — la "
                "lectura por ruta pertenece a E5."
            ),
        }
        rules.append(r)

    # --- BdE servicios-pago: entidades domesticas
    bde_dom_conds = [
        {"field": "codigo_tipo_entidad", "op": "IN", "value": BDE_DOMESTIC_TYPES},
        {"field": "fecha_baja", "op": "NULL"},
        {"field": "actividades_codes", "op": "NOT_NULL"},
    ]
    r = _base(
        "bde-psp-domestic-service-entitled",
        "BDE_REGISTRO_SERVICIOS_PAGO",
        bde_dom_conds,
        required=["codigo_be", "fecha_alta", "actividades_codes"],
        coverage=["bde-psp-in-domestic-entities"],
        rationale=(
            "Entidad domestica BdE en alta: cada codigo de la hoja "
            "ACTIVIDADES es un positivo granular DOMESTIC con fecha de "
            "alta de la inscripcion."
        ),
    )
    r["emit_per"] = {
        "iterate": {"field": "actividades_codes", "mode": "LIST"},
        "emit": _emit_positive(
            code_map=BDE_CODE_MAP,
            entity_class={"field": "codigo_tipo_entidad", "map": BDE_TYPE_CLASS},
            mechanism={"field": "codigo_tipo_entidad", "map": BDE_TYPE_MECH},
            territorial_basis="DOMESTIC",
            effective_from=_FECHA_ALTA,
            effective_to={"derivation": "FIELD_DDMMYYYY_OR_NULL", "field": "fecha_baja"},
            legal_basis=(
                "PSD2 (UE) 2015/2366 + legislacion nacional de EP/EDE: "
                "servicio autorizado declarado en el registro BdE "
                "(hoja ACTIVIDADES)"
            ),
            scope="un servicio atomico Annex I autorizado a la entidad",
            extra={"evidence_basis": "NCA_PRIMARY"},
        ),
    }
    rules.append(r)

    for family, universe, guards in BDE_UNIVERSES:
        conds = list(bde_dom_conds) + [
            {"field": "actividades_codes", "op": "ABSENT_IN", "value": g}
            for g in guards
        ]
        r = _base(
            f"bde-psp-domestic-service-absent-{family}",
            "BDE_REGISTRO_SERVICIOS_PAGO",
            conds,
            required=["codigo_be", "actividades_codes"],
            coverage=["bde-domestic-pi-activities"],
            rationale=(
                "Slice bde-domestic-*-activities: la hoja ACTIVIDADES "
                "enumera completa la capacidad de una fila domestica en "
                "alta (CAPABILITY_VECTOR_COMPLETE_WHEN_RECORD_PRESENT)."
                + (
                    f" Guarda: los codigos legacy {guards} presentes "
                    "bloquean el negativo de la familia — un codigo "
                    "compuesto nunca se descompone."
                    if guards
                    else ""
                )
            ),
            limitations=[
                "codigos legacy (Ley 16/2009) nunca generan negativos "
                "atomicos por descomposicion"
            ],
        )
        r["emit_per"] = {
            "iterate": {
                "field": "actividades_codes",
                "mode": "ABSENT_FROM_SET",
                "universe": universe,
            },
            "emit": _emit_absence(
                code_map=BDE_CODE_MAP,
                entity_class={"field": "codigo_tipo_entidad", "map": BDE_TYPE_CLASS},
                mechanism={"field": "codigo_tipo_entidad", "map": BDE_TYPE_MECH},
                territorial_basis="DOMESTIC",
                coverage_policy_id="bde-domestic-pi-activities",
                legal_basis=(
                    "Servicio Annex I ausente de la enumeracion completa "
                    "ACTIVIDADES de una entidad domestica en alta"
                ),
                scope="un servicio atomico Annex I no autorizado",
                extra={"evidence_basis": "NCA_PRIMARY", "admissibility": "ADMISSIBLE"},
            ),
        }
        rules.append(r)

    # --- BdE servicios-pago: fila cerrada (baja)
    r = _base(
        "bde-psp-closed-service-entitled",
        "BDE_REGISTRO_SERVICIOS_PAGO",
        [
            {"field": "codigo_tipo_entidad", "op": "IN", "value": BDE_DOMESTIC_TYPES},
            {"field": "fecha_baja", "op": "NOT_NULL"},
            {"field": "actividades_codes", "op": "NOT_NULL"},
        ],
        required=["codigo_be", "fecha_alta", "fecha_baja", "actividades_codes"],
        coverage=["bde-psp-in-domestic-entities"],
        rationale=(
            "Fila domestica con baja: los servicios de la enumeracion "
            "son positivos historicos cerrados [alta, baja) — "
            "interval_end=EXCLUSIVE. Una baja por transformacion sigue "
            "produciendo el positivo historico (la capacidad existio), "
            "pero jamas un negativo de retirada."
        ),
    )
    r["emit_per"] = {
        "iterate": {"field": "actividades_codes", "mode": "LIST"},
        "emit": _emit_positive(
            code_map=BDE_CODE_MAP,
            entity_class={"field": "codigo_tipo_entidad", "map": BDE_TYPE_CLASS},
            mechanism={"field": "codigo_tipo_entidad", "map": BDE_TYPE_MECH},
            territorial_basis="DOMESTIC",
            effective_from=_FECHA_ALTA,
            effective_to=_FECHA_BAJA,
            legal_basis=(
                "Servicio autorizado vigente en [FECHA ALTA, FECHA "
                "BAJA) segun el registro BdE"
            ),
            scope="un servicio atomico Annex I autorizado en el intervalo",
            extra={"evidence_basis": "NCA_PRIMARY", "interval_end": "EXCLUSIVE"},
        ),
    }
    rules.append(r)

    r = _base(
        "bde-psp-entity-baja",
        "BDE_REGISTRO_SERVICIOS_PAGO",
        [{"field": "fecha_baja", "op": "NOT_NULL"}],
        rationale=(
            "Baja de la entidad en el registro BdE: hecho negativo de "
            "familia. La clase depende del motivo — renuncia/revocacion "
            "cierra la autorizacion (EXPLICIT_WITHDRAWAL); "
            "transformacion/escision/fusion es evento societario "
            "(ENTITY_BAJA), nunca retirada de la autorizacion."
        ),
    )
    r["emit_status_fact"] = {
        "reported_status": "WITHDRAWN",
        "negative_scope": "ROOT_FAMILY",
        "negative_evidence_class_from": {
            "field": "bde_baja_kind",
            "map": BAJA_CLASS_MAP,
        },
        "effective_from_field": "fecha_baja_iso",
        "interval_end": "EXCLUSIVE",
        "detail": (
            "FECHA BAJA declarada en el registro BdE de servicios de "
            "pago. ENTITY_BAJA no es retirada de autorizacion."
        ),
    }
    rules.append(r)

    r = _base(
        "bde-psp-transformation-successor-finding",
        "BDE_REGISTRO_SERVICIOS_PAGO",
        [{"field": "bde_baja_kind", "op": "EQ", "value": "TRANSFORMATION"}],
        rationale=(
            "Baja por transformacion/escision/fusion: la continuidad "
            "de capacidades del sucesor no esta demostrada por las "
            "fuentes congeladas — finding bloqueante, no negativo."
        ),
    )
    r["emit"] = None
    r["finding"] = {
        "classification": "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED",
        "detail": (
            "Baja por evento societario (transformacion/escision/fusion): "
            "las fuentes congeladas no demuestran a que entidad sucesora "
            "—si la hay— pasaron las capacidades. Evidencia negativa "
            "bloqueada, nunca NOT_ENTITLED admisible."
        ),
    }
    rules.append(r)

    # --- BdE con-establecimiento: sucursales
    bde_br_conds = [
        {"field": "codigo_tipo_entidad", "op": "IN", "value": BDE_BRANCH_TYPES},
        {"field": "fecha_baja", "op": "NULL"},
        {"field": "actividades_codes", "op": "NOT_NULL"},
    ]
    r = _base(
        "bde-ce-branch-service-entitled",
        "BDE_REGISTRO_CON_ESTABLECIMIENTO",
        bde_br_conds,
        required=["codigo_be", "fecha_alta", "actividades_codes"],
        coverage=["bde-ce-in-branch"],
        rationale=(
            "Sucursal ES en alta en el registro BdE de entidades con "
            "establecimiento: cada codigo de su enumeracion es positivo "
            "granular BRANCH con fecha de alta."
        ),
    )
    r["emit_per"] = {
        "iterate": {"field": "actividades_codes", "mode": "LIST"},
        "emit": _emit_positive(
            code_map=BDE_CODE_MAP,
            entity_class={"field": "codigo_tipo_entidad", "map": BDE_TYPE_CLASS},
            mechanism={"field": "codigo_tipo_entidad", "map": BDE_TYPE_MECH},
            territorial_basis="BRANCH",
            effective_from=_FECHA_ALTA,
            effective_to={"derivation": "FIELD_DDMMYYYY_OR_NULL", "field": "fecha_baja"},
            legal_basis=(
                "PSD2 (UE) 2015/2366 art. 28: sucursal de EP/EDE "
                "comunitaria inscrita; servicio declarado en la hoja "
                "ACTIVIDADES del registro BdE"
            ),
            scope="un servicio atomico Annex I de la sucursal",
            extra={"evidence_basis": "NCA_PRIMARY"},
        ),
    }
    rules.append(r)

    for family, universe, guards in BDE_UNIVERSES:
        conds = list(bde_br_conds) + [
            {"field": "actividades_codes", "op": "ABSENT_IN", "value": g}
            for g in guards
        ]
        r = _base(
            f"bde-ce-branch-service-absent-{family}",
            "BDE_REGISTRO_CON_ESTABLECIMIENTO",
            conds,
            required=["codigo_be", "actividades_codes"],
            coverage=["bde-branch-pi-activities"],
            rationale=(
                "Slice bde-branch-*-activities: enumeracion completa de "
                "la sucursal en alta; ausencia atomica = "
                "ENUMERATED_ABSENCE de la ruta BRANCH."
                + (f" Guarda legacy {guards}." if guards else "")
            ),
        )
        r["emit_per"] = {
            "iterate": {
                "field": "actividades_codes",
                "mode": "ABSENT_FROM_SET",
                "universe": universe,
            },
            "emit": _emit_absence(
                code_map=BDE_CODE_MAP,
                entity_class={"field": "codigo_tipo_entidad", "map": BDE_TYPE_CLASS},
                mechanism={"field": "codigo_tipo_entidad", "map": BDE_TYPE_MECH},
                territorial_basis="BRANCH",
                coverage_policy_id="bde-branch-pi-activities",
                legal_basis=(
                    "Servicio Annex I ausente de la enumeracion completa "
                    "de la sucursal en alta"
                ),
                scope="un servicio atomico Annex I no declarado por la sucursal",
                extra={"evidence_basis": "NCA_PRIMARY", "admissibility": "ADMISSIBLE"},
            ),
        }
        rules.append(r)

    r = _base(
        "bde-ce-branch-baja",
        "BDE_REGISTRO_CON_ESTABLECIMIENTO",
        [{"field": "fecha_baja", "op": "NOT_NULL"}],
        rationale=(
            "Baja expresa de la sucursal: negativo de ruta — solo la "
            "BRANCH observada queda cerrada, nunca otras vias."
        ),
    )
    r["emit_status_fact"] = {
        "reported_status": "WITHDRAWN",
        "negative_scope": "ROUTE_CAPABILITY",
        "negative_evidence_class_from": {
            "field": "bde_baja_kind",
            "map": BAJA_CLASS_MAP,
        },
        "effective_from_field": "fecha_baja_iso",
        "interval_end": "EXCLUSIVE",
        "detail": (
            "FECHA BAJA de la sucursal en el registro BdE de entidades "
            "con establecimiento: cierra solo la ruta BRANCH observada."
        ),
    }
    rules.append(r)

    return rules


def main() -> None:
    ruleset = {
        "ruleset": {
            "ruleset_id": "finreg-g1-derivation",
            "ruleset_version": "FINREG_G1_DERIVATION_V5",
            "gate": "G1-E",
            "purpose": (
                "SourceAssertion[] -> EntitlementAssertion[] + "
                "reported_facts + findings. E4 materializa hechos "
                "negativos con clase/ambito (ROOT_FAMILY vs "
                "ROUTE_CAPABILITY), actividades PSD2 granulares y "
                "interval_end=EXCLUSIVE. La agregacion global "
                "(CONFIRMED_*) pertenece a E5 — ningun veredicto "
                "global se decide aqui."
            ),
            "frozen_inputs": {
                "claims_ledger": "fixtures/g1/claim-ledger-g1-e-001.json",
                "corpus": "fixtures/g1/corpus-g1-e-001.json",
                "source_manifest": "fixtures/g1/sources/manifest-g1-e-run.json",
                "contracts_dir": "fixtures/contracts",
                "negative_corpus": "fixtures/g1/sources/extracted/g1-e-negative-corpus-003.json",
            },
            "policy": {
                "no_negative_from_absence": (
                    "la ausencia poblacional (entidad no listada en el "
                    "registro) nunca es evidencia negativa; solo los "
                    "slices declarados CAPABILITY_VECTOR_COMPLETE_WHEN_"
                    "RECORD_PRESENT producen ENUMERATED_ABSENCE"
                ),
                "root_vs_route_scope": (
                    "la retirada de raiz es un hecho ROOT_FAMILY sin "
                    "territorial_basis inventada; solo la baja/ausencia "
                    "de una ruta observada es ROUTE_CAPABILITY"
                ),
                "temporal": (
                    "interval_end=EXCLUSIVE en los hechos nuevos "
                    "derivados de ENT_AUT/fechas BdE; los vectores de "
                    "capacidad solo atestiguan el snapshot actual "
                    "(effective_from=EVIDENCE_AS_OF)"
                ),
                "blocked_evidence": (
                    "la continuidad de sucesor tras transformacion no "
                    "demostrada materializa admissibility=BLOCKED + "
                    "finding — nunca un NOT_ENTITLED admisible que E5 "
                    "tendria que deshacer"
                ),
                "source_granularity": (
                    "un codigo compuesto (BdE '5' bare, familias "
                    "legacy) nunca se descompone en hechos atomicos"
                ),
                "no_global_aggregation": (
                    "E4 no decide CONFIRMED_ENTITLED/NOT_ENTITLED "
                    "globales ni conflictos entre rutas — E5"
                ),
            },
            "failure_taxonomy": [
                "REQUIRED_FIELD_MISSING",
                "REQUIRED_FIELD_UNDERIVABLE",
                "UNSUPPORTED_ENTITY_CLASS",
                "UNSUPPORTED_ACTIVITY_MAPPING",
                "INSUFFICIENT_LEGAL_BASIS",
                "DERIVED_PRECONDITION_NOT_MET",
                "TRANSFORMATION_SUCCESSOR_SEMANTICS_UNRESOLVED",
            ],
            "effective_derivations": {
                "CONSTANT_NULL": "ventana abierta",
                "EVIDENCE_AS_OF": (
                    "retrieved_at del snapshot: fecha mas temprana en "
                    "que la evidencia atestigua el hecho"
                ),
                "FIELD_COPY": (
                    "campo ya normalizado ISO (p. ej. "
                    "eba_ent_aut_last_withdrawal, fecha_baja_iso)"
                ),
                "FIELD_COPY_OR_NULL": "FIELD_COPY tolerante a ausencia",
                "FIELD_DDMMYYYY": "parse dd/mm/yyyy -> ISO; fallo => REQUIRED_FIELD_UNDERIVABLE",
                "FIELD_DDMMYYYY_OR_NULL": "parse dd/mm/yyyy -> ISO; vacio => null",
                "EBA_ENT_AUT_LAST_AUTH": "ultima fecha de autorizacion de la secuencia ENT_AUT",
            },
            "rules": _rules(),
            "derived_rules": [],
        }
    }
    OUT.write_bytes(
        (json.dumps(ruleset, ensure_ascii=False, indent=1) + "\n").encode(
            "utf-8"
        )
    )
    print(f"ruleset V5: {len(ruleset['ruleset']['rules'])} reglas")

    # G1-E (E4.1): sucesor -002. Mismas reglas + declaracion de los
    # campos de raiz (root_key / root_home_jurisdiction via campos
    # derivados del grupo) y provenance en los hechos — E5 los consume.
    # -001 permanece congelado como materializacion E4.
    import copy

    ruleset_v2 = copy.deepcopy(ruleset)
    ruleset_v2["ruleset"]["ruleset_version"] = "FINREG_G1_DERIVATION_V6"
    ruleset_v2["ruleset"]["purpose"] += (
        " -002: cada emit declara root_key_from/root_home_jurisdiction_"
        "from y cada emit_status_fact adjunta provenance (source_claim_"
        "ids + source_assertions) para la evaluacion bitemporal y de "
        "staleness de la raiz en E5."
    )
    for rule in ruleset_v2["ruleset"]["rules"]:
        for emit in (
            [rule["emit"]] if rule.get("emit") else []
        ) + (
            [rule["emit_per"]["emit"]] if rule.get("emit_per") else []
        ):
            emit["root_key_from"] = "root_key"
            emit["root_home_jurisdiction_from"] = "root_home_jurisdiction"
        if rule.get("emit_status_fact"):
            spec = rule["emit_status_fact"]
            spec["root_key_from"] = "root_key"
            spec["root_home_jurisdiction_from"] = "root_home_jurisdiction"
            spec["emit_source_provenance"] = True
    OUT_V2 = OUT.with_name("derivation-rules-g1-e-002.json")
    OUT_V2.write_bytes(
        (json.dumps(ruleset_v2, ensure_ascii=False, indent=1) + "\n").encode(
            "utf-8"
        )
    )
    print(f"ruleset V6 (-002): {len(ruleset_v2['ruleset']['rules'])} reglas")


if __name__ == "__main__":
    main()
