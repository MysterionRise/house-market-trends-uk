import { describe, expect, it } from "vitest";

import { bandVar, fillColorExpression, gradientCss } from "./colors";
import {
  CHROME,
  DIVERGING,
  RAMP,
  THEME_COLORS,
  THEME_ORDER,
  blend,
  contrast,
  deltaE,
  hexToOklab,
  oklch,
  tokensCss,
  type Mode,
} from "./palette";

const MODES: Mode[] = ["light", "dark"];

describe("colour maths", () => {
  it("round-trips OKLCH through hex", () => {
    const hex = oklch(0.6, 0.15, 44);
    const [L] = hexToOklab(hex);
    expect(hex).toMatch(/^#[0-9a-f]{6}$/);
    expect(L).toBeCloseTo(0.6, 2);
  });

  it("computes WCAG contrast", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrast("#ffffff", "#000000")).toBeCloseTo(21, 1);
  });

  it("blends over a surface", () => {
    expect(blend("#000000", "#ffffff", 0)).toBe("#ffffff");
    expect(blend("#000000", "#ffffff", 1)).toBe("#000000");
  });
});

describe.each(MODES)("%s chrome", (mode) => {
  const c = CHROME[mode];

  it("text passes 4.5:1 on both surfaces (small labels use text-muted)", () => {
    for (const surface of [c.page, c.surface]) {
      expect(contrast(c.textPrimary, surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(c.textSecondary, surface)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(c.textMuted, surface)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("focus ring, critical text and no-data are visible on the surface", () => {
    expect(contrast(c.focus, c.surface)).toBeGreaterThanOrEqual(3);
    expect(contrast(c.critical, c.surface)).toBeGreaterThanOrEqual(3);
    expect(deltaE(c.noData, RAMP[mode][4])).toBeGreaterThanOrEqual(8);
  });
});

describe.each(MODES)("%s map ramp", (mode) => {
  const ramp = RAMP[mode];
  const L = (hex: string) => hexToOklab(hex)[0];

  it("has nine stops with a neutral middle", () => {
    expect(ramp).toHaveLength(9);
    const [, a, b] = hexToOklab(ramp[4]);
    expect(Math.hypot(a, b)).toBeLessThan(0.03);
  });

  it("is monotone in lightness on each arm, poles most saturated", () => {
    // Light mode: poles dark, middle pale. Dark mode: the reverse.
    const sign = mode === "light" ? 1 : -1;
    for (let i = 0; i < 4; i++) expect(sign * (L(ramp[i + 1]) - L(ramp[i]))).toBeGreaterThan(0.04);
    for (let i = 4; i < 8; i++) expect(sign * (L(ramp[i]) - L(ramp[i + 1]))).toBeGreaterThan(0.04);
  });

  it("poles stand out from the surface and from each other", () => {
    expect(contrast(ramp[0], CHROME[mode].surface)).toBeGreaterThanOrEqual(3);
    expect(contrast(ramp[8], CHROME[mode].surface)).toBeGreaterThanOrEqual(3);
    expect(deltaE(ramp[0], ramp[8])).toBeGreaterThanOrEqual(15);
  });

  it("the heatmap reuses the ramp's warm and cool steps", () => {
    expect(ramp).toContain(DIVERGING[mode].neg);
    expect(ramp).toContain(DIVERGING[mode].pos);
  });
});

describe.each(MODES)("%s theme colours", (mode) => {
  const colours = THEME_ORDER.map((t) => THEME_COLORS[mode][t]);

  it("covers every theme with a distinct colour", () => {
    expect(new Set(colours).size).toBe(THEME_ORDER.length);
  });

  it("keeps neighbours in the on-screen order apart for full-colour vision (ΔE ≥ 15)", () => {
    // Colour-blind separation of the same order was checked with the data-viz validator
    // (docs/design.md); this guards against accidental re-ordering or re-stepping
    for (let i = 1; i < colours.length; i++) expect(deltaE(colours[i - 1], colours[i])).toBeGreaterThanOrEqual(15);
  });

  it("is never confused with the ramp's poles", () => {
    for (const c of colours) {
      expect(deltaE(c, RAMP[mode][0])).toBeGreaterThanOrEqual(8);
      expect(deltaE(c, RAMP[mode][8])).toBeGreaterThanOrEqual(8);
    }
  });
});

describe("tokens and map expressions", () => {
  it("writes every token in all three scopes", () => {
    const css = tokensCss();
    expect(css).toContain(":root {");
    expect(css).toContain(':root:not([data-theme="light"])');
    expect(css).toContain(':root[data-theme="dark"]');
    for (const t of THEME_ORDER) expect(css.match(new RegExp(`--theme-${t}:`, "g"))).toHaveLength(3);
    expect(css.match(/--ramp-8:/g)).toHaveLength(3);
    expect(css).not.toContain("series-1");
  });

  it("maps 0–100 onto the ramp and no value onto no-data", () => {
    const expr = fillColorExpression(false) as unknown[];
    expect(expr[0]).toBe("case");
    expect(expr[3]).toBe(CHROME.light.noData);
    const interpolate = expr[2] as unknown[];
    expect(interpolate.slice(3)).toEqual(RAMP.light.flatMap((c, i) => [i * 12.5, c]));
  });

  it("composites the legend at the fill opacity", () => {
    expect(gradientCss(false)).toMatch(/^linear-gradient\(to right, #[0-9a-f]{6}(, #[0-9a-f]{6}){8}\)$/);
    expect(gradientCss(false)).not.toContain(RAMP.light[0]);
    expect(gradientCss(false, 1)).toContain(RAMP.light[0]);
  });

  it("gives bands the ramp's fifths", () => {
    expect(bandVar(1)).toBe("var(--ramp-1)");
    expect(bandVar(3)).toBe("var(--ramp-4)");
    expect(bandVar(5)).toBe("var(--ramp-8)");
  });
});
