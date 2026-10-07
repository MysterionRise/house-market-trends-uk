import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: { alias: { "@": import.meta.dirname } },
  test: { include: ["**/*.test.ts"], exclude: ["node_modules/**", ".next/**"] },
});
