"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { useLocaleChoice } from "@/components/LocaleProvider";

const PAGES = [
  ["/methodology", "method"],
  ["/methodology/validation", "validation"],
  ["/methodology/evals", "evals"],
  ["/about", "sources"],
] as const;

/** The documentation pages' header; the pages themselves are English only. */
export function DocHeader({ current }: { current: string }) {
  const t = useTranslations("Docs");
  const tHeader = useTranslations("Header");
  const { locale } = useLocaleChoice();
  return (
    <>
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[var(--border)] bg-[var(--surface-1)] px-4 py-2">
        <Link href="/" className="text-base font-semibold">
          {tHeader("title")}
        </Link>
        <nav className="flex flex-wrap gap-3 text-sm" aria-label={t("nav")}>
          {PAGES.map(([href, key]) => (
            <Link
              key={href}
              href={href}
              aria-current={href === current ? "page" : undefined}
              className={href === current ? "font-medium underline" : "text-[var(--text-secondary)] hover:underline"}
            >
              {t(key)}
            </Link>
          ))}
        </nav>
        <Link href="/" className="ml-auto text-sm text-[var(--text-secondary)] underline">
          {t("backToMap")}
        </Link>
      </header>
      {locale !== "en" && (
        <p className="mx-auto max-w-3xl px-4 pt-4 text-sm text-[var(--text-secondary)]" data-testid="english-only">
          {t("englishOnly")}
        </p>
      )}
    </>
  );
}
