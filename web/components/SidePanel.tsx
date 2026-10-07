"use client";

import { CopilotChat, useConfigureSuggestions } from "@copilotkit/react-core/v2";
import { useEffect, useRef } from "react";

import { useLiveability } from "@/components/AppData";
import { type Tab, usePanel } from "@/components/PanelContext";
import { AnalystPanel } from "@/components/panels/AnalystPanel";
import { AreaPanel } from "@/components/panels/AreaPanel";
import { ShortlistPanel } from "@/components/panels/ShortlistPanel";
import { WeightPanel } from "@/components/panels/WeightPanel";

const SUGGESTIONS = [
  { title: "Family-friendly near Leeds", message: "We have two young kids and a budget of £350k. Where should we look around Leeds?" },
  { title: "Well-run pubs nearby", message: "Show me well-run pubs near SW1A 1AA" },
  { title: "Compare two places", message: "Compare Headingley and Chapel Allerton" },
  { title: "Explain a score", message: "Why does Manchester city centre score low on safety?" },
];

export function SidePanel() {
  const { state, update } = useLiveability();
  const { tab, setTab } = usePanel();

  useConfigureSuggestions({ suggestions: SUGGESTIONS, available: "before-first-message" }, []);

  // Selecting an area (on the map or from a list) opens its profile, unless chatting.
  // The tab lives in a parent context, so this runs after render, not during it.
  const selected = state.map.selected;
  const seenSelected = useRef(selected);
  useEffect(() => {
    if (selected === seenSelected.current) return;
    seenSelected.current = selected;
    if (selected && tab !== "assistant") setTab("area");
  }, [selected, tab, setTab]);

  const tabs: [Tab, string][] = [
    ["assistant", "Assistant"],
    ["weights", "Weights"],
    ["area", "Area"],
    ["shortlist", `Shortlist${state.shortlist.length ? ` (${state.shortlist.length})` : ""}`],
    ...(state.mode === "analyst" ? [["analyst", "Analyst"] as [Tab, string]] : []),
  ];

  return (
    <aside className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--surface-1)]">
      <nav
        className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-[var(--border)] px-2"
        role="tablist"
        aria-label="Panels"
        onKeyDown={(e) => {
          // Arrow keys move between tabs (WAI-ARIA tabs pattern)
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          const ids = tabs.map(([id]) => id);
          const next = ids[(ids.indexOf(tab) + (e.key === "ArrowRight" ? 1 : ids.length - 1)) % ids.length];
          setTab(next);
          document.getElementById(`tab-${next}`)?.focus();
        }}
      >
        {tabs.map(([id, label]) => (
          <button
            key={id}
            id={`tab-${id}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            tabIndex={tab === id ? 0 : -1}
            data-testid={`tab-${id}`}
            onClick={() => setTab(id)}
            className={`whitespace-nowrap border-b-2 px-2.5 py-2 text-sm ${
              tab === id
                ? "border-[var(--text-primary)] font-medium text-[var(--text-primary)]"
                : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {label}
          </button>
        ))}
        <label className="ml-auto flex shrink-0 items-center gap-1.5 py-2 pl-2 text-xs text-[var(--text-secondary)]">
          <input
            type="checkbox"
            data-testid="analyst-toggle"
            checked={state.mode === "analyst"}
            onChange={(e) => {
              const analyst = e.target.checked;
              update((s) => ({ ...s, mode: analyst ? "analyst" : "consumer" }));
              if (!analyst && tab === "analyst") setTab("assistant");
            }}
          />
          Analyst
        </label>
      </nav>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {/* Keep the chat mounted so the conversation survives tab switches */}
        <div className={tab === "assistant" ? "h-full" : "hidden"} data-testid="chat" id="panel-assistant" role="tabpanel">
          <CopilotChat
            className="h-full"
            labels={{ chatInputPlaceholder: "Ask about places in England…" }}
          />
        </div>
        {tab !== "assistant" && (
          <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
            {tab === "weights" && <WeightPanel />}
            {tab === "area" && <AreaPanel />}
            {tab === "shortlist" && <ShortlistPanel />}
            {tab === "analyst" && <AnalystPanel />}
          </div>
        )}
      </div>
    </aside>
  );
}
