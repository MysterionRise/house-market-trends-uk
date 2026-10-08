"use client";

import { useLocale, useTranslations } from "next-intl";

import { useLiveability } from "@/components/AppData";
import { Card, Muted, formatValue } from "@/components/ui";
import type { RankResult } from "@/lib/contracts.gen";
import { useCoverageName } from "@/lib/copy";

// Below this share of plausible weightings keeping it in the list, a result is a close call
const CLOSE_CALL = 0.6;

export function RankedList({ result }: { result: RankResult }) {
  const { update } = useLiveability();
  const t = useTranslations("Ranked");
  const locale = useLocale();
  const coverage = useCoverageName();
  // "within N km of X" comes from the API already phrased; a named area gets "in"
  const where = result.within
    ? result.within.startsWith("within")
      ? result.within
      : t("inPlace", { place: result.within })
    : t("inCoverage", { coverage });
  const count = result.results.length;

  return (
    <Card
      testId="ranked-list"
      title={result.level === "msoa" ? t("titleMsoa", { count, where }) : t("titleLsoa", { count, where })}
      subtitle={t("subtitle", { count: result.candidates, preset: result.preset })}
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
                      title={t("closeCallTitle", { n: result.results.length, pct: Math.round(r.stability * 100) })}
                    >
                      {t("closeCall")}
                    </span>
                  )}
                </span>
                <span className="block truncate text-xs text-[var(--text-secondary)]">
                  {r.local_authority}
                  {r.median_price != null && ` · ${t("typicalPrice", { price: formatValue(r.median_price, "£", locale) })}`}
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
        {t("note")}
        {result.results.some((r) => r.stability != null && r.stability < CLOSE_CALL) && ` ${t("closeCallNote")}`}
      </Muted>
    </Card>
  );
}
