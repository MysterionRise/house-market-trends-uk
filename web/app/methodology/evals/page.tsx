import type { Metadata } from "next";

import { DocPage, readDoc } from "@/components/Doc";

export const metadata: Metadata = { title: "Assistant evals · UK Liveability Index" };

const source = readDoc("evals.md");

export default function Evals() {
  return <DocPage current="/methodology/evals" sources={[{ text: source, base: "docs/" }]} />;
}
