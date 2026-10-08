import fs from "node:fs";
import path from "node:path";

import Link from "next/link";
import type { ReactNode } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

const REPO = "https://github.com/MysterionRise/uk-liveability-index/blob/master/";
// Docs that have a page in the app; other repo files open on GitHub
const IN_APP: Record<string, string> = {
  "methodology.md": "/methodology",
  "validation.md": "/methodology/validation",
  "evals.md": "/methodology/evals",
  "data-sources.md": "/about",
  "ATTRIBUTION.md": "/about",
  "DATA-LICENCE.md": "/about",
};

/** A doc copied into web/content by scripts/copy-docs.mjs (read at build time). */
export function readDoc(name: string): string {
  try {
    return fs.readFileSync(path.join(process.cwd(), "content", name), "utf-8");
  } catch {
    return `*This page's source (${name}) wasn't found. Run \`npm run dev\` or \`npm run build\`, which copy the docs in.*`;
  }
}

function resolve(href: string | undefined, base: string): string {
  if (!href || /^(https?:|mailto:|#)/.test(href)) return href ?? "#";
  const name = href.split("/").pop()!.split("#")[0];
  if (IN_APP[name]) return IN_APP[name];
  return REPO + path.posix.normalize(path.posix.join(base, href));
}

const PAGES = [
  ["/methodology", "Method"],
  ["/methodology/validation", "Validation"],
  ["/methodology/evals", "Assistant evals"],
  ["/about", "Sources & licences"],
] as const;

/** A documentation page: the map link, page tabs, an optional intro and rendered markdown. */
export function DocPage({ current, sources, intro }: {
  current: string;
  sources: { text: string; base: string }[];
  intro?: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-[var(--page)] text-[var(--text-primary)]">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[var(--border)] bg-[var(--surface-1)] px-4 py-2">
        <Link href="/" className="text-base font-semibold">
          UK Liveability Index
        </Link>
        <nav className="flex flex-wrap gap-3 text-sm" aria-label="Documentation">
          {PAGES.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={href === current ? "page" : undefined}
              className={href === current ? "font-medium underline" : "text-[var(--text-secondary)] hover:underline"}
            >
              {label}
            </Link>
          ))}
        </nav>
        <Link href="/" className="ml-auto text-sm text-[var(--text-secondary)] underline">
          Back to the map
        </Link>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        {intro}
        {sources.map((s, i) => (
          <article key={i} className="doc">
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => {
                  const to = resolve(href, s.base);
                  const external = to.startsWith("http");
                  return (
                    <a href={to} {...(external ? { target: "_blank", rel: "noreferrer" } : {})}>
                      {children}
                    </a>
                  );
                },
              }}
            >
              {s.text}
            </Markdown>
          </article>
        ))}
      </main>
    </div>
  );
}
