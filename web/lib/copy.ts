"use client";

/** Copy that depends on the data pack and the interface language. */
import { useFormatter, useTranslations } from "next-intl";

import { useData } from "@/components/AppData";
import { coverageName } from "@/lib/data";

/** "England and Wales" in the interface language, for the current data pack. */
export function useCoverageName(): string {
  const { manifest } = useData();
  const t = useTranslations("Nations");
  const format = useFormatter();
  return coverageName(
    manifest,
    (code) => t(code as "uk" | "E" | "W" | "S" | "N"),
    (names) => format.list(names, { type: "conjunction" }),
  );
}
