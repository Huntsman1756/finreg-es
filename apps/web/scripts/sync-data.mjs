// Copies the frozen public projection into public/data so the static
// site serves it as downloadable artifacts. Build-time only.
import { cpSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(fileURLToPath(import.meta.url), "../../../..");
const src = path.join(root, "projections/public");
const dst = path.join(root, "apps/web/public/data");
mkdirSync(dst, { recursive: true });
cpSync(src, dst, { recursive: true });
console.log(`sync-data: ${src} -> ${dst}`);
