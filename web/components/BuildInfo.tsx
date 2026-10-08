"use client";

import { useFormatter, useTranslations } from "next-intl";

import { useData } from "@/components/AppData";

/** Which release and data build the page is showing (the About page). */
export function BuildInfo({ version }: { version: string }) {
  const { manifest } = useData();
  const t = useTranslations("BuildInfo");
  const format = useFormatter();
  const built = manifest
    ? format.dateTime(new Date(manifest.generated_at), { day: "numeric", month: "long", year: "numeric" })
    : null;
  return (
    <p className="mb-6 rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm" data-testid="build-info">
      {t("version", { version })}
      {built && ` · ${t("dataBuilt", { date: built })}`}
      {manifest?.demo && ` (${t("demo")})`} ·{" "}
      <a className="underline" href="https://github.com/MysterionRise/uk-liveability-index" target="_blank" rel="noreferrer">
        {t("sourceCode")}
      </a>
      <br />
      <span className="text-[var(--text-secondary)]">{t("disclaimer")}</span>
    </p>
  );
}
