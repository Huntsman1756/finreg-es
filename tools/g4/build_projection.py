#!/usr/bin/env python3
"""Build the public projection (read model) for Regulatory Record ES.

Consumes frozen evidence only — no live requests:
  - fixtures/g4/corpus/entities.json
  - fixtures/g4/sources/{manifest.json,raw/*}
  - AlertaFin  g0/normalized/notices.jsonl        (warnings / clones)
  - OpenDGSFP  data/derived/v0.1/opendgsfp-0.1.jsonl (insurance identity)
  - EBA PSD2 fixture zip                          (registration facts)
  - BdE Registro_ServicioPagos.xlsx               (frozen snapshot)

Emits projections/public/ per docs/product/PUBLIC-DATA-MODEL.md.
Serialization via finreg_es.canonical (deterministic); bundle_sha256
covers all emitted artifacts.
"""

import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="Workbook contains no default style")
import openpyxl  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from finreg_es.canonical import canonical_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
G4 = ROOT / "fixtures/g4"
OUT = ROOT / "projections/public"
# Frozen upstream slices (see fixtures/g4/upstream/manifest.json): the full
# upstream artifacts remain authoritative in their repos; these slices keep
# the builder offline and byte-reproducible.
ALERTAFIN_NOTICES = G4 / "upstream/alertafin-notices-slice.jsonl"
OPENDGSFP_JSONL = G4 / "upstream/opendgsfp-slice.jsonl"
EBA_ZIP = ROOT / "fixtures/g0.5/sources/raw/h4-eba-psd2-20260913.zip"
BDE_XLSX = G4 / "sources/raw/BDE__registro_serviciospagos.xlsx"

SCHEMA = "regulatory-record-entity/v1"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def slug_id(vertical: str, key: str) -> str:
    prefix = {"CNMV_ESI": "esi", "CNMV_SGIIC": "sgiic",
              "BDE_EBA_PSD2": "ede", "INSURANCE_DGSFP": "ins"}[vertical]
    return f"{prefix}-{re.sub(r'[^a-z0-9]+', '', key.lower())}"


# ---------------------------------------------------------------- CNMV HTML

def cell_text(td_html: str) -> str:
    t = re.sub(r"<span[^>]*class=\"textotooltip\".*?</span>", "", td_html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), t)
    t = re.sub(r"&nbsp;?", " ", t)
    return re.sub(r"\s+", " ", t.replace("&amp;", "&")).strip()


def parse_tables(path: Path):
    """Return list of tables; each table = list of rows; each row = list of
    {'text': str, 'alt': [img alt texts]} preserving check marks."""
    html = path.read_text(encoding="utf-8", errors="replace")
    i = html.find("ContentPrincipal")
    seg = html[i:] if i >= 0 else html
    tables = []
    for tb in re.findall(r"<table.*?</table>", seg, re.S):
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = []
            for td in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S):
                cells.append({"text": cell_text(td),
                              "alt": re.findall(r'alt="([^"]*)"', td)})
            if any(c["text"] or c["alt"] for c in cells):
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def kv_tables(tables):
    """Tables whose rows are header-row + single data row → dict."""
    out = {}
    for t in tables:
        if len(t) == 2 and len(t[0]) == len(t[1]):
            for h, v in zip(t[0], t[1]):
                if h["text"]:
                    out[h["text"]] = v["text"]
    return out


def list_table(tables, first_header: str):
    for t in tables:
        if t and t[0] and t[0][0]["text"].lower().startswith(first_header.lower()):
            hdr = [c["text"] for c in t[0]]
            return hdr, [[c["text"] for c in r] for r in t[1:]]
    return None, []


def parse_programa(path: Path):
    """vista_17 → services with instrument letters + client types (Si marks)."""
    tables = parse_tables(path)
    services = []
    for t in tables:
        if not t or not t[0]:
            continue
        h0 = t[0][0]["text"]
        if not (h0.startswith("Servicios") or h0.startswith("Servicios aux")):
            continue
        kind = "auxiliary" if "auxiliar" in h0.lower() else "investment"
        # instrument letter columns come from row 1 (a…k) + client columns
        colhdr = [c["text"] for c in t[1]] if len(t) > 1 else []
        for r in t[2:]:
            if not r or not r[0]["text"]:
                continue
            name = re.sub(r"^(Recepci\u00f3n|Gesti\u00f3n|Colocaci\u00f3n|Asesoramiento|Elaboraci\u00f3n|Custodia|Concesi\u00f3n|Operaci\u00f3n|Servicio)",
                          lambda m: m.group(0), r[0]["text"])
            name = re.split(r"(?<=[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1)])(?=[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z])",
                            r[0]["text"])[0].strip()
            instruments = []
            clients = []
            for j, c in enumerate(r[1:], 1):
                if "Si" in c["alt"] and j - 1 < len(colhdr):
                    h = colhdr[j - 1]
                    m = re.match(r"^([a-k])", h)
                    if m:
                        instruments.append(m.group(1))
                    elif h in ("Minoristas", "Profesionales", "Contrapartes elegibles"):
                        clients.append(h)
            services.append({"kind": kind, "service": name,
                             "instruments": instruments, "clients": clients})
    return services


def page_name(path: Path) -> str:
    t = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<title>(.*?)</title>", t, re.S)
    if not m:
        return ""
    parts = [p.strip() for p in m.group(1).split(" - ")]
    return parts[2] if len(parts) >= 3 else ""


# ------------------------------------------------------------------ builder

def main() -> int:
    corpus = json.loads((G4 / "corpus/entities.json").read_text(encoding="utf-8"))
    manifest = json.loads((G4 / "sources/manifest.json").read_text(encoding="utf-8"))
    reqs = manifest["requests"]

    def reqs_for(slot, label_prefix=None):
        return [r for r in reqs if r["slot"] == slot
                and (label_prefix is None or r["label"].startswith(label_prefix))]

    def ev(r):
        return {"source": "CNMV_PORTAL", "url": r["url"],
                "requested_fs": r.get("fs_requested"),
                "retrieved_at": r["retrieved_at"], "sha256": r["sha256"]}

    entities, changes = [], []
    raw = G4 / "sources/raw"

    def add_change(entity_id, cls, date_or_interval, summary, evidence):
        changes.append({"entity_id": entity_id, "class": cls,
                        "date_or_interval": date_or_interval,
                        "summary": summary, "evidence": evidence})

    # ---- AlertaFin notices: exact registry-number clone targets ----
    notices = []
    if ALERTAFIN_NOTICES.exists():
        for line in ALERTAFIN_NOTICES.read_text(encoding="utf-8").splitlines():
            if line.strip():
                notices.append(json.loads(line))
    clones_by_reg = {}
    for n in notices:
        tgt = (n.get("clone") or {}).get("clone_target_registry_number")
        if tgt:
            clones_by_reg.setdefault(tgt, []).append(n)

    # ---- OpenDGSFP ----
    dgsfp_by_id = {}
    if OPENDGSFP_JSONL.exists():
        for line in OPENDGSFP_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                dgsfp_by_id[d.get("entity_id")] = d
    dgsfp_sha = sha256_file(OPENDGSFP_JSONL) if OPENDGSFP_JSONL.exists() else None
    bde_sha = sha256_file(BDE_XLSX)
    eba_sha = sha256_file(EBA_ZIP)
    alertafin_sha = sha256_file(ALERTAFIN_NOTICES) if ALERTAFIN_NOTICES.exists() else None

    # ---- BdE XLSX ----
    wb = openpyxl.load_workbook(BDE_XLSX, read_only=True)
    bde_general, bde_act, bde_xb = {}, {}, {}
    for ws in wb:
        ws.reset_dimensions()
        rows = list(ws.iter_rows(values_only=True))
        hdr_i = next(i for i, r in enumerate(rows) if r and r[0] == "CÓDIGO BE")
        hdr = [str(c) if c else "" for c in rows[hdr_i]]
        for r in rows[hdr_i + 1:]:
            if not r or r[0] is None:
                continue
            rec = dict(zip(hdr, [str(c) if c is not None else "" for c in r]))
            code = rec["CÓDIGO BE"]
            if ws.title == "DATOS GENERALES":
                bde_general[code] = rec
            elif ws.title == "ACTIVIDADES":
                bde_act.setdefault(code, []).append(rec)
            else:
                bde_xb.setdefault(code, []).append(rec)

    for e in corpus["entities"]:
        slot, vert = e["slot"], e["vertical"]
        timeline, sources, coverage = [], [], {}

        if vert in ("CNMV_ESI", "CNMV_SGIIC"):
            nif = e["nif"].replace("-", "")
            dg_file = raw / f"{slot}__{'vista_0' if vert == 'CNMV_ESI' else 'dg_current'}.html"
            tables = parse_tables(dg_file)
            kv = kv_tables(tables)
            reg_no = kv.get("Nº Registro Oficial") or kv.get("Nº Registro oficial") or "UNKNOWN"
            reg_date = kv.get("Fecha registro oficial") or "UNKNOWN"
            name = page_name(dg_file) or e["name"]
            eid = slug_id(vert, nif)

            dg_reqs = reqs_for(slot, "vista_0" if vert == "CNMV_ESI" else "dg_current")
            ev_dg = ev(dg_reqs[0]) if dg_reqs else None

            # organisation / locations
            _, admins = list_table(parse_tables(raw / f"{slot}__vista_4.html"), "Apellidos")
            _, socios = list_table(parse_tables(raw / f"{slot}__vista_7.html"), "Socio")
            _, agentes = list_table(parse_tables(raw / f"{slot}__vista_8.html"), "Nombre agentes") \
                if (raw / f"{slot}__vista_8.html").exists() else (None, [])
            _, sucursales = list_table(parse_tables(raw / f"{slot}__vista_9.html"), "Dirección") \
                if (raw / f"{slot}__vista_9.html").exists() else (None, [])
            services = parse_programa(raw / f"{slot}__vista_17.html") \
                if (raw / f"{slot}__vista_17.html").exists() else []

            # fs historical states (SGIIC/IIC only)
            fs_states = []
            for r in reqs_for(slot, "dg_fs"):
                f = raw / f"{slot}__{r['label']}.html"
                if f.exists():
                    kvv = kv_tables(parse_tables(f))
                    fs_states.append({"requested_fs": r["fs_requested"],
                                      "address": kvv.get("Dirección", "UNKNOWN"),
                                      "capital": kvv.get("Capital social", "UNKNOWN"),
                                      "evidence": ev(r)})

            cur_addr = kv.get("Dirección", "UNKNOWN")
            for st in fs_states:
                timeline.append({
                    "date_or_interval": st["requested_fs"],
                    "kind": "OFFICIAL_AS_OF_STATE",
                    "summary": f"Estado servido por la fuente para fs={st['requested_fs']}: "
                               f"dirección «{st['address']}», capital {st['capital']}",
                    "evidence": st["evidence"]["sha256"]})
                if st["address"] != "UNKNOWN" and st["address"] != cur_addr:
                    timeline.append({
                        "date_or_interval": [st["requested_fs"], dg_reqs[0]["retrieved_at"][:10] if dg_reqs else "UNKNOWN"],
                        "kind": "OBSERVED_CHANGE",
                        "summary": f"Cambio de dirección entre {st['requested_fs']} y la observación "
                                   f"actual («{st['address']}» → «{cur_addr}»)",
                        "evidence": st["evidence"]["sha256"]})

            timeline.append({"date_or_interval": reg_date,
                             "kind": "EXPLICIT_OFFICIAL_EVENT",
                             "summary": f"Inscripción en el registro oficial CNMV nº {reg_no}",
                             "evidence": ev_dg["sha256"] if ev_dg else "UNKNOWN"})
            for a in admins:
                if len(a) >= 3 and a[2]:
                    timeline.append({"date_or_interval": a[2],
                                     "kind": "EXPLICIT_OFFICIAL_EVENT",
                                     "summary": f"Nombramiento: {a[0]} — {a[1]}",
                                     "evidence": "vista_4"})

            record = {
                "schema": SCHEMA, "id": eid,
                "identity": {
                    "legal_name": name, "aliases": [e["name"]] if e["name"] != name else [],
                    "identifiers": [{"scheme": "es:nif", "value": nif},
                                    {"scheme": "cnmv:registro", "value": reg_no}],
                    "resolution": "EXACT"},
                "status": {"value": "REGISTERED", "as_of": dg_reqs[0]["retrieved_at"][:10] if dg_reqs else "UNKNOWN",
                           "basis": "OFFICIAL_AS_OF_STATE"},
                "registrations": [{"regulator": "CNMV", "register": vert,
                                   "number": reg_no, "date": reg_date,
                                   "state": "INSCRITA", "basis": "OFFICIAL_AS_OF_STATE"}],
                "permissions": [{"service": s["service"], "kind": s["kind"],
                                 "instruments": s["instruments"], "clients": s["clients"],
                                 "since": None, "basis": "OFFICIAL_AS_OF_STATE"}
                                for s in services],
                "locations": {"domicile": cur_addr,
                              "branches": [r[0] for r in sucursales if r],
                              "agents": [r[0] for r in agentes if r],
                              "passporting": "UNKNOWN"},
                "organisation": {
                    "shareholders": [{"name": r[0], "pct": r[1]} for r in socios if len(r) >= 2],
                    "administrators": [{"name": r[0], "role": r[1], "appointed": r[2] if len(r) > 2 else None}
                                       for r in admins if len(r) >= 2]},
                "regulatory_record": {"sanctions": [], "appeals": [],
                                      "direct_warnings": [], "impersonations": [], "candidates": []},
                "timeline": timeline,
                "sources": [ev(r) for r in reqs_for(slot)],
                "coverage": {},
                "freshness": {"last_successful_refresh": dg_reqs[0]["retrieved_at"] if dg_reqs else "UNKNOWN",
                              "source_status": "OK"},
            }

            # sanction evidence (corpus-declared)
            if e.get("sanction_evidence"):
                se = e["sanction_evidence"]
                record["regulatory_record"]["sanctions"].append({
                    "register": se["register"], "resolution": se["resolution"],
                    "register_date": se["register_date"], "boe_reference": se["boe_reference"],
                    "basis": "OFFICIAL_DOCUMENT_DERIVATION"})
                timeline.append({"date_or_interval": se["register_date"],
                                 "kind": "OFFICIAL_DOCUMENT_DERIVATION",
                                 "summary": se["resolution"],
                                 "evidence": "sanciones_registro"})

            # AlertaFin clones targeting this exact registry number
            for n in clones_by_reg.get(reg_no, []):
                warn = {"notice_id": n["notice_id"], "fecha": n.get("fecha"),
                        "warned_name": n["entidad_raw"],
                        "relation": "IMPERSONATES",
                        "legitimate_entity": {"registry_number": reg_no,
                                              "relation": "MENTIONED_AS_LEGITIMATE_ENTITY"},
                        "domains": [d["host_normalized"] for d in n.get("domains", [])],
                        "observaciones": n.get("observaciones_raw"),
                        "evidence": {"source": "ALERTAFIN",
                                     "artifact": "g0/normalized/notices.jsonl",
                                     "notice_id": n["notice_id"],
                                     "source_sha256": n["provenance"]["source_sha256"],
                                     "retrieved_at": n["provenance"]["retrieved_at"]}}
                record["regulatory_record"]["impersonations"].append(warn)
                timeline.append({"date_or_interval": n.get("fecha"),
                                 "kind": "EXPLICIT_OFFICIAL_EVENT",
                                 "summary": f"Advertencia CNMV de clon: {n['entidad_raw']} "
                                            f"(no guarda relación con la entidad registrada nº {reg_no})",
                                 "evidence": n["notice_id"]})

        elif vert == "BDE_EBA_PSD2":
            code = e["bde_nat_ref"]
            g = bde_general.get(code, {})
            eid = slug_id(vert, code)
            bde_ev = {"source": "BDE_REGISTRO_SERVICIOS_PAGO",
                      "artifact": "fixtures/g4/sources/raw/BDE__registro_serviciospagos.xlsx",
                      "sha256": bde_sha, "as_of": "2026-09-17", "retrieved_at": "G0"}
            eba_ev = {"source": "EBA_PSD2_REGISTER", "artifact": str(EBA_ZIP.relative_to(ROOT)),
                      "sha256": eba_sha}
            nif = g.get("DOCUMENTO IDENTIFICATIVO", "UNKNOWN")
            identifiers = [{"scheme": "es:nif", "value": nif},
                           {"scheme": "bde:codigo", "value": code},
                           {"scheme": "eba:entity_code", "value": e["eba_entity_code"]}]
            if g.get("CÓDIGO LEI"):
                identifiers.append({"scheme": "lei", "value": g["CÓDIGO LEI"]})

            acts = bde_act.get(code, [])
            xb = bde_xb.get(code, [])
            bde_alta = g.get("FECHA ALTA", "UNKNOWN")
            timeline.append({"date_or_interval": bde_alta,
                             "kind": "EXPLICIT_OFFICIAL_EVENT",
                             "summary": f"Alta en el registro BdE de entidades de dinero electrónico (código {code})",
                             "evidence": bde_sha})
            for a in acts:
                if a.get("FECHA DE ALTA ACTIVIDAD"):
                    timeline.append({"date_or_interval": a["FECHA DE ALTA ACTIVIDAD"],
                                     "kind": "EXPLICIT_OFFICIAL_EVENT",
                                     "summary": f"Alta de actividad BdE: {a.get('CÓDIGO ACTIVIDAD','')} "
                                                f"{a.get('ACTIVIDAD','')[:80]}",
                                     "evidence": bde_sha})
            if e.get("ent_aut") and e["ent_aut"] != bde_alta:
                timeline.append({"date_or_interval": e["ent_aut"],
                                 "kind": "EXPLICIT_OFFICIAL_EVENT",
                                 "summary": f"Fecha ENT_AUT en el registro EBA PSD2 "
                                            f"(difiere del alta BdE {bde_alta}; conflicto preservado)",
                                 "evidence": eba_sha})

            record = {
                "schema": SCHEMA, "id": eid,
                "identity": {"legal_name": g.get("NOMBRE", e["name"]),
                             "aliases": [e["name"]] if e["name"] != g.get("NOMBRE") else [],
                             "identifiers": identifiers, "resolution": "EXACT"},
                "status": {"value": "REGISTERED", "as_of": "2026-09-17",
                           "basis": "OFFICIAL_AS_OF_STATE"},
                "registrations": [
                    {"regulator": "Banco de España", "register": "BDE_REGISTRO_SERVICIOS_PAGO",
                     "number": code, "date": bde_alta, "state": "INSCRITA",
                     "basis": "OFFICIAL_AS_OF_STATE"},
                    {"regulator": "EBA", "register": "EBA_PSD2_REGISTER",
                     "number": e["eba_entity_code"], "date": e.get("ent_aut", "UNKNOWN"),
                     "state": "INSCRITA", "basis": "OFFICIAL_AS_OF_STATE",
                     "conflict_with": "bde:codigo" if e.get("ent_aut") != bde_alta else None}],
                "permissions": [{"service": a.get("ACTIVIDAD", ""), "code": a.get("CÓDIGO ACTIVIDAD", ""),
                                 "norm": a.get("NORMATIVA", ""), "since": a.get("FECHA DE ALTA ACTIVIDAD"),
                                 "basis": "OFFICIAL_AS_OF_STATE"} for a in acts],
                "locations": {"domicile": " ".join(x for x in [g.get("DIRECCIÓN"), g.get("POBLACIÓN"),
                                                               g.get("CÓDIGO POSTAL")] if x),
                              "branches": [], "agents": [],
                              "passporting": [{"mode": x.get("FORMA DE OPERAR"), "country": x.get("PAÍS EN EL QUE OPERA (ISO2)"),
                                               "activity": x.get("ACTIVIDAD") or None,
                                               "since": x.get("FECHA DE ALTA ACTIVIDAD") or None,
                                               "basis": "OFFICIAL_AS_OF_STATE"} for x in xb]},
                "organisation": {"shareholders": [], "administrators": [],
                                 "parent": g.get("NOMBRE ENTIDAD MATRIZ") or None},
                "regulatory_record": {"sanctions": [], "appeals": [],
                                      "direct_warnings": [], "impersonations": [], "candidates": []},
                "timeline": timeline, "sources": [bde_ev, eba_ev],
                "coverage": {},
                "freshness": {"last_successful_refresh": "2026-09-18", "source_status": "OK"},
            }
            # AlertaFin clones targeting BdE entities by name (no registry-number
            # crosswalk → candidates only, never attribution)
            for n in notices:
                en = (n.get("entidad_raw") or "").upper()
                nm = (g.get("NOMBRE") or e["name"]).split(",")[0].split(" ")[0].upper()
                if nm and len(nm) > 4 and nm in en and "(CLON" not in en:
                    record["regulatory_record"]["candidates"].append({
                        "notice_id": n["notice_id"], "warned_name": n["entidad_raw"],
                        "relation": "CANDIDATE", "basis": "name-similarity-only"})

        elif vert == "INSURANCE_DGSFP":
            d = dgsfp_by_id.get(e["upstream_entity_id"])
            eid = slug_id(vert, e["dgsfp_key"])
            ins_ev = {"source": "OPENDGSFP", "artifact": "data/derived/v0.1/opendgsfp-0.1.jsonl",
                      "schema": "opendgsfp/0.1", "sha256": dgsfp_sha}
            if not d:
                record = {"schema": SCHEMA, "id": eid,
                          "identity": {"legal_name": "UNKNOWN", "aliases": [],
                                       "identifiers": [{"scheme": "dgsfp:clave", "value": e["dgsfp_key"]}],
                                       "resolution": "UNRESOLVED"},
                          "status": {"value": "UNKNOWN", "as_of": "UNKNOWN", "basis": "NOT_REPRESENTABLE"},
                          "registrations": [], "permissions": [],
                          "locations": {"domicile": "UNKNOWN", "branches": [], "agents": [], "passporting": []},
                          "organisation": {"shareholders": [], "administrators": []},
                          "regulatory_record": {"sanctions": [], "appeals": [], "direct_warnings": [],
                                                "impersonations": [], "candidates": []},
                          "timeline": [], "sources": [ins_ev], "coverage": {},
                          "freshness": {"last_successful_refresh": "UNKNOWN", "source_status": "NO_EVIDENCE"}}
            else:
                ids = [{"scheme": i["scheme"], "value": i["value"],
                        **({"country": i["country"]} if i.get("country") else {})}
                       for i in d["identifiers"]]
                situ = (d["registrations"][0].get("situacion") if d["registrations"] else None) or "UNKNOWN"
                snap = (d["snapshots"][0]["source_snapshot_date"] if d["snapshots"] else "UNKNOWN")
                reg_as = next((a for a in d.get("source_assertions", [])
                               if a["predicate"] == "REGISTERED_AS" and a["object"].get("clave")), None)
                pub_name = next((a for a in d.get("source_assertions", [])
                                 if a["predicate"] == "PUBLISHES_NAME"), None)
                name = (pub_name["object"] if pub_name else None) or \
                       (reg_as["object"].get("denominacion") if reg_as else None) or \
                       f"DGSFP {e['dgsfp_key']}"
                f_aut = reg_as["object"].get("fecha_autorizacion") if reg_as else None
                f_can = reg_as["object"].get("fecha_cancelacion") if reg_as else None
                timeline.append({"date_or_interval": snap, "kind": "OFFICIAL_AS_OF_STATE",
                                 "summary": f"Estado DGSFP «{situ}» observado en snapshot {snap}",
                                 "evidence": (d["registrations"][0].get("assertion") if d["registrations"] else "UNKNOWN")})
                if f_aut:
                    timeline.append({"date_or_interval": f_aut, "kind": "EXPLICIT_OFFICIAL_EVENT",
                                     "summary": f"Autorización DGSFP ({e['dgsfp_key']})",
                                     "evidence": reg_as["assertion_id"]})
                if f_can:
                    timeline.append({"date_or_interval": f_can, "kind": "EXPLICIT_OFFICIAL_EVENT",
                                     "summary": "Cancelación en el registro DGSFP",
                                     "evidence": reg_as["assertion_id"]})
                if situ == "Cancelada" and not f_can:
                    timeline.append({"date_or_interval": ["UNKNOWN", snap],
                                     "kind": "OBSERVED_CHANGE",
                                     "summary": "Entidad cancelada en el registro DGSFP; fecha exacta de "
                                                "baja no disponible en el artefacto (límite acotado)",
                                     "evidence": ins_ev["sha256"]})
                record = {
                    "schema": SCHEMA, "id": eid,
                    "identity": {"legal_name": name, "aliases": [],
                                 "identifiers": ids,
                                 "resolution": d.get("identity_status", "UNRESOLVED")},
                    "status": {"value": "DEREGISTERED" if situ == "Cancelada" else "REGISTERED",
                               "as_of": snap, "basis": "OFFICIAL_AS_OF_STATE",
                               "source_value": situ},
                    "registrations": [{"regulator": "DGSFP", "register": r.get("system", "DGSFP_RRPP"),
                                       "number": r.get("register_key"), "register_type": r.get("register_type"),
                                       "date": f_aut, "cancelled": f_can,
                                       "state": r.get("situacion"), "basis": "OFFICIAL_AS_OF_STATE"}
                                      for r in d["registrations"]],
                    "permissions": "UNKNOWN",
                    "locations": {"domicile": "UNKNOWN", "branches": [], "agents": [],
                                  "passporting": d.get("cross_border_operations", [])},
                    "organisation": {"shareholders": [], "administrators": [],
                                     "entity_kind": d.get("entity_kind")},
                    "regulatory_record": {"sanctions": [], "appeals": [], "direct_warnings": [],
                                          "impersonations": [],
                                          "candidates": d.get("conflicts", [])},
                    "timeline": timeline, "sources": [ins_ev], "coverage": {},
                    "freshness": {"last_successful_refresh": snap, "source_status": "OK"},
                }

        # coverage denominators
        rr = record["regulatory_record"]
        record["coverage"] = {
            "identity": "EXACT" if record["identity"]["resolution"] == "EXACT" else record["identity"]["resolution"],
            "registration": "COVERED" if record["registrations"] else "NO_EVIDENCE",
            "permission": ("COVERED" if isinstance(record["permissions"], list) and record["permissions"]
                           else "NO_EVIDENCE" if record["permissions"] == "UNKNOWN" else "NO_EVIDENCE"),
            "history": ("COVERED" if any(t["kind"] == "OFFICIAL_AS_OF_STATE" and "fs" in str(t.get("evidence", "")).lower()
                                         or t["kind"] == "OBSERVED_CHANGE" for t in timeline)
                        else "NO HISTORICAL EVIDENCE"),
            "sanction": "COVERED" if rr["sanctions"] else ("NO_EVIDENCE" if vert.startswith("CNMV") else "NOT_REPRESENTABLE"),
            "warning": "COVERED" if (rr["impersonations"] or rr["direct_warnings"]) else "NO_EVIDENCE",
            "branch": "COVERED" if record["locations"]["branches"] else "NO_EVIDENCE",
            "passport": "COVERED" if isinstance(record["locations"]["passporting"], list) and record["locations"]["passporting"] else "NO_EVIDENCE",
            "provenance": "COVERED",
        }
        entities.append(record)
        for t in timeline:
            cls = {"EXPLICIT_OFFICIAL_EVENT": "OFFICIAL_EVENT",
                   "OFFICIAL_AS_OF_STATE": "RECONSTRUCTED_HISTORICAL",
                   "OFFICIAL_DOCUMENT_DERIVATION": "OFFICIAL_EVENT",
                   "OBSERVED_CHANGE": "OBSERVED_CURRENT"}[t["kind"]]
            add_change(record["id"], cls, t["date_or_interval"], t["summary"], t["evidence"])

    # ---- index artifacts ----
    entities.sort(key=lambda r: r["id"])
    index = [{"id": r["id"], "name": r["identity"]["legal_name"],
              "aliases": r["identity"]["aliases"],
              "identifiers": r["identity"]["identifiers"],
              "status": r["status"]["value"],
              "vertical": r["id"].split("-")[0]} for r in entities]
    search = [{"id": r["id"],
               "terms": sorted({r["identity"]["legal_name"], *r["identity"]["aliases"],
                                *[i["value"] for i in r["identity"]["identifiers"]]} - {""})}
              for r in entities]
    src_seen = {}
    for r in entities:
        for s in r["sources"]:
            key = s.get("url") or s.get("artifact")
            src_seen.setdefault(key, s)
    sources = sorted(src_seen.values(), key=lambda s: (s["source"], s.get("url") or s.get("artifact") or ""))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "entities").mkdir(exist_ok=True)
    written = []
    for r in entities:
        p = OUT / "entities" / f"{r['id']}.json"
        p.write_text(canonical_json(r), encoding="utf-8")
        written.append(p)
    artifacts = {
        "entities.json": index,
        "search.json": search,
        "changes.json": sorted(changes, key=lambda c: (c["entity_id"], str(c["date_or_interval"]))),
        "sources.json": sources,
    }
    for fn, obj in artifacts.items():
        p = OUT / fn
        p.write_text(canonical_json(obj), encoding="utf-8")
        written.append(p)

    bundle = hashlib.sha256()
    for p in sorted(written):
        bundle.update(p.read_bytes())
    man = {"schema": "regulatory-record-public/v1",
           "generated_at": max(s.get("retrieved_at", "") for r in entities for s in r["sources"]
                               if isinstance(s.get("retrieved_at"), str)),
           "entity_count": len(entities),
           "artifact_count": len(written),
           "inputs": {"corpus": "fixtures/g4/corpus/entities.json",
                      "manifest": "fixtures/g4/sources/manifest.json",
                      "bde_xlsx_sha256": bde_sha, "eba_zip_sha256": eba_sha,
                      "opendgsfp_sha256": dgsfp_sha, "alertafin_sha256": alertafin_sha},
           "bundle_sha256": bundle.hexdigest()}
    (OUT / "manifest.json").write_text(canonical_json(man), encoding="utf-8")
    print(f"projections/public: {len(entities)} entities, "
          f"{len(changes)} changes, bundle {bundle.hexdigest()[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
