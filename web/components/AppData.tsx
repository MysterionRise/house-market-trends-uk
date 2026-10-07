"use client";

/**
 * App-wide data and state:
 * - manifest + scores loaded once from the static data server
 * - the shared assistant state (AG-UI), read and written through useLiveability()
 * - scores recomputed in the browser for the current weights (useScores)
 */
import { UseAgentUpdate, useAgent } from "@copilotkit/react-core/v2";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { type Manifest, type ScoreData, loadManifest, loadScores, scoredIndicators } from "@/lib/data";
import { type ScoreResult, aggregate, percentileRank, percentileWithin, scoreLsoas } from "@/lib/scoring";
import type { LiveabilityState as WireState } from "@/lib/contracts.gen";
import { DEFAULT_STATE, type LiveabilityState, effectiveWeights, normaliseState } from "@/lib/state";
import { readHash, writeHash } from "@/lib/urlState";

interface DataContext {
  manifest: Manifest | null;
  scores: ScoreData | null;
  error: string | null;
}

const Ctx = createContext<DataContext>({ manifest: null, scores: null, error: null });

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<DataContext>({ manifest: null, scores: null, error: null });
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const manifest = await loadManifest();
        const scores = await loadScores(manifest);
        if (!cancelled) setValue({ manifest, scores, error: null });
      } catch (e) {
        if (!cancelled) setValue((v) => ({ ...v, error: String(e) }));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useData = () => useContext(Ctx);

/** The state shared with the assistant, plus an updater that syncs it back. */
export function useLiveability() {
  const { agent } = useAgent({ updates: [UseAgentUpdate.OnStateChanged] });
  const state = normaliseState(agent.state as Partial<WireState>);

  const update = useCallback(
    (fn: (s: LiveabilityState) => LiveabilityState) => {
      agent.setState(fn(normaliseState(agent.state as Partial<WireState>)));
    },
    [agent],
  );

  return { state, update };
}

/** Restores a shared view from the URL once and keeps the URL in step. Mount once:
 * restoring from every component that reads the state would undo the assistant's
 * updates whenever a new card mounts. */
export function UrlStateSync() {
  const { state, update } = useLiveability();
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    const fromHash = readHash();
    if (Object.keys(fromHash).length) update((s) => normaliseState({ ...s, ...fromHash } as Partial<WireState>));
  }, [update]);
  useEffect(() => {
    if (restored.current) writeHash(state);
  }, [state]);
  return null;
}

export interface LayerValues {
  /** England percentile (0–100) per LSOA for the active layer (NaN = no value) */
  lsoa: Float64Array;
  msoa: Map<string, number>;
  lad: Map<string, number>;
  result: ScoreResult;
  label: string;
}

/** Scores for the current weights and the values the map colours by. */
export function useScores(state: LiveabilityState): LayerValues | null {
  const { manifest, scores } = useData();
  // Recompute only when the weighting changes, not on every map move
  const themeKey = JSON.stringify(state.theme_weights);
  const indicatorKey = JSON.stringify(state.indicator_weights);
  const preset = state.preset;
  const weights = useMemo(() => {
    if (!manifest) return null;
    return effectiveWeights(manifest, {
      ...DEFAULT_STATE,
      preset,
      theme_weights: JSON.parse(themeKey),
      indicator_weights: JSON.parse(indicatorKey),
    });
  }, [manifest, preset, themeKey, indicatorKey]);
  const result = useMemo(() => {
    if (!manifest || !scores || !weights) return null;
    performance.mark("lix-score-start");
    const r = scoreLsoas(scores.indicators, scoredIndicators(manifest), weights.themes, weights.indicators);
    performance.measure("lix-score", "lix-score-start");
    return r;
  }, [manifest, scores, weights]);

  return useMemo(() => {
    if (!manifest || !scores || !result) return null;
    const layer = state.map.layer || "overall";
    let lsoa: Float64Array;
    let label: string;
    // Colour by England percentile: scores bunch in the middle of 0–100, so percentiles
    // use the whole colour ramp and read as "better than X% of England"
    if (layer.startsWith("theme:") && result.themes[layer.slice(6)]) {
      const t = layer.slice(6);
      lsoa = result.themes[t].percentile;
      label = manifest.themes[t]?.label ?? t;
    } else if (layer.startsWith("indicator:") && scores.indicators[layer.slice(10)]) {
      const id = layer.slice(10);
      lsoa = percentileRank(scores.indicators[id]);
      label = manifest.indicators.find((i) => i.id === id)?.label ?? id;
    } else {
      lsoa = result.overallPercentile;
      label = "Overall";
    }
    if (state.compare_within_urban_rural) {
      lsoa = percentileWithin(lsoa, scores.ruc);
      label += " (vs similar urban/rural areas)";
    }
    return {
      lsoa,
      msoa: aggregate(lsoa, scores.msoa, scores.population),
      lad: aggregate(lsoa, scores.lad, scores.population),
      result,
      label,
    };
  }, [manifest, scores, result, state.map.layer, state.compare_within_urban_rural]);
}
