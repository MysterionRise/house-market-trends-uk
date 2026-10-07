/**
 * Data the browser loads once: the build manifest (indicators, themes, presets,
 * sources) and scores.parquet (per-LSOA indicator scores as uint16 × 100).
 */
import { asyncBufferFromUrl, parquetReadObjects } from "hyparquet";

import { DATA_URL } from "./config";
import type { ScoredIndicator } from "./scoring";

export const MISSING_U16 = 65535;

export interface IndicatorMeta extends ScoredIndicator {
  label: string;
  description: string;
  unit: string;
  direction: "higher_better" | "lower_better";
  role: "scored" | "context" | "diagnostic";
  caveats: string | null;
  sources: string[];
}

export interface PresetMeta {
  label: string;
  description: string;
  themes: Record<string, number>;
  indicators: Record<string, number>;
}

export interface Manifest {
  generated_at: string;
  scored_indicators: string[];
  indicators: IndicatorMeta[];
  themes: Record<string, { label: string; description: string }>;
  default_preset: string;
  presets: Record<string, PresetMeta>;
  sources: Record<string, { title: string; licence: string; attribution: string; version?: string }>;
  /** Neighbourhoods in this build (33,755 for England; fewer in a demo cut) */
  lsoa_count?: number;
  /** A small cut of the full build (CI and quick starts): see `lix demo-data` */
  demo?: boolean;
  /** Spearman correlations between scored indicators, ordered by theme */
  correlations?: { ids: string[]; themes: string[]; rho: number[][] } | null;
}

export interface ScoreData {
  n: number;
  codes: string[];
  msoa: string[];
  lad: string[];
  ruc: string[];
  urban: boolean[];
  population: Float64Array;
  /** Indicator id → 0–100 score per LSOA (NaN when missing) */
  indicators: Record<string, Float64Array>;
  flags: Uint32Array;
  index: Map<string, number>;
}

export async function loadManifest(): Promise<Manifest> {
  const res = await fetch(`${DATA_URL}/manifest.json`);
  if (!res.ok) throw new Error(`manifest.json: HTTP ${res.status}`);
  return res.json();
}

export async function loadScores(manifest: Manifest): Promise<ScoreData> {
  const file = await asyncBufferFromUrl({ url: `${DATA_URL}/scores.parquet` });
  const rows = (await parquetReadObjects({ file })) as Record<string, unknown>[];
  const n = rows.length;
  const indicators: Record<string, Float64Array> = {};
  for (const id of manifest.scored_indicators) {
    const col = new Float64Array(n);
    for (let i = 0; i < n; i++) {
      const v = rows[i][id] as number;
      col[i] = v === MISSING_U16 || v == null ? NaN : v / 100;
    }
    indicators[id] = col;
  }
  const codes = rows.map((r) => r.lsoa21cd as string);
  return {
    n,
    codes,
    msoa: rows.map((r) => r.msoa21cd as string),
    lad: rows.map((r) => r.lad_cd as string),
    ruc: rows.map((r) => r.ruc21cd as string),
    urban: rows.map((r) => Boolean(r.urban)),
    population: Float64Array.from(rows, (r) => Number(r.population)),
    indicators,
    flags: Uint32Array.from(rows, (r) => Number(r.quality_flags)),
    index: new Map(codes.map((c, i) => [c, i])),
  };
}

export function scoredIndicators(manifest: Manifest): ScoredIndicator[] {
  const byId = new Map(manifest.indicators.map((i) => [i.id, i]));
  return manifest.scored_indicators.map((id) => {
    const i = byId.get(id)!;
    return { id, theme: i.theme, weight: i.weight };
  });
}
