"use client";

/**
 * Generative UI: one renderer per assistant tool. The assistant's tool results are
 * typed (contracts.gen.ts), so each call becomes a component in the chat. This file is
 * the only place that knows about CopilotKit's renderer API.
 */
import { useRenderTool } from "@copilotkit/react-core/v2";
import { z } from "zod";

import { AreaProfileCard } from "@/components/genui/AreaProfileCard";
import { ComparisonTable } from "@/components/genui/ComparisonTable";
import { MethodExplainer } from "@/components/genui/MethodExplainer";
import { PoiList } from "@/components/genui/PoiList";
import { RankedList } from "@/components/genui/RankedList";
import { type SqlData, SqlResult } from "@/components/genui/SqlResult";
import { parseResult } from "@/components/ui";
import type { AreaProfile, Comparison, Explanation, IndicatorInfo, Place, PoiResult, RankResult } from "@/lib/contracts.gen";

const anyArgs = z.record(z.string(), z.unknown());

const WORKING: Record<string, string> = {
  rank_areas: "Ranking areas…",
  get_area_profile: "Profiling the area…",
  compare_areas: "Comparing…",
  nearest_pois: "Finding places nearby…",
  explain_score: "Working out the score…",
  set_weights: "Adjusting the weights…",
  show_on_map: "Moving the map…",
  run_sql: "Running the query…",
  search_place: "Looking up the place…",
  list_indicators: "Listing indicators…",
  add_to_shortlist: "Saving to your shortlist…",
  remove_from_shortlist: "Updating your shortlist…",
};

function Pending({ name }: { name: string }) {
  return (
    <div className="my-1 inline-flex items-center gap-2 rounded-full border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent)]" />
      {WORKING[name] ?? `Running ${name}…`}
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-1 inline-flex flex-wrap items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
      {children}
    </div>
  );
}

/** Register one renderer: pending chip while running, the component once there's a result. */
function useToolCard<T>(name: string, render: (result: T, args: Record<string, unknown>) => React.ReactElement | null) {
  useRenderTool(
    {
      name,
      parameters: anyArgs,
      render: ({ status, result, parameters }) => {
        if (status !== "complete") return <Pending name={name} />;
        const data = parseResult<T>(result);
        if (data == null) return <Chip>{name}: no result</Chip>;
        return render(data, (parameters ?? {}) as Record<string, unknown>);
      },
    },
    [],
  );
}

export function GenerativeUI() {
  useToolCard<RankResult>("rank_areas", (r) => <RankedList result={r} />);
  useToolCard<AreaProfile>("get_area_profile", (p) => <AreaProfileCard profile={p} />);
  useToolCard<Comparison>("compare_areas", (c) => <ComparisonTable comparison={c} />);
  useToolCard<PoiResult>("nearest_pois", (r) => <PoiList result={r} />);
  useToolCard<Explanation>("explain_score", (e) => <MethodExplainer explanation={e} />);
  useToolCard<SqlData>("run_sql", (d, args) => <SqlResult data={d} query={String(args.query ?? "")} />);
  useToolCard<{ preset: string; theme_weights: Record<string, number> }>("set_weights", (w) => (
    <Chip>
      Weights set: <strong className="font-medium text-[var(--text-primary)]">{w.preset}</strong>
      {Object.entries(w.theme_weights)
        .filter(([, v]) => v !== 1)
        .map(([t, v]) => (
          <span key={t}>· {t} ×{v}</span>
        ))}
    </Chip>
  ));
  useToolCard<{ layer: string }>("show_on_map", (m) => <Chip>Map updated · colouring by {m.layer}</Chip>);
  useToolCard<unknown[]>("add_to_shortlist", (items) => <Chip>Shortlist: {items.length} saved</Chip>);
  useToolCard<unknown[]>("remove_from_shortlist", (items) => <Chip>Shortlist: {items.length} saved</Chip>);
  useToolCard<Place[]>("search_place", (places) => (
    <Chip>
      Found: {places.slice(0, 3).map((p) => `${p.name}${p.detail ? ` (${p.detail})` : ""}`).join("; ") || "nothing"}
    </Chip>
  ));
  useToolCard<IndicatorInfo[]>("list_indicators", (items) => (
    <details className="my-1 text-xs">
      <summary className="cursor-pointer text-[var(--text-secondary)]">{items.length} indicators</summary>
      <ul className="mt-1 space-y-1">
        {items.map((i) => (
          <li key={i.id}>
            <span className="font-medium">{i.label}</span> <span className="text-[var(--text-muted)]">({i.role}, {i.unit})</span>
            <div className="text-[var(--text-secondary)]">{i.description}</div>
          </li>
        ))}
      </ul>
    </details>
  ));
  return null;
}
