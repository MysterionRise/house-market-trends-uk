"use client";

import { CopilotKit } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

import { DataProvider, LiveabilityStateProvider } from "@/components/AppData";
import { GenerativeUI } from "@/components/genui/registry";
import { LocaleProvider } from "@/components/LocaleProvider";
import { ThemeProvider } from "@/components/ThemeProvider";

/** CopilotKit talks to our Next route (/api/copilotkit), which relays to the Python agent. */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <LocaleProvider>
        <CopilotKit runtimeUrl="/api/copilotkit" enableInspector={false}>
          <DataProvider>
            <LiveabilityStateProvider>
              <GenerativeUI />
              {children}
            </LiveabilityStateProvider>
          </DataProvider>
        </CopilotKit>
      </LocaleProvider>
    </ThemeProvider>
  );
}
