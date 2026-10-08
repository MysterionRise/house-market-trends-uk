// Writes app/tokens.gen.css from lib/palette.ts, the one source of every colour in the
// app. Run with `npm run tokens` (also before dev and build); CI checks the file is current.
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const { tokensCss } = await import("../lib/palette.ts");

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "app", "tokens.gen.css");
writeFileSync(out, tokensCss());
console.log(`wrote ${out}`);
