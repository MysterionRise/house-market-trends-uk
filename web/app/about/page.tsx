import fs from "node:fs";
import path from "node:path";

import type { Metadata } from "next";

import { BuildInfo } from "@/components/BuildInfo";
import { DocPage, readDoc } from "@/components/Doc";

export const metadata: Metadata = { title: "Sources & licences · UK Liveability Index" };

// Read at build time: the release this front end belongs to
const { version } = JSON.parse(fs.readFileSync(path.join(process.cwd(), "package.json"), "utf-8"));

const sources = [
  { text: readDoc("data-licence.md"), base: "" },
  { text: readDoc("data-sources.md"), base: "docs/" },
  { text: readDoc("attribution.md"), base: "" },
];

export default function About() {
  return <DocPage current="/about" intro={<BuildInfo version={version} />} sources={sources} />;
}
