# Changelog

All notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

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

[0.1.0]: https://github.com/MysterionRise/uk-liveability-index/releases/tag/v0.1.0
