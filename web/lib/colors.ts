/** The map's colours: the diverging ramp as MapLibre expressions and CSS, from lib/palette.ts. */
import { CHROME, FILL_OPACITY, RAMP, blend, type Mode } from "@/lib/palette";

export function ramp(dark: boolean): string[] {
  return RAMP[dark ? "dark" : "light"];
}

/** MapLibre expression: colour by feature-state "v" (0–100 percentile), grey when there is no value. */
export function fillColorExpression(dark: boolean): unknown[] {
  const stops = ramp(dark).flatMap((c, i, all) => [(i / (all.length - 1)) * 100, c]);
  return [
    "case",
    ["==", ["typeof", ["feature-state", "v"]], "number"],
    ["interpolate", ["linear"], ["feature-state", "v"], ...stops],
    CHROME[dark ? "dark" : "light"].noData,
  ];
}

/** The ramp as the eye sees it on the map: each stop composited over the surface at the fill opacity. */
export function gradientCss(dark: boolean, opacity: number = FILL_OPACITY.lsoa): string {
  const mode: Mode = dark ? "dark" : "light";
  const seen = RAMP[mode].map((c) => blend(c, CHROME[mode].surface, opacity));
  return `linear-gradient(to right, ${seen.join(", ")})`;
}

/** Colour of a consumer band (1 = bottom fifth … 5 = top fifth): the ramp at that fifth's middle. */
export function bandVar(band: number): string {
  const index = [0, 1, 3, 4, 6, 8][Math.max(1, Math.min(5, Math.round(band)))];
  return `var(--ramp-${index})`;
}
