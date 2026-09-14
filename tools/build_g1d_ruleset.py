"""Genera fixtures/g1/derivation-rules-g1-d.json desde el ruleset G1-C.

Delta G1-D sobre V2: corrige la semantica entry_mechanism del pasaporte
(la comunicacion territorial nunca muta el mecanismo de base), restringe
el hecho de parent-status a agentes (la sucursal se resuelve con regla
positiva propia) y anade las reglas territoriales + residuales
fail-closed preregistradas en D1/D2.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SRC = ROOT / "fixtures" / "g1" / "derivation-rules.json"
OUT = ROOT / "fixtures" / "g1" / "derivation-rules-g1-d.json"

rs = json.loads(SRC.read_text(encoding="utf-8"))
rules = rs["ruleset"]["rules"]

for r in rules:
    if r["rule_id"] == "mica-art63-domestic-psc":
        MICA_LETTER_MAP = r["emit_per"]["emit"]["activity_from"]["map"]

for r in rules:
    if r["rule_id"] == "eba-psd2-passport-services":
        r["match"]["conditions"].append(
            {"field": "country", "op": "NOT_IN", "value": ["ES"]}
        )
        it = r["emit_per"]["iterate"]
        it["exclude_field_value"] = "country"
        emit = r["emit_per"]["emit"]
        emit["entry_mechanism"] = "AUTHORISATION"
        emit["legal_basis"] = (
            "PSD2 (UE) 2015/2366 art. 28 + Reg. Delegado (UE) 2017/2055: "
            "servicios passportados declarados por pais de acogida en el "
            "registro EBA; el mecanismo de base es la autorizacion home "
            "(AUTHORISATION), la comunicacion territorial no la muta. "
            "Efecto territorial sin resolver para paises != ES."
        )
        emit["scope"] = (
            "servicio mapeado a pais de acogida en el registro PSD2; "
            "para ES la suficiencia territorial la decide la regla "
            "eba-psd2-fps-es-entitled"
        )
        r["rationale"] = (
            "El mapeo servicio-pais del registro es evidencia de pasaporte "
            "declarado. G1-D: para ES se emite positivo solo con "
            "procedimiento completado; el resto de paises queda como hecho "
            "UNKNOWN."
        )
    if r["rule_id"] == "eba-psd2-agent-branch-parent-status":
        r["rule_id"] = "eba-psd2-agent-parent-status"
        r["match"]["conditions"] = [
            {"field": "entity_type", "op": "EQ", "value": "PSD_AG"}
        ]
        r["emit_status_fact"]["detail"] = (
            "Estado heredado del parent (DER_CHI_ENT_AUT / resolucion "
            "parent->child): el agente opera por cuenta del principal "
            "(ruta delegada PSD2 art. 19), nunca autorizacion propia ni "
            "entitlement territorial independiente."
        )
        r["rationale"] = (
            "Spec EBA: DER_CHI_ENT_AUT hereda del parent. En G1-D el agente "
            "sigue produciendo 0 entitlement: el estado del padre explica el "
            "registro, no crea entitlement propio."
        )
        r["known_limitations"] = [
            "requiere claims ent_cod_par_ent/ent_typ_par_ent; sin ellos "
            "eba_parent_status no se resuelve y no se emite el hecho",
            "la inscripcion del agente en el registro del Estado de acogida "
            "(BdE) no esta observada en este ruleset",
        ]
    if r["rule_id"] == "mica-passport-territorial-deferred":
        # G1-D: el hecho "deferred" solo procede cuando NO hay trigger
        # territorial resoluble (sin categoria CNMV LP/sucursal). Con
        # ruta resuelta la regla positiva emite la asercion y un hecho
        # "deferred" simultaneo seria contradictorio.
        r["match"]["conditions"].append(
            {
                "field": "cnmv_territorial_route",
                "op": "NOT_IN",
                "value": ["LP", "BRANCH"],
            }
        )
        r["emit_status_fact"]["detail"] = (
            "ac_serviceCode_cou declara paises distintos del home state: "
            "hecho reportado de prestacion declarada. La suficiencia "
            "territorial exige el trigger CNMV (categoria + services_from) "
            "compuesto con la evidencia ESMA; country-code solo nunca es "
            "entitlement."
        )

new_rules = [
    {
        "rule_id": "eba-psd2-branch-es-parent-not-active",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "eba_parent_status", "op": "NOT_IN", "value": ["ACTIVE"]},
        ]},
        "finding": {
            "classification": "DERIVED_PRECONDITION_NOT_MET",
            "detail": "sucursal ES sin join exacto a parent ENT_AUT ACTIVE: DER_CHI_ENT_AUT solo no basta — la ruta de establecimiento exige la autorizacion vigente del principal; 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "D4: branch row + parent join + parent ACTIVE son precondiciones conjuntas; si el join falla o el parent no esta activo no hay positivo.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "eba-psd2-branch-es-date-conflict",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "bde_branch_date_conflict", "op": "EQ", "value": "TRUE"},
        ]},
        "finding": {
            "classification": "DATE_CONFLICT",
            "detail": "dos fechas territoriales divergentes de la misma semantica para la sucursal ES: sin precedencia silenciosa; abstencion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "Fechas divergentes entre evidencias del mismo trigger territorial: fail-closed (D3-10).",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "eba-psd2-branch-es-child-not-active",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "eba_parent_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "eba_child_status", "op": "NOT_IN", "value": ["ACTIVE"]},
        ]},
        "finding": {
            "classification": "DERIVED_PRECONDITION_NOT_MET",
            "detail": "parent ACTIVE pero DER_CHI_ENT_AUT de la sucursal no es Active: la NCA no reporta la sucursal como vigente; 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "Estado de la sucursal reportado por la NCA es input requerido; su ausencia/no-active produce finding, nunca positivo por el padre.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "eba-psd2-branch-es-registration-missing",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "eba_parent_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "eba_child_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "bde_branch_registered", "op": "NOT_IN", "value": ["TRUE"]},
        ]},
        "finding": {
            "classification": "REQUIRED_FIELD_MISSING",
            "detail": "sucursal EBA activa con parent activo pero sin inscripcion BdE vigente demostrada (registro especial de servicios de pago): PSD2 art. 28 exige inscripcion previa al inicio; 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "El trigger territorial de la ruta branch es la inscripcion en el registro del Estado de acogida; ausente o dada de baja => abstencion clasificada.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "eba-psd2-fps-es-entitled",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "IN", "value": ["PSD_PI", "PSD_EMI"]},
            {"field": "country", "op": "NOT_IN", "value": ["ES"]},
            {"field": "eba_ent_aut_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "eba_es_services", "op": "NOT_NULL"},
        ]},
        "required_fields": ["legal_name", "entity_code", "entity_type", "ent_aut_raw", "eba_home_nca", "eba_ent_aut_last_auth"],
        "coverage_preconditions": ["eba-psd2-in-eea"],
        "emit": {
            "entity_class_from": {"field": "entity_type", "map": {"PSD_PI": "PAYMENT_INSTITUTION", "PSD_EMI": "E_MONEY_INSTITUTION"}},
            "activity_from": {"field": "entity_type", "map": {"PSD_PI": "PAYMENT_SERVICES", "PSD_EMI": "E_MONEY_ISSUANCE"}},
            "jurisdiction": "ES",
            "territorial_basis": "FREEDOM_TO_PROVIDE_SERVICES",
            "legal_effect": "ENTITLED_TO_PROVIDE",
            "entry_mechanism": "AUTHORISATION",
            "evidence_basis": "NCA_REPORTED_VIA_EBA",
            "reported_status_from": {"field": "eba_ent_aut_status"},
            "status_intervals_from": {"field": "eba_ent_aut_intervals"},
            "legal_basis": "autorizacion {eba_ent_class_label} home NCA ({eba_home_nca}, {eba_ent_aut_last_auth}) + PSD2 art. 28 LPS + Reg. Delegado (UE) 2017/2055: servicios passportados a ES reportados por la NCA de origen via EBA; entry_mechanism permanece AUTHORISATION (la comunicacion territorial no lo muta)",
            "scope": "puede prestar en ES al menos los servicios PSD2 exactos declarados: {eba_es_services_str} — nunca la totalidad de payment services",
            "effective_from": {"derivation": "EVIDENCE_AS_OF"},
            "effective_to": {"derivation": "CONSTANT_NULL"},
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "H12-A: home ACTIVE + servicios exactos declarados para ES en el registro NCA/EBA = procedimiento art.28 completado observado. Sin fecha juridica territorial publicada se usa EVIDENCE_AS_OF (fecha mas temprana en que la evidencia atestigua el hecho); la fecha de autorizacion home nunca es fallback territorial.",
        "known_limitations": [
            "el registro EBA no publica la fecha de inicio del pasaporte: effective_from es evidencia, no concesion",
            "la modalidad LPS vs sucursal se decide por la evidencia: la sucursal ES emite ademas por la regla branch (COMPATIBLE_MULTI_ROUTE)",
        ],
    },
    {
        "rule_id": "eba-psd2-branch-es-entitled",
        "required_source_contract": "EBA_PSD2_REGISTER",
        "match": {"source": "EBA_PSD2_REGISTER", "conditions": [
            {"field": "entity_type", "op": "EQ", "value": "PSD_BR"},
            {"field": "country", "op": "EQ", "value": "ES"},
            {"field": "eba_child_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "eba_parent_status", "op": "EQ", "value": "ACTIVE"},
            {"field": "bde_branch_registered", "op": "EQ", "value": "TRUE"},
            {"field": "bde_branch_date_conflict", "op": "EQ", "value": None},
            {"field": "eba_es_services", "op": "NOT_NULL"},
        ]},
        "required_fields": ["legal_name", "entity_code", "entity_type", "eba_parent_nca", "eba_parent_last_auth", "bde_branch_codigo", "bde_branch_fecha_alta"],
        "coverage_preconditions": ["eba-psd2-in-eea"],
        "emit": {
            "entity_class_from": {"field": "eba_parent_entity_type", "map": {"PSD_PI": "PAYMENT_INSTITUTION", "PSD_EMI": "E_MONEY_INSTITUTION"}},
            "activity_from": {"field": "eba_parent_entity_type", "map": {"PSD_PI": "PAYMENT_SERVICES", "PSD_EMI": "E_MONEY_ISSUANCE"}},
            "jurisdiction": "ES",
            "territorial_basis": "BRANCH",
            "legal_effect": "ENTITLED_TO_PROVIDE",
            "entry_mechanism": "AUTHORISATION",
            "evidence_basis": "NCA_REPORTED_VIA_EBA",
            "reported_status_from": {"field": "eba_child_status"},
            "legal_basis": "autorizacion {eba_parent_class_label} home NCA ({eba_parent_nca}, {eba_parent_last_auth}) + PSD2 art. 28 establecimiento + PSD2 art. 28 sucursal (BdE {bde_branch_codigo}, {bde_branch_fecha_alta}): inscripcion sucursal BdE {bde_branch_codigo} ({bde_branch_fecha_alta}) demostrada; la actividad inicia tras inscripcion",
            "scope": "puede prestar en ES al menos los servicios PSD2 exactos declarados por la sucursal: {eba_es_services_str} — nunca la totalidad de payment services",
            "effective_from": {"derivation": "FIELD_DDMMYYYY", "field": "bde_branch_fecha_alta"},
            "effective_to": {"derivation": "CONSTANT_NULL"},
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "H12/D4: branch row + join exacto a parent + parent ENT_AUT ACTIVE + DER_CHI_ENT_AUT Active + inscripcion BdE vigente + servicio exacto => BRANCH. La fecha territorial es la fecha de alta BdE de la sucursal; la SourceAssertion[] incorpora parent y BdE como evidencia corroborante.",
        "known_limitations": [
            "la igualdad de clave (entity_type, entity_code) del join EBA es la identidad exacta; una clave parent no presente produce DERIVED_PRECONDITION_NOT_MET",
            "si la misma entidad tambien declara LPS a ES coexisten dos aserciones (COMPATIBLE_MULTI_ROUTE), nunca se colapsan",
        ],
    },
    {
        "rule_id": "mica-territorial-date-missing",
        "required_source_contract": "ESMA_MICA_REGISTER",
        "match": {"source": "ESMA_MICA_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "IN", "value": ["LP", "BRANCH"]},
            {"field": "mica_es_declared", "op": "EQ", "value": "TRUE"},
            {"field": "cnmv_services_from", "op": "EQ", "value": None},
        ]},
        "finding": {
            "classification": "REQUIRED_FIELD_MISSING",
            "detail": "cnmv_services_from ausente: la fecha territorial MiCA ('desde la que puede prestar') no esta probada; authorisationNotificationDate ESMA no es fallback (significado juridico distinto). 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "D3-09: fecha territorial ausente = abstencion auditable, disjunta del conflicto de fechas.",
        "required_fields": [], "coverage_preconditions": [],
        "known_limitations": ["la identidad exacta ESMA<->CNMV es invariante del join por corpus_id"],
    },
    {
        "rule_id": "mica-territorial-es-not-declared",
        "required_source_contract": "ESMA_MICA_REGISTER",
        "match": {"source": "ESMA_MICA_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "IN", "value": ["LP", "BRANCH"]},
            {"field": "mica_es_declared", "op": "NOT_IN", "value": ["TRUE"]},
        ]},
        "finding": {
            "classification": "TERRITORIAL_ROUTE_UNRESOLVED",
            "detail": "categoria CNMV territorial sin ES declarado en ac_serviceCode_cou: el trigger CNMV existe pero la composicion ESMA no atestigua el ambito; 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "La asercion territorial MiCA es composicion ESMA+CNMV: falta cualquiera de las dos evidencias => abstencion, nunca positivo por una sola fuente.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "mica-lp-es-entitled",
        "required_source_contract": "ESMA_MICA_REGISTER",
        "match": {"source": "ESMA_MICA_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "EQ", "value": "LP"},
            {"field": "mica_es_declared", "op": "EQ", "value": "TRUE"},
            {"field": "cnmv_services_from", "op": "NOT_NULL"},
        ]},
        "required_fields": ["legal_name", "lei", "service_codes_raw", "mica_service_letters", "authorisation_notification_date"],
        "coverage_preconditions": ["esma-mica-in-casp"],
        "emit_per": {
            "iterate": {"field": "mica_service_letters", "mode": "SPLIT", "separator": "|"},
            "emit": {
                "entity_class": "CASP",
                "activity_from": {"field": "$ITEM", "map": MICA_LETTER_MAP},
                "jurisdiction": "ES",
                "territorial_basis": "FREEDOM_TO_PROVIDE_SERVICES",
                "legal_effect": "ENTITLED_TO_PROVIDE",
                "entry_mechanism": "AUTHORISATION",
                "legal_basis": "MiCA art. 63 (autorizacion {home_member_state}, {authorisation_notification_date}) + MiCA art. 65 (comunicacion transfronteriza; inicio a recepcion o <=15 dias) + CNMV {cnmv_route_label}, services_from {cnmv_services_from}",
                "scope": "servicio MiCA concreto listado en ac_serviceCode; una asercion por servicio; ruta LP nunca se lee como DOMESTIC",
                "effective_from": {"derivation": "FIELD_DDMMYYYY", "field": "cnmv_services_from"},
                "effective_to": {"derivation": "FIELD_DDMMYYYY_OR_NULL", "field": "authorisation_end_date"},
            },
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "H12-B: autorizacion art.63 de origen + comunicacion art.65 observada en la lista CNMV (categoria LP + services_from) => entitlement territorial ES por libre prestacion. La fecha territorial es cnmv_services_from, nunca la fecha ESMA.",
        "known_limitations": ["solo servicios explicitamente listados; servicio no listado nunca se deriva"],
    },
    {
        "rule_id": "mica-branch-es-entitled",
        "required_source_contract": "ESMA_MICA_REGISTER",
        "match": {"source": "ESMA_MICA_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "EQ", "value": "BRANCH"},
            {"field": "mica_es_declared", "op": "EQ", "value": "TRUE"},
            {"field": "cnmv_services_from", "op": "NOT_NULL"},
        ]},
        "required_fields": ["legal_name", "lei", "service_codes_raw", "mica_service_letters", "authorisation_notification_date"],
        "coverage_preconditions": ["esma-mica-in-casp"],
        "emit_per": {
            "iterate": {"field": "mica_service_letters", "mode": "SPLIT", "separator": "|"},
            "emit": {
                "entity_class": "CASP",
                "activity_from": {"field": "$ITEM", "map": MICA_LETTER_MAP},
                "jurisdiction": "ES",
                "territorial_basis": "BRANCH",
                "legal_effect": "ENTITLED_TO_PROVIDE",
                "entry_mechanism": "AUTHORISATION",
                "legal_basis": "MiCA art. 63 (autorizacion {home_member_state}, {authorisation_notification_date}) + MiCA art. 59(7) establecimiento/sucursal + MiCA art. 65 (comunicacion) + CNMV {cnmv_route_label}, services_from {cnmv_services_from}",
                "scope": "servicio MiCA concreto listado en ac_serviceCode; una asercion por servicio; ruta sucursal nunca se colapsa a FPS",
                "effective_from": {"derivation": "FIELD_DDMMYYYY", "field": "cnmv_services_from"},
                "effective_to": {"derivation": "FIELD_DDMMYYYY_OR_NULL", "field": "authorisation_end_date"},
            },
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "H12-C: sucursal y LP son rutas territoriales distintas sobre el mismo entitlement de origen (art. 59(7) permite sucursal). BRANCH != FPS.",
        "known_limitations": ["la inscripcion mercantil de la sucursal no esta observada; el trigger es la categoria+fecha CNMV compuesta con ESMA"],
    },
    {
        "rule_id": "cnmv-limited-lp-route-unresolved",
        "required_source_contract": "CNMV_MICA_CASP_LIST",
        "match": {"source": "CNMV_PSC_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "EQ", "value": "LIMITED_LP"},
        ]},
        "emit_status_fact": {
            "reported_status": "TERRITORIAL_ROUTE_UNRESOLVED",
            "detail": "categoria CNMV 'LIMITED PSC EN REGIMEN DE LP' observada solo como epigrafe: sin fila real ni fuente primaria que defina el regimen (H12-E); prohibido inferir equivalencia con LP. 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "El label no es significado juridico: abstencion clasificada hasta fuente primaria.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
    {
        "rule_id": "cnmv-territorial-route-other-unresolved",
        "required_source_contract": "CNMV_MICA_CASP_LIST",
        "match": {"source": "CNMV_PSC_REGISTER", "conditions": [
            {"field": "cnmv_territorial_route", "op": "EQ", "value": "OTHER"},
        ]},
        "emit_status_fact": {
            "reported_status": "TERRITORIAL_ROUTE_UNRESOLVED",
            "detail": "categoria CNMV territorial no clasificada en las rutas congeladas D2 (LP/sucursal/domestica): conservada como evidencia; 0 asercion",
        },
        "failure_behavior": "FINDING_AND_NO_ASSERTION",
        "rationale": "Fail-closed ante categorias territoriales no contempladas en la matriz D2.",
        "required_fields": [], "coverage_preconditions": [], "known_limitations": [],
    },
]

spec = rs["ruleset"]
spec["ruleset_version"] = "FINREG_G1_DERIVATION_V3"
spec["gate"] = "G1-D"
spec["purpose"] = (
    "SourceAssertion[] -> EntitlementAssertion[] + reported_facts. G1-D: "
    "territorialidad — mecanismo de base (entry_mechanism) separado de la "
    "activacion territorial (territorial_basis); positivas solo para PSD2 "
    "FPS, PSD2 branch, MiCA LP art.63 y MiCA branch art.63; agente = ruta "
    "delegada; country-code solo nunca es trigger; LIMITED_LP abstencion; "
    "fechas territoriales ausentes/divergentes = findings. Sin regla "
    "art.60 cross-border (NON_REPRESENTABLE_IN_CURRENT_CORPUS)."
)
spec["frozen_inputs"] = {
    "claims_ledger": "fixtures/g1/claim-ledger-g1-d-001.json",
    "corpus": "fixtures/g1/corpus-g1-d.json",
    "source_manifest": "fixtures/g1/sources/manifest-g1-d-run.json",
    "contracts_dir": "fixtures/contracts",
    "territorial_corpus": "fixtures/g1/sources/extracted/g1-d-territorial-corpus.json",
    "legal_freeze_manifest": "fixtures/g1/sources/manifest-g1-d1.json",
}
spec["policy"]["mica_territorial"] = (
    "la asercion territorial MiCA es composicion ESMA (entitlement home + "
    "servicios + paises declarados) + CNMV (categoria LP/sucursal + "
    "services_from). ac_serviceCode_cou solo nunca es trigger territorial."
)
spec["policy"]["territorial_routes"] = (
    "entry_mechanism nunca muta por la activacion territorial: passport = "
    "comunicacion procedimental, no mecanismo. BRANCH y LP/FPS son rutas "
    "distintas que coexisten (COMPATIBLE_MULTI_ROUTE), nunca conflicto."
)
spec["policy"]["psd2_branch_evidence"] = (
    "sucursal PSD2 ES exige conjuntamente: fila PSD_BR + join exacto al "
    "parent (entity_type, entity_code) + parent ENT_AUT ACTIVE + "
    "DER_CHI_ENT_AUT Active + inscripcion BdE vigente + servicios exactos. "
    "La evidencia del parent y BdE entra como SourceAssertion corroborante."
)
spec["policy"]["territorial_dates"] = (
    "fecha territorial = la del trigger territorial (cnmv_services_from / "
    "bde fecha_alta); sin fecha de trigger publicada se usa EVIDENCE_AS_OF "
    "(fecha mas temprana en que la evidencia atestigua el hecho); la fecha "
    "de autorizacion home nunca es fallback territorial"
)
spec["failure_taxonomy"] = spec["failure_taxonomy"] + [
    "TERRITORIAL_ROUTE_UNRESOLVED",
    "COMPATIBLE_MULTI_ROUTE",
]
spec["rules"] = rules + new_rules

from finreg_es.canonical import canonical_json

OUT.write_text(canonical_json({"ruleset": spec}) + "\n", encoding="utf-8", newline="\n")
print(f"rules: {len(spec['rules'])} -> {OUT}")
