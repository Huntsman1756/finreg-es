// G4-G2 build verification — asserts preregistered cases W01–W10 on dist/.
// Run after `npm run build`. Exits 1 on first failure set.
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import path from "node:path";

const DIST = path.resolve(process.cwd(), "dist");
const failures = [];
const ok = (cond, name) => { if (!cond) failures.push(name); else console.log("PASS", name); };

function html(rel) {
  const p = path.join(DIST, rel, "index.html");
  return existsSync(p) ? readFileSync(p, "utf-8") : "";
}
function* walk(dir) {
  for (const f of readdirSync(dir)) {
    const p = path.join(dir, f);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

// W01 — required routes + 20 entity pages + index
for (const r of ["", "buscar", "cambios", "metodologia", "fuentes", "datos",
                 "aviso-legal", "privacidad", "reguladores", "entidad"])
  ok(html(r).length > 0 || existsSync(path.join(DIST, r === "" ? "index.html" : r)), `W01 route /${r}/`);
const entities = readdirSync(path.join(DIST, "entidad")).filter(d => d !== "index.html");
ok(entities.length === 20, `W01 20 entity pages (found ${entities.length})`);

// W02 — ESI-4: impersonations framed as "no guarda relación"
const esi4 = html("entidad/esi-a83217281");
ok(esi4.includes("no guarda relación") && esi4.includes("ABANTE"), "W02 ESI-4 impersonations");
ok(!esi4.includes("advertencia contra"), "W02 no warning-against framing");

// W03 — ESI-1: NO HISTORICAL EVIDENCE + services visible
const esi1 = html("entidad/esi-a87515540");
ok(esi1.includes("NO HISTORICAL EVIDENCE"), "W03 ESI-1 NO HISTORICAL EVIDENCE");
ok(esi1.includes("Recepción y transmisión"), "W03 ESI-1 services");
// W03b — alantrafx (reg 245) must NOT appear as attributed clone
ok(!esi1.includes("alantrafx"), "W03b ESI-1 no false attribution (alantrafx→245)");

// W04 — SAN-1: sanction + fs states labelled
const san1 = html("entidad/sgiic-a28867000");
ok(san1.includes("17/07/2026") && san1.includes("BOE"), "W04 SAN-1 sanction + BOE ref");
ok(san1.includes("fs pedido"), "W04 SAN-1 requested_fs visible");

// W05 — INS-5: deregistered with bounded date, no invented exact date
const ins5 = html("entidad/ins-e0006");
ok(ins5.includes("Cancelada") && ins5.includes("UNKNOWN"), "W05 INS-5 bounded cancellation");

// W06 — Pagefind index exists and covers entity pages
ok(existsSync(path.join(DIST, "pagefind/pagefind-entry.json")), "W06 pagefind index");

// W07 — downloadable data
for (const f of ["manifest.json", "entities.json", "changes.json", "sources.json"])
  ok(existsSync(path.join(DIST, "data", f)), `W07 data/${f}`);

// W08 — entity pages carry no <script> at all
let scriptsInEntities = 0;
for (const d of entities) {
  if (d === "index.html") continue;
  const h = html(`entidad/${d}`);
  if (/<script/i.test(h)) scriptsInEntities++;
}
ok(scriptsInEntities === 0, `W08 entity pages script-free (${scriptsInEntities} violators)`);

// W09 — no rating/score features (footer disclaimer mentions are allowed)
const banned = /class="[^"]*(rating|score|rank)|data-rating|risk_score|reputaci/i;
let w09bad = [];
for (const p of walk(DIST)) {
  if (p.endsWith(".html") && banned.test(readFileSync(p, "utf-8"))) w09bad.push(p);
}
ok(w09bad.length === 0, `W09 no rating/score features (${w09bad.length} hits)`);

// W10 — sitemap + breadcrumbs
ok(existsSync(path.join(DIST, "sitemap-index.xml")), "W10 sitemap");
ok(esi4.includes('aria-label="Miga de pan"') || esi4.includes("crumbs"), "W10 breadcrumbs");

// W11 — basic a11y invariants (documented light check; full axe deferred)
const home = html("");
ok(/<html lang="es">/.test(home), "W11 lang attribute");
ok((home.match(/<h1/g) ?? []).length === 1, "W11 single h1 on home");
ok(/<label for="q">/.test(home), "W11 labelled search input");
ok((esi4.match(/<h1/g) ?? []).length === 1, "W11 single h1 on ficha");
ok(!/<img(?![^>]*alt=)/i.test(home + esi4), "W11 all images have alt");
ok(/aria-label="Principal"/.test(home), "W11 labelled main nav");

if (failures.length) {
  console.error("\nFAILURES:", failures.length);
  failures.forEach(f => console.error(" -", f));
  process.exit(1);
}
console.log("\nAll W-checks passed.");
