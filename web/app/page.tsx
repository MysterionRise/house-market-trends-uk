"use client";

import dynamic from "next/dynamic";

import { useData } from "@/components/AppData";
import { SidePanel } from "@/components/SidePanel";

// MapLibre needs the browser
const LiveabilityMap = dynamic(() => import("@/components/map/LiveabilityMap").then((m) => m.LiveabilityMap), {
  ssr: false,
});

export default function Home() {
  const { error } = useData();
  return (
    <main className="grid h-dvh grid-rows-[auto_1fr] bg-[var(--page)] text-[var(--text-primary)]">
      <header className="flex items-baseline gap-3 border-b border-[var(--border)] bg-[var(--surface-1)] px-4 py-2">
        <h1 className="text-base font-semibold">UK Liveability Index</h1>
        <span className="hidden text-xs text-[var(--text-secondary)] sm:inline">
          England&apos;s 33,755 neighbourhoods, scored from open data
        </span>
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
