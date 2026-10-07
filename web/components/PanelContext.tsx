"use client";

import { createContext, useContext, useState } from "react";

export type Tab = "assistant" | "weights" | "area" | "shortlist" | "analyst";

interface PanelValue {
  tab: Tab;
  setTab: (tab: Tab) => void;
}

const PanelCtx = createContext<PanelValue>({ tab: "assistant", setTab: () => {} });

/** Which side-panel tab is open, shared so the header search can open an area's profile. */
export function PanelProvider({ children }: { children: React.ReactNode }) {
  const [tab, setTab] = useState<Tab>("assistant");
  return <PanelCtx.Provider value={{ tab, setTab }}>{children}</PanelCtx.Provider>;
}

export const usePanel = () => useContext(PanelCtx);
