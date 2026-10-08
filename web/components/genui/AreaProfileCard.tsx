"use client";

import { useState } from "react";

import { useLiveability } from "@/components/AppData";
import { Band, Card, Muted, ScoreBar, formatValue, qualityNote } from "@/components/ui";
import type { AreaProfile, IndicatorValue } from "@/lib/contracts.gen";
import { bboxOf } from "@/lib/state";

function Facts({ items }: { items: IndicatorValue[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
      {items.map((f) => (
        <div key={f.id} className="min-w-0">
          <dt className="truncate text-xs text-[var(--text-muted)]">{f.label}</dt>
          <dd className="text-sm tabular-nums">
            {formatValue(f.value, f.unit)}
            {qualityNote(f.quality) && (
              <span className="ml-1 text-xs text-[var(--text-muted)]">({qualityNote(f.quality)})</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Copies a link that opens this area with the current weights (the URL hash holds the view). */
function CopyLink({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn"
      onClick={async () => {
        const url = new URL(window.location.href);
        try {
          const view = JSON.parse(decodeURIComponent(url.hash.slice(1) || "{}"));
          url.hash = encodeURIComponent(JSON.stringify({ ...view, s: code }));
        } catch {
          /* keep the current hash */
        }
        try {
          await navigator.clipboard.writeText(url.toString());
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        } catch {
          window.prompt("Copy this link", url.toString());
        }
      }}
    >
      {copied ? "Link copied" : "Copy link"}
    </button>
  );
}

export function AreaProfileCard({ profile }: { profile: AreaProfile }) {
  const { state, update } = useLiveability();
  const saved = state.shortlist.some((i) => i.code === profile.lsoa21cd);
  const title = profile.neighbourhood ? `${profile.neighbourhood}, ${profile.local_authority}` : profile.lsoa_name;

  return (
    <Card
      testId="area-profile"
      title={title}
      subtitle={`${profile.lsoa_name} · ${profile.urban_rural} · ${profile.population.toLocaleString("en-GB")} residents`}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums">{profile.overall?.toFixed(0) ?? "–"}</span>
        <span className="text-xs text-[var(--text-muted)]">/ 100 overall ({profile.preset})</span>
      </div>
      <div className="mt-1">
        <Band band={profile.band} percentile={profile.overall_percentile} />
      </div>
      {profile.overall_percentile_range && (
        <p
          className="mt-1 text-xs text-[var(--text-muted)]"
          data-testid="percentile-range"
          title="The 5–95% range of the UK percentile when each theme's weight is nudged by about a quarter"
        >
          With slightly different weights: better than {profile.overall_percentile_range[0]}–
          {profile.overall_percentile_range[1]}% of the UK
        </p>
      )}

      <div className="mt-3" data-testid="theme-bars">
        {profile.themes.map((t) => (
          <ScoreBar
            key={t.theme}
            label={t.label}
            score={t.score}
            theme={t.theme}
            hint={t.percentile != null ? `Better than ${t.percentile}% of the UK` : undefined}
            marks={[
              { value: t.local_median, kind: "local", label: `${profile.local_authority} median` },
              { value: t.country_median, kind: "england", label: "UK median" },
            ]}
          />
        ))}
        <p className="mt-1 flex gap-3 text-[10px] text-[var(--text-muted)]">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2.5 w-[2px] bg-[var(--text-primary)]" aria-hidden /> {profile.local_authority} median
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2.5 w-px bg-[var(--text-muted)]" aria-hidden /> UK median
          </span>
        </p>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="mb-1 font-medium text-[var(--text-secondary)]">Strengths</div>
          {profile.strengths.map((s) => <div key={s.id}>{s.label}</div>)}
        </div>
        <div>
          <div className="mb-1 font-medium text-[var(--text-secondary)]">Weaker spots</div>
          {profile.weaknesses.map((s) => <div key={s.id}>{s.label}</div>)}
        </div>
      </div>

      <div className="mt-3 border-t border-[var(--border)] pt-2">
        <Facts items={profile.key_facts} />
      </div>

      {profile.flags && profile.flags.length > 0 && (
        <ul className="mt-2 list-disc pl-4 text-xs text-[var(--text-secondary)]">
          {profile.flags.map((f) => <li key={f}>{f}</li>)}
        </ul>
      )}

      <div className="mt-3 flex gap-2">
        <button
          className="btn"
          onClick={() =>
            update((s) => ({
              ...s,
              map: { ...s.map, selected: profile.lsoa21cd, bbox: bboxOf(profile.bbox) },
            }))
          }
        >
          Show on map
        </button>
        <button
          className="btn"
          disabled={saved}
          onClick={() =>
            update((s) => ({
              ...s,
              shortlist: [...s.shortlist, { code: profile.lsoa21cd, name: title, centre: profile.centre }],
            }))
          }
        >
          {saved ? "In shortlist" : "Add to shortlist"}
        </button>
        <CopyLink code={profile.lsoa21cd} />
      </div>
      <Muted>Scores are 0–100 (higher is better). Distances are straight-line.</Muted>
    </Card>
  );
}
