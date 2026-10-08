import { defineConfig } from "@playwright/test";

// Runs against the real local build (data/serve) with the scripted assistant (no API key),
// starting the dev servers. LIX_E2E_STACK=docker tests the running docker compose stack
// instead (make gif, rehearsals, the release smoke test).
const external = process.env.LIX_E2E_STACK === "docker";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: process.env.LIX_BASE_URL ?? "http://localhost:3000", viewport: { width: 1400, height: 900 } },
  webServer: external ? undefined : [
    {
      command: "cd .. && LIX_MODEL=test uv run lix-api",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
