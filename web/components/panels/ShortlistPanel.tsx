"use client";

import { useEffect } from "react";

import { useLiveability } from "@/components/AppData";

const KEY = "lix.shortlist";

/** Saved areas; kept in this browser (localStorage) and shared with the assistant. */
export function ShortlistPanel() {
  const { state, update } = useLiveability();

  // Restore once, then persist on change
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) ?? "[]");
      if (Array.isArray(saved) && saved.length) update((s) => (s.shortlist.length ? s : { ...s, shortlist: saved }));
    } catch {
      /* storage may be unavailable */
    }
  }, [update]);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state.shortlist));
    } catch {
      /* ignore */
    }
  }, [state.shortlist]);

  if (state.shortlist.length === 0) {
    return <p className="p-4 text-sm text-[var(--text-secondary)]">No saved areas yet. Use “Add to shortlist” on an area, or ask the assistant to save one.</p>;
  }
  return (
    <ul className="divide-y divide-[var(--border)] p-2 text-sm" data-testid="shortlist">
      {state.shortlist.map((item) => (
        <li key={item.code} className="flex items-center justify-between gap-2 py-2">
          <button
            className="min-w-0 text-left"
            onClick={() =>
              update((s) => ({
                ...s,
                map: {
                  ...s.map,
                  selected: item.code.startsWith("E01") ? item.code : s.map.selected,
                  bbox: item.centre
                    ? [item.centre.lon - 0.02, item.centre.lat - 0.012, item.centre.lon + 0.02, item.centre.lat + 0.012]
                    : s.map.bbox,
                },
              }))
            }
          >
            <span className="block truncate font-medium">{item.name}</span>
            {item.note && <span className="block truncate text-xs text-[var(--text-secondary)]">{item.note}</span>}
          </button>
          <button
            className="text-xs text-[var(--text-muted)] underline"
            onClick={() => update((s) => ({ ...s, shortlist: s.shortlist.filter((i) => i.code !== item.code) }))}
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}
