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
  c?: 1;
}

export function readHash(): Partial<WireState> {
  if (typeof window === "undefined" || window.location.hash.length < 2) return {};
  try {
    const h: HashState = JSON.parse(decodeURIComponent(window.location.hash.slice(1)));
    return {
      ...(h.p ? { preset: h.p } : {}),
      ...(h.w ? { theme_weights: h.w } : {}),
      ...(h.c ? { compare_within_urban_rural: true } : {}),
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
    ...(state.compare_within_urban_rural ? { c: 1 as const } : {}),
  };
  const next = `#${encodeURIComponent(JSON.stringify(h))}`;
  if (window.location.hash !== next) window.history.replaceState(null, "", next);
}
