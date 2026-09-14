"""Construye los artefactos de entrada de G1-E (E4) de forma determinista:

- ``fixtures/g1/claim-ledger-g1-e-001.json``: claims de las 10 anclas
  del corpus adversarial E3 (-003), extraidos de los snapshots
  congelados reales (EBA zip, xlsx BdE servicios-pago y
  con-establecimiento). Nada se escribe a mano: raw_value/
  normalized_value se derivan del registro real.
- ``fixtures/g1/corpus-g1-e-001.json``: corpus operativo E3-* con sus
  source_records.
- ``fixtures/g1/sources/manifest-g1-e-run.json``: manifest del run
  (snapshots EBA + BdE servicios-pago + con-establecimiento).

Reglas de construccion (auditables):

- Cada claim lleva la traza FIELD_TRACES_G1E (regla + referencia raw),
  igual que los ledgers anteriores.
- ``actividades_codes`` materializa la hoja ACTIVIDADES (sheet2) del
  workbook BdE: el vector de capacidades por CODIGO BE. El raw_value es
  la lista de codigos observada; el record_key sigue siendo el CODIGO BE.
- El corpus E3-006 (Fintonic) agrupa dos personas juridicas sucesoras
  (6892 PI escindida -> 6935 AISP) bajo un unico corpus_id: la cuestion
  preregistrada es precisamente la continuidad tras la transformacion.
"""
import hashlib
import json
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finreg_es.canonical import canonical_json  # noqa: E402
from finreg_es.provenance import (  # noqa: E402
    FIELD_TRACES,
    SOURCE_PROVENANCE,
    _normalized_from_raw,
    _raw_value,
    _record_sha256,
)

# Trazas G1-E: campos nuevos del delta negativo. Viven en el builder
# (no en FIELD_TRACES) porque claim_ledger() regenera los ledgers
# historicos solo con la tabla original — ampliarla cambiaria la
# salida congelada.
FIELD_TRACES_G1E: dict[str, dict[str, tuple[str, str | None]]] = {
    "EBA_PSD2_REGISTER": {
        **FIELD_TRACES["EBA_PSD2_REGISTER"],
        "ent_cod_par_ent": ("PROPERTY", "ENT_COD_PAR_ENT"),
        "ent_typ_par_ent": ("PROPERTY", "ENT_TYP_PAR_ENT"),
        "der_chi_ent_aut": ("PROPERTY", "DER_CHI_ENT_AUT"),
    },
    "BDE_REGISTRO_SERVICIOS_PAGO": {
        "legal_name": ("COPY", "NOMBRE"),
        "codigo_be": ("COPY", "CÓDIGO BE"),
        "tipo_entidad": ("COPY", "TIPO ENTIDAD"),
        "codigo_tipo_entidad": ("COPY", "CODIGO TIPO ENTIDAD"),
        "nombre_matriz": ("COPY", "NOMBRE ENTIDAD MATRIZ"),
        "fecha_alta": ("COPY", "FECHA ALTA"),
        "fecha_baja": ("EMPTY_TO_NULL", "FECHA BAJA"),
        "motivo_baja": ("EMPTY_TO_NULL", "MOTIVO BAJA"),
        "sucesoras": ("EMPTY_TO_NULL", "SUCESORAS"),
        "pais_origen": ("COPY", "PAÍS DE ORIGEN (ISO2)"),
        # Sheet ACTIVIDADES del workbook: vector de capacidades por
        # codigo BE. La referencia raw es la propia lista materializada
        # desde la hoja (record_key = CODIGO BE).
        "actividades_codes": ("COPY", "ACTIVIDADES"),
    },
    "BDE_REGISTRO_CON_ESTABLECIMIENTO": {
        "legal_name": ("COPY", "NOMBRE"),
        "codigo_be": ("COPY", "CÓDIGO BE"),
        "tipo_entidad": ("COPY", "TIPO ENTIDAD"),
        "codigo_tipo_entidad": ("COPY", "CODIGO TIPO ENTIDAD"),
        "nombre_matriz": ("COPY", "NOMBRE ENTIDAD MATRIZ"),
        "fecha_alta": ("COPY", "FECHA ALTA"),
        "fecha_baja": ("EMPTY_TO_NULL", "FECHA BAJA"),
        "motivo_baja": ("EMPTY_TO_NULL", "MOTIVO BAJA"),
        "sucesoras": ("EMPTY_TO_NULL", "SUCESORAS"),
        "pais_origen": ("COPY", "PAÍS DE ORIGEN (ISO2)"),
        "actividades_codes": ("COPY", "ACTIVIDADES"),
    },
}

EBA_ZIP = ROOT / "fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip"
BDE_PAGO = ROOT / "fixtures/g1/sources/raw/bde-registro-servicios-pago.xlsx"
BDE_CE = ROOT / "fixtures/g1/sources/raw/bde-registro-con-establecimiento.xlsx"

OUT_LEDGER = ROOT / "fixtures/g1/claim-ledger-g1-e-001.json"
OUT_CORPUS = ROOT / "fixtures/g1/corpus-g1-e-001.json"
OUT_MANIFEST = ROOT / "fixtures/g1/sources/manifest-g1-e-run.json"

EXTRACTOR_VERSION = "G1E_NEGATIVE_EXTRACT_V1"
EXTRACTED_AT = "2026-09-14T00:00:00Z"
PARSER_BY_SOURCE = {
    "EBA_PSD2_REGISTER": "EbaPsd2Adapter",
    "BDE_REGISTRO_SERVICIOS_PAGO": "BdeServiciosPagoAdapter",
    "BDE_REGISTRO_CON_ESTABLECIMIENTO": "BdeConEstablecimientoAdapter",
}
SNAPSHOT_META = {
    "raw/h4-eba-psd2-20260913.zip": {
        "retrieved_at": "2026-09-13",
        "source_as_of": "2026-09-13T08:00:04Z",
        "source_date_reliability": "TRUSTED",
    },
    "raw/bde-registro-servicios-pago.xlsx": {
        "retrieved_at": "2026-09-14",
        "source_as_of": "2026-09-10",
        "source_date_reliability": "TRUSTED",
    },
    "raw/bde-registro-con-establecimiento.xlsx": {
        "retrieved_at": "2026-09-14",
        "source_as_of": "2026-09-10",
        "source_date_reliability": "TRUSTED",
    },
}
SEMANTIC_DERIVATION = {
    "status": "RAW_FACTS_ONLY",
    "reason": "NEGATIVE_EVIDENCE_G1E; la clasificacion negativa nunca muta el hecho reportado",
}

EBA_SNAPSHOT = "raw/h4-eba-psd2-20260913.zip"
BDE_PAGO_SNAPSHOT = "raw/bde-registro-servicios-pago.xlsx"
BDE_CE_SNAPSHOT = "raw/bde-registro-con-establecimiento.xlsx"

SHA_EBA = hashlib.sha256(EBA_ZIP.read_bytes()).hexdigest()
SHA_BDE_PAGO = hashlib.sha256(BDE_PAGO.read_bytes()).hexdigest()
SHA_BDE_CE = hashlib.sha256(BDE_CE.read_bytes()).hexdigest()

_XLS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XLS_REL = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)


def _norm_header(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    ).strip()


def _xlsx_sheet_rows(path: Path, sheet_index: int) -> list[dict[str, str]]:
    """Filas de una hoja xlsx como dict col->texto (sin cabecera)."""
    with zipfile.ZipFile(path) as z:
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid = {r.get("Id"): r.get("Target") for r in rels}
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        order = [s.get(_XLS_REL) for s in wb.iter(_XLS_NS + "sheet")]
        target = "xl/" + rid[order[sheet_index]].lstrip("/")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sroot.iter(_XLS_NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(_XLS_NS + "t")))
        root = ET.fromstring(z.read(target))
    out: list[dict[str, str]] = []
    for row in root.iter(_XLS_NS + "row"):
        vals: dict[str, str] = {}
        for cell in row.iter(_XLS_NS + "c"):
            ref = cell.get("r")
            value = cell.find(_XLS_NS + "v")
            inline = cell.find(_XLS_NS + "is")
            if inline is not None:
                text = "".join(t.text or "" for t in inline.iter(_XLS_NS + "t"))
            elif value is not None:
                text = (
                    shared[int(value.text)]
                    if cell.get("t") == "s"
                    else value.text
                )
            else:
                continue
            col = "".join(ch for ch in ref if ch.isalpha())
            vals[col] = text
        if vals:
            out.append(vals)
    return out


def _load_bde(path: Path) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """(filas sheet1 por codigo BE, actividades sheet2 por codigo BE).

    Sheet1 se parsea por cabecera (nombres de columna, robusto a
    padding); sheet2 es posicional A..G (CODIGO BE / NOMBRE / TIPO /
    NORMATIVA / CODIGO ACTIVIDAD / ACTIVIDAD / FECHA ALTA ACTIVIDAD).
    """
    sheet1 = _xlsx_sheet_rows(path, 0)
    header: dict[str, str] | None = None
    entities: dict[str, dict] = {}
    for vals in sheet1:
        if header is None:
            normalized = {_norm_header(v): v for v in vals.values()}
            if "CODIGO BE" in normalized:
                header = vals
            continue
        record = {header[k]: v for k, v in vals.items() if k in header}
        code = next(
            (v for k, v in record.items() if _norm_header(k) == "CODIGO BE"),
            None,
        )
        if code:
            entities[code] = record
    activities: dict[str, list[str]] = {}
    sheet2 = _xlsx_sheet_rows(path, 1)
    seen_header = False
    for vals in sheet2:
        if not seen_header:
            if _norm_header(vals.get("A", "")) == "CODIGO BE":
                seen_header = True
            continue
        code, act = vals.get("A"), vals.get("E")
        if code and act:
            activities.setdefault(code, [])
            if act not in activities[code]:
                activities[code].append(act)
    return entities, activities


def _load_eba_records() -> dict[tuple[str, str], dict]:
    with zipfile.ZipFile(EBA_ZIP) as z:
        payload = json.loads(z.read("download-PSDMD-202609130800.json"))
    return {
        (r.get("EntityCode"), r.get("EntityType")): r for r in payload[1]
    }


def _claim(
    *,
    corpus_id: str,
    source: str,
    field: str,
    record_key: dict,
    raw_record: object,
    snapshot_file: str,
    snapshot_sha256: str,
    discriminator: str | None = None,
) -> dict:
    rule, ref = FIELD_TRACES_G1E[source][field]
    raw_value = _raw_value(raw_record, rule, ref)
    normalized = _normalized_from_raw(rule, raw_value)
    provenance = SOURCE_PROVENANCE[source]
    meta = SNAPSHOT_META[snapshot_file]
    parts = [corpus_id, source]
    if discriminator:
        parts.append(discriminator)
    parts.append(field)
    return {
        "claim_id": "|".join(parts),
        "corpus_id": corpus_id,
        "source": source,
        "register_id": provenance["register_id"],
        "authority": provenance["authority"],
        "field": field,
        "raw_value": raw_value,
        "normalized_value": normalized,
        "record_key": record_key,
        "snapshot_file": snapshot_file,
        "snapshot_sha256": snapshot_sha256,
        "raw_record_sha256": _record_sha256(raw_record),
        "retrieved_at": meta["retrieved_at"],
        "source_as_of": meta["source_as_of"],
        "source_date_reliability": meta["source_date_reliability"],
        "extracted_at": EXTRACTED_AT,
        "extractor_version": EXTRACTOR_VERSION,
        "parser": PARSER_BY_SOURCE[source],
        "rule": rule,
        "rule_version": EXTRACTOR_VERSION,
        "semantic_derivation": dict(SEMANTIC_DERIVATION),
        "assertion_candidate": "NOT_CREATED",
    }


_EBA_ROOT_FIELDS = (
    "legal_name",
    "commercial_name",
    "entity_code",
    "entity_type",
    "national_reference_code",
    "country",
    "ent_aut_raw",
    "ent_aut_raw_type",
    "services_raw",
    "service_codes",
    "entity_version",
)
_EBA_CHILD_FIELDS = (
    "legal_name",
    "entity_code",
    "entity_type",
    "national_reference_code",
    "country",
    "ent_typ_par_ent",
    "ent_cod_par_ent",
    "der_chi_ent_aut",
    "services_raw",
    "service_codes",
    "entity_version",
)
_BDE_FIELDS = (
    "legal_name",
    "codigo_be",
    "tipo_entidad",
    "codigo_tipo_entidad",
    "nombre_matriz",
    "fecha_alta",
    "fecha_baja",
    "motivo_baja",
    "sucesoras",
    "pais_origen",
    "actividades_codes",
)


def _eba_claims(corpus_id: str, rec: dict) -> list[dict]:
    record_key = {
        "EntityCode": rec["EntityCode"],
        "EntityType": rec["EntityType"],
        "EntityVersion": rec["__EBA_EntityVersion"],
    }
    discriminator = f"{rec['EntityType']}:{rec['EntityCode']}"
    fields = (
        _EBA_CHILD_FIELDS
        if rec["EntityType"] in {"PSD_BR", "PSD_AG"}
        else _EBA_ROOT_FIELDS
    )
    return [
        _claim(
            corpus_id=corpus_id,
            source="EBA_PSD2_REGISTER",
            field=field,
            record_key=record_key,
            raw_record=rec,
            snapshot_file=EBA_SNAPSHOT,
            snapshot_sha256=SHA_EBA,
            discriminator=discriminator,
        )
        for field in fields
    ]


def _bde_claims(
    corpus_id: str,
    source: str,
    row: dict,
    activities: list[str],
    code: str,
    snapshot_file: str,
    sha: str,
) -> list[dict]:
    record_key = {"field": "CÓDIGO BE", "value": code}
    claims = []
    for field in _BDE_FIELDS:
        raw_record: object = row
        if field == "actividades_codes":
            raw_record = {"ACTIVIDADES": activities}
        claims.append(
            _claim(
                corpus_id=corpus_id,
                source=source,
                field=field,
                record_key=record_key,
                raw_record=raw_record,
                snapshot_file=snapshot_file,
                snapshot_sha256=sha,
                discriminator=code,
            )
        )
    return claims


# Tabla de anclas E3 (-003): corpus_id -> registros fuente.
# Cada EBA tuple = (EntityType, EntityCode); cada BDE tuple =
# (source, codigo_be, workbook, sha).
ENTITIES: list[dict] = [
    {
        "corpus_id": "E3-001",
        "legal_name": "DENIZEN GLOBAL FINANCIAL, S.A.",
        "inclusion_reason": (
            "E3-01: retirada dual-source el mismo dia (BdE renuncia "
            "23/07/2020 + EBA ENT_AUT par); raiz unica"
        ),
        "eba": [("PSD_PI", "ES_BE!6822")],
        "bde_pago": ["6822"],
    },
    {
        "corpus_id": "E3-002",
        "legal_name": "MMG Corporation s.r.o.",
        "inclusion_reason": (
            "E3-02: ENT_AUT len=3 (retirada + reautorizacion); probes "
            "bitemporales raiz vs ruta territorial"
        ),
        "eba": [("PSD_PI", "CZ_CNB!29142024")],
    },
    {
        "corpus_id": "E3-003",
        "legal_name": "BANKINTER CONSUMER FINANCE, E.F.C., S.A.",
        "inclusion_reason": (
            "E3-03: baja BdE por transformacion 22/02/2019 distinta de "
            "la retirada EBA 01/07/2026"
        ),
        "eba": [("PSD_PI", "ES_BE!8832")],
        "bde_pago": ["8832"],
    },
    {
        "corpus_id": "E3-004",
        "legal_name": "CERRO CATEDRAL ENTIDAD DE PAGO, S.A.",
        "inclusion_reason": (
            "E3-04: EP domestica en alta con ACTIVIDADES={6} — "
            "ENUMERATED_ABSENCE atomica + positivo en la misma via"
        ),
        "bde_pago": ["6844"],
    },
    {
        "corpus_id": "E3-005",
        "legal_name": "Mollie B.V.",
        "inclusion_reason": (
            "E3-05: PI retirada 03/02/2025 + EMI autorizada el mismo "
            "dia — root withdrawal no es entity-global"
        ),
        "eba": [("PSD_PI", "NL_DNB!F0038"), ("PSD_EMI", "NL_DNB!F0038")],
    },
    {
        "corpus_id": "E3-006",
        "legal_name": "FINTONIC (6892 -> 6935)",
        "inclusion_reason": (
            "E3-06: PI 6892 escindida 29/01/2024 -> sucesora 6935 "
            "(BdE baja transformacion 26/11/2024 + EBA AISP 03/12/2024); "
            "continuidad PIS no demostrada"
        ),
        "eba": [("PSD_PI", "ES_BE!6892"), ("PSD_AISP", "ES_BE!6935")],
        "bde_pago": ["6935"],
    },
    {
        "corpus_id": "E3-007",
        "legal_name": "SIBS Pagamentos",
        "inclusion_reason": (
            "E3-07: LPS PI ausente de los workbooks BdE — ausencia no "
            "interpretable como negativo BdE"
        ),
        "eba": [("PSD_PI", "PSD_PI!PT_BP!8703")],
    },
    {
        "corpus_id": "E3-008",
        "legal_name": "Wise Europe SA",
        "inclusion_reason": (
            "E3-08: PIS ausente en los tres vectores (parent FPS, "
            "PSD_BR, sucursal BdE 6946) — todas las vias cerradas"
        ),
        "eba": [
            ("PSD_PI", "BE_NBB!0713629988"),
            ("PSD_BR", "BE_NBB!0713629988!ES"),
        ],
        "bde_ce": ["6946"],
    },
    {
        "corpus_id": "E3-009",
        "legal_name": "Eupago - Instituicao de Pagamento Lda",
        "inclusion_reason": (
            "E3-09: PIS ausente en Services{ES} del parent (FPS) pero "
            "presente en PSD_BR + BdE 6938 (BRANCH) — contraste E3-008"
        ),
        "eba": [
            ("PSD_PI", "PSD_PI!PT_BP!8709"),
            ("PSD_BR", "PSD_PI!PT_BP!8709"),
        ],
        "bde_ce": ["6938"],
    },
    {
        "corpus_id": "E3-010",
        "legal_name": "THUNES FINANCIAL SERVICES",
        "inclusion_reason": (
            "E3-01b: retirada 27/08/2026 con Services{ES} aun "
            "declarados — codigos tras retirada no son entitlement"
        ),
        "eba": [("PSD_PI", "FR_ACPR!384558")],
    },
]


def main() -> None:
    eba = _load_eba_records()
    bde_pago_rows, bde_pago_acts = _load_bde(BDE_PAGO)
    bde_ce_rows, bde_ce_acts = _load_bde(BDE_CE)

    claims: list[dict] = []
    corpus_entities: list[dict] = []
    for entity in ENTITIES:
        cid = entity["corpus_id"]
        source_records: list[dict] = []
        for entity_type, code in entity.get("eba", []):
            rec = eba[(code, entity_type)]
            claims += _eba_claims(cid, rec)
            source_records.append(
                {
                    "source": "EBA_PSD2_REGISTER",
                    "snapshot_file": EBA_SNAPSHOT,
                    "record_key": {
                        "EntityCode": code,
                        "EntityType": entity_type,
                        "EntityVersion": rec["__EBA_EntityVersion"],
                    },
                }
            )
        for code in entity.get("bde_pago", []):
            row = bde_pago_rows[code]
            claims += _bde_claims(
                cid,
                "BDE_REGISTRO_SERVICIOS_PAGO",
                row,
                bde_pago_acts.get(code, []),
                code,
                BDE_PAGO_SNAPSHOT,
                SHA_BDE_PAGO,
            )
            source_records.append(
                {
                    "source": "BDE_REGISTRO_SERVICIOS_PAGO",
                    "snapshot_file": BDE_PAGO_SNAPSHOT,
                    "record_key": {"field": "CÓDIGO BE", "value": code},
                }
            )
        for code in entity.get("bde_ce", []):
            row = bde_ce_rows[code]
            claims += _bde_claims(
                cid,
                "BDE_REGISTRO_CON_ESTABLECIMIENTO",
                row,
                bde_ce_acts.get(code, []),
                code,
                BDE_CE_SNAPSHOT,
                SHA_BDE_CE,
            )
            source_records.append(
                {
                    "source": "BDE_REGISTRO_CON_ESTABLECIMIENTO",
                    "snapshot_file": BDE_CE_SNAPSHOT,
                    "record_key": {"field": "CÓDIGO BE", "value": code},
                }
            )
        corpus_entities.append(
            {
                "corpus_id": cid,
                "legal_name": entity["legal_name"],
                "source_records": source_records,
                "inclusion_reason": entity["inclusion_reason"],
            }
        )

    ledger = {
        "ledger": {
            "ledger_id": "claim-ledger-g1-e-001",
            "ledger_version": "FINREG_G06_CLAIM_PROVENANCE_V1",
            "run_id": "g1-e-negative-corpus-claims-2026-09-14",
            "claims_total": len(claims),
            "untraced_fields": [],
            "run_result_sha": hashlib.sha256(
                json.dumps(claims, ensure_ascii=False, sort_keys=True).encode(
                    "utf-8"
                )
            ).hexdigest(),
        },
        "claims": claims,
    }
    corpus = {
        "corpus_id": "corpus-g1-e-001",
        "as_of": "2026-09-14",
        "entity_count": len(corpus_entities),
        "selection_rule": (
            "Corpus adversarial G1-E preregistrado (E3, extracto -003): "
            "10 entidades reales con evidencia negativa heterogenea"
        ),
        "entities": corpus_entities,
    }
    manifest = {
        "capture_id": (
            "g1-e-run-2026-09-14 (eba psd2 h4 + bde servicios-pago + "
            "bde con-establecimiento)"
        ),
        "retrieved_at": "2026-09-14",
        "hash_algorithm": "SHA-256",
        "encoding": "binary-preserving for ZIP and XLSX snapshots",
        "snapshots": [
            {
                "snapshot_file": EBA_SNAPSHOT,
                "sha256": SHA_EBA,
                "bytes": EBA_ZIP.stat().st_size,
                "hypothesis": "H4",
                "source_url": "https://webgate.ec.europa.eu/psd2register/",
                "source_as_of": "2026-09-13T08:00:04Z",
            },
            {
                "snapshot_file": BDE_PAGO_SNAPSHOT,
                "sha256": SHA_BDE_PAGO,
                "bytes": BDE_PAGO.stat().st_size,
                "hypothesis": "G1-B1",
                "source_url": "https://www.bde.es/f/webbe/SGE/regis/ficheros/es/Registro_ServicioPagos.xlsx",
                "source_as_of": "2026-09-10",
            },
            {
                "snapshot_file": BDE_CE_SNAPSHOT,
                "sha256": SHA_BDE_CE,
                "bytes": BDE_CE.stat().st_size,
                "hypothesis": "G1-E",
                "source_url": "https://www.bde.es/f/webbe/SGE/regis/ficheros/es/Registro_ConEstablecimiento.xlsx",
                "source_as_of": "2026-09-10",
            },
        ],
    }

    for path, doc in (
        (OUT_LEDGER, ledger),
        (OUT_CORPUS, corpus),
        (OUT_MANIFEST, manifest),
    ):
        path.write_bytes(
            (json.dumps(doc, ensure_ascii=False, indent=1) + "\n").encode(
                "utf-8"
            )
        )
    print(
        f"ledger: {len(claims)} claims | corpus: "
        f"{len(corpus_entities)} entidades"
    )


if __name__ == "__main__":
    main()
