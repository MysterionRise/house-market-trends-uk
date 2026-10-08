/**
 * Browser port of lix_core.scoring: theme and overall scores from per-indicator
 * 0–100 scores, for any weighting, in a few milliseconds for every LSOA in the build.
 *
 * Must match the Python implementation exactly; both are tested against
 * contracts/fixtures/scoring_golden.json. Missing values are NaN.
 */

export const MIN_THEME_COVERAGE = 0.5;

export interface ScoredIndicator {
  id: string;
  theme: string;
  weight: number;
}

export interface ThemeResult {
  score: Float64Array;
  percentile: Float64Array;
  /** Percentile within the group passed to scoreLsoas (the nation), when given. */
  percentileWithin?: Float64Array;
  coverage: Float64Array;
}

export interface ScoreResult {
  themes: Record<string, ThemeResult>;
  overall: Float64Array;
  overallPercentile: Float64Array;
  overallPercentileWithin?: Float64Array;
  coverage: Float64Array;
}

/** 0–100 percentile, ties averaged, lowest 0 and highest 100; NaN stays NaN. */
export function percentileRank(values: Float64Array): Float64Array {
  const n = values.length;
  const out = new Float64Array(n).fill(NaN);
  const idx: number[] = [];
  for (let i = 0; i < n; i++) if (!Number.isNaN(values[i])) idx.push(i);
  const m = idx.length;
  if (m === 0) return out;
  if (m === 1) {
    out[idx[0]] = 50;
    return out;
  }
  idx.sort((a, b) => values[a] - values[b]);
  let start = 0;
  while (start < m) {
    let end = start;
    while (end + 1 < m && values[idx[end + 1]] === values[idx[start]]) end++;
    // Average 1-based rank of the tie group
    const rank = (start + end) / 2 + 1;
    const pct = ((rank - 1) / (m - 1)) * 100;
    for (let k = start; k <= end; k++) out[idx[k]] = pct;
    start = end + 1;
  }
  return out;
}

/** Weighted mean of 0–100 columns over the ones present; null below minCoverage. */
export function weightedScore(
  columns: Float64Array[],
  weights: number[],
  minCoverage = MIN_THEME_COVERAGE,
): { score: Float64Array; coverage: Float64Array } {
  const active = columns.map((c, i) => [c, weights[i]] as const).filter(([, w]) => w > 0);
  if (active.length === 0) throw new Error("At least one weight must be positive");
  const n = active[0][0].length;
  const total = active.reduce((s, [, w]) => s + w, 0);
  const score = new Float64Array(n);
  const coverage = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let num = 0;
    let avail = 0;
    for (const [col, w] of active) {
      const v = col[i];
      if (!Number.isNaN(v)) {
        num += v * w;
        avail += w;
      }
    }
    coverage[i] = avail / total;
    score[i] = avail / total >= minCoverage ? num / avail : NaN;
  }
  return { score, coverage };
}

/**
 * Theme and overall scores for every LSOA. With `groups` (one label per row, e.g. the
 * nation) each percentile is also taken within the group, as lix_core.scoring does with
 * `group=`.
 */
export function scoreLsoas(
  norms: Record<string, Float64Array>,
  indicators: ScoredIndicator[],
  themeWeights: Record<string, number>,
  multipliers: Record<string, number> = {},
  minCoverage = MIN_THEME_COVERAGE,
  groups?: string[],
): ScoreResult {
  const themeNames = [...new Set(indicators.map((i) => i.theme))].sort();
  const themes: Record<string, ThemeResult> = {};
  for (const theme of themeNames) {
    const members = indicators.filter((i) => i.theme === theme);
    const weights = members.map((i) => i.weight * (multipliers[i.id] ?? 1));
    if (!weights.some((w) => w > 0)) continue;
    const { score, coverage } = weightedScore(
      members.map((i) => norms[i.id]),
      weights,
      minCoverage,
    );
    themes[theme] = { score, percentile: percentileRank(score), coverage };
    if (groups) themes[theme].percentileWithin = percentileWithin(score, groups);
  }
  const present = Object.keys(themes);
  const { score: overall, coverage } = weightedScore(
    present.map((t) => themes[t].score),
    present.map((t) => themeWeights[t] ?? 0),
    minCoverage,
  );
  const result: ScoreResult = { themes, overall, overallPercentile: percentileRank(overall), coverage };
  if (groups) result.overallPercentileWithin = percentileWithin(overall, groups);
  return result;
}

/** Percentile within groups (e.g. urban/rural class), for like-for-like comparison. */
export function percentileWithin(values: Float64Array, groups: string[]): Float64Array {
  const out = new Float64Array(values.length).fill(NaN);
  const byGroup = new Map<string, number[]>();
  groups.forEach((g, i) => byGroup.set(g, [...(byGroup.get(g) ?? []), i]));
  for (const members of byGroup.values()) {
    const ranks = percentileRank(Float64Array.from(members, (i) => values[i]));
    members.forEach((i, k) => (out[i] = ranks[k]));
  }
  return out;
}

/** Population-weighted mean of LSOA values per parent area (MSOA or local authority). */
export function aggregate(
  values: Float64Array,
  parents: string[],
  population: Float64Array,
): Map<string, number> {
  const sums = new Map<string, [number, number]>();
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (Number.isNaN(v)) continue;
    const acc = sums.get(parents[i]) ?? [0, 0];
    acc[0] += v * population[i];
    acc[1] += population[i];
    sums.set(parents[i], acc);
  }
  return new Map([...sums].map(([k, [s, w]]) => [k, s / w]));
}
