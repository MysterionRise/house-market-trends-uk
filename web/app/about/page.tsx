import type { Metadata } from "next";

import { DocPage, readDoc } from "@/components/Doc";

export const metadata: Metadata = { title: "Sources & licences · UK Liveability Index" };

const sources = [
  { text: readDoc("data-sources.md"), base: "docs/" },
  { text: readDoc("attribution.md"), base: "" },
];

export default function About() {
  return <DocPage current="/about" sources={sources} />;
}
