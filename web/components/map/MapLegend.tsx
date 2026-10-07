import { gradientCss } from "@/lib/colors";

export function MapLegend({ label, dark }: { label: string; dark: boolean }) {
  return (
    <div
      className="absolute bottom-6 left-3 z-10 w-60 rounded-lg border border-[var(--border)] bg-[var(--surface-1)] p-3 text-xs shadow-sm"
      data-testid="legend"
    >
      <div className="font-medium text-[var(--text-primary)]">{label}</div>
      <div className="mb-2 text-[var(--text-muted)]">England percentile (higher is better)</div>
      <div className="h-2.5 rounded-sm" style={{ background: gradientCss(dark) }} />
      <div className="mt-1 flex justify-between tabular-nums text-[var(--text-secondary)]">
        <span>0 · worst</span>
        <span>50</span>
        <span>best · 100</span>
      </div>
      <div className="mt-2 flex items-center gap-1.5 text-[var(--text-muted)]">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-[var(--no-data)]" /> No data
      </div>
    </div>
  );
}
