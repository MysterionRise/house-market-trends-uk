# Design

One page on how the interface looks, so changes stay consistent. The tokens live in
`web/lib/palette.ts`; `npm run tokens` writes them to `web/app/tokens.gen.css`, and CI
fails if that file is stale.

## Colour means data

The chrome (page, cards, buttons, links, sliders, the "working" pulse) is monochrome on
warm neutrals, in light and dark. Colour is reserved for data, so a coloured thing on screen
is always a value or an identity:

- **Place names on the map are chrome, not data.** The basemap's labels are hidden and
  the app draws its own from the same tiles (`web/components/map/placeLabels.ts`): Noto
  Sans, the tile server's font, bold for cities and regular below, in `--text-primary`
  down to `--text-muted` with a soft `--page` halo so they read over any fill, and in the
  interface language.
- **The map ramp is diverging around the median.** Scores are percentiles, so 50 is
  "typical". Warm terracotta means worse than typical, pale sand means typical, teal-green
  means better. Nine stops, equal steps each side, orange–teal because that pair stays
  apart under red–green colour blindness. In dark mode the poles are bright and the middle
  recedes into the surface. The legend draws the ramp composited over the surface at the
  map's fill opacity, so it matches what the map shows. Areas with no value are a cool grey,
  which never reads as "typical".
- **Each theme has one colour**, used wherever that theme is shown: score bars, weight
  sliders, the histogram, the explainer. The order follows the screen (safety, environment,
  health, education, transport, amenities, housing, community) and the hues were chosen
  from the data-viz reference palette so every neighbouring pair stays apart under
  simulated protan and deutan vision in both modes (worst adjacent pair ΔE 7.2 light,
  8.6 dark; full-colour worst pair 19.6 and 19.3). Don't reorder or re-step them without
  re-running the validator. Theme colours always sit next to a text label; they never
  carry meaning alone.
- **The overall score is ink**, not a theme colour, and ranked-list bars are ink too.
- **The correlation heatmap** reuses the ramp's warm and cool steps (warm = negative, cool
  = positive) around a neutral grey, so there is one diverging language in the app.
- **Bands** (bottom fifth … top fifth) take the ramp colour of that fifth.
- **Status** stays separate: `--critical` for errors and stale data, always with words.

## Tokens

| Token | Use |
|---|---|
| `--page`, `--surface-1` | page background; cards, panels, the legend |
| `--text-primary`, `--text-secondary`, `--text-muted` | ink; all three pass 4.5:1 on both surfaces, so small labels may use muted |
| `--border`, `--hover`, `--track`, `--baseline` | hairlines, hover wash, empty bars, chart axes |
| `--accent` | ink for controls and links (links are underlined, not coloured) |
| `--focus` | the keyboard focus ring (amber, ≥ 3:1 on both surfaces) |
| `--no-data` | areas without a value |
| `--ramp-0` … `--ramp-8` | the map ramp, worst to best |
| `--theme-<id>` | one colour per theme |
| `--div-neg`, `--div-mid`, `--div-pos` | the heatmap |
| `--critical` | errors, stale data |

Components use tokens through Tailwind arbitrary values (`bg-[var(--surface-1)]`) or
`style`. The only place that reads colours in TypeScript is the map, which MapLibre needs
as real values; it imports them from `palette.ts`.

## Light and dark

Dark mode follows the system setting, with a header toggle (auto / light / dark) stored
in `localStorage`. `components/ThemeProvider.tsx` writes `data-theme` on `<html>` (what
the tokens key on) and the `dark` class (what CopilotKit's chat stylesheet keys on); an
inline script in `app/layout.tsx` does the same before the first paint. The chat's own
shadcn-style variables are mapped onto our tokens in `globals.css`, so it uses the same
warm greys as the rest of the app.

Dark values are chosen, not inverted: the ramp flips its lightness, the theme colours use
the reference palette's dark steps, the neutrals are a separate set.

## Checks

`web/lib/palette.test.ts` checks text contrast, the focus ring, the ramp's shape and
poles, theme-colour separation, and that the generated tokens are complete. For a new
categorical colour, run the data-viz palette validator (the `dataviz` skill's
`validate_palette.js`) in both modes before adding it. Lighthouse desktop stays ≥ 88.

## Type and shape

System sans everywhere (`system-ui, -apple-system, "Segoe UI", sans-serif`), tabular
figures only in columns that align. Cards are `rounded-xl` with a hairline border on
`--surface-1`; bars are 8px thin with 4px rounded ends; a bar never carries a value alone,
the number is always printed beside it.
