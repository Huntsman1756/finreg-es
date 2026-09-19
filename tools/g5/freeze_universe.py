"""G5-A U-01 — Universe freeze.

Captures CNMV category listings ONCE each (no per-entity ficha
requests, no detail pages) plus the OpenDGSFP canonical export from
an exact upstream commit, into a SUCCESSOR manifest. Historical
manifests are never modified.

Per request: url, http_status, bytes, sha256, retrieved_at, raw_file,
plus lightweight signals (table row estimate, pager hints, export
links) for U-02 to classify EMPTY_VALID vs unavailable. Capture is
kept separate from resolution: this script produces raw snapshots
only — no canonical entities, no merges, no fuzzy joins.
"""

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
G5 = ROOT / "fixtures" / "g5" / "sources"
RAW = G5 / "raw"
MANIFEST = G5 / "manifest-universe-20260919.json"

UA = {"User-Agent": "finreg-es/0.1 evidence freeze (public regulatory data)"}

CNMV = "https://www.cnmv.es/Portal/Consultas/"

# Category listing endpoints discovered inside the frozen G4 ficha
# evidence (href audit of ESI-1/SGIIC-1 pages). One request each; no
# per-entity detail pages are visited.
LIST_PAGES = [
    "ESI-Nacionales.aspx",
    "ESI-Extranjeras.aspx",
    "Entidades-Credito.aspx",
    "Vehiculos-Inversion-Extranjeros.aspx",
    "ERIR.aspx",
    "IndiceIIC.aspx",
    "IndiceECR.aspx",
    "IndiceEAO.aspx",
    "Asesoramiento-Financiero-Nacional.aspx",
    "EntRegIIC.aspx",
    "Proveedores-Servicios-Criptoactivos.aspx",
    "Proveedores-Datos.aspx",
    "BusquedaPorEntidad.aspx",
    "Notificacion-Directivos.aspx",
    "ESI/BusquedaAgentes.aspx",
    "ESI/BusquedaAgentesAFN.aspx",
    "EE/BusquedaIGC.aspx",
    "EE/DistribucionPorBolsas.aspx",
    "EE/DistribucionPorSectores.aspx",
    "FTA/ListadoGestorasFTA.aspx",
    "FTA/Listado_ROFT.aspx",
    "ListadoAgenciasCRA.aspx",
    "ListadoFAB.aspx",
    "Rectoras/ListadoAuditoriasCuentasAnuales.aspx",
    "Rectoras/ListadosIM.aspx",
    "Rectoras/ReglamentosSMN.aspx",
    "RegistroSanciones/IniRegSanciones.aspx",
    "Servicios-Financiacion-Participativa/Indice.aspx",
    "Servicios-Financiacion-Participativa/Listado-PFP-No-Armonizadas.aspx",
    "Servicios-Financiacion-Participativa/Listado-Proveedores-Europeos.aspx",
    "Servicios-Financiacion-Participativa/Listado-Proveedores.aspx",
]
BUSQUEDA_IDS = [1, 2, 6, 7, 11, 13, 14, 15, 16, 19, 20, 22, 27, 29, 33, 34, 35, 36]
LISTADOENT_TIPOENT = list(range(14))  # id=1&tipoent=0..13
LISTADOENT_EXTRA = [(4, 0)]
MOSTRAR_IDS = [0, 1, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]

OPENDGSFP_REPO = Path("F:/_Proyectos/OpenDGSFP")
OPENDGSFP_ARTIFACT = "data/derived/v0.1/opendgsfp-0.1.jsonl"
OPENDGSFP_COMMIT = "f0d0035842cdc9c991d5229d7e223c9ae9f15daa"

# Already-frozen universe-level sources reused as-is (no recapture):
# (file, original manifest, declared role)
REUSED = [
    ("fixtures/g1/sources/raw/bde-registro-entidades.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE all registered entities"),
    ("fixtures/g1/sources/raw/bde-registro-entidades-credito.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE credit institutions"),
    ("fixtures/g1/sources/raw/bde-registro-con-establecimiento.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE foreign with establishment"),
    ("fixtures/g1/sources/raw/bde-registro-sin-establecimiento.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE foreign without establishment"),
    ("fixtures/g1/sources/raw/bde-registro-servicios-pago.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE payment services register"),
    ("fixtures/g1/sources/raw/bde-registro-psp-excluidos.xlsx",
     "fixtures/g1/sources/manifest.json", "BdE excluded PSPs"),
    ("fixtures/g4/sources/raw/BDE__registro_serviciospagos.xlsx",
     "fixtures/g4/sources/manifest.json", "BdE PSP register (G4 refreeze)"),
    ("fixtures/g0.5/sources/raw/h8-bde-mfi-es.csv",
     "fixtures/g0.5/sources/manifest.json", "BdE MFI list ES"),
    ("fixtures/g2/sources/raw/eba-psd2-202609150000.zip",
     "fixtures/g2/sources/manifest.json", "EBA PSD2 full register"),
    ("fixtures/g1/sources/raw/esma-mica-casps.csv",
     "fixtures/g1/sources/manifest.json", "ESMA MiCA CASPs"),
    ("fixtures/g1/sources/raw/esma-mica-ncasp.csv",
     "fixtures/g1/sources/manifest.json", "ESMA MiCA non-compliant CASPs"),
]


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001 — recorded, not raised
        return -1, str(e).encode()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def signals(body):
    """Light structural signals for later classification — not parsing."""
    h = body.decode("utf-8", errors="replace")
    tr = len(re.findall(r"<tr[\s>]", h, flags=re.I))
    pager = len(re.findall(r"__doPostBack|Page\$|paged|pagin", h, flags=re.I))
    export = sorted(set(re.findall(
        r'href="([^"]*(?:xls|xlsx|csv|Descargar|Export)[^"]*)"',
        h, flags=re.I)))[:5]
    err = bool(re.search(r"error (?:en|de)|no se ha podido|Se ha producido",
                         h, flags=re.I))
    return {"tr_count": tr, "pager_hints": pager,
            "export_links": export, "error_text_hint": err}


def slug(url):
    s = url.split("Consultas/", 1)[-1]
    s = s.replace(".aspx", "").replace("/", "__").replace("?", "_").replace("&", "_").replace("=", "-")
    return s


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = []

    urls = [CNMV + p for p in LIST_PAGES]
    urls += [f"{CNMV}busqueda.aspx?id={i}" for i in BUSQUEDA_IDS]
    urls += [f"{CNMV}listadoentidad.aspx?id=1&tipoent={t}" for t in LISTADOENT_TIPOENT]
    urls += [f"{CNMV}listadoentidad.aspx?id={i}&tipoent={t}" for i, t in LISTADOENT_EXTRA]
    urls += [f"{CNMV}mostrarlistados.aspx?id={i}" for i in MOSTRAR_IDS]

    for url in urls:
        status, body = fetch(url)
        name = f"CNMV__{slug(url)}.html"
        (RAW / name).write_bytes(body)
        entries.append({
            "source_id": name[:-5],
            "kind": "CAPTURED",
            "url": url, "http_status": status,
            "bytes": len(body), "sha256": sha256(body),
            "retrieved_at": now, "raw_file": f"raw/{name}",
            "signals": signals(body) if status == 200 else {},
        })
        print(f"{status}  {len(body):>8}  {name}")

    # Pagination pass: mostrarlistados pages are GET-paginated
    # (&page=N). Last page is derived from the already-frozen page-0
    # HTML — deterministic, no extra probing.
    for mid in MOSTRAR_IDS:
        base = RAW / f"CNMV__mostrarlistados_id-{mid}.html"
        h = base.read_text(encoding="utf-8", errors="replace")
        last = max((int(x) for x in re.findall(
            r'page=(\d+)[^"]*"? title="Ir a la', h)), default=-1)
        for pg in range(1, last + 1):
            url = f"{CNMV}mostrarlistados.aspx?id={mid}&page={pg}"
            status, body = fetch(url)
            name = f"CNMV__mostrarlistados_id-{mid}_page-{pg}.html"
            (RAW / name).write_bytes(body)
            entries.append({
                "source_id": name[:-5], "kind": "CAPTURED",
                "url": url, "http_status": status,
                "bytes": len(body), "sha256": sha256(body),
                "retrieved_at": now, "raw_file": f"raw/{name}",
                "signals": signals(body) if status == 200 else {},
            })
        if last > 0:
            print(f"paginated id={mid}: pages 1..{last} captured")

    # OpenDGSFP: export from exact upstream commit (artifact bytes).
    src = OPENDGSFP_REPO / OPENDGSFP_ARTIFACT
    data = src.read_bytes()
    name = "OpenDGSFP__opendgsfp-0.1.jsonl"
    (RAW / name).write_bytes(data)
    entries.append({
        "source_id": name[:-6],
        "kind": "UPSTREAM_EXPORT",
        "url": None,
        "upstream": {
            "repo": "OpenDGSFP", "commit": OPENDGSFP_COMMIT,
            "artifact": OPENDGSFP_ARTIFACT,
            "schema": "opendgsfp/0.1",
        },
        "http_status": None, "bytes": len(data),
        "sha256": sha256(data), "retrieved_at": now,
        "raw_file": f"raw/{name}",
        "records": sum(1 for _ in data.splitlines() if _.strip()),
        "signals": {},
    })
    print(f"OK   {len(data):>8}  {name}")

    for file, man, role in REUSED:
        p = ROOT / file
        if not p.exists():
            entries.append({"source_id": Path(file).stem, "kind": "REUSED",
                            "file": file, "original_manifest": man,
                            "role": role, "status": "MISSING"})
            print(f"MISSING {file}")
            continue
        b = p.read_bytes()
        entries.append({
            "source_id": Path(file).stem, "kind": "REUSED",
            "file": file, "original_manifest": man, "role": role,
            "status": "FROZEN", "bytes": len(b), "sha256": sha256(b),
        })

    manifest = {
        "capture_id": "universe-2026-09-19",
        "retrieved_at": now,
        "hash_algorithm": "SHA-256",
        "schema": "FINREG_G5_UNIVERSE_MANIFEST_V1",
        "note": ("Universe-level listing freeze. Raw snapshots only; "
                 "capture is separate from resolution (no canonical "
                 "entities, no merges, no fuzzy joins). Historical "
                 "manifests untouched."),
        "sources": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\nmanifest: {MANIFEST.relative_to(ROOT)}")
    print(f"sources: {len(entries)}  "
          f"captured: {sum(1 for e in entries if e['kind']=='CAPTURED')}  "
          f"reused: {sum(1 for e in entries if e['kind']=='REUSED')}  "
          f"errors: {sum(1 for e in entries if e.get('http_status',200)!=200 and e['kind']=='CAPTURED')}")


if __name__ == "__main__":
    sys.exit(main())
