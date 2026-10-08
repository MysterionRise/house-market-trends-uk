"use client";

import { useData, useLiveability } from "@/components/AppData";
import { themeVar } from "@/lib/palette";
import { effectiveWeights } from "@/lib/state";

/** Preset picker and one slider per theme. Moving a slider recolours the map at once,
 * and the assistant sees the new weights on its next turn. */
export function WeightPanel() {
  const { manifest } = useData();
  const { state, update } = useLiveability();
  if (!manifest) return null;
  const weights = effectiveWeights(manifest, state).themes;
  const preset = manifest.presets[state.preset];

  return (
    <div className="space-y-3 p-3 text-sm" data-testid="weights">
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Start from a preset</span>
        <select
          className="input w-full"
          value={state.preset}
          data-testid="preset-select"
          onChange={(e) =>
            update((s) => ({ ...s, preset: e.target.value, theme_weights: {}, indicator_weights: {} }))
          }
        >
          {Object.entries(manifest.presets).map(([id, p]) => (
            <option key={id} value={id}>{p.label}</option>
          ))}
        </select>
        {preset && <span className="mt-1 block text-xs text-[var(--text-muted)]">{preset.description}</span>}
      </label>

      <div>
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-xs font-medium text-[var(--text-secondary)]">How much each theme matters</span>
          {Object.keys(state.theme_weights).length > 0 && (
            <button className="text-xs underline" onClick={() => update((s) => ({ ...s, theme_weights: {} }))}>
              Reset
            </button>
          )}
        </div>
        {Object.entries(manifest.themes).map(([theme, meta]) => (
          <label key={theme} className="grid grid-cols-[8.5rem_1fr_2rem] items-center gap-2 py-1">
            <span className="flex min-w-0 items-center gap-1.5 text-xs" title={meta.description}>
              <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: themeVar(theme) }} aria-hidden />
              <span className="truncate">{meta.label}</span>
            </span>
            <input
              type="range"
              style={{ accentColor: themeVar(theme) }}
              min={0}
              max={3}
              step={0.25}
              value={weights[theme] ?? 0}
              aria-label={`${meta.label} weight`}
              data-testid={`weight-${theme}`}
              onChange={(e) =>
                update((s) => ({ ...s, theme_weights: { ...s.theme_weights, [theme]: Number(e.target.value) } }))
              }
            />
            <span className="text-right text-xs tabular-nums">{(weights[theme] ?? 0).toFixed(2).replace(/\.?0+$/, "")}</span>
          </label>
        ))}
      </div>

      <label className="block">
        <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Colour the map by</span>
        <select
          className="input w-full"
          value={state.map.layer}
          data-testid="layer-select"
          onChange={(e) => update((s) => ({ ...s, map: { ...s.map, layer: e.target.value } }))}
        >
          <option value="overall">Overall score</option>
          <optgroup label="Themes">
            {Object.entries(manifest.themes).map(([t, m]) => <option key={t} value={`theme:${t}`}>{m.label}</option>)}
          </optgroup>
          <optgroup label="Indicators">
            {manifest.indicators
              .filter((i) => manifest.scored_indicators.includes(i.id))
              .map((i) => <option key={i.id} value={`indicator:${i.id}`}>{i.label}</option>)}
          </optgroup>
        </select>
      </label>

      <label className="flex items-start gap-2 text-xs">
        <input
          type="checkbox"
          checked={state.compare_within_urban_rural}
          onChange={(e) => update((s) => ({ ...s, compare_within_urban_rural: e.target.checked }))}
        />
        <span>
          Compare like with like
          <span className="block text-[var(--text-muted)]">
            Rank each area against others of the same urban/rural type, so villages aren&apos;t judged against city centres.
          </span>
        </span>
      </label>
    </div>
  );
}
