import type { Metadata } from "next";

import { DocPage, readDoc } from "@/components/Doc";

export const metadata: Metadata = { title: "Validation · UK Liveability Index" };

const source = readDoc("validation.md");

export default function Validation() {
  return <DocPage current="/methodology/validation" sources={[{ text: source, base: "docs/" }]} />;
}
