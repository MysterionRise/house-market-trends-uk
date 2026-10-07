"use client";

import { useLiveability } from "@/components/AppData";
import { Card, Muted, formatValue } from "@/components/ui";
import type { PoiResult } from "@/lib/contracts.gen";

const TITLES: Record<string, string> = {
  well_run_pub: "Well-run pubs", pub: "Pubs", gp: "GP practices", primary_school: "Primary schools",
  secondary_school: "Secondary schools", nursery: "Nurseries", supermarket: "Supermarkets",
};

function detailLine(category: string, d: Record<string, unknown>): string {
  if (category.includes("pub") && d.rating != null) return `Food hygiene rating ${d.rating}/5${d.real_ale === "yes" ? " · real ale" : ""}`;
  if (category.includes("school") && typeof d.quality === "number") {
    return `Inspection quality ${(d.quality * 100).toFixed(0)}/100${d.phase ? ` · ${d.phase}` : ""}`;
  }
  if (typeof d.brand === "string") return d.brand;
  return "";
}

export function PoiList({ result }: { result: PoiResult }) {
  const { update } = useLiveability();
  const title = TITLES[result.category] ?? result.category.replaceAll("_", " ");
  const sources = [...new Set(result.pois.map((p) => `${p.source} (${p.licence})`))];

  return (
    <Card testId="poi-list" title={`${title} near ${result.origin_label}`} subtitle={`${result.pois.length} found`}>
      {result.pois.length === 0 && <p className="text-xs text-[var(--text-secondary)]">None within range — try a larger radius.</p>}
      <ul className="divide-y divide-[var(--border)]">
        {result.pois.map((p, i) => (
          <li key={`${p.name}-${i}`}>
            <button
              className="flex w-full items-baseline justify-between gap-2 py-1.5 text-left hover:bg-[var(--hover)]"
              onClick={() =>
                update((s) => ({
                  ...s,
                  map: { ...s.map, bbox: [p.point.lon - 0.006, p.point.lat - 0.004, p.point.lon + 0.006, p.point.lat + 0.004] },
                }))
              }
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{p.name ?? "Unnamed"}</span>
                <span className="block truncate text-xs text-[var(--text-secondary)]">{detailLine(result.category, p.detail ?? {})}</span>
              </span>
              <span className="shrink-0 text-xs tabular-nums text-[var(--text-secondary)]">{formatValue(p.distance_m, "metres")}</span>
            </button>
          </li>
        ))}
      </ul>
      <Muted>Straight-line distance. Source: {sources.join("; ")}.</Muted>
    </Card>
  );
}
