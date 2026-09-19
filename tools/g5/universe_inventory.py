"""G5-A U-01 — Universe source inventory.

Analysis-only pass over the frozen raw snapshots: record counts per
source/category, identifier availability, and EXACT-ID overlap
candidates between sources. Produces no canonical entities, no
merges, no fuzzy joins — name-only co-occurrences are reported as
counts, never resolved.
"""

import csv
import io
import json
import re
import warnings
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "fixtures" / "g5" / "sources" / "raw"
G1RAW = ROOT / "fixtures" / "g1" / "sources" / "raw"
OUT = ROOT / "fixtures" / "g5" / "sources" / "universe-inventory.json"

NIF_RE = re.compile(r"\b[A-Z][-\s]?\d{7,8}[A-Z0-9]?\b")


def cnmv_category(h):
    heads = [re.sub(r"<[^>]+>", "", x).strip()
             for x in re.findall(r"<h[1-5][^>]*>(.*?)</h[1-5]>", h, re.S | re.I)]
    heads = [x for x in heads if x and "cookie" not in x.lower()
             and "Configuraci" not in x]
    return heads[-1] if heads else "?"


def cnmv_file_stats(path):
    h = path.read_text(encoding="utf-8", errors="replace")
    rows = len(re.findall(r"liSubtituloRegistro", h))
    nifs = set(re.findall(r"nif=([A-Z0-9\-]+)", h))
    return cnmv_category(h), rows, nifs


def xlsx_rows(path, sheet="DATOS GENERALES", nif_col=None, lei_col=None):
    import openpyxl
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet] if sheet in wb.sheetnames else wb.worksheets[0]
    rows = [r for r in ws.iter_rows(values_only=True)
            if any(c is not None for c in r)]
    wb.close()
    return rows


def main():
    inv = {"cnmv": {}, "opendgsfp": {}, "bde": {}, "eba": {}, "esma": {},
           "overlap": {}}

    # --- CNMV per-category ---
    cat_rows = Counter()
    cat_nifs = defaultdict(set)
    cat_files = defaultdict(int)
    for f in sorted(RAW.glob("CNMV__*.html")):
        cat, rows, nifs = cnmv_file_stats(f)
        base = re.sub(r"_page-\d+$", "", f.stem)
        cat_files[(cat, base)] += 0  # group key
        cat_rows[cat] += rows
        cat_nifs[cat] |= nifs
        cat_files[cat] += 1
    for cat in sorted(cat_rows):
        inv["cnmv"][cat] = {"files": cat_files[cat],
                           "records": cat_rows[cat],
                           "nif_links": len(cat_nifs[cat])}
        print(f"{cat_rows[cat]:>6}  nif={len(cat_nifs[cat]):<5} {cat[:70]}")

    # --- BdE ---
    bde_nifs, bde_leis = set(), set()
    for fname, sheet in [("bde-registro-entidades.xlsx", None),
                         ("bde-registro-entidades-credito.xlsx", None),
                         ("bde-registro-con-establecimiento.xlsx", None),
                         ("bde-registro-sin-establecimiento.xlsx", None),
                         ("bde-registro-servicios-pago.xlsx", None)]:
        rows = xlsx_rows(G1RAW / fname)
        data = [r for r in rows[1:]
                if len(r) > 1 and r[1] and str(r[1]).strip()]
        n = sum(1 for r in data if len(r) > 3 and r[3])
        lei = sum(1 for r in data if len(r) > 7 and r[7])
        for r in data:
            if len(r) > 3 and r[3]:
                bde_nifs.add(str(r[3]).strip())
            if len(r) > 7 and r[7]:
                bde_leis.add(str(r[7]).strip())
        inv["bde"][fname] = {"rows": len(data), "with_docid": n,
                             "with_lei": lei}
        print(f"BDE {fname[:45]:45} rows={len(data)} docid={n} lei={lei}")

    # --- EBA ---
    with zipfile.ZipFile(ROOT / "fixtures" / "g2" / "sources" / "raw" /
                         "eba-psd2-202609150000.zip") as f:
        j = json.loads(f.read("download-PSDMD-202609150000.json"))
    recs = j[1]
    types = Counter(r.get("EntityType") for r in recs)
    owners = Counter(r.get("CA_OwnerID") for r in recs)
    es = [r for r in recs if r.get("CA_OwnerID") == "ES_BE"]
    es_types = Counter(r.get("EntityType") for r in es)
    passport_in_es = sum(1 for r in recs if any(
        "ES" in (p.get("ENT_SERVICES") or p.get("ENT_SERV_PASS") or {})
        for p in r.get("Properties", [])))
    inv["eba"] = {"total": len(recs), "by_type": dict(types.most_common(10)),
                  "es_be": len(es), "es_be_by_type": dict(es_types),
                  "passport_into_es_hint": passport_in_es,
                  "nca_owners": len(owners)}
    print(f"EBA total={len(recs)} ES_BE={len(es)} types={dict(es_types)}")

    # --- OpenDGSFP ---
    kinds, idents = Counter(), Counter()
    nifs_d, leis_d = set(), set()
    for ln in (RAW / "OpenDGSFP__opendgsfp-0.1.jsonl").read_text(
            encoding="utf-8").splitlines():
        d = json.loads(ln)
        if d.get("record_type") != "entity":
            continue
        kinds[d.get("entity_kind")] += 1
        for i in d.get("identifiers", []):
            s = i.get("scheme")
            idents[s] += 1
            if s == "es:nif":
                nifs_d.add(i.get("value"))
            elif s == "lei":
                leis_d.add(i.get("value"))
    inv["opendgsfp"] = {"entities": sum(kinds.values()),
                       "by_kind": dict(kinds),
                       "identifier_schemes": dict(idents)}
    print(f"DGSFP entities={sum(kinds.values())} {dict(kinds)}")

    # --- ESMA MiCA ---
    for name in ["esma-mica-casps.csv", "esma-mica-ncasp.csv"]:
        rows = list(csv.reader(io.StringIO(
            (G1RAW / name).read_text(encoding="utf-8", errors="replace"))))
        inv["esma"][name] = {"rows": len(rows) - 1}
        print(f"ESMA {name}: {len(rows)-1}")

    # --- EXACT-ID overlap candidates ---
    cnmv_nifs_all = set()
    for s in cat_nifs.values():
        cnmv_nifs_all |= s
    inv["overlap"] = {
        "nif_bde_x_cnmv": len(bde_nifs & cnmv_nifs_all),
        "nif_bde_x_dgsfp": len(bde_nifs & nifs_d),
        "nif_cnmv_x_dgsfp": len(cnmv_nifs_all & nifs_d),
        "lei_bde_x_dgsfp": len(bde_leis & leis_d),
        "sets": {"bde_nif": len(bde_nifs), "bde_lei": len(bde_leis),
                 "cnmv_nif": len(cnmv_nifs_all),
                 "dgsfp_nif": len(nifs_d), "dgsfp_lei": len(leis_d)},
    }
    print("overlap:", inv["overlap"])

    OUT.write_text(json.dumps(inv, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\nwritten: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
