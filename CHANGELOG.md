# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- **Place names on the map** are drawn by the app, not the basemap: one type scale from
  city to hamlet in the interface's ink and surface colours, legible on both themes over
  the choropleth, and in the interface language (Caerdydd when the page is in Welsh).

### Fixed

- Switching the theme no longer blanks the map while the other basemap loads.
- "Better than 100% of the UK" can no longer appear: the top area reads 99%.
- On phones the legend sits clear of the map attribution.
- Three English strings in the Welsh interface: the "and" in "Lloegr a Chymru" (browsers
  have no Welsh list patterns, so the catalogue supplies it), the assistant's greeting and
  disclaimer, and the switcher's "(drafft)".

## [0.3.0] - 2026-10-08

### Added

- **Wales.** Every neighbourhood in England and Wales is scored: 35,672 LSOAs, with
  Welsh sources where England's stop (WIMD 2025, the Welsh Government's schools list and
  council tax levels, local-authority exam results, Natural Resources Wales flood risk
  areas, the Wales bus timetable and OpenStreetMap extract). A few indicators are
  England-only for now and say so in Welsh profiles.
- **Benchmarks per indicator.** Measures that are the same everywhere are ranked across
  both nations; those each nation records its own way (crime, deprivation indices,
  schools, prices, council tax) are ranked within the nation. Profiles show which, and
  carry nation and UK medians and percentiles. "Compare against" on the map now offers
  every area, the same nation or the same urban/rural type.
- Nation as configuration (`config/nations.yaml`, `LIX_NATIONS=E,W`), coverage per
  source and `lix validate config`, which lists the themes still short of data in a
  nation.
- **Languages.** A locale layer for the interface (English, Cymraeg as a draft; Gàidhlig
  and Gaeilge to follow with their nations): every string comes from a catalogue, numbers
  and dates follow the locale, the data labels have a Welsh catalogue with English
  fallback, and the assistant replies and reports failures in the chosen language. See
  [docs/i18n.md](docs/i18n.md) for how to review a draft.

### Changed

- Data pack schema v2: per-indicator quality codes replace the 32-bit mask (which capped
  the index at 32 scored indicators), the manifest carries the geography, and older
  packs are refused with a message that says to run `make data-download`.
- Population comes from the ONS mid-2024 estimates for both nations instead of IoD
  2025's England-only mid-2022 figures.
- `/health` reports the active nations; `ThemeScore.england_median` is now
  `country_median`, beside `nation_median`.

## [0.2.0] - 2026-10-08

### Changed

- A new look: colour now means data. The chrome is monochrome on warm neutrals; the map
  uses a diverging ramp around the median (orange worse than typical, pale neutral
  typical, teal better) instead of one blue; each theme has its own colour in score bars,
  sliders and charts; bands take the ramp's colour for their fifth.
- Dark mode now includes the assistant's chat, and a header toggle chooses auto, light or
  dark. Small labels pass 4.5:1 contrast on both surfaces, and keyboard focus has a
  visible ring.
- Every colour comes from `web/lib/palette.ts`; `npm run tokens` generates the CSS
  variables and CI checks the file is current. Tests cover contrast, the ramp and
  theme-colour separation ([docs/design.md](docs/design.md)).

## [0.1.0] - 2026-10-08

The first release: scores for every neighbourhood in England from open data, a map
to explore them and an assistant that answers by building the interface it needs.
Run it with `make quickstart` (Docker, make and curl; see the README).

### Scores

- All 33,755 England neighbourhoods (2021 LSOAs) scored 0–100 on eight themes: safety,
  environment, health services, schools and childcare, transport, amenities, housing and
  community. 64 indicators from about 40 open datasets; 31 of them are scored and the
  rest are shown for context, so related measures aren't counted twice.
- Five ready-made weightings (balanced, family, young professional, retired, commuter),
  any custom weighting, and a "compare like with like" switch for urban and rural areas.
- How much a result depends on the weights: each area's percentile range over
  plausible weightings, and "close call" flags in rankings.
- Checked: a 25-place face-validity review (49/49 checks, the key ones run on every
  build) and the method in [docs/methodology.md](docs/methodology.md).

### The app

- A map of every neighbourhood, recoloured in the browser as weights change.
- Postcode and place search; area profiles with council and England benchmarks,
  strengths and weak spots, data dates and shareable links.
- A shortlist with side-by-side comparison of up to five areas.
- Analyst mode: distributions, an indicator overlap heatmap, read-only SQL and CSV export.
- Pages for the method, validation, assistant evals and sources; light and dark mode;
  works on a phone.

### The assistant

- Ranks, profiles, compares and explains areas, finds well-run pubs, GPs and schools
  nearby, and moves the map and weights. Its replies are tested to use only numbers
  from the data.
- Any provider through Pydantic AI: OpenRouter by default (Claude Haiku 5.5, with Qwen
  3.8 27B as fallback), or Anthropic, OpenAI, Google or a local Ollama model.
- 30-case eval suite; Claude Opus 5.5, Claude Haiku 5.5 and Qwen 3.8 27B pass all 30
  ([docs/evals.md](docs/evals.md)). Haiku costs about $0.0014 a question.
- Caps per question, conversation, minute and day; refusals and model errors are chat
  replies and the map keeps working. Without a key, the suggested questions are
  answered from recordings.
- The same tools over MCP at `/mcp`, for Claude Desktop and other MCP clients.

### Running it

- docker compose behind one address (port 3000 by default) that works on any host.
- Images for linux/amd64 and linux/arm64 on GitHub's container registry, and the data
  pack (about 120 MB) as a release asset, so nobody needs the 20 GB build.
- The `lix` pipeline rebuilds everything from the original sources:
  resolve, fetch, stage, indicators, score, tiles, validate.

### Known limitations

- England only. Scores describe neighbourhoods of 1,000–3,000 residents, not streets or
  homes, and distances are straight-line.
- Greater Manchester Police publishes no street crime data, so crime there is estimated.
- Road and rail noise, surface-water flooding and tree cover aren't included yet.
- Each source has its own date (shown in the app); the data pack was built on
  7 October 2026.

[Unreleased]: https://github.com/MysterionRise/uk-liveability-index/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/MysterionRise/uk-liveability-index/releases/tag/v0.3.0
[0.2.0]: https://github.com/MysterionRise/uk-liveability-index/releases/tag/v0.2.0
[0.1.0]: https://github.com/MysterionRise/uk-liveability-index/releases/tag/v0.1.0
