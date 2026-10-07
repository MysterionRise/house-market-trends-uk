"use client";

import { CopilotChat, useConfigureSuggestions } from "@copilotkit/react-core/v2";
import { useState } from "react";

import { useLiveability } from "@/components/AppData";
import { AnalystPanel } from "@/components/panels/AnalystPanel";
import { AreaPanel } from "@/components/panels/AreaPanel";
import { ShortlistPanel } from "@/components/panels/ShortlistPanel";
import { WeightPanel } from "@/components/panels/WeightPanel";

type Tab = "assistant" | "weights" | "area" | "shortlist" | "analyst";

const SUGGESTIONS = [
  { title: "Family-friendly near Leeds", message: "We have two young kids and a budget of £350k. Where should we look around Leeds?" },
  { title: "Well-run pubs nearby", message: "Show me well-run pubs near SW1A 1AA" },
  { title: "Compare two places", message: "Compare Headingley and Chapel Allerton" },
  { title: "Explain a score", message: "Why does Manchester city centre score low on safety?" },
];

export function SidePanel() {
  const { state, update } = useLiveability();
  const [tab, setTab] = useState<Tab>("assistant");

  useConfigureSuggestions({ suggestions: SUGGESTIONS, available: "before-first-message" }, []);

  // Selecting an area (on the map or from a list) opens its profile, unless chatting.
  // Adjusted during render rather than in an effect, as React recommends.
  const [lastSelected, setLastSelected] = useState(state.map.selected);
  if (state.map.selected !== lastSelected) {
    setLastSelected(state.map.selected);
    if (state.map.selected && tab !== "assistant") setTab("area");
  }

  const tabs: [Tab, string][] = [
    ["assistant", "Assistant"],
    ["weights", "Weights"],
    ["area", "Area"],
    ["shortlist", `Shortlist${state.shortlist.length ? ` (${state.shortlist.length})` : ""}`],
    ...(state.mode === "analyst" ? [["analyst", "Analyst"] as [Tab, string]] : []),
  ];

  return (
    <aside className="flex h-full min-h-0 flex-col border-l border-[var(--border)] bg-[var(--surface-1)]">
      <nav className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-[var(--border)] px-2" role="tablist">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
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
        <div className={tab === "assistant" ? "h-full" : "hidden"} data-testid="chat">
          <CopilotChat
            className="h-full"
            labels={{ chatInputPlaceholder: "Ask about places in England…" }}
          />
        </div>
        {tab === "weights" && <WeightPanel />}
        {tab === "area" && <AreaPanel />}
        {tab === "shortlist" && <ShortlistPanel />}
        {tab === "analyst" && <AnalystPanel />}
      </div>
    </aside>
  );
}
