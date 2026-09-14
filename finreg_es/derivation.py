"""G0.7-A — Derivacion SourceAssertion[] -> EntitlementAssertion[].

Interprete determinista del ruleset congelado
``fixtures/g0.7/derivation-rules.json`` sobre el ledger de claims de
G0.6. No ejecuta assessment: produce aserciones de entitlement,
findings clasificados de derivacion y el indice de identidad del corpus.

Reglas congeladas del modulo:
  - ningun fallo de derivacion inventa una asercion positiva: produce un
    finding con clasificacion de la taxonomia del ruleset;
  - ninguna regla emite NOT_ENTITLED: el corpus no contiene evidencia
    negativa explicita ni enumeracion completa verificada;
  - identificadores con diagnostico LEI distinto de VALID nunca entran
    en el indice de identidad (no soportan joins); el raw se conserva;
  - N fuentes que repiten el mismo hecho soportan una unica conclusion:
    la multiplicidad de evidencia no es multiplicidad juridica.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .canonical import canonical_json, strict_json_loads
from .identity import Identifier, IdentityIndexEntry
from .semantics import EntitlementAssertion, SourceAssertion
from .vocab import LegalEffect


DERIVATION_VERSION = "FINREG_G07_DERIVATION_V1"
ARTIFACT_VERSION = "FINREG_G07_DERIVED_ASSERTIONS_V1"
G1_DERIVATION_VERSION = "FINREG_G1_DERIVATION_V1"
G1_ARTIFACT_VERSION = "FINREG_G1_DERIVED_ASSERTIONS_V1"
# G1-D: mismo formato de artefacto; la version de derivacion sube por
# los campos derivados territoriales (join parent EBA, join BdE sucursal,
# ruta territorial CNMV) y la interpolacion de legal_basis/scope.
G1D_DERIVATION_VERSION = "FINREG_G1_DERIVATION_V2"

_EBA_ENT_AUT_DATE = r"\d{4}-\d{2}-\d{2}"


def _eba_ent_aut_derived(ent_aut: Any) -> dict[str, Any]:
    """Interpreta ENT_AUT segun la especificacion oficial EBA (G1-A,
    H9-A PROVEN): lista cronologica de cambios de estado; posicion
    impar = autorizacion/registro, par = retirada. Semantica
    documentada por la autoridad, no heuristica.

    Devuelve status (ACTIVE/WITHDRAWN/UNKNOWN), intervalos
    [aut, retirada) preservados y la ultima fecha de autorizacion.
    """
    out = {"status": "UNKNOWN", "intervals": [], "last_auth": None}
    if not isinstance(ent_aut, list) or not ent_aut:
        return out
    if not all(
        isinstance(d, str) and re.fullmatch(_EBA_ENT_AUT_DATE, d) for d in ent_aut
    ):
        return out
    pairs = zip(ent_aut[0::2], ent_aut[1::2] + [None])
    out["intervals"] = [{"from": a, "to": w} for a, w in pairs]
    out["status"] = "ACTIVE" if len(ent_aut) % 2 == 1 else "WITHDRAWN"
    out["last_auth"] = ent_aut[-2] if len(ent_aut) % 2 == 0 else ent_aut[-1]
    return out

# Identificadores admitidos como clave de join en el indice de identidad
# del corpus. Los LEI solo entran si su diagnostico V2 es VALID.
IDENTIFIER_KIND_BY_FIELD = {
    ("EBA_PSD2_REGISTER", "entity_code"): "BDE_REGISTRY_ID",
    ("CNMV_ESI_FPS", "official_number"): "CNMV_REGISTRY_ID",
    ("BDE_MFI_CLASSIFICATION_ES", "european_code"): "BDE_REGISTRY_ID",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mica_service_letters(raw: Any) -> str | None:
    """Letras a-j de ac_serviceCode (robusto a separadores irregulares)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    letters = [c for c in "abcdefghij" if re.search(rf"(?<![A-Za-z]){c}\.", raw)]
    return "|".join(letters) or None


def _mica_foreign_countries(raw: Any, home: Any) -> str | None:
    """Paises de ac_serviceCode_cou distintos del home member state."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    foreign = [c.strip() for c in raw.split("|") if c.strip() and c.strip() != home]
    return "|".join(foreign) or None


def _eba_country_services(services_raw: Any, country: str) -> list[str] | None:
    """Codigos de servicio declarados para ``country`` en Services EBA."""
    if not isinstance(services_raw, list):
        return None
    codes: list[str] = []
    for entry in services_raw:
        if isinstance(entry, dict):
            value = entry.get(country)
            if isinstance(value, str):
                value = [value]
            for code in value or []:
                if code not in codes:
                    codes.append(code)
    return codes or None


def _eba_nca_code(entity_code: Any) -> str | None:
    """Emisor NCA del EntityCode EBA. Formatos observados:
    ``IE_CBI!C58301`` (nca primero) y ``PSD_PI!PT_BP!8709`` (tipo antes
    del nca, p. ej. en referencias parent)."""
    if not isinstance(entity_code, str) or "!" not in entity_code:
        return None
    parts = entity_code.split("!")
    if parts[0].startswith("PSD_") and len(parts) > 1:
        return parts[1]
    return parts[0]


def _mica_territorial_route(cnmv_category: Any) -> tuple[str | None, str | None]:
    """Clasifica la categoria territorial CNMV (G1-D, freeze D2).

    Devuelve (route, label). LIMITED se evalua antes que LP: la categoria
    'LIMITED PSC EN REGIMEN DE LP' contiene el patron LP pero no esta
    definida por fuente primaria — jamas se promociona a LP (H12-E).
    """
    if not isinstance(cnmv_category, str) or not cnmv_category.strip():
        return None, None
    cat = cnmv_category.upper()
    if "LIMITED" in cat:
        return "LIMITED_LP", "LIMITED PSC EN REGIMEN DE LP"
    if "SUCURSAL" in cat:
        return "BRANCH", "PSC A TRAVES DE SUCURSAL"
    if "REGIMEN DE LP" in cat.replace("É", "E"):
        return "LP", "PSC EN REGIMEN DE LP"
    if cat in {"PSC (ESPAÑA)", "ENTIDAD DE CRÉDITO (ESPAÑA)"}:
        return "DOMESTIC", None
    return "OTHER", None


def _mica_es_declared(service_countries_raw: Any) -> str | None:
    """ES declarado en ac_serviceCode_cou (hecho reportado, no trigger)."""
    if not isinstance(service_countries_raw, str):
        return None
    countries = {c.strip() for c in service_countries_raw.split("|") if c.strip()}
    return "TRUE" if "ES" in countries else "FALSE"


def _parse_ddmmyyyy(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()
    except ValueError:
        return None


def _group_claims(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Agrupa claims por (corpus_id, source, record) conservando el orden.

    El discriminador de registro (G1-D) permite que una misma entidad
    del corpus tenga varios registros de la misma fuente — p. ej. una
    PI y su sucursal ES son registros EBA distintos de la misma persona
    juridica. En los ledgers G0/G1-A/G1-C cada (corpus_id, source) tiene
    un unico record_key, por lo que el agrupamiento es identico.
    """
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for claim in ledger["claims"]:
        key = (
            claim["corpus_id"],
            claim["source"],
            canonical_json(claim["record_key"]),
        )
        group = groups.setdefault(
            key,
            {
                "corpus_id": claim["corpus_id"],
                "source": claim["source"],
                "fields": {},
                "raws": {},
                "claim_ids": [],
                "context": {
                    "authority": claim["authority"],
                    "register_id": claim["register_id"],
                    "snapshot_file": claim["snapshot_file"],
                    "snapshot_sha256": claim["snapshot_sha256"],
                    "record_key": claim["record_key"],
                    "raw_record_sha256": claim["raw_record_sha256"],
                    "extractor_version": claim["extractor_version"],
                    "retrieved_at": claim["retrieved_at"],
                    "source_as_of": claim["source_as_of"],
                    "source_date_reliability": claim["source_date_reliability"],
                },
            },
        )
        group["fields"][claim["field"]] = claim["normalized_value"]
        group["raws"][claim["field"]] = claim["raw_value"]
        group["claim_ids"].append(claim["claim_id"])

    groups_list = list(groups.values())

    # G1-A: campos derivados EBA (namespace eba_*), calculados por el
    # motor para que las reglas puedan hacer match sobre ellos sin
    # hardcodear la semantica ENT_AUT en las condiciones.
    status_by_code: dict[tuple[str | None, str | None], str] = {}
    group_by_code: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for group in groups_list:
        if group["source"] == "EBA_PSD2_REGISTER":
            fields = group["fields"]
            derived = _eba_ent_aut_derived(fields.get("ent_aut_raw"))
            fields["eba_ent_aut_status"] = derived["status"]
            fields["eba_ent_aut_intervals"] = derived["intervals"]
            fields["eba_ent_aut_last_auth"] = derived["last_auth"]
            status_by_code[
                (fields.get("entity_type"), fields.get("entity_code"))
            ] = derived["status"]
            group_by_code[
                (fields.get("entity_type"), fields.get("entity_code"))
            ] = group
            # G1-D: servicios exactos declarados para ES (Services{"ES":...})
            # y etiqueta del emisor NCA para la base juridica.
            fields["eba_es_services"] = _eba_country_services(
                fields.get("services_raw"), "ES"
            )
            es_codes = fields["eba_es_services"]
            fields["eba_es_services_str"] = (
                "|".join(es_codes) if es_codes else None
            )
            fields["eba_home_nca"] = _eba_nca_code(fields.get("entity_code"))
            fields["eba_ent_class_label"] = {
                "PSD_PI": "PI",
                "PSD_EMI": "EMI",
            }.get(fields.get("entity_type"))
            # DER_CHI_ENT_AUT (PSD_AG/PSD_BR): estado del hijo reportado
            # por la NCA — evidencia del parent, no autorizacion propia.
            child_status = fields.get("der_chi_ent_aut")
            fields["eba_child_status"] = (
                "ACTIVE" if child_status == "Active"
                else "WITHDRAWN" if child_status in {"Removed", "Withdrawn"}
                else "UNKNOWN" if child_status
                else None
            )

    # G1-A: resolucion parent->child para PSD_AG/PSD_BR. El estado del
    # hijo es evidencia DEL PARENT (spec EBA: DER_CHI_ENT_AUT hereda);
    # nunca autorizacion independiente.
    # G1-D: el join exacto incorpora el grupo del parent como evidencia
    # corroborante (SourceAssertion[] de la conclusion incluye el
    # registro del parent, no solo su estado resuelto).
    for group in groups_list:
        fields = group["fields"]
        if group["source"] != "EBA_PSD2_REGISTER":
            continue
        par_code = fields.get("ent_cod_par_ent")
        par_type = fields.get("ent_typ_par_ent")
        if par_code and par_type:
            fields["eba_parent_status"] = status_by_code.get(
                (par_type, par_code), "UNKNOWN"
            )
            parent_group = group_by_code.get((par_type, par_code))
            if parent_group is not None:
                group.setdefault("corroborating_groups", []).append(
                    parent_group
                )
                parent_fields = parent_group["fields"]
                fields["eba_parent_entity_type"] = parent_fields.get(
                    "entity_type"
                )
                fields["eba_parent_class_label"] = {
                    "PSD_PI": "PI",
                    "PSD_EMI": "EMI",
                }.get(parent_fields.get("entity_type"))
                fields["eba_parent_nca"] = _eba_nca_code(par_code)
                fields["eba_parent_last_auth"] = parent_fields.get(
                    "eba_ent_aut_last_auth"
                )

    # G1-D: join BdE registro de servicios de pago -> sucursal EBA por
    # corpus_id. La inscripcion BdE (sucursal activa, fecha de alta) es
    # el trigger territorial del regimen de establecimiento PSD2; la
    # fecha de baja cerrada marca la sucursal como no activa.
    bde_by_entity: dict[str, list[dict[str, Any]]] = {}
    for group in groups_list:
        if group["source"] == "BDE_REGISTRO_SERVICIOS_PAGO":
            bde_by_entity.setdefault(group["corpus_id"], []).append(group)
    for group in groups_list:
        fields = group["fields"]
        if group["source"] != "EBA_PSD2_REGISTER":
            continue
        if fields.get("entity_type") != "PSD_BR":
            continue
        bde_groups = bde_by_entity.get(group["corpus_id"], [])
        if not bde_groups:
            continue
        altas = {
            g["fields"].get("fecha_alta")
            for g in bde_groups
            if g["fields"].get("fecha_alta")
        }
        bajas = [
            g["fields"].get("fecha_baja") for g in bde_groups
        ]
        fields["bde_branch_date_conflict"] = (
            "TRUE" if len(altas) > 1 else None
        )
        primary = bde_groups[0]["fields"]
        fields["bde_branch_fecha_alta"] = (
            primary.get("fecha_alta") if len(altas) <= 1 else None
        )
        fields["bde_branch_codigo"] = primary.get("codigo_be")
        fields["bde_branch_registered"] = (
            "TRUE" if altas and all(not b for b in bajas) else "FALSE"
        )
        group.setdefault("corroborating_groups", []).extend(bde_groups)

    # G1-C: join CNMV_PSC_REGISTER -> ESMA_MICA_REGISTER por corpus_id.
    # La categoria CNMV ancla el mecanismo juridico (art. 60/63); el CSV
    # ESMA nunca lo decide por si mismo (ae_authorisationNotificationDate
    # no distingue autorizacion de notificacion).
    cnmv_by_entity: dict[str, dict[str, Any]] = {}
    for group in groups_list:
        if group["source"] == "CNMV_PSC_REGISTER":
            cnmv_by_entity[group["corpus_id"]] = group
            route, route_label = _mica_territorial_route(
                group["fields"].get("cnmv_category")
            )
            group["fields"]["cnmv_territorial_route"] = route
            group["fields"]["cnmv_route_label"] = route_label
    for group in groups_list:
        if group["source"] != "ESMA_MICA_REGISTER":
            continue
        fields = group["fields"]
        cnmv_group = cnmv_by_entity.get(group["corpus_id"])
        cnmv = cnmv_group["fields"] if cnmv_group else {}
        if cnmv_group is not None:
            # Las aserciones MiCA derivadas se apoyan en los claims CNMV
            # (categoria ancla del mecanismo): quedan citados como
            # evidencia corroborante en la procedencia de la asercion.
            group["corroborating_groups"] = [cnmv_group]
        fields["cnmv_category"] = cnmv.get("cnmv_category")
        fields["cnmv_services_from"] = cnmv.get("services_from")
        # G1-D: ruta territorial de la categoria CNMV (LP / BRANCH /
        # LIMITED_LP / DOMESTIC) y si ES aparece en los paises
        # declarados. La ruta territorial no cambia el mecanismo base.
        route, route_label = _mica_territorial_route(
            fields.get("cnmv_category")
        )
        fields["cnmv_territorial_route"] = route
        fields["cnmv_route_label"] = route_label
        fields["mica_es_declared"] = _mica_es_declared(
            fields.get("service_countries_raw")
        )
        fields["mica_service_letters"] = _mica_service_letters(
            fields.get("service_codes_raw")
        )
        fields["mica_foreign_countries"] = _mica_foreign_countries(
            fields.get("service_countries_raw"), fields.get("home_member_state")
        )
        esma_date = _parse_ddmmyyyy(fields.get("authorisation_notification_date"))
        cnmv_date = _parse_ddmmyyyy(fields.get("cnmv_services_from"))
        fields["mica_dates_agree"] = (
            "TRUE" if esma_date and esma_date == cnmv_date
            else "FALSE" if esma_date and cnmv_date
            else None
        )
        fields["mica_status"] = (
            "ENDED" if (fields.get("authorisation_end_date") or "").strip()
            else "ACTIVE"
        )

    # G1-D-F01: mecanismo home MiCA desde fuentes NCA primarias. La
    # Unternehmensdatenbank BaFin cita por permiso la base legal
    # (Art. 59 Abs. 1a = autorizacion art.63; Abs. 1b = entidad
    # financiera via art.60); Finanstilsynet lo corrobora con remarks
    # (p. ej. "Article 60(3)"). La categoria CNMV decide la ruta
    # territorial, NUNCA el mecanismo — sin prueba home no hay positivo.
    mech_by_entity: dict[str, list[dict[str, Any]]] = {}
    for group in groups_list:
        if group["source"] in (
            "BAFIN_UNTERNEHMENSDATENBANK",
            "FINANSTILSYNET_REGISTRY",
        ):
            mech_by_entity.setdefault(group["corpus_id"], []).append(group)
    for group in groups_list:
        if group["source"] != "ESMA_MICA_REGISTER":
            continue
        fields = group["fields"]
        mech_groups = mech_by_entity.get(group["corpus_id"], [])
        if mech_groups:
            group.setdefault("corroborating_groups", []).extend(mech_groups)
        signals: set[str] = set()
        art60_3 = False
        entity_class: str | None = None
        for g in mech_groups:
            f = g["fields"]
            route = f.get("mica_home_route")  # ART_59_1A | ART_59_1B
            remark = f.get("home_mechanism_remark")  # ART_60_3
            if route == "ART_59_1A":
                signals.add("AUTHORISATION")
            elif route == "ART_59_1B":
                signals.add("NOTIFICATION")
            if remark == "ART_60_3":
                signals.add("NOTIFICATION")
                art60_3 = True
            gattung = f.get("home_entity_class_de") or ""
            licences = f.get("home_licences") or ""
            if "Wertpapierinstitut" in gattung or "Investment firm" in licences:
                entity_class = "INVESTMENT_FIRM_ESI"
            elif "Kreditinstitut" in gattung:
                entity_class = "CREDIT_INSTITUTION"
        if len(signals) > 1:
            fields["mica_home_mechanism"] = None
            fields["mica_home_mechanism_conflict"] = "TRUE"
        elif signals:
            mechanism = next(iter(signals))
            fields["mica_home_mechanism"] = mechanism
            if mechanism == "AUTHORISATION":
                fields["mica_home_legal_ref"] = "art. 63 (art. 59(1)(a))"
                fields["mica_home_entity_class"] = entity_class or "CASP"
            elif art60_3 or entity_class == "INVESTMENT_FIRM_ESI":
                fields["mica_home_legal_ref"] = "art. 60(3) (art. 59(1)(b))"
                fields["mica_home_entity_class"] = entity_class or "CASP"
            else:
                fields["mica_home_legal_ref"] = "art. 60 (art. 59(1)(b))"
                fields["mica_home_entity_class"] = entity_class or "CASP"

    return groups_list


def _source_assertion(group: dict[str, Any], manifest: dict[str, Any]) -> dict:
    ctx = group["context"]
    item = next(
        s for s in manifest["snapshots"] if s["snapshot_file"] == ctx["snapshot_file"]
    )
    return {
        "authority": ctx["authority"],
        "register_id": ctx["register_id"],
        "source_url": item["source_url"],
        "retrieved_at": ctx["retrieved_at"],
        # date.fromisoformat exige componente fecha: el datetime EBA se
        # reduce a su parte de fecha (el raw completo queda en raw_value).
        "source_as_of": (
            ctx["source_as_of"].split("T")[0] if ctx["source_as_of"] else None
        ),
        "source_date_reliability": ctx["source_date_reliability"],
        "raw_value": canonical_json(
            {"record_key": ctx["record_key"], "fields": group["raws"]}
        ),
        "raw_snapshot_sha256": ctx["snapshot_sha256"],
        "extractor_version": ctx["extractor_version"],
        "observed_current": True,
    }


def _condition(fields: dict[str, Any], condition: dict[str, Any]) -> bool:
    value = fields.get(condition["field"])
    op = condition["op"]
    if op == "EQ":
        return value == condition["value"]
    if op == "NOT_NULL":
        return value is not None and value != ""
    if op == "IN":
        return value in condition["value"]
    if op == "NOT_IN":
        return value not in condition["value"]
    raise ValueError(f"operador de condicion desconocido: {op}")


def _iterate_items(
    fields: dict[str, Any], spec: dict[str, Any]
) -> list[str] | None:
    raw = fields.get(spec["field"])
    if spec["mode"] == "SPLIT":
        if not isinstance(raw, str) or not raw.strip():
            return None
        items = [part.strip() for part in raw.split(spec["separator"])]
    elif spec["mode"] == "DICT_KEYS":
        if not isinstance(raw, list):
            return None
        items = [key for entry in raw if isinstance(entry, dict) for key in entry]
    else:
        raise ValueError(f"modo de iteracion desconocido: {spec['mode']}")
    excluded = set(spec.get("exclude_values", []))
    if spec.get("exclude_field_value"):
        excluded.add(fields.get(spec["exclude_field_value"]))
    seen: list[str] = []
    for item in items:
        if item and item not in excluded and item not in seen:
            seen.append(item)
    return seen


_FIELD_REF = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


def _interpolate(text: Any, fields: dict[str, Any]) -> tuple[str | None, list[str]]:
    """Sustituye ``{campo}`` por el valor del claim group (G1-D).

    Devuelve (texto, placeholders_sin_valor). Un placeholder sin valor
    es un input juridico requerido ausente: la regla emite finding, no
    una asercion con la referencia vacia.
    """
    if not isinstance(text, str):
        return text, []
    missing: list[str] = []

    def _sub(match: re.Match[str]) -> str:
        value = fields.get(match.group(1))
        if value is None or value == "":
            missing.append(match.group(1))
            return match.group(0)
        return str(value)

    return _FIELD_REF.sub(_sub, text), missing


def _resolve_effective(
    spec: dict[str, Any] | None,
    fields: dict[str, Any],
    evidence_as_of: str,
) -> tuple[str | None, bool]:
    """Devuelve (valor_iso, ok). ok=False => REQUIRED_FIELD_UNDERIVABLE."""
    if spec is None or spec["derivation"] == "CONSTANT_NULL":
        return None, True
    kind = spec["derivation"]
    if kind == "EVIDENCE_AS_OF":
        return evidence_as_of, True
    if kind == "FIELD_DDMMYYYY":
        parsed = _parse_ddmmyyyy(fields.get(spec["field"]))
        return parsed, parsed is not None
    if kind == "FIELD_DDMMYYYY_OR_NULL":
        return _parse_ddmmyyyy(fields.get(spec["field"])), True
    if kind == "EBA_ENT_AUT_LAST_AUTH":
        # G1-A: ultima fecha de autorizacion/registro de la secuencia
        # ENT_AUT ya interpretada por _eba_ent_aut_derived.
        value = fields.get("eba_ent_aut_last_auth")
        return value, value is not None
    raise ValueError(f"derivacion efectiva desconocida: {kind}")


def _emit_assertion(
    assertion_id: str,
    emit: dict[str, Any],
    group: dict[str, Any],
    evidence_as_of: str,
    source_assertion: dict[str, Any],
    item: str | None,
    findings: list[dict[str, Any]],
    rule: dict[str, Any],
    ruleset_version: str,
) -> dict[str, Any] | None:
    """Materializa una asercion desde el bloque emit de la regla.

    Devuelve None (con finding registrado) cuando la derivacion falla:
    ningun fallo produce una asercion positiva inventada.
    """
    fields = group["fields"]

    def _resolve(key: str, failure: str) -> str | None:
        mapped = emit.get(f"{key}_from")
        if mapped is not None:
            # "$ITEM" como field: el item iterado actua como clave del
            # mapa (p. ej. letra de servicio MiCA -> actividad canonica).
            value = item if mapped["field"] == "$ITEM" else fields.get(mapped["field"])
            result = mapped["map"].get(value)
            if result is None:
                findings.append(
                    _finding(group, rule, failure, f"{mapped['field']}={value!r} no mapeable")
                )
            return result
        literal = emit.get(key)
        if literal == "$ITEM":
            return item
        return literal

    entity_class = _resolve("entity_class", "UNSUPPORTED_ENTITY_CLASS")
    activity = _resolve("activity", "UNSUPPORTED_ACTIVITY_MAPPING")
    jurisdiction = _resolve("jurisdiction", "UNSUPPORTED_ACTIVITY_MAPPING")
    # G1-D-F01: entry_mechanism puede provenir de un campo derivado
    # (entry_mechanism_from): la ruta territorial nunca fija el
    # mecanismo, solo la evidencia home probada lo hace.
    entry_mechanism = _resolve("entry_mechanism", "REQUIRED_FIELD_MISSING")
    if (
        entity_class is None
        or activity is None
        or jurisdiction is None
        or entry_mechanism is None
    ):
        return None

    effective_from, ok = _resolve_effective(
        emit.get("effective_from"), fields, evidence_as_of
    )
    if not ok:
        findings.append(
            _finding(
                group,
                rule,
                "REQUIRED_FIELD_UNDERIVABLE",
                f"effective_from no derivable desde {emit['effective_from']}",
            )
        )
        return None
    effective_to, ok = _resolve_effective(
        emit.get("effective_to"), fields, evidence_as_of
    )
    if not ok:
        findings.append(
            _finding(
                group,
                rule,
                "REQUIRED_FIELD_UNDERIVABLE",
                f"effective_to no derivable desde {emit['effective_to']}",
            )
        )
        return None

    legal_basis, missing_lb = _interpolate(emit["legal_basis"], fields)
    scope, missing_scope = _interpolate(emit["scope"], fields)
    missing_refs = missing_lb + missing_scope
    if missing_refs:
        findings.append(
            _finding(
                group,
                rule,
                "REQUIRED_FIELD_MISSING",
                f"campos: {missing_refs} (interpolacion legal_basis/scope)",
            )
        )
        return None

    assertion = {
        "assertion_id": assertion_id,
        "register_id": group["context"]["register_id"],
        "entity_id": group["corpus_id"],
        "entity_class": entity_class,
        "activity": activity,
        "jurisdiction": jurisdiction,
        "legal_effect": emit["legal_effect"],
        "entry_mechanism": entry_mechanism,
        "territorial_basis": emit["territorial_basis"],
        "legal_basis": legal_basis,
        "effective_from": effective_from,
        "effective_to": effective_to,
        "scope": scope,
        "rule_id": rule["rule_id"],
        "ruleset_version": ruleset_version,
        "source_claim_ids": group["claim_ids"] + [
            cid
            for g in group.get("corroborating_groups", [])
            for cid in g["claim_ids"]
        ],
        "source_assertions": [source_assertion]
        + group.get("corroborating_source_assertions", []),
        "derived_by": None,
        "principal_entity_id": None,
    }
    # G1-A: campos opcionales declarados por el emit. Solo se incluyen
    # si la regla los declara — los artefactos G0 no los llevan.
    if "evidence_basis" in emit:
        assertion["evidence_basis"] = emit["evidence_basis"]
    if "reported_status" in emit:
        assertion["reported_status"] = emit["reported_status"]
    elif "reported_status_from" in emit:
        assertion["reported_status"] = fields.get(
            emit["reported_status_from"]["field"]
        )
    if "status_intervals_from" in emit:
        assertion["status_intervals"] = fields.get(
            emit["status_intervals_from"]["field"]
        )
    # G1-D-F02: aserciones conjuntivas (EBA+BdE, ESMA+CNMV+home NCA)
    # declaran composicion ALL_REQUIRED: cada fuente requerida exige
    # contrato + scope + freshness bajo su propio contrato en assess().
    if "evidence_composition" in emit:
        assertion["evidence_composition"] = emit["evidence_composition"]
    return assertion


def _finding(
    group: dict[str, Any] | None,
    rule: dict[str, Any],
    classification: str,
    detail: str,
    entity_id: str | None = None,
) -> dict[str, Any]:
    return {
        "finding_id": None,  # asignado en secuencia al final
        "corpus_id": entity_id or (group["corpus_id"] if group else None),
        "source": group["source"] if group else None,
        "rule_id": rule["rule_id"],
        "classification": classification,
        "detail": detail,
    }


def build_identity_index(
    corpus: dict[str, Any], groups: list[dict[str, Any]], manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Indice de identidad del corpus + identificadores invalidos.

    Solo entran identificadores verificados: LEI con diagnostico VALID y
    codigos de registro de fuente. El entity_id es el corpus_id: el
    corpus congelado ES el marco de identidad de G0.5.
    """
    groups_by_entity: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        groups_by_entity.setdefault(group["corpus_id"], []).append(group)

    index: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for entity in corpus["entities"]:
        corpus_id = entity["corpus_id"]
        identifiers: list[dict[str, str]] = []
        classes: list[str] = []
        for group in groups_by_entity.get(corpus_id, []):
            item = next(
                s
                for s in manifest["snapshots"]
                if s["snapshot_file"] == group["context"]["snapshot_file"]
            )
            lei = group["fields"].get("lei")
            diagnostic = group["fields"].get("lei_diagnostic")
            if lei and diagnostic == "VALID":
                identifiers.append(
                    {
                        "kind": "LEI",
                        "value": lei,
                        "source_url": item["source_url"],
                        "retrieved_at": group["context"]["retrieved_at"],
                    }
                )
            elif lei:
                invalid.append(
                    {
                        "corpus_id": corpus_id,
                        "kind": "LEI",
                        "value": lei,
                        "lei_diagnostic": diagnostic,
                    }
                )
            for (source, field_name), id_kind in IDENTIFIER_KIND_BY_FIELD.items():
                if source != group["source"]:
                    continue
                value = group["fields"].get(field_name)
                if value:
                    identifiers.append(
                        {
                            "kind": id_kind,
                            "value": str(value),
                            "source_url": item["source_url"],
                            "retrieved_at": group["context"]["retrieved_at"],
                        }
                    )
        index.append(
            {
                "entity_id": corpus_id,
                "legal_name": entity["legal_name"],
                "entity_classes": classes,
                "identifiers": identifiers,
                "principal_entity_id": None,
            }
        )
    return index, invalid


def derive_entitlements(
    ledger: dict[str, Any],
    ruleset: dict[str, Any],
    manifest: dict[str, Any],
    corpus: dict[str, Any],
    *,
    derivation_version: str = DERIVATION_VERSION,
    id_prefix: str = "g07",
) -> dict[str, Any]:
    """Ejecuta el ruleset sobre el ledger: aserciones + findings + indice."""
    spec = ruleset["ruleset"]
    groups = _group_claims(ledger)
    evidence_as_of = manifest["retrieved_at"]
    assertions: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    reported_facts: list[dict[str, Any]] = []

    for group in groups:
        fields = group["fields"]
        source_assertion = _source_assertion(group, manifest)
        if "corroborating_groups" in group:
            group["corroborating_source_assertions"] = [
                _source_assertion(g, manifest)
                for g in group["corroborating_groups"]
            ]
        for rule in spec["rules"]:
            match = rule["match"]
            if match["source"] != group["source"]:
                continue
            if not all(_condition(fields, c) for c in match["conditions"]):
                continue
            missing = [
                f for f in rule.get("required_fields", []) if fields.get(f) is None
            ]
            if missing:
                findings.append(
                    _finding(
                        group, rule, "REQUIRED_FIELD_MISSING", f"campos: {missing}"
                    )
                )
                continue
            if "emit_status_fact" in rule:
                # G1-A: hecho de estado reportado (p. ej. WITHDRAWN).
                # No es una EntitlementAssertion ni un efecto juridico
                # negativo — la lectura juridica es de assessment/G1-E.
                fact_spec = rule["emit_status_fact"]
                status = fact_spec.get("reported_status")
                if status is None:
                    status = fields.get(fact_spec["reported_status_from"]["field"])
                if status is None:
                    # sin estado resoluble no se emite medio hecho
                    continue
                reported_facts.append(
                    {
                        "fact_id": f"{id_prefix}-fact-{len(reported_facts) + 1:03d}",
                        "corpus_id": group["corpus_id"],
                        "source": group["source"],
                        "rule_id": rule["rule_id"],
                        "reported_status": status,
                        "status_intervals": fields.get("eba_ent_aut_intervals"),
                        "detail": fact_spec.get("detail"),
                    }
                )
                continue
            if "emit_per" in rule:
                items = _iterate_items(fields, rule["emit_per"]["iterate"])
                if not items:
                    continue
                emits = [(rule["emit_per"]["emit"], item) for item in items]
            elif rule.get("emit") is None:
                spec_finding = rule["finding"]
                findings.append(
                    _finding(group, rule, spec_finding["classification"], spec_finding["detail"])
                )
                continue
            else:
                emits = [(rule["emit"], None)]
            for emit, item in emits:
                assertion = _emit_assertion(
                    f"{id_prefix}-asm-{len(assertions) + 1:03d}",
                    emit,
                    group,
                    evidence_as_of,
                    source_assertion,
                    item,
                    findings,
                    rule,
                    derivation_version,
                )
                if assertion is not None:
                    assertions.append(assertion)

    # Segunda pasada: reglas derivadas sobre las aserciones emitidas.
    for rule in spec["derived_rules"]:
        base = rule["base"]
        fired = False
        emitted_keys: set[tuple] = set()
        for assertion in list(assertions):
            if not all(assertion[k] == v for k, v in base.items()):
                continue
            fired = True
            # Una entidad con N aserciones base que acreditan la misma
            # clase (p.ej. N servicios MiCA art.60) produce UNA asercion
            # derivada por (entidad, actividad, ambito): la multiplicidad
            # de evidencia nunca se convierte en multiplicidad juridica.
            key = (
                assertion["entity_id"],
                rule["emit"]["activity"],
                assertion["jurisdiction"],
                assertion["territorial_basis"],
                rule["emit"]["legal_effect"],
                rule["emit"]["entry_mechanism"],
            )
            if key in emitted_keys:
                continue
            emitted_keys.add(key)
            derived = {
                "assertion_id": f"{id_prefix}-asm-{len(assertions) + 1:03d}",
                "register_id": assertion["register_id"],
                "entity_id": assertion["entity_id"],
                "entity_class": assertion["entity_class"],
                "activity": rule["emit"]["activity"],
                "jurisdiction": assertion["jurisdiction"],
                "legal_effect": rule["emit"]["legal_effect"],
                "entry_mechanism": rule["emit"]["entry_mechanism"],
                "territorial_basis": assertion["territorial_basis"],
                "legal_basis": rule["emit"]["legal_basis"],
                "effective_from": assertion["effective_from"],
                "effective_to": assertion["effective_to"],
                "scope": rule["emit"]["scope"],
                "rule_id": rule["rule_id"],
                "ruleset_version": rule["ruleset_version"],
                "source_claim_ids": assertion["source_claim_ids"],
                "source_assertions": assertion["source_assertions"],
                "derived_by": {
                    "rule_id": rule["rule_id"],
                    "ruleset_version": rule["ruleset_version"],
                    "effective_from": assertion["effective_from"],
                },
                "principal_entity_id": None,
            }
            assertions.append(derived)
        if not fired:
            candidates = {
                a["entity_id"]
                for a in assertions
                if a["entity_class"] == base["entity_class"]
            }
            for entity_id in sorted(candidates):
                findings.append(
                    _finding(
                        None,
                        rule,
                        rule["untriggered_finding"]["classification"],
                        rule["untriggered_finding"]["detail"],
                        entity_id=entity_id,
                    )
                )

    for index, finding in enumerate(findings, start=1):
        finding["finding_id"] = f"{id_prefix}-fnd-{index:03d}"

    # Clases evidenciadas: union de las clases de las aserciones emitidas.
    index, invalid = build_identity_index(corpus, groups, manifest)
    classes_by_entity: dict[str, set[str]] = {}
    for assertion in assertions:
        classes_by_entity.setdefault(assertion["entity_id"], set()).add(
            assertion["entity_class"]
        )
    for entry in index:
        entry["entity_classes"] = sorted(classes_by_entity.get(entry["entity_id"], ()))

    result = {
        "assertions": assertions,
        "findings": findings,
        "identity_index": index,
        "invalid_identifiers": invalid,
    }
    # G1-A: hechos de estado reportados. Solo presente cuando el
    # ruleset emite al menos uno — los artefactos G0 no llevan la clave.
    if reported_facts:
        result["reported_facts"] = reported_facts
    return result


def to_entitlement_assertions(artifact: dict[str, Any]) -> list[EntitlementAssertion]:
    return [
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
            effective_to=a["effective_to"],
            scope=a["scope"],
            source_assertions=tuple(
                SourceAssertion(**s) for s in a["source_assertions"]
            ),
            derived_by=a.get("derived_by"),
            principal_entity_id=a.get("principal_entity_id"),
            evidence_basis=a.get("evidence_basis"),
            reported_status=a.get("reported_status"),
            status_intervals=(
                tuple(a["status_intervals"]) if a.get("status_intervals") else None
            ),
            evidence_composition=a.get("evidence_composition"),
        )
        for a in artifact["assertions"]
    ]


def to_identity_index(artifact: dict[str, Any]) -> list[IdentityIndexEntry]:
    return [
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
                for i in e["identifiers"]
            ),
            principal_entity_id=e.get("principal_entity_id"),
        )
        for e in artifact["identity_index"]
    ]


def _build_artifact(
    repo_root: Path,
    *,
    ledger_rel: str,
    ruleset_rel: str,
    corpus_rel: str,
    manifest_rel: str,
    artifact_version: str,
    derivation_version: str,
    id_prefix: str,
) -> dict[str, Any]:
    ledger_path = repo_root / ledger_rel
    ruleset_path = repo_root / ruleset_rel
    corpus_path = repo_root / corpus_rel
    manifest_path = repo_root / manifest_rel

    ledger = strict_json_loads(ledger_path.read_text(encoding="utf-8"))
    ruleset = strict_json_loads(ruleset_path.read_text(encoding="utf-8"))
    corpus = strict_json_loads(corpus_path.read_text(encoding="utf-8"))
    manifest = strict_json_loads(manifest_path.read_text(encoding="utf-8"))

    result = derive_entitlements(
        ledger,
        ruleset,
        manifest,
        corpus,
        derivation_version=derivation_version,
        id_prefix=id_prefix,
    )
    artifact = {
        "artifact": {
            "artifact_version": artifact_version,
            "derivation_version": derivation_version,
            "ruleset_version": ruleset["ruleset"]["ruleset_version"],
            "claims_ledger_sha256": _sha256_file(ledger_path),
            "derivation_ruleset_sha256": _sha256_file(ruleset_path),
            "corpus_sha256": _sha256_file(corpus_path),
            "source_manifest_sha256": _sha256_file(manifest_path),
            "claims_consumed": len(ledger["claims"]),
            "assertions_emitted": len(result["assertions"]),
            "findings_emitted": len(result["findings"]),
            "assessment": "NOT_RUN",
        },
        **result,
    }
    if result.get("reported_facts"):
        artifact["artifact"]["reported_facts_emitted"] = len(
            result["reported_facts"]
        )
    return artifact


def build_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto congelado de G0.7-A: inputs fijados por sha256."""
    return _build_artifact(
        repo_root,
        ledger_rel="fixtures/g0.6/claim-provenance-g0.5-a-003.json",
        ruleset_rel="fixtures/g0.7/derivation-rules.json",
        corpus_rel="fixtures/g0.5/corpus/entities.json",
        manifest_rel="fixtures/g0.5/sources/manifest.json",
        artifact_version=ARTIFACT_VERSION,
        derivation_version=DERIVATION_VERSION,
        id_prefix="g07",
    )


def build_g1_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto G1-A: mismo ledger/corpus G0 congelados, ruleset G1."""
    return _build_artifact(
        repo_root,
        ledger_rel="fixtures/g0.6/claim-provenance-g0.5-a-003.json",
        ruleset_rel="fixtures/g1/derivation-rules-g1-a.json",
        corpus_rel="fixtures/g0.5/corpus/entities.json",
        manifest_rel="fixtures/g0.5/sources/manifest.json",
        artifact_version=G1_ARTIFACT_VERSION,
        derivation_version=G1_DERIVATION_VERSION,
        id_prefix="g1a",
    )


def build_g1c_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto G1-C: ledger G1-C (incluye claims CNMV ancla de
    mecanismo), ruleset G1-C, manifest fusionado."""
    return _build_artifact(
        repo_root,
        ledger_rel="fixtures/g1/claim-ledger-g1-c-001.json",
        ruleset_rel="fixtures/g1/derivation-rules.json",
        corpus_rel="fixtures/g0.5/corpus/entities.json",
        manifest_rel="fixtures/g1/sources/manifest-g1-c-run.json",
        artifact_version=G1_ARTIFACT_VERSION,
        derivation_version=G1_DERIVATION_VERSION,
        id_prefix="g1c",
    )


def build_g1d_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto G1-D: ledger G1-D (G1-C + claims territoriales del
    corpus D3), ruleset G1-D, corpus extendido y manifest fusionado."""
    return _build_artifact(
        repo_root,
        ledger_rel="fixtures/g1/claim-ledger-g1-d-001.json",
        ruleset_rel="fixtures/g1/derivation-rules-g1-d.json",
        corpus_rel="fixtures/g1/corpus-g1-d.json",
        manifest_rel="fixtures/g1/sources/manifest-g1-d-run.json",
        artifact_version=G1_ARTIFACT_VERSION,
        derivation_version=G1D_DERIVATION_VERSION,
        id_prefix="g1d",
    )


def build_g1d_v2_artifact(repo_root: Path) -> dict[str, Any]:
    """Artefacto G1-D-F01 (sucesor -002): ledger con evidencia de
    mecanismo home (BaFin/Finanstilsynet) y ruleset con
    evidence_composition ALL_REQUIRED. La cadena -001 permanece
    congelada como registro historico."""
    return _build_artifact(
        repo_root,
        ledger_rel="fixtures/g1/claim-ledger-g1-d-002.json",
        ruleset_rel="fixtures/g1/derivation-rules-g1-d-002.json",
        corpus_rel="fixtures/g1/corpus-g1-d-002.json",
        manifest_rel="fixtures/g1/sources/manifest-g1-d-run-002.json",
        artifact_version=G1_ARTIFACT_VERSION,
        derivation_version=G1D_DERIVATION_VERSION,
        id_prefix="g1d2",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--g1", action="store_true", help="ruleset G1 (default: G0.7)")
    parser.add_argument("--g1c", action="store_true", help="artefacto G1-C")
    parser.add_argument("--g1d", action="store_true", help="artefacto G1-D")
    parser.add_argument(
        "--g1d2", action="store_true", help="artefacto G1-D-F01 (sucesor -002)"
    )
    args = parser.parse_args(argv)

    builder = build_artifact
    if args.g1:
        builder = build_g1_artifact
    if args.g1c:
        builder = build_g1c_artifact
    if args.g1d:
        builder = build_g1d_artifact
    if args.g1d2:
        builder = build_g1d_v2_artifact
    artifact = builder(args.repo_root.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical_json(artifact) + "\n")
    summary = artifact["artifact"]
    print(
        f"assertions={summary['assertions_emitted']} "
        f"findings={summary['findings_emitted']} -> {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
