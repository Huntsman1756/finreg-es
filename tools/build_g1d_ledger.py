"""Construye los artefactos de entrada de G1-D de forma determinista:

- ``fixtures/g1/claim-ledger-g1-d-001.json``: claims G1-C verbatim +
  claims territoriales del corpus D3, extraidos de los snapshots
  congelados reales (EBA zip, ESMA csv, extract CNMV, xlsx BdE).
- ``fixtures/g1/corpus-g1-d.json``: corpus operativo = corpus G0.5 +
  entidades G1D-* con sus source_records.
- ``fixtures/g1/sources/manifest-g1-d-run.json``: manifest fusionado
  (g1-c-run + bde servicios de pago + esma/cnmv g1-c1 + textos D1).

Reglas de construccion (auditables):

- Cada claim se emite con la traza FIELD_TRACES (regla + referencia
  raw), igual que el ledger G1-C: raw_value/normalized_value se
  derivan del registro real, nunca se escriben a mano.
- El record_key de cada claim discrimina el registro fisico
  (EntityCode+EntityType+EntityVersion en EBA; ae_lei en ESMA; entity
  en CNMV; codigo BE en BdE), lo que permite varios registros EBA por
  entidad (parent + sucursal ES).
- G1D-002 incluye el registro EBA del parent (PSD_PI PT_BP!8709):
  la regla de sucursal exige join exacto a parent ENT_AUT ACTIVE y el
  propio registro de la sucursal lo referencia via ENT_COD_PAR_ENT.
  Es evidencia corroborante exigida por D4, no un caso nuevo.
- G1D-006 es la entidad sintetica marcada del corpus D3 (epigrafe
  LIMITED_LP sin filas reales): el claim apunta a la categoria
  observada en el extract, marcada synthetic.
"""
import csv
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

# Trazas G1-D: campos/fuentes nuevos del delta territorial. Viven en el
# builder (no en FIELD_TRACES) porque claim_ledger() regenera el ledger
# G0.6 historico solo con la tabla original — ampliarla cambiaria la
# salida congelada.
FIELD_TRACES_G1D: dict[str, dict[str, tuple[str, str | None]]] = {
    "EBA_PSD2_REGISTER": {
        **FIELD_TRACES["EBA_PSD2_REGISTER"],
        "ent_cod_par_ent": ("PROPERTY", "ENT_COD_PAR_ENT"),
        "ent_typ_par_ent": ("PROPERTY", "ENT_TYP_PAR_ENT"),
        "der_chi_ent_aut": ("PROPERTY", "DER_CHI_ENT_AUT"),
    },
    "ESMA_MICA_REGISTER": FIELD_TRACES["ESMA_MICA_REGISTER"],
    "CNMV_PSC_REGISTER": {
        "legal_name": ("COPY", "entity"),
        "cnmv_category": ("COPY", "cnmv_category"),
        "services_from": ("COPY", "services_from"),
        "mica_route_label": ("COPY", "mica_route"),
    },
    "BDE_REGISTRO_SERVICIOS_PAGO": {
        "legal_name": ("COPY", "NOMBRE"),
        "codigo_be": ("COPY", "CÓDIGO BE"),
        "tipo_entidad": ("COPY", "TIPO ENTIDAD"),
        "nombre_matriz": ("COPY", "NOMBRE ENTIDAD MATRIZ"),
        "fecha_alta": ("COPY", "FECHA ALTA"),
        # La hoja expone FECHA BAJA (+ MOTIVO BAJA): vacia = vigente.
        "fecha_baja": ("EMPTY_TO_NULL", "FECHA BAJA"),
        "pais_origen": ("COPY", "PAÍS DE ORIGEN (ISO2)"),
    },
    # G1-D-F01: mecanismo home MiCA probado por el NCA home. El
    # "registro" aqui es la ficha parseada del snapshot congelado —
    # los valores normalizados (mica_home_route, home_licences,
    # home_mechanism_remark) se derivan del HTML oficial en el parser
    # de abajo, nunca a mano.
    "BAFIN_UNTERNEHMENSDATENBANK": {
        "legal_name": ("COPY", "legal_name"),
        "bafin_id": ("COPY", "bafin_id"),
        "home_entity_class_de": ("COPY", "gattung"),
        "mica_home_route": ("COPY", "mica_home_route"),
        "home_permission_date": ("COPY", "home_permission_date"),
        "home_permission_services": ("COPY", "home_permission_services"),
        "home_permission_raw": ("COPY", "home_permission_raw"),
    },
    "FINANSTILSYNET_REGISTRY": {
        "legal_name": ("COPY", "legal_name"),
        "finanstilsynet_id": ("COPY", "finanstilsynet_id"),
        "home_licences": ("COPY", "home_licences"),
        "home_mechanism_remark": ("COPY", "home_mechanism_remark"),
        "home_mechanism_remark_raw": ("COPY", "home_mechanism_remark_raw"),
    },
}

G1C_LEDGER = ROOT / "fixtures/g1/claim-ledger-g1-c-001.json"
G1D_CORPUS_DOC = ROOT / "fixtures/g1/sources/extracted/g1-d-territorial-corpus.json"
G05_CORPUS = ROOT / "fixtures/g0.5/corpus/entities.json"
MANIFEST_G1C_RUN = ROOT / "fixtures/g1/sources/manifest-g1-c-run.json"
MANIFEST_G1_B1 = ROOT / "fixtures/g1/sources/manifest-g1-b1.json"
MANIFEST_G1_C1 = ROOT / "fixtures/g1/sources/manifest-g1-c1.json"
MANIFEST_G1_D1 = ROOT / "fixtures/g1/sources/manifest-g1-d1.json"

EBA_ZIP = ROOT / "fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip"
ESMA_CSV = ROOT / "fixtures/g1/sources/raw/esma-mica-casps.csv"
CNMV_EXTRACT = ROOT / "fixtures/g1/sources/extracted/cnmv-psc-extract.json"
BDE_XLSX = ROOT / "fixtures/g1/sources/raw/bde-registro-servicios-pago.xlsx"
BAFIN_360T = ROOT / "fixtures/g1/sources/raw/bafin-unternehmensdatenbank-360t-118252.html"
BAFIN_IG = ROOT / "fixtures/g1/sources/raw/bafin-unternehmensdatenbank-ig-europe-148759.html"
FT_IG = ROOT / "fixtures/g1/sources/raw/finanstilsynet-vreg-ig-europe-199254.html"
FT_360T = ROOT / "fixtures/g1/sources/raw/finanstilsynet-vreg-360t-114184.html"

OUT_LEDGER = ROOT / "fixtures/g1/claim-ledger-g1-d-001.json"
OUT_CORPUS = ROOT / "fixtures/g1/corpus-g1-d.json"
OUT_MANIFEST = ROOT / "fixtures/g1/sources/manifest-g1-d-run.json"
# Sucesor G1-D-F01 (-002): misma cadena + evidencia de mecanismo home.
OUT_LEDGER_V2 = ROOT / "fixtures/g1/claim-ledger-g1-d-002.json"
OUT_CORPUS_V2 = ROOT / "fixtures/g1/corpus-g1-d-002.json"
OUT_MANIFEST_V2 = ROOT / "fixtures/g1/sources/manifest-g1-d-run-002.json"
MANIFEST_G1_D2 = ROOT / "fixtures/g1/sources/manifest-g1-d2.json"

EXTRACTOR_VERSION = "G1D_TERRITORIAL_EXTRACT_V1"
EXTRACTED_AT = "2026-09-14T00:00:00Z"
PARSER_BY_SOURCE = {
    "EBA_PSD2_REGISTER": "EbaPsd2Adapter",
    "ESMA_MICA_REGISTER": "EsmaCaspsAdapter",
    "CNMV_PSC_REGISTER": "CnmvPscExtract",
    "BDE_REGISTRO_SERVICIOS_PAGO": "BdeServiciosPagoAdapter",
    "BAFIN_UNTERNEHMENSDATENBANK": "BafinUdbAdapter",
    "FINANSTILSYNET_REGISTRY": "FinanstilsynetVregAdapter",
}
# Procedencia temporal por snapshot (retrieved_at / source_as_of del
# manifest de origen; source_as_of ausente = UNAVAILABLE por diseno).
SNAPSHOT_META = {
    "raw/h4-eba-psd2-20260913.zip": {
        "retrieved_at": "2026-09-13",
        "source_as_of": "2026-09-13T08:00:04Z",
        "source_date_reliability": "TRUSTED",
    },
    "raw/esma-mica-casps.csv": {
        "retrieved_at": "2026-09-14",
        "source_as_of": None,
        "source_date_reliability": "UNAVAILABLE",
    },
    "extracted/cnmv-psc-extract.json": {
        "retrieved_at": "2026-09-14",
        "source_as_of": "2026-09-14",
        "source_date_reliability": "TRUSTED",
    },
    "raw/bde-registro-servicios-pago.xlsx": {
        "retrieved_at": "2026-09-14",
        "source_as_of": "2026-09-10",
        "source_date_reliability": "TRUSTED",
    },
    "raw/bafin-unternehmensdatenbank-360t-118252.html": {
        "retrieved_at": "2026-09-14",
        "source_as_of": None,
        "source_date_reliability": "UNAVAILABLE",
    },
    "raw/bafin-unternehmensdatenbank-ig-europe-148759.html": {
        "retrieved_at": "2026-09-14",
        "source_as_of": None,
        "source_date_reliability": "UNAVAILABLE",
    },
    "raw/finanstilsynet-vreg-ig-europe-199254.html": {
        "retrieved_at": "2026-09-14",
        "source_as_of": None,
        "source_date_reliability": "UNAVAILABLE",
    },
    "raw/finanstilsynet-vreg-360t-114184.html": {
        "retrieved_at": "2026-09-14",
        "source_as_of": None,
        "source_date_reliability": "UNAVAILABLE",
    },
}
SEMANTIC_DERIVATION = {
    "status": "RAW_FACTS_ONLY",
    "reason": "TERRITORIAL_ROUTE_EVIDENCE_G1D; la ruta territorial nunca muta el mecanismo de base",
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _norm_header(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    ).strip()


def _load_eba_records() -> dict[tuple[str, str], dict]:
    with zipfile.ZipFile(EBA_ZIP) as z:
        payload = json.loads(z.read("download-PSDMD-202609130800.json"))
    records = payload[1]
    out: dict[tuple[str, str], dict] = {}
    for rec in records:
        out[(rec.get("EntityCode"), rec.get("EntityType"))] = rec
    return out


def _load_esma_rows() -> dict[str, dict]:
    with ESMA_CSV.open(encoding="utf-8-sig", newline="") as f:
        rows = {
            r["ae_lei"]: {k: v for k, v in r.items() if k}
            for r in csv.DictReader(f)
            if r.get("ae_lei")
        }
    return rows


def _load_cnmv_rows() -> tuple[dict[str, dict], dict]:
    doc = json.loads(CNMV_EXTRACT.read_text(encoding="utf-8"))
    rows = {r["entity"]: r for r in doc["rows"]}
    return rows, doc


def _load_bde_rows() -> dict[str, dict]:
    """Filas del xlsx BdE de servicios de pago, clave = codigo BE."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(BDE_XLSX) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sroot.iter(ns + "si"):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    header: dict[str, str] | None = None
    out: dict[str, dict] = {}
    for row in root.iter(ns + "row"):
        vals: dict[str, str] = {}
        for cell in row.iter(ns + "c"):
            ref = cell.get("r")
            value = cell.find(ns + "v")
            inline = cell.find(ns + "is")
            if inline is not None:
                text = "".join(t.text or "" for t in inline.iter(ns + "t"))
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
            out[code] = record
    return out


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
    rule, ref = FIELD_TRACES_G1D[source][field]
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


_EBA_PI_FIELDS = (
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
    "entity_version",
)
_ESMA_FIELDS = (
    "legal_name",
    "lei",
    "lei_valid",
    "lei_diagnostic",
    "home_member_state",
    "competent_authority",
    "commercial_name",
    "service_codes_raw",
    "service_countries_raw",
    "authorisation_notification_date",
    "authorisation_end_date",
    "last_update",
)
_CNMV_FIELDS = (
    "legal_name",
    "cnmv_category",
    "services_from",
    "mica_route_label",
)
_BDE_FIELDS = (
    "legal_name",
    "codigo_be",
    "tipo_entidad",
    "nombre_matriz",
    "fecha_alta",
    "fecha_baja",
    "pais_origen",
)

EBA_SNAPSHOT = "raw/h4-eba-psd2-20260913.zip"
ESMA_SNAPSHOT = "raw/esma-mica-casps.csv"
CNMV_SNAPSHOT = "extracted/cnmv-psc-extract.json"
BDE_SNAPSHOT = "raw/bde-registro-servicios-pago.xlsx"


def _eba_claims(corpus_id: str, rec: dict, fields: tuple[str, ...]) -> list[dict]:
    record_key = {
        "EntityCode": rec["EntityCode"],
        "EntityType": rec["EntityType"],
        "EntityVersion": rec["__EBA_EntityVersion"],
    }
    discriminator = f"{rec['EntityType']}:{rec['EntityCode']}"
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


def _esma_claims(corpus_id: str, row: dict) -> list[dict]:
    return [
        _claim(
            corpus_id=corpus_id,
            source="ESMA_MICA_REGISTER",
            field=field,
            record_key={"field": "ae_lei", "value": row["ae_lei"]},
            raw_record=row,
            snapshot_file=ESMA_SNAPSHOT,
            snapshot_sha256=SHA_ESMA,
        )
        for field in _ESMA_FIELDS
    ]


def _cnmv_claims(corpus_id: str, row: dict, *, discriminator=None) -> list[dict]:
    return [
        _claim(
            corpus_id=corpus_id,
            source="CNMV_PSC_REGISTER",
            field=field,
            record_key={"field": "entity", "value": row["entity"]},
            raw_record=row,
            snapshot_file=CNMV_SNAPSHOT,
            snapshot_sha256=SHA_CNMV_EXTRACT,
            discriminator=discriminator,
        )
        for field in _CNMV_FIELDS
    ]


def _bde_claims(corpus_id: str, row: dict, code: str) -> list[dict]:
    record_key = {
        "field": "CÓDIGO BE",
        "value": code,
    }
    return [
        _claim(
            corpus_id=corpus_id,
            source="BDE_REGISTRO_SERVICIOS_PAGO",
            field=field,
            record_key=record_key,
            raw_record=row,
            snapshot_file=BDE_SNAPSHOT,
            snapshot_sha256=SHA_BDE,
            discriminator=code,
        )
        for field in _BDE_FIELDS
    ]


SHA_EBA = _sha256_file(EBA_ZIP)
SHA_ESMA = _sha256_file(ESMA_CSV)
SHA_CNMV_EXTRACT = _sha256_file(CNMV_EXTRACT)
SHA_BDE = _sha256_file(BDE_XLSX)
SHA_BAFIN_360T = _sha256_file(BAFIN_360T)
SHA_BAFIN_IG = _sha256_file(BAFIN_IG)
SHA_FT_IG = _sha256_file(FT_IG)
SHA_FT_360T = _sha256_file(FT_360T)


def _parse_bafin_udb(path: Path) -> dict:
    """Parsea la ficha BaFin Unternehmensdatenbank congelada.

    Extrae la Gattung y los permisos cripto con su cita legal. La base
    'Art. 59 Abs. 1a' corresponde a la autorizacion art. 63; 'Abs. 1b'
    a la via de entidad financiera del art. 60 (notificacion). El raw
    oficial muestra variantes tipograficas ('Abs. 1b', 'Abs .1b',
    'Abs.1b') — el parser las normaliza todas.
    """
    import re

    html = path.read_text(encoding="utf-8", errors="replace")
    gattung_m = re.search(r"Gattung:</dt>\s*<dd>([^<]+)", html)
    bafin_id_m = re.search(r"Bafin-ID:</dt>\s*<dd>([^&<]+)", html)
    bak_m = re.search(r"Bak Nr\.:</dt>\s*<dd>([^&<]+)", html)
    name_m = re.search(r"<h2>Unternehmen</h2>\s*<p>\s*<strong>([^<]+)", html)
    perms: list[dict[str, str]] = []
    for m in re.finditer(
        r"<td>([^<]*Kryptowerte[^<]*\(Art\.\s*59\s*Abs\.?\s*\.?\s*1([ab])"
        r"\s*i\.V\.m\.\s*Art\.\s*3\s*Abs\.\s*1\s*Nr\.\s*16\s*([a-j])"
        r"\s*MiCA-R\)[^<]*)</td>\s*<td>(\d{2}\.\d{2}\.\d{4})</td>",
        html,
    ):
        perms.append(
            {
                "text": m.group(1).strip(),
                "art59": "ART_59_1" + m.group(2).upper(),
                "service": m.group(3),
                "date": m.group(4),
            }
        )
    routes = {p["art59"] for p in perms}
    if len(routes) == 1:
        route = next(iter(routes))
    elif not routes:
        route = None
    else:
        route = "MIXED"
    dates = {p["date"] for p in perms}
    return {
        "legal_name": name_m.group(1).strip() if name_m else None,
        "bafin_id": bafin_id_m.group(1).strip() if bafin_id_m else None,
        "bak_nr": bak_m.group(1).strip() if bak_m else None,
        "gattung": (
            gattung_m.group(1).replace("&nbsp;", "").replace("\xa0", " ").strip()
            if gattung_m else None
        ),
        "mica_home_route": route,
        "home_permission_date": (
            next(iter(dates)) if len(dates) == 1 else None
        ),
        "home_permission_services": "|".join(sorted({p["service"] for p in perms}))
        or None,
        "home_permission_raw": " || ".join(p["text"] for p in perms) or None,
    }


def _parse_ft_vreg(path: Path) -> dict:
    """Parsea la ficha Finanstilsynet (React VregDetails embebido).

    El remark de la licencia CASP cita la base legal expresa cuando la
    NCA home la publica (p. ej. 'MiCA Article 60(3)')."""
    import re

    html = path.read_text(encoding="utf-8", errors="replace")
    name_m = re.search(r'"name":"([^"]+)"', html)
    ft_id_m = re.search(r'"finanstilsynetId":"([^"]+)"', html)
    entity_m = re.search(r'"entityId":(\d+)', html)
    licences = sorted(set(re.findall(r'"licenceCode":"([^"]+)"', html)))
    remark_m = re.search(r'"remarks":"([^"]*)"', html)
    remark = remark_m.group(1) if remark_m else None
    mechanism = None
    if remark and re.search(r"MiCA\s+Article\s+60\(3\)", remark):
        mechanism = "ART_60_3"
    return {
        "legal_name": name_m.group(1) if name_m else None,
        "finanstilsynet_id": ft_id_m.group(1) if ft_id_m else None,
        "entity_id": entity_m.group(1) if entity_m else None,
        "home_licences": "|".join(licences) or None,
        "home_mechanism_remark": mechanism,
        "home_mechanism_remark_raw": remark,
    }


_BAFIN_FIELDS = (
    "legal_name",
    "bafin_id",
    "home_entity_class_de",
    "mica_home_route",
    "home_permission_date",
    "home_permission_services",
    "home_permission_raw",
)
_FT_FIELDS = (
    "legal_name",
    "finanstilsynet_id",
    "home_licences",
    "home_mechanism_remark",
    "home_mechanism_remark_raw",
)


def _bafin_claims(corpus_id: str, rec: dict, snapshot: str, sha: str) -> list[dict]:
    return [
        _claim(
            corpus_id=corpus_id,
            source="BAFIN_UNTERNEHMENSDATENBANK",
            field=field,
            record_key={"field": "Bak Nr.", "value": rec["bak_nr"]},
            raw_record=rec,
            snapshot_file=snapshot,
            snapshot_sha256=sha,
            discriminator=rec["bak_nr"],
        )
        for field in _BAFIN_FIELDS
    ]


def _ft_claims(corpus_id: str, rec: dict, snapshot: str, sha: str) -> list[dict]:
    return [
        _claim(
            corpus_id=corpus_id,
            source="FINANSTILSYNET_REGISTRY",
            field=field,
            record_key={"field": "entityId", "value": rec["entity_id"]},
            raw_record=rec,
            snapshot_file=snapshot,
            snapshot_sha256=sha,
            discriminator=rec["entity_id"],
        )
        for field in _FT_FIELDS
    ]


def build_new_claims() -> list[dict]:
    """Claims territoriales G1-D sobre los snapshots reales congelados."""
    eba = _load_eba_records()
    esma = _load_esma_rows()
    cnmv_rows, cnmv_doc = _load_cnmv_rows()
    bde = _load_bde_rows()
    claims: list[dict] = []

    def eba_rec(code: str, etype: str) -> dict:
        rec = eba.get((code, etype))
        if rec is None:
            raise KeyError(f"registro EBA no encontrado: {code} {etype}")
        return rec

    # G1D-001 Fire Financial Services Limited — PI irlandesa, FPS->ES.
    claims += _eba_claims("G1D-001", eba_rec("IE_CBI!C58301", "PSD_PI"), _EBA_PI_FIELDS)

    # G1D-002 Eupago — sucursal ES + parent PI (join exacto D4) + BdE 6938.
    claims += _eba_claims("G1D-002", eba_rec("PSD_PI!PT_BP!8709", "PSD_BR"), _EBA_CHILD_FIELDS + ("services_raw", "service_codes"))
    claims += _eba_claims("G1D-002", eba_rec("PSD_PI!PT_BP!8709", "PSD_PI"), _EBA_PI_FIELDS)
    claims += _bde_claims("G1D-002", bde["6938"], "6938")

    # G1D-003 FMG Destinos — agente ES + parent PI francesa.
    claims += _eba_claims("G1D-003", eba_rec("PSD_PI!FR_ACPR!54167!758639", "PSD_AG"), _EBA_CHILD_FIELDS)
    claims += _eba_claims("G1D-003", eba_rec("FR_ACPR!54167", "PSD_PI"), _EBA_PI_FIELDS)

    # G1D-004 360 Treasury Systems AG — CNMV LP + ESMA.
    claims += _cnmv_claims("G1D-004", cnmv_rows["360 TREASURY SYSTEMS AG"])
    claims += _esma_claims("G1D-004", esma["529900P0204W9HA8JP36"])

    # G1D-005 IG Europe GmbH — CNMV sucursal + ESMA.
    claims += _cnmv_claims("G1D-005", cnmv_rows["IG EUROPE GMBH"])
    claims += _esma_claims("G1D-005", esma["213800HFC5G4V293BN91"])

    # G1D-006 LIMITED_LP sintetico: el epigrafe existe en el extract
    # pero no hay fila real. El claim documenta la categoria observada
    # (evidencia de categoria, no de entidad).
    epigraph = next(
        c for c in cnmv_doc["categories_observed"] if "LIMITED" in c
    )
    synthetic_row = {
        "entity": "SYNTHETIC_LIMITED_LP (categoria sin filas reales)",
        "cnmv_category": epigraph,
        "synthetic": True,
    }
    claims += [
        _claim(
            corpus_id="G1D-006",
            source="CNMV_PSC_REGISTER",
            field=field,
            record_key={
                "field": "category_epigraph",
                "value": epigraph,
            },
            raw_record=synthetic_row,
            snapshot_file=CNMV_SNAPSHOT,
            snapshot_sha256=SHA_CNMV_EXTRACT,
        )
        for field in ("legal_name", "cnmv_category")
    ]

    # G1D-007 Wise Europe SA — parent PI (LPS) + sucursal ES + BdE 6946.
    claims += _eba_claims("G1D-007", eba_rec("BE_NBB!0713629988", "PSD_PI"), _EBA_PI_FIELDS)
    claims += _eba_claims("G1D-007", eba_rec("BE_NBB!0713629988!ES", "PSD_BR"), _EBA_CHILD_FIELDS + ("services_raw", "service_codes"))
    claims += _bde_claims("G1D-007", bde["6946"], "6946")

    # G1D-008 Bitpanda GmbH — ESMA sola (cou=ES sin trigger CNMV).
    claims += _esma_claims("G1D-008", esma["5493007WZ7IFULIL8G21"])

    return claims


def build_corpus() -> dict:
    g05 = json.loads(G05_CORPUS.read_text(encoding="utf-8"))
    doc = json.loads(G1D_CORPUS_DOC.read_text(encoding="utf-8"))
    entities = list(g05["entities"])
    for e in doc["entities"]:
        records = [
            {
                "source": s["source"],
                "snapshot_file": s["snapshot_file"],
                "record_key": s["record_key"],
            }
            for s in e["source_records"]
        ]
        records += EXTRA_SOURCE_RECORDS.get(e["corpus_id"], [])
        entities.append(
            {
                "corpus_id": e["corpus_id"],
                "legal_name": e["entity"],
                "source_records": records,
                "inclusion_reason": e["notes"],
            }
        )
    return {
        "corpus_id": "corpus-g1-d",
        "as_of": "2026-09-14",
        "entity_count": len(entities),
        "selection_rule": (
            "corpus G0.5 congelado + entidades G1D-* del corpus "
            "territorial preregistrado D3 (g1-d-territorial-corpus.json); "
            "G1D-002 declara ademas el registro EBA del parent exigido "
            "por el join exacto de la regla de sucursal"
        ),
        "entities": entities,
    }


# Registro EBA del parent de Eupago: lo referencia ENT_COD_PAR_ENT de
# la sucursal declarada en D3; el join exacto de la regla de sucursal
# lo exige como evidencia corroborante (D4).
EXTRA_SOURCE_RECORDS = {
    "G1D-002": [
        {
            "source": "EBA_PSD2_REGISTER",
            "snapshot_file": EBA_SNAPSHOT,
            "record_key": {
                "EntityCode": "PSD_PI!PT_BP!8709",
                "EntityType": "PSD_PI",
            },
        }
    ]
}


def build_manifest() -> dict:
    merged: dict[str, dict] = {}
    for path in (MANIFEST_G1C_RUN, MANIFEST_G1_B1, MANIFEST_G1_C1, MANIFEST_G1_D1):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for snap in doc["snapshots"]:
            merged[snap["snapshot_file"]] = snap
    return {
        "capture_id": "g1-d-run-2026-09-14 (merge: g1-c-run + g1-b1 bde-psp + g1-c1 esma/cnmv + g1-d1 legal)",
        "retrieved_at": "2026-09-14",
        "hash_algorithm": "SHA-256",
        "encoding": "UTF-8 for text snapshots; binary-preserving for PDF, ZIP and XLSX snapshots",
        "snapshots": [merged[k] for k in sorted(merged)],
    }


def build_new_claims_v2() -> list[dict]:
    """Claims -002: los de -001 + mecanismo home MiCA (G1-D-F01).

    360T e IG Europe tienen su permiso cripto citado por BaFin como
    Art. 59 Abs. 1b MiCA-R — la via de entidad financiera del art. 60,
    no la autorizacion art. 63. La expectativa preregistrada D3
    (AUTHORISATION) quedo falsada por evidencia primaria.
    """
    claims = build_new_claims()
    claims += _bafin_claims(
        "G1D-004", _parse_bafin_udb(BAFIN_360T),
        "raw/bafin-unternehmensdatenbank-360t-118252.html", SHA_BAFIN_360T,
    )
    claims += _ft_claims(
        "G1D-004", _parse_ft_vreg(FT_360T),
        "raw/finanstilsynet-vreg-360t-114184.html", SHA_FT_360T,
    )
    claims += _bafin_claims(
        "G1D-005", _parse_bafin_udb(BAFIN_IG),
        "raw/bafin-unternehmensdatenbank-ig-europe-148759.html", SHA_BAFIN_IG,
    )
    claims += _ft_claims(
        "G1D-005", _parse_ft_vreg(FT_IG),
        "raw/finanstilsynet-vreg-ig-europe-199254.html", SHA_FT_IG,
    )
    return claims


# Registros de mecanismo home añadidos en la remediacion G1-D-F01.
EXTRA_SOURCE_RECORDS_V2 = {
    "G1D-004": [
        {
            "source": "BAFIN_UNTERNEHMENSDATENBANK",
            "snapshot_file": "raw/bafin-unternehmensdatenbank-360t-118252.html",
            "record_key": {"field": "Bak Nr.", "value": "118252"},
        },
        {
            "source": "FINANSTILSYNET_REGISTRY",
            "snapshot_file": "raw/finanstilsynet-vreg-360t-114184.html",
            "record_key": {"field": "entityId", "value": "114184"},
        },
    ],
    "G1D-005": [
        {
            "source": "BAFIN_UNTERNEHMENSDATENBANK",
            "snapshot_file": "raw/bafin-unternehmensdatenbank-ig-europe-148759.html",
            "record_key": {"field": "Bak Nr.", "value": "148759"},
        },
        {
            "source": "FINANSTILSYNET_REGISTRY",
            "snapshot_file": "raw/finanstilsynet-vreg-ig-europe-199254.html",
            "record_key": {"field": "entityId", "value": "199254"},
        },
    ],
}


def build_corpus_v2() -> dict:
    doc = build_corpus()
    doc["corpus_id"] = "corpus-g1-d-002"
    for entity in doc["entities"]:
        entity["source_records"] += EXTRA_SOURCE_RECORDS_V2.get(
            entity["corpus_id"], []
        )
    doc["selection_rule"] += (
        "; G1-D-F01: source_records de mecanismo home (BaFin/Finanstilsynet)"
        " para G1D-004/005"
    )
    return doc


def build_manifest_v2() -> dict:
    doc = build_manifest()
    extra = json.loads(MANIFEST_G1_D2.read_text(encoding="utf-8"))
    merged = {s["snapshot_file"]: s for s in doc["snapshots"]}
    for snap in extra["snapshots"]:
        merged[snap["snapshot_file"]] = snap
    doc["capture_id"] += " + g1-d2 home-mechanism (G1-D-F01)"
    doc["snapshots"] = [merged[k] for k in sorted(merged)]
    return doc


def build_ledger() -> dict:
    g1c = json.loads(G1C_LEDGER.read_text(encoding="utf-8"))
    claims = list(g1c["claims"])
    claims += build_new_claims()
    ids = [c["claim_id"] for c in claims]
    assert len(ids) == len(set(ids)), "claim_id duplicado en ledger G1-D"
    return {
        "ledger": {
            "ledger_id": "claim-ledger-g1-d-001",
            "ledger_version": g1c["ledger"]["ledger_version"],
            "run_id": g1c["ledger"]["run_id"] + "+g1-d-territorial-claims-2026-09-14",
            "run_result_sha": g1c["ledger"]["run_result_sha"],
            "claims_total": len(claims),
            "untraced_fields": [],
        },
        "claims": claims,
    }


def build_ledger_v2() -> dict:
    doc = build_ledger()
    g1c = json.loads(G1C_LEDGER.read_text(encoding="utf-8"))
    claims = list(g1c["claims"]) + build_new_claims_v2()
    ids = [c["claim_id"] for c in claims]
    assert len(ids) == len(set(ids)), "claim_id duplicado en ledger G1-D-002"
    doc["claims"] = claims
    doc["ledger"]["ledger_id"] = "claim-ledger-g1-d-002"
    doc["ledger"]["run_id"] += "+g1-d-f01-home-mechanism"
    doc["ledger"]["claims_total"] = len(claims)
    return doc


def main() -> int:
    v2 = "--v2" in sys.argv
    if v2:
        outputs = (
            (OUT_LEDGER_V2, build_ledger_v2()),
            (OUT_CORPUS_V2, build_corpus_v2()),
            (OUT_MANIFEST_V2, build_manifest_v2()),
        )
    else:
        ledger = build_ledger()
        outputs = (
            (OUT_LEDGER, ledger),
            (OUT_CORPUS, build_corpus()),
            (OUT_MANIFEST, build_manifest()),
        )
    for path, doc in outputs:
        path.write_text(canonical_json(doc) + "\n", encoding="utf-8")
        print(f"{len(json.dumps(doc))} bytes -> {path.relative_to(ROOT)}")
    ledger = outputs[0][1]
    print(f"claims: {ledger['ledger']['claims_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
