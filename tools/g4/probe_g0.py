#!/usr/bin/env python3
"""G4-G0 probe — CNMV ficha snapshots + parsing for the preregistered corpus.

Reads fixtures/g4/corpus/entities.json, downloads the preregistered views,
saves raw bytes to fixtures/g4/sources/raw/, records a manifest and emits
parsed probe results to fixtures/g4/probes/.

Evidence discipline:
- every request recorded with url, requested fs, status, sha256(bytes),
  retrieved_at;
- parsed fields marked found/not_found; nothing is invented;
- `fs` is only used on surfaces where the preregistered audit showed it
  is honored (iic/*.aspx); on esis.aspx it is probed once to document
  the 400 rejection.
"""

import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "fixtures/g4/corpus/entities.json"
RAW = ROOT / "fixtures/g4/sources/raw"
MANIFEST = ROOT / "fixtures/g4/sources/manifest.json"
PROBES = ROOT / "fixtures/g4/probes"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) G4-G0-probe/1.0"}
DELAY = 1.2  # seconds between requests, polite probing

VISTAS_ESI = {0: "datos_generales", 4: "administradores", 7: "socios",
              8: "agentes", 9: "sucursales_es", 17: "programa"}
VISTAS_SGIIC = {0: "datos_generales", 4: "administradores", 7: "socios",
                9: "sucursales_es", 17: "programa", 20: "delegacion"}
FS_DATES = ["18/09/2025", "18/09/2023", "18/09/2021"]  # -1y, -3y, -5y


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001 — recorded, not raised
        return -1, str(e).encode()


def visible_text(html_bytes):
    h = html_bytes.decode("utf-8", errors="replace")
    h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<[^>]+>", "|", h)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"&#160;", " ", t)
    t = re.sub(r"&#\d+;", " ", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"\|+", "|", t)
    return t


def html_unescape(s):
    return (s.replace("&amp;", "&").replace("&#243;", "ó").replace("&#237;", "í")
             .replace("&#225;", "á").replace("&#233;", "é").replace("&#250;", "ú")
             .replace("&#241;", "ñ").replace("&#186;", "º").replace("&#8226;", "•")
             .replace("&#8211;", "–").replace("&#8217;", "'").replace("&#39;", "'")
             .replace("&quot;", '"'))


def parse_datos_generales(html_bytes):
    """Extract key fields from the datos-generales view (vista=0)."""
    h = html_bytes.decode("utf-8", errors="replace")
    out = {}
    m = re.search(r"<title>(.*?)</title>", h, re.S)
    out["page_title"] = html_unescape(m.group(1)).strip() if m else None
    m = re.search(r'wFecha\$txtFecha" value="([^"]+)"', h)
    out["declared_data_date"] = m.group(1) if m else None
    t = visible_text(html_bytes)

    def field(label_pat):
        m = re.search(label_pat + r"\|([^|]{1,120})\|", t)
        return html_unescape(m.group(1).strip()) if m else None

    # registration number/date rows
    m = re.search(r"Nº Registro [Oo]ficial\|?[^|]*\|?\s*Fecha registro oficial\|([^|]+)\|([^|]+)\|", t)
    if m:
        out["registry_number"] = m.group(1).strip()
        out["registration_date"] = m.group(2).strip()
    else:
        m2 = re.search(r"Registro oficial[^|]*\|([^|]{1,40})\|", t)
        out["registry_number"] = m2.group(1).strip() if m2 else None
        out["registration_date"] = None
    for lab, key in [(r"Situaci[óo]n", "status"), (r"Domicilio", "domicile"),
                     (r"Capital social inicial", "share_capital"),
                     (r"Fecha [úu]ltimo folleto", "last_prospectus_date")]:
        v = field(lab)
        if v:
            out[key] = v
    return out


def parse_table_view(html_bytes):
    """Extract the data table(s) of a vista as header+rows text blocks."""
    h = html_bytes.decode("utf-8", errors="replace")
    i = h.find("ContentPrincipal")
    seg = h[i:] if i > 0 else h
    tables = re.findall(r"<table.*?</table>", seg, flags=re.S)
    parsed = []
    for tb in tables:
        heads = [html_unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<th[^>]*>(.*?)</th>", tb, re.S)]
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S):
            cells = [html_unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            cells = [c for c in cells if c]
            if cells:
                rows.append(cells)
        if heads or rows:
            parsed.append({"headers": heads, "rows": rows[:50]})
    return parsed


def main():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))["entities"]
    manifest = {"schema": "FINREG_G4_SOURCE_MANIFEST_V1", "generated_for": "G4-G0",
                "preregistration": "docs/gates/G4-G0-PREREG.md", "requests": []}
    probes = {}

    def record(slot, label, url, fs_requested):
        time.sleep(DELAY)
        status, body = fetch(url)
        name = f"{slot}__{label}.html"
        (RAW / name).write_bytes(body)
        entry = {
            "slot": slot, "label": label, "url": url,
            "fs_requested": fs_requested, "http_status": status,
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        manifest["requests"].append(entry)
        p = probes.setdefault(slot, {"views": {}, "errors": []})
        if status != 200:
            p["errors"].append({"label": label, "status": status})
            return
        if label == "fs_rejection_probe":
            p["fs_rejection"] = {"url": url, "status": status}
        elif label.startswith("vista_") or label.startswith("dg"):
            if "dg_" in label or label == "vista_0":
                p["views"][label] = parse_datos_generales(body)
                p["views"][label]["tables"] = parse_table_view(body)
            else:
                p["views"][label] = {"tables": parse_table_view(body)}
            # declared data date if present on any view
            m = re.search(rb'wFecha\$txtFecha" value="([^"]+)"', body)
            if m:
                p["views"][label]["declared_data_date"] = m.group(1).decode()
        print(f"{slot:8s} {label:28s} -> {status} {len(body)}B")

    for e in corpus:
        slot, vert, nif = e["slot"], e["vertical"], e.get("nif")
        if vert == "CNMV_ESI":
            base = f"https://www.cnmv.es/Portal/Consultas/ESI/esis.aspx?nif={nif}"
            for v, label in VISTAS_ESI.items():
                record(slot, f"vista_{v}", f"{base}&vista={v}", None)
            record(slot, "fs_rejection_probe",
                   f"{base}&fs=01%2F01%2F2020", "01/01/2020")
        elif vert == "CNMV_SGIIC":
            base = f"https://www.cnmv.es/portal/consultas/iic/sgiic.aspx?nif={nif}"
            record(slot, "dg_current", base, None)
            for fs in FS_DATES:
                enc = fs.replace("/", "%2F")
                record(slot, f"dg_fs_{fs.replace('/', '')}", f"{base}&fs={enc}", fs)
            for v, label in VISTAS_SGIIC.items():
                if v == 0:
                    continue
                record(slot, f"vista_{v}", f"{base}&vista={v}", None)
        # BDE_* and INS_* are extracted from frozen artifacts separately.

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for slot, p in probes.items():
        (PROBES / f"{slot}.json").write_text(
            json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nrequests: {len(manifest['requests'])}")
    print(f"errors: {sum(len(p['errors']) for p in probes.values())}")


if __name__ == "__main__":
    sys.exit(main())
