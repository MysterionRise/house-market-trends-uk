"use client";

import { useSyncExternalStore } from "react";

import { useData, useLiveability } from "@/components/AppData";

const KEY = "lix.welcomed";
const listeners = new Set<() => void>();

function readWelcomed(): boolean {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return true; // storage blocked: don't nag on every visit
  }
}

function dismiss() {
  try {
    localStorage.setItem(KEY, "1");
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}

// The manifest's labels, so the card can show before the manifest arrives (it is the
// largest text on a first visit, and waiting for the fetch delays the first paint of it)
const PERSONAS: Record<string, string> = {
  family: "Family with children",
  young_professional: "Young professional",
  retiree: "Retired",
  commuter: "Commuter",
  balanced: "Balanced",
};

/** First visit: pick who you are (sets the weights) and how to read the map. */
export function Onboarding() {
  const { manifest } = useData();
  const { update } = useLiveability();
  const welcomed = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    readWelcomed,
    () => true, // server render: no card, so nothing flashes
  );
  if (welcomed) return null;
  const presets = Object.keys(PERSONAS).filter((p) => !manifest || manifest.presets[p]);

  return (
    <div
      className="absolute left-3 top-3 z-20 w-[min(22rem,calc(100%-1.5rem))] rounded-lg border border-[var(--border)] bg-[var(--surface-1)] p-4 shadow-lg"
      role="dialog"
      aria-labelledby="welcome-title"
      data-testid="onboarding"
    >
      <h2 id="welcome-title" className="text-sm font-semibold">
        Find a neighbourhood that suits you
      </h2>
      <p className="mt-1 text-xs text-[var(--text-secondary)]">
        Every neighbourhood in England, scored from open data. Darker blue is better than more of England. Zoom in
        and click an area to see why, or ask the assistant.
      </p>
      <p className="mt-3 text-xs font-medium text-[var(--text-secondary)]">Who&apos;s looking?</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {presets.map((id) => (
          <button
            key={id}
            className="btn text-xs"
            data-testid={`persona-${id}`}
            title={manifest?.presets[id].description}
            onClick={() => {
              update((s) => ({ ...s, preset: id, theme_weights: {}, indicator_weights: {} }));
              dismiss();
            }}
          >
            {manifest?.presets[id].label ?? PERSONAS[id]}
          </button>
        ))}
      </div>
      <button className="mt-3 text-xs text-[var(--text-muted)] underline" onClick={dismiss}>
        Skip
      </button>
    </div>
  );
}
