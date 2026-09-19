#!/usr/bin/env python3
"""G4-G3 refresh — CNMV vistas not frozen in G0.

Captures the pending surfaces declared NO_EVIDENCE in G4-G2:
  ESI   slots: vistas 6,10,11,12,13,16,38
  SGIIC slots: vistas 5,6,10,11,12,13,16,38  (adds 5 = fondos gestionados)

Evidence discipline (same as probe_g0):
- raw bytes → fixtures/g4/sources/raw/<slot>__vista_<n>.html
  (disjoint labels; no historical file is touched);
- NEW independent manifest fixtures/g4/sources/manifest-refresh-<date>.json
  — the G0 manifest.json is not modified;
- per request: url, http_status, bytes, sha256, retrieved_at,
  source_as_of (declared wFecha read from the served page, never
  inferred from retrieval time), content_check;
- parsed probes → fixtures/g4/probes/refresh/<slot>.json (new dir).
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_g0  # noqa: E402  reuse fetch/parsers (same repo, same contract)

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "fixtures/g4/corpus/entities.json"
RAW = ROOT / "fixtures/g4/sources/raw"
PROBES = ROOT / "fixtures/g4/probes/refresh"

TODAY = time.strftime("%Y%m%d", time.gmtime())
MANIFEST = ROOT / f"fixtures/g4/sources/manifest-refresh-{TODAY}.json"

VISTAS_ESI = {6: "sociedades_gestionadas", 10: "sucursales_eee",
              11: "sucursales_fuera_eee", 12: "libre_prestacion_eee",
              13: "libre_prestacion_fuera_eee", 16: "atencion_cliente",
              38: "auditorias"}
VISTAS_SGIIC = {5: "fondos_gestionados", **VISTAS_ESI}


def source_as_of(body: bytes):
    m = re.search(rb'wFecha\$txtFecha" value="([^"]+)"', body)
    return m.group(1).decode() if m else None


def content_check(status: int, body: bytes) -> str:
    if status != 200:
        return "HTTP_ERROR"
    if b"ContentPrincipal" not in body:
        return "NO_FICHA_MARKUP"
    return "OK"


def main():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))["entities"]
    manifest = {"schema": "FINREG_G4_SOURCE_MANIFEST_V1",
                "generated_for": "G4-G3",
                "preregistration": "docs/gates/G4-G3-PREREG.md",
                "succeeds": "fixtures/g4/sources/manifest.json",
                "requests": []}
    probes = {}
    PROBES.mkdir(parents=True, exist_ok=True)

    for e in corpus:
        slot, vert, nif = e["slot"], e["vertical"], e.get("nif")
        if vert == "CNMV_ESI":
            base = f"https://www.cnmv.es/Portal/Consultas/ESI/esis.aspx?nif={nif}"
            vistas = VISTAS_ESI
        elif vert == "CNMV_SGIIC":
            base = f"https://www.cnmv.es/portal/consultas/iic/sgiic.aspx?nif={nif}"
            vistas = VISTAS_SGIIC
        else:
            continue  # BDE_*/INS_* are artifact-frozen, not CNMV fichas

        for v in sorted(vistas):
            label = f"vista_{v}"
            url = f"{base}&vista={v}"
            time.sleep(probe_g0.DELAY)
            status, body = probe_g0.fetch(url)
            (RAW / f"{slot}__{label}.html").write_bytes(body)
            entry = {"slot": slot, "label": label, "semantic": vistas[v],
                     "url": url, "fs_requested": None,
                     "http_status": status, "bytes": len(body),
                     "sha256": hashlib.sha256(body).hexdigest(),
                     "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                     "source_as_of": source_as_of(body),
                     "content_check": content_check(status, body)}
            manifest["requests"].append(entry)
            p = probes.setdefault(slot, {"views": {}, "errors": []})
            if status != 200:
                p["errors"].append({"label": label, "status": status})
            else:
                p["views"][label] = {"semantic": vistas[v],
                                     "tables": probe_g0.parse_table_view(body),
                                     "declared_data_date": entry["source_as_of"]}
            print(f"{slot:8s} {label:9s} {vistas[v]:28s} -> {status} "
                  f"{len(body)}B {entry['content_check']}", flush=True)

    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    for slot, p in probes.items():
        (PROBES / f"{slot}.json").write_text(
            json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ok = sum(1 for r in manifest["requests"] if r["content_check"] == "OK")
    print(f"\nrequests: {len(manifest['requests'])}  OK: {ok}  "
          f"errors: {len(manifest['requests']) - ok}")
    print(f"manifest: {MANIFEST.name}")


if __name__ == "__main__":
    sys.exit(main())
