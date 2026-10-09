"use client";

/** Copy that depends on the data pack and the interface language. */
import { useFormatter, useTranslations } from "next-intl";

import { useData } from "@/components/AppData";
import { coverageName } from "@/lib/data";

/** "England and Wales" in the interface language, for the current data pack. */
export function useCoverageName(): string {
  const { manifest } = useData();
  const t = useTranslations("Nations");
  // A named pair first ("Lloegr a Chymru" mutates), else the catalogue's own "and":
  // browsers have no list patterns for Welsh, Gaelic or Irish
  const active = manifest?.geography?.active ?? [];
  if (active.length === 2 && active.join("_") === "E_W") return t("E_W");
  return coverageName(
    manifest,
    (code) => t(code as "uk" | "E" | "W" | "S" | "N"),
    (names) => `${names.slice(0, -1).join(", ")} ${t("and")} ${names[names.length - 1]}`,
  );
}
