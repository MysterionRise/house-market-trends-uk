import { defineConfig } from "@playwright/test";

// Runs against the real local build (data/serve) with the scripted assistant (no API key).
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:3000", viewport: { width: 1400, height: 900 } },
  webServer: [
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
