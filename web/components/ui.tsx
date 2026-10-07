/** Small shared pieces: cards, single-hue score bars, bands and number formatting. */
import type { ReactNode } from "react";

export function Card({ title, subtitle, children, testId }: {
  title?: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  testId?: string;
}) {
  return (
    <section
      data-testid={testId}
      className="my-2 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-3 text-sm text-[var(--text-primary)]"
    >
      {title && <h3 className="text-[15px] font-semibold leading-snug">{title}</h3>}
      {subtitle && <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{subtitle}</p>}
      <div className={title ? "mt-2" : ""}>{children}</div>
    </section>
  );
}

/** A 0–100 score as a thin bar with its value in text (the bar never carries it alone). */
export interface BarMark {
  value: number | null | undefined;
  kind: "local" | "england";
  label: string;
}

export function ScoreBar({
  label,
  score,
  hint,
  marks = [],
}: {
  label: string;
  score: number | null | undefined;
  hint?: string;
  marks?: BarMark[];
}) {
  const v = score == null || Number.isNaN(score) ? null : Math.max(0, Math.min(100, score));
  const shown = marks.filter((m) => m.value != null && !Number.isNaN(m.value));
  return (
    <div
      className="grid grid-cols-[minmax(0,9.5rem)_1fr_2.5rem] items-center gap-2 py-0.5"
      title={[hint, ...shown.map((m) => `${m.label}: ${Math.round(m.value as number)}`)].filter(Boolean).join(" · ")}
    >
      <span className="truncate text-xs text-[var(--text-secondary)]">{label}</span>
      <span className="relative h-2 rounded-r-[4px] bg-[var(--track)]">
        {v !== null && <span className="block h-2 rounded-r-[4px] bg-[var(--series-1)]" style={{ width: `${v}%` }} />}
        {shown.map((m) => (
          <span
            key={m.kind}
            aria-hidden
            className={`absolute -top-0.5 h-3 ${m.kind === "local" ? "w-[2px] bg-[var(--text-primary)]" : "w-px bg-[var(--text-muted)]"}`}
            style={{ left: `calc(${Math.max(0, Math.min(100, m.value as number))}% - 1px)` }}
          />
        ))}
      </span>
      <span className="text-right text-xs tabular-nums text-[var(--text-primary)]">{v === null ? "–" : Math.round(v)}</span>
    </div>
  );
}

const BAND_TEXT = ["", "Bottom fifth", "Below average", "Middle", "Above average", "Top fifth"];

export function Band({ band, percentile }: { band?: number | null; percentile?: number | null }) {
  if (!band) return null;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">
      <span className="flex gap-0.5" aria-hidden>
        {[1, 2, 3, 4, 5].map((b) => (
          <span key={b} className={`h-2 w-1.5 rounded-[1px] ${b <= band ? "bg-[var(--series-1)]" : "bg-[var(--track)]"}`} />
        ))}
      </span>
      {BAND_TEXT[band]}
      {percentile != null && ` · better than ${Math.round(percentile)}% of England`}
    </span>
  );
}

export function formatValue(value: number | null | undefined, unit: string): string {
  if (value == null || Number.isNaN(value)) return "–";
  if (unit.startsWith("£")) return `£${Math.round(value).toLocaleString("en-GB")}`;
  if (unit === "metres") return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`;
  if (unit.startsWith("%")) return `${value.toFixed(value > 0 && value < 10 ? 1 : 0)}%`;
  if (unit.startsWith("index")) return value.toFixed(2);
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString("en-GB");
  return value.toFixed(1);
}

const QUALITY_NOTE: Record<string, string> = {
  imputed: "estimated",
  low_n: "few sales",
  broadcast_msoa: "wider area",
  broadcast_lad: "council-wide",
};

/** Plain-English note for a value that isn't measured directly for the LSOA. */
export function qualityNote(quality: string | null | undefined): string | undefined {
  return quality ? QUALITY_NOTE[quality] : undefined;
}

export function Muted({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-xs text-[var(--text-muted)]">{children}</p>;
}

export function parseResult<T>(result: unknown): T | null {
  if (result == null) return null;
  if (typeof result !== "string") return result as T;
  try {
    return JSON.parse(result) as T;
  } catch {
    return null;
  }
}
