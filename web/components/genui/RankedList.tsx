"use client";

import { useLiveability } from "@/components/AppData";
import { Card, Muted, formatValue } from "@/components/ui";
import type { RankResult } from "@/lib/contracts.gen";

// Below this share of plausible weightings keeping it in the list, a result is a close call
const CLOSE_CALL = 0.6;

export function RankedList({ result }: { result: RankResult }) {
  const { update } = useLiveability();
  const where = result.within ? ` ${result.within.startsWith("within") ? "" : "in "}${result.within}` : " in England";
  const level = result.level === "msoa" ? "neighbourhoods" : "small areas";

  return (
    <Card
      testId="ranked-list"
      title={`Top ${result.results.length} ${level}${where}`}
      subtitle={`${result.candidates.toLocaleString("en-GB")} matched · weighting: ${result.preset}`}
    >
      <ol className="divide-y divide-[var(--border)]">
        {result.results.map((r) => (
          <li key={r.code}>
            <button
              className="grid w-full grid-cols-[1.5rem_1fr_auto] items-center gap-2 py-1.5 text-left hover:bg-[var(--hover)]"
              onClick={() =>
                update((s) => ({
                  ...s,
                  map: {
                    ...s.map,
                    selected: r.level === "lsoa" ? r.code : s.map.selected,
                    highlighted: [r.code],
                    bbox: [r.centre.lon - 0.025, r.centre.lat - 0.015, r.centre.lon + 0.025, r.centre.lat + 0.015],
                  },
                }))
              }
            >
              <span className="text-xs tabular-nums text-[var(--text-muted)]">{r.rank}</span>
              <span className="min-w-0">
                <span className="flex items-baseline gap-1.5">
                  <span className="truncate font-medium">{r.name}</span>
                  {r.stability != null && r.stability < CLOSE_CALL && (
                    <span
                      className="shrink-0 rounded border border-[var(--border)] px-1 text-[10px] text-[var(--text-muted)]"
                      title={`Stays in this top ${result.results.length} under ${Math.round(r.stability * 100)}% of plausible weightings`}
                    >
                      close call
                    </span>
                  )}
                </span>
                <span className="block truncate text-xs text-[var(--text-secondary)]">
                  {r.local_authority}
                  {r.median_price != null && ` · typical price ${formatValue(r.median_price, "£")}`}
                </span>
              </span>
              <span className="text-right">
                <span className="block text-base font-semibold tabular-nums">{r.overall?.toFixed(0) ?? "–"}</span>
                <span className="block h-1.5 w-14 rounded-r-[4px] bg-[var(--track)]">
                  <span className="block h-1.5 rounded-r-[4px] bg-[var(--accent)]" style={{ width: `${r.overall ?? 0}%` }} />
                </span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <Muted>
        Click an area to show it on the map.
        {result.results.some((r) => r.stability != null && r.stability < CLOSE_CALL) &&
          " “Close call”: small changes to the weights could swap it out of this list."}
      </Muted>
    </Card>
  );
}
