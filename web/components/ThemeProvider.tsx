"use client";

/**
 * Light, dark or follow the system. The choice is kept in localStorage; the resolved
 * mode is written to <html> twice over: `data-theme` (what our tokens key on) and the
 * `dark` class (what CopilotKit's stylesheet keys on). `app/layout.tsx` runs the same
 * logic inline before the first paint, so there is no flash of the wrong theme.
 */
import { useTranslations } from "next-intl";
import { createContext, useCallback, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

export type ThemeChoice = "system" | "light" | "dark";
export type Mode = "light" | "dark";

export const THEME_KEY = "lix.theme";
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((l) => l());

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemMode(): Mode {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** What the document should show for a choice (system follows the OS setting). */
export function resolve(choice: ThemeChoice): Mode {
  return choice === "system" ? systemMode() : choice;
}

/** Stamp the choice on <html>; mirrored by the inline script in app/layout.tsx. */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  root.classList.toggle("dark", resolve(choice) === "dark");
}

interface ThemeContext {
  choice: ThemeChoice;
  mode: Mode;
  setChoice: (choice: ThemeChoice) => void;
}

const Context = createContext<ThemeContext>({ choice: "system", mode: "light", setChoice: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const subscribe = useCallback((cb: () => void) => {
    listeners.add(cb);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", cb);
    return () => {
      listeners.delete(cb);
      mq.removeEventListener("change", cb);
    };
  }, []);
  // The server (and hydration) assume "system" + light; the real values follow at once
  const choice = useSyncExternalStore(subscribe, readChoice, () => "system" as ThemeChoice);
  const mode = useSyncExternalStore(subscribe, () => resolve(readChoice()), () => "light" as Mode);

  useEffect(() => {
    applyTheme(choice);
  }, [choice, mode]);

  const setChoice = useCallback((next: ThemeChoice) => {
    try {
      if (next === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage blocked: the choice lasts for this page only */
    }
    applyTheme(next);
    notify();
  }, []);

  return <Context.Provider value={{ choice, mode, setChoice }}>{children}</Context.Provider>;
}

export function useTheme(): ThemeContext {
  return useContext(Context);
}

const CHOICES: ThemeChoice[] = ["system", "light", "dark"];

/** System / light / dark, as a compact select. */
export function ThemeToggle({ label }: { label: string }) {
  const { choice, setChoice } = useTheme();
  const t = useTranslations("Theme");
  return (
    <select
      className="input py-0.5 text-xs"
      aria-label={label}
      value={choice}
      data-testid="theme-toggle"
      onChange={(e) => setChoice(e.target.value as ThemeChoice)}
    >
      {CHOICES.map((c) => (
        <option key={c} value={c}>
          {t(c)}
        </option>
      ))}
    </select>
  );
}
