"use client";

import { useMemo, useState } from "react";

/** Distribution of a 0–100 score across England's LSOAs, with the selected area marked. */
export function IndicatorHistogram({ values, label, marker }: { values: Float64Array; label: string; marker?: number | null }) {
  const BINS = 20;
  const [hover, setHover] = useState<number | null>(null);
  const counts = useMemo(() => {
    const c = new Array(BINS).fill(0);
    for (const v of values) if (!Number.isNaN(v)) c[Math.min(BINS - 1, Math.floor(v / (100 / BINS)))]++;
    return c;
  }, [values]);
  const max = Math.max(...counts, 1);
  const W = 320, H = 120, PAD = 18;
  const bw = (W - PAD) / BINS;

  return (
    <figure className="text-xs" data-testid="histogram">
      <figcaption className="mb-1 font-medium">{label}: neighbourhoods by score</figcaption>
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="w-full" role="img" aria-label={`Histogram of ${label}`}>
        <line x1={PAD} x2={W} y1={H} y2={H} stroke="var(--baseline)" />
        {counts.map((c, i) => {
          const h = (c / max) * (H - 8);
          return (
            <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              {/* Hit target taller than the bar */}
              <rect x={PAD + i * bw} y={0} width={bw} height={H} fill="transparent" />
              <rect
                x={PAD + i * bw + 1}
                y={H - h}
                width={bw - 2}
                height={h}
                rx={2}
                fill="var(--series-1)"
                opacity={hover === null || hover === i ? 1 : 0.55}
              />
            </g>
          );
        })}
        {marker != null && !Number.isNaN(marker) && (
          <g>
            <line x1={PAD + (marker / 100) * (W - PAD)} x2={PAD + (marker / 100) * (W - PAD)} y1={4} y2={H} stroke="var(--text-primary)" strokeWidth={2} />
            <text x={PAD + (marker / 100) * (W - PAD) + 3} y={12} fill="var(--text-primary)" fontSize={10}>selected {Math.round(marker)}</text>
          </g>
        )}
        {[0, 50, 100].map((t) => (
          <text key={t} x={PAD + (t / 100) * (W - PAD)} y={H + 13} textAnchor="middle" fill="var(--text-muted)" fontSize={10}>{t}</text>
        ))}
      </svg>
      <div className="h-4 text-[var(--text-secondary)]">
        {hover !== null && `${hover * 5}–${hover * 5 + 5}: ${counts[hover].toLocaleString("en-GB")} neighbourhoods`}
      </div>
    </figure>
  );
}
