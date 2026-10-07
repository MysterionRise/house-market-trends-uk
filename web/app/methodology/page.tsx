import type { Metadata } from "next";

import { DocPage, readDoc } from "@/components/Doc";

export const metadata: Metadata = { title: "How scores work · UK Liveability Index" };

const source = readDoc("methodology.md");

export default function Methodology() {
  return <DocPage current="/methodology" sources={[{ text: source, base: "docs/" }]} />;
}
