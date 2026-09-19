// G4-G3 browser verification — axe, keyboard, reflow, JS-disabled,
// console errors, screenshots, perf budgets, link/SEO crawl.
// Serves apps/web/dist statically; writes JSON evidence to
// fixtures/g4/browser/g3-browser-<date>.json + PNG screenshots.
import { chromium } from "playwright";
import http from "node:http";
import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync, existsSync } from "node:fs";
import { join, extname, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(HERE, "../dist");
const OUT = resolve(HERE, "../../../fixtures/g4/browser");
const DATE = new Date().toISOString().slice(0, 10).replaceAll("-", "");
mkdirSync(OUT, { recursive: true });

const MIME = { ".html": "text/html", ".json": "application/json", ".js": "text/javascript",
  ".css": "text/css", ".xml": "application/xml", ".png": "image/png",
  ".svg": "image/svg+xml", ".txt": "text/plain", ".webmanifest": "application/manifest+json" };

const server = http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const f = join(DIST, p);
  if (!f.startsWith(DIST) || !existsSync(f) || !statSync(f).isFile()) {
    res.writeHead(404).end("nf"); return;
  }
  res.writeHead(200, { "content-type": MIME[extname(f)] ?? "application/octet-stream" })
    .end(readFileSync(f));
});
await new Promise(r => server.listen(0, r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const R = { date: new Date().toISOString(), base: "dist/", checks: {}, evidence: {} };
const fail = (k, msg) => { R.checks[k] = { status: "FAIL", detail: msg }; };
const pass = (k, detail = "") => { R.checks[k] = { status: "PASS", detail }; };

const PAGES = ["/", "/entidad/esi-a87515540/", "/entidad/esi-a83217281/",
  "/buscar/", "/fuentes/"];
const REFLOW_PAGES = [...PAGES, "/entidad/sgiic-a84144625/", "/entidad/"];

const browser = await chromium.launch();
const axeSrc = readFileSync(resolve(HERE, "../node_modules/axe-core/axe.min.js"), "utf8");

// ---------- R-06 axe ----------
{
  const page = await browser.newPage();
  const all = {};
  for (const p of PAGES) {
    await page.goto(`${BASE}${p}`, { waitUntil: "load" });
    await page.addScriptTag({ content: axeSrc });
    const res = await page.evaluate(async () => await axe.run());
    all[p] = { violations: res.violations.map(v => ({ id: v.id, impact: v.impact,
      nodes: v.nodes.length, target: v.nodes[0]?.target })) };
  }
  R.evidence.axe = all;
  const total = Object.values(all).flatMap(v => v.violations);
  total.length === 0 ? pass("R06_axe", "0 violations on 5 pages")
    : fail("R06_axe", JSON.stringify(total));
  await page.close();
}

// ---------- console errors + JS-disabled ----------
{
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", e => errors.push(`pageerror: ${e.message}`));
  page.on("console", m => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  for (const p of PAGES) await page.goto(`${BASE}${p}`, { waitUntil: "load" });
  await page.close();
  errors.length === 0 ? pass("console_clean", "0 uncaught errors")
    : fail("console_clean", errors.join(" | "));

  const ctx = await browser.newContext({ javaScriptEnabled: false });
  const pj = await ctx.newPage();
  await pj.goto(`${BASE}/entidad/esi-a87515540/`);
  const noJs = await pj.evaluate(() => ({
    h1: document.querySelector("h1")?.textContent?.trim(),
    tables: document.querySelectorAll("table").length,
    scripts: document.querySelectorAll("script").length,
    auditsVisible: !!document.body.textContent.match(/Ejercicio\s*Auditora/),
    managedNote: document.body.textContent.includes("ALEMANIA"),
  }));
  R.evidence.js_disabled = noJs;
  (noJs.h1 && noJs.tables >= 4 && noJs.scripts === 0 && noJs.auditsVisible && noJs.managedNote)
    ? pass("R07_js_disabled", `h1+${noJs.tables} tables sin JS`)
    : fail("R07_js_disabled", JSON.stringify(noJs));
  await ctx.close();
}

// ---------- R-07 keyboard + reflow ----------
{
  const page = await browser.newPage();
  await page.goto(`${BASE}/`);
  const kbd = await page.evaluate(async () => {
    const seen = [];
    const active = () => document.activeElement;
    for (let i = 0; i < 15; i++) {
      const ev = new KeyboardEvent("keydown", { key: "Tab", bubbles: true });
      const ae = active();
      if (ae && ae !== document.body) {
        const cs = getComputedStyle(ae);
        seen.push({ tag: ae.tagName, text: (ae.textContent || "").trim().slice(0, 30),
          outline: cs.outlineStyle !== "none" || cs.boxShadow !== "none" });
      }
      ae.dispatchEvent(ev);
      const next = ae.nextElementSibling ?? document.body;
      (next || document.body).focus?.();
    }
    return { focusable: seen.length, visibleFocus: seen.filter(s => s.outline).length, first: seen[0] };
  });
  // real Tab key via playwright (evaluate can't synthesize trusted events)
  const realOrder = [];
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    realOrder.push(await page.evaluate(() => {
      const ae = document.activeElement;
      return ae ? `${ae.tagName}:${(ae.textContent || ae.getAttribute("aria-label") || "").trim().slice(0, 24)}` : "?";
    }));
  }
  const visFocus = await page.evaluate(() => {
    const ae = document.activeElement;
    if (!ae || ae === document.body) return null;
    const cs = getComputedStyle(ae);
    return { el: ae.tagName, outline: cs.outlineStyle, width: cs.outlineWidth, color: cs.outlineColor };
  });
  R.evidence.keyboard = { order: realOrder, focusStyle: visFocus };
  (realOrder.length >= 3 && realOrder.every(s => s !== "?" && !s.startsWith("BODY")))
    ? pass("R07_keyboard", `tab order: ${realOrder.slice(0, 4).join(" → ")}…`)
    : fail("R07_keyboard", JSON.stringify(realOrder));

  const reflow = {};
  for (const p of REFLOW_PAGES) {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(`${BASE}${p}`);
    reflow[p] = await page.evaluate(() => ({
      sw: document.documentElement.scrollWidth, vw: innerWidth }));
  }
  R.evidence.reflow320 = reflow;
  const over = Object.entries(reflow).filter(([, v]) => v.sw > v.vw + 1);
  over.length === 0 ? pass("R07_reflow320", "no horizontal overflow on 7 pages")
    : fail("R07_reflow320", JSON.stringify(over));
  await page.close();
}

// ---------- R-08 screenshots (baseline congelada post-refresh) ----------
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const shots = {};
  for (const [name, p] of [["home", "/"], ["esi1", "/entidad/esi-a87515540/"],
                           ["esi4", "/entidad/esi-a83217281/"],
                           ["sgiic5", "/entidad/sgiic-a84144625/"], ["buscar", "/buscar/"]]) {
    await page.goto(`${BASE}${p}`, { waitUntil: "load" });
    const f = join(OUT, `g3-${name}-${DATE}.png`);
    await page.screenshot({ path: f, fullPage: name !== "buscar" });
    shots[name] = `fixtures/g4/browser/g3-${name}-${DATE}.png`;
  }
  R.evidence.screenshots = shots;
  pass("R08_screenshots", Object.keys(shots).join(","));
  await page.close();
}

// ---------- R-09 performance budgets ----------
{
  const gz = f => zlib.gzipSync(readFileSync(f)).length;
  const pageBytes = p => {
    const f = join(DIST, p, "index.html");
    return { raw: statSync(f).size, gz: gz(f) };
  };
  const budgets = {};
  for (const p of ["/", "/entidad/esi-a87515540/", "/entidad/sgiic-a84144625/", "/buscar/"]) {
    budgets[p] = pageBytes(p);
  }
  // CSS is inlined per page; pagefind payload is lazy (only /buscar/).
  let pagefindGz = 0;
  const walkPf = d => { for (const f of readdirSync(d, { withFileTypes: true })) {
    const p = join(d, f.name);
    if (f.isDirectory()) walkPf(p); else pagefindGz += gz(p);
  } };
  walkPf(join(DIST, "pagefind"));
  const heaviest = Math.max(...Object.values(budgets).map(b => b.gz));
  R.evidence.perf = { pages: budgets, pagefind_lazy_gz: pagefindGz,
    heaviest_page_gz: heaviest, budget_gz: 600 * 1024 };
  heaviest < 600 * 1024
    ? pass("R09_perf", `heaviest page ${(heaviest / 1024).toFixed(0)}KB gz < 600KB`)
    : fail("R09_perf", `heaviest ${(heaviest / 1024).toFixed(0)}KB gz`);

  // request count + no external render-blocking on ficha
  const page = await browser.newPage();
  const reqs = [];
  page.on("request", r => reqs.push(r.url()));
  await page.goto(`${BASE}/entidad/esi-a87515540/`, { waitUntil: "networkidle" });
  const external = reqs.filter(u => !u.startsWith(BASE));
  const renderBlocking = await page.evaluate(() =>
    [...document.querySelectorAll('link[rel="stylesheet"], script[src]')]
      .map(e => e.href || e.src).filter(u => u && !u.startsWith(location.origin)));
  R.evidence.requests = { count: reqs.length, external, renderBlocking };
  (reqs.length < 40 && external.length === 0 && renderBlocking.length === 0)
    ? pass("R09_requests", `${reqs.length} reqs, 0 external, 0 render-blocking`)
    : fail("R09_requests", JSON.stringify(R.evidence.requests));
  await page.close();
}

// ---------- R-10 SEO / link / URL contract ----------
{
  const htmlFiles = [];
  const walk = d => { for (const f of readdirSync(d, { withFileTypes: true })) {
    const p = join(d, f.name);
    if (f.isDirectory()) walk(p); else if (f.name.endsWith(".html")) htmlFiles.push(p);
  } };
  walk(DIST);
  const missing = [], seo = { canonical: 0, title: 0, desc: 0, noTrailingSlash: [] };
  for (const f of htmlFiles) {
    const h = readFileSync(f, "utf8");
    if (h.includes("rel=\"canonical\"")) seo.canonical++;
    if (/<title>[^<]+<\/title>/.test(h)) seo.title++;
    if (h.includes("name=\"description\"")) seo.desc++;
    for (const m of h.matchAll(/href="(\/[^"#]*)"/g)) {
      const href = m[1];
      if (href.startsWith("//") || href.startsWith("/pagefind/") || href.startsWith("/data/")) continue;
      const target = join(DIST, href, "index.html");
      const targetFile = join(DIST, href);
      if (!existsSync(target) && !existsSync(targetFile)) missing.push(`${f.slice(DIST.length)} -> ${href}`);
    }
  }
  const sitemap = readFileSync(join(DIST, "sitemap-index.xml"), "utf8");
  const sitemapXml = readFileSync(join(DIST, "sitemap-0.xml"), "utf8");
  const urls = (sitemapXml.match(/<loc>/g) || []).length;
  R.evidence.seo = { htmlFiles: htmlFiles.length, ...seo, sitemapUrls: urls,
    brokenLinks: missing.slice(0, 10), brokenCount: missing.length };
  (missing.length === 0 && urls >= 30 && seo.title === htmlFiles.length && seo.desc === htmlFiles.length)
    ? pass("R10_seo_links", `${htmlFiles.length} pages, ${urls} sitemap urls, 0 broken`)
    : fail("R10_seo_links", JSON.stringify(R.evidence.seo).slice(0, 500));
}

await browser.close();
server.close();
const verdict = Object.values(R.checks).every(c => c.status === "PASS") ? "ALL_PASS" : "FAILURES";
R.verdict = verdict;
writeFileSync(join(OUT, `g3-browser-${DATE}.json`), JSON.stringify(R, null, 1) + "\n");
console.log(JSON.stringify(R.checks, null, 1));
console.log("VERDICT:", verdict, "->", `fixtures/g4/browser/g3-browser-${DATE}.json`);
process.exit(verdict === "ALL_PASS" ? 0 : 1);
