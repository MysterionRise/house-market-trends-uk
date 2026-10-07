/**
 * Choropleth ramp: one hue (blue), light → dark for higher scores in light mode.
 * In dark mode low scores recede into the dark surface and high scores are lightest.
 * Steps are the validated sequential ramp from the dataviz reference palette.
 */
const BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

export const RAMP_LIGHT = BLUE;
export const RAMP_DARK = [...BLUE].reverse();

export function ramp(dark: boolean): string[] {
  return dark ? RAMP_DARK : RAMP_LIGHT;
}

/** MapLibre expression: colour by feature-state "v" (0–100), grey when there is no value. */
export function fillColorExpression(dark: boolean): unknown[] {
  const stops = ramp(dark).flatMap((c, i, all) => [(i / (all.length - 1)) * 100, c]);
  return [
    "case",
    ["==", ["typeof", ["feature-state", "v"]], "number"],
    ["interpolate", ["linear"], ["feature-state", "v"], ...stops],
    dark ? "#383835" : "#e1e0d9",
  ];
}

export function gradientCss(dark: boolean): string {
  return `linear-gradient(to right, ${ramp(dark).join(", ")})`;
}
