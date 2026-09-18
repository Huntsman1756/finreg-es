import { readFileSync } from "node:fs";
import path from "node:path";

// Build-time only: cwd is apps/web (npm scripts run there).
const PROJECTIONS = path.resolve(process.cwd(), "../../projections/public");

function load<T = any>(rel: string): T {
  return JSON.parse(readFileSync(path.join(PROJECTIONS, rel), "utf-8")) as T;
}

export const manifest = load("manifest.json");
export const index = load("entities.json");
export const changes = load("changes.json");
export const sources = load("sources.json");

export interface EntityRecord {
  schema: string;
  id: string;
  identity: {
    legal_name: string;
    aliases: string[];
    identifiers: { scheme: string; value: string; country?: string }[];
    resolution: string;
  };
  status: { value: string; as_of: string; basis: string; source_value?: string };
  registrations: any[];
  permissions: any;
  locations: any;
  organisation: any;
  regulatory_record: {
    sanctions: any[]; appeals: any[]; direct_warnings: any[];
    impersonations: any[]; candidates: any[];
  };
  timeline: { date_or_interval: string | string[]; kind: string; summary: string; evidence: string }[];
  sources: any[];
  coverage: Record<string, string>;
  freshness: { last_successful_refresh: string; source_status: string };
}

export function loadEntity(id: string): EntityRecord {
  return load<EntityRecord>(`entities/${id}.json`);
}

export function verticalLabel(id: string): string {
  const p = id.split("-")[0];
  return { esi: "ESI · CNMV", sgiic: "SGIIC · CNMV", ede: "EDE · BdE/EBA", ins: "Seguros · DGSFP" }[p] ?? p;
}

export const KIND_LABEL: Record<string, string> = {
  EXPLICIT_OFFICIAL_EVENT: "Hecho oficial fechado",
  OFFICIAL_AS_OF_STATE: "Estado oficial a fecha",
  OFFICIAL_DOCUMENT_DERIVATION: "Derivado de documento oficial",
  OBSERVED_CHANGE: "Cambio observado (intervalo)",
};
