"use client";

import dynamic from "next/dynamic";
import Link from "next/link";

import { useData } from "@/components/AppData";
import { Onboarding } from "@/components/Onboarding";
import { PanelProvider } from "@/components/PanelContext";
import { SearchBox } from "@/components/SearchBox";
import { SidePanel } from "@/components/SidePanel";

// MapLibre needs the browser
const LiveabilityMap = dynamic(() => import("@/components/map/LiveabilityMap").then((m) => m.LiveabilityMap), {
  ssr: false,
});

export default function Home() {
  const { error, manifest, scores } = useData();
  const count = (manifest?.lsoa_count ?? 33755).toLocaleString("en-GB");
  return (
    <PanelProvider>
      {/* minmax(0, …) columns: content can't widen the page past a phone screen */}
      <main className="grid h-dvh grid-cols-[minmax(0,1fr)] grid-rows-[auto_1fr] bg-[var(--page)] text-[var(--text-primary)]">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-[var(--border)] bg-[var(--surface-1)] px-4 py-2">
          <h1 className="text-base font-semibold">UK Liveability Index</h1>
          <span className="hidden text-xs text-[var(--text-secondary)] lg:inline">
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
          <div className="order-last w-full sm:order-none sm:ml-auto sm:w-auto">
            <SearchBox />
          </div>
          <nav className="ml-auto flex flex-wrap gap-x-3 text-xs text-[var(--text-secondary)] sm:ml-0" aria-label="About">
            <Link className="underline" href="/methodology">
              How scores work
            </Link>
            <Link className="underline" href="/about">
              Sources
            </Link>
          </nav>
        </header>
        <div className="grid min-h-0 grid-cols-[minmax(0,1fr)] grid-rows-[45dvh_1fr] md:grid-cols-[minmax(0,1fr)_minmax(360px,440px)] md:grid-rows-1">
          <div className="relative min-h-0">
            {error ? (
              <div className="p-6 text-sm text-[var(--text-secondary)]" role="alert">
                Couldn&apos;t load the scores ({error}). Is the API running (<code>make api</code>) and has{" "}
                <code>make score tiles</code> been run?
              </div>
            ) : (
              <>
                <LiveabilityMap />
                {!scores && (
                  <div
                    className="absolute inset-0 z-10 grid place-items-center bg-[var(--page)]/60 text-sm text-[var(--text-secondary)]"
                    role="status"
                    data-testid="map-loading"
                  >
                    Loading England&apos;s neighbourhoods…
                  </div>
                )}
                <Onboarding />
              </>
            )}
          </div>
          <div className="min-h-0">
            <SidePanel />
          </div>
        </div>
      </main>
    </PanelProvider>
  );
}
