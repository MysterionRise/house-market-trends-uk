import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { aggregate, percentileRank, percentileWithin, scoreLsoas } from "./scoring";

// Shared with core/tests/test_golden.py: both implementations must match
const golden = JSON.parse(
  readFileSync(path.resolve(import.meta.dirname, "../../contracts/fixtures/scoring_golden.json"), "utf8"),
);

const toArray = (xs: (number | null)[]) => Float64Array.from(xs, (x) => (x === null ? NaN : x));
const close = (a: number, b: number | null) =>
  b === null ? Number.isNaN(a) : Math.abs(a - b) < 1e-9;

describe("golden cases match the Python scorer", () => {
  const norms = Object.fromEntries(
    golden.indicators.map((i: { id: string }) => [i.id, toArray(golden.normalised[`n__${i.id}`])]),
  );
  const indicators = golden.indicators.map((i: { id: string; theme: string; weight: number }) => ({
    id: i.id,
    theme: i.theme,
    weight: i.weight,
  }));

  for (const [name, c] of Object.entries(golden.cases) as [string, any][]) {
    it(name, () => {
      const r = scoreLsoas(norms, indicators, c.themes, c.indicators);
      const expected = golden.expected[name];
      for (const [col, values] of Object.entries(expected) as [string, (number | null)[]][]) {
        let got: Float64Array;
        if (col === "overall") got = r.overall;
        else if (col === "overall_pct") got = r.overallPercentile;
        else if (col === "coverage") got = r.coverage;
        else {
          const [kind, theme] = col.split("__");
          const t = r.themes[theme];
          got = kind === "theme" ? t.score : kind === "theme_pct" ? t.percentile : t.coverage;
        }
        values.forEach((v, i) => expect(close(got[i], v), `${name}.${col}[${i}]`).toBe(true));
      }
    });
  }
});

describe("helpers", () => {
  it("percentileRank averages ties and keeps NaN", () => {
    expect([...percentileRank(toArray([1, 2, 2, 3, null]))]).toEqual([0, 50, 50, 100, NaN]);
  });

  it("percentileWithin ranks inside each group", () => {
    const out = percentileWithin(toArray([1, 5, 10, 20]), ["u", "r", "u", "r"]);
    expect([...out]).toEqual([0, 0, 100, 100]);
  });

  it("aggregate is population weighted and skips NaN", () => {
    const m = aggregate(toArray([10, 20, null]), ["a", "a", "a"], toArray([1, 3, 5]));
    expect(m.get("a")).toBeCloseTo(17.5);
  });
});
