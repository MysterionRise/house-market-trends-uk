// The methodology and sources pages render the repo's own docs; copy them in before a
// build so the web app (and its Docker image) doesn't reach outside its folder at runtime
import { copyFileSync, existsSync, mkdirSync } from "node:fs";

const DOCS = {
  "../docs/methodology.md": "methodology.md",
  "../docs/validation.md": "validation.md",
  "../docs/evals.md": "evals.md",
  "../docs/data-sources.md": "data-sources.md",
  "../ATTRIBUTION.md": "attribution.md",
};

mkdirSync("content", { recursive: true });
for (const [from, to] of Object.entries(DOCS)) {
  if (existsSync(from)) copyFileSync(from, `content/${to}`);
  else console.warn(`copy-docs: ${from} not found`);
}
