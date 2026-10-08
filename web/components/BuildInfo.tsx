"use client";

import { useData } from "@/components/AppData";

/** Which release and data build the page is showing (the About page). */
export function BuildInfo({ version }: { version: string }) {
  const { manifest } = useData();
  const built = manifest
    ? new Date(manifest.generated_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })
    : null;
  return (
    <p className="mb-6 rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 text-sm" data-testid="build-info">
      Version {version}
      {built && ` · data built ${built}`}
      {manifest?.demo && " (demo dataset)"} ·{" "}
      <a className="underline" href="https://github.com/MysterionRise/uk-liveability-index" target="_blank" rel="noreferrer">
        source code
      </a>
      <br />
      <span className="text-[var(--text-secondary)]">
        For exploring neighbourhoods, not property, financial or legal advice.
      </span>
    </p>
  );
}
