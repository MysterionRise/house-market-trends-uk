/**
 * Shareable views: preset, weight overrides, map layer and selected area in the URL hash.
 */
import type { LiveabilityState as WireState } from "./contracts.gen";
import type { LiveabilityState } from "./state";

interface HashState {
  p?: string;
  w?: Record<string, number>;
  l?: string;
  s?: string;
  /** compare against: "nation" or "urban_rural" (1 is the old urban/rural flag) */
  c?: 1 | "nation" | "urban_rural";
}

export function readHash(): Partial<WireState> {
  if (typeof window === "undefined" || window.location.hash.length < 2) return {};
  try {
    const h: HashState = JSON.parse(decodeURIComponent(window.location.hash.slice(1)));
    return {
      ...(h.p ? { preset: h.p } : {}),
      ...(h.w ? { theme_weights: h.w } : {}),
      ...(h.c === 1 || h.c === "urban_rural"
        ? { compare_within: "urban_rural" as const, compare_within_urban_rural: true }
        : h.c === "nation"
          ? { compare_within: "nation" as const }
          : {}),
      map: {
        bbox: null,
        layer: h.l ?? "overall",
        highlighted: [],
        selected: h.s ?? null,
        pois: [],
      },
    };
  } catch {
    return {};
  }
}

export function writeHash(state: LiveabilityState): void {
  const h: HashState = {
    p: state.preset,
    ...(Object.keys(state.theme_weights ?? {}).length ? { w: state.theme_weights } : {}),
    ...(state.map.layer !== "overall" ? { l: state.map.layer } : {}),
    ...(state.map.selected ? { s: state.map.selected } : {}),
    ...(state.compare_within !== "uk" ? { c: state.compare_within } : {}),
  };
  const next = `#${encodeURIComponent(JSON.stringify(h))}`;
  if (window.location.hash !== next) window.history.replaceState(null, "", next);
}
