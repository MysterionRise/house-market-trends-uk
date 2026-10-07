"use client";

import dynamic from "next/dynamic";

import { useData } from "@/components/AppData";
import { SidePanel } from "@/components/SidePanel";

// MapLibre needs the browser
const LiveabilityMap = dynamic(() => import("@/components/map/LiveabilityMap").then((m) => m.LiveabilityMap), {
  ssr: false,
});

export default function Home() {
  const { error, manifest } = useData();
  const count = (manifest?.lsoa_count ?? 33755).toLocaleString("en-GB");
  return (
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-[var(--page)] text-[var(--text-primary)]">
      <header className="flex items-baseline gap-3 border-b border-[var(--border)] bg-[var(--surface-1)] px-4 py-2">
        <h1 className="text-base font-semibold">UK Liveability Index</h1>
        <span className="hidden text-xs text-[var(--text-secondary)] sm:inline">
          {manifest?.demo ? `Demo dataset: ${count} neighbourhoods` : `England's ${count} neighbourhoods`}, scored
          from open data
        </span>
        {manifest?.demo && (
          <span
            className="rounded border border-[var(--border)] px-1.5 py-0.5 text-xs text-[var(--text-secondary)]"
            data-testid="demo-badge"
            title="A small cut of the full build; percentiles on the map are relative to these areas"
          >
            demo data
          </span>
        )}
        <a className="ml-auto text-xs text-[var(--text-secondary)] underline" href="https://github.com/MysterionRise/uk-liveability-index/blob/master/docs/methodology.md" target="_blank" rel="noreferrer">
          How scores work
        </a>
      </header>
      <div className="grid min-h-0 grid-rows-[45dvh_1fr] md:grid-cols-[1fr_minmax(360px,440px)] md:grid-rows-1">
        <div className="relative min-h-0">
          {error ? (
            <div className="p-6 text-sm text-[var(--text-secondary)]" role="alert">
              Couldn&apos;t load the scores ({error}). Is the API running (<code>make api</code>) and has <code>make score tiles</code> been run?
            </div>
          ) : (
            <LiveabilityMap />
          )}
        </div>
        <div className="min-h-0">
          <SidePanel />
        </div>
      </div>
    </main>
  );
}
