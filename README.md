# UK Liveability Index

> **Being restructured.** This repo started in 2020 as a plan to analyse UK house price trends.
> It is now a data platform that scores **English** neighbourhoods on safety, environment,
> health access, schools, transport, amenities, affordability and community, using open data
> only, with a map and an AI assistant that answers by building the interface it needs.

Everything is computed at **LSOA** level (Lower Layer Super Output Area, 1,000 to 3,000 residents
each; 33,755 in England).

## What works today

The pipeline downloads, stages and joins the open datasets below:

- `lix resolve` finds each source's current file and pins it in `config/datasets.lock.json`.
  ONS deletes Open Geography items whenever it publishes a new version, so those are found by
  search; GOV.UK files through the content API.
- `lix fetch` downloads what the lockfile pins (resumable, checksummed, rejects error pages served
  as data, waits out ArcGIS exports still being generated, extracts only the files it needs)
- `lix stage` turns each raw file into tidy Parquet in `data/staged/`
- `geo_lsoa` is the backbone every indicator joins onto: each England LSOA with its MSOA,
  local authority, region, friendly MSOA name, population-weighted centroid, urban/rural class,
  population, area and map bounding box; `lix validate geo` checks it
- helpers bring other geographies onto LSOAs: points, output areas, MSOA/local-authority values,
  1km grids (sampled at postcodes, so population-weighted) and distance-based access to places
- `lix indicators` builds 57 indicators (29 scored across 8 themes) from
  [`config/indicators.yaml`](config/indicators.yaml); `lix score` turns them into theme and
  overall scores per LSOA for five persona presets ([`config/weights.yaml`](config/weights.yaml)),
  plus a QA report. The method, including how Greater Manchester's missing crime data and
  Ofsted's framework changes are handled, is in [docs/methodology.md](docs/methodology.md)
- CI runs ruff and pytest on every push and PR to `master` (tests never touch the network);
  a nightly job checks every source is still reachable

Datasets ingested so far (full list with licences: [docs/data-sources.md](docs/data-sources.md)):

| Theme | Sources |
|-------|---------|
| Geography | NSPL postcode lookup, LSOA/MSOA/local authority boundaries, population-weighted centroids, OA and 2011→2021 lookups, rural–urban class, House of Commons Library MSOA names, OS Open Names |
| Community | English Indices of Deprivation 2025; Census 2021 (population, density, age, households, health, accommodation, cars, tenure, commuting, qualifications); Nomis claimant count (monthly) |
| Housing | HM Land Registry Price Paid (LSOA medians); ONS small-area income; council tax by billing authority; VOA housing stock by council tax band and build period |
| Safety | police.uk street crime, 36 months (Greater Manchester Police publishes none; flagged); DfT road collisions (STATS19, 5 years) |
| Environment | Defra modelled NO₂, PM2.5 and PM10 (1km, population-weighted to LSOAs); OS Open Greenspace; Environment Agency flood risk from rivers and the sea, by postcode |
| Health | NHS GP practices, patients registered by LSOA (real catchments), GP workforce; NHS dental practices; NHSBSA community pharmacies |
| Education | Get Information About Schools; Ofsted inspections blended across the 2024 and 2025 framework changes; Ofsted nurseries and pre-schools |
| Transport | DfT Transport Connectivity Metric; NaPTAN stations and stops; Ofcom broadband coverage |
| Amenities | OpenStreetMap points of interest; Food Standards Agency hygiene ratings |

### API and assistant

`make api` (or `uv run lix-api`) serves, on http://localhost:8000:

- a REST API under `/api/v1`: place search, area profiles, rankings with any weights and
  filters, comparisons, nearest places (GPs, schools, well-run pubs, ...), score explanations,
  the indicator catalogue and read-only SQL (docs at `/docs`)
- an AI assistant at `/agent` speaking [AG-UI](https://docs.ag-ui.com), built with
  [Pydantic AI](https://ai.pydantic.dev): its tools return typed results the front end renders as
  maps, cards and tables, and it moves the map and weight sliders through shared state
- an [MCP](https://modelcontextprotocol.io) server at `/mcp` with the same tools, for Claude
  Desktop and other MCP clients

The model is set with `LIX_MODEL` (default `anthropic:claude-opus-5-5`; also `openai:...`,
`google:...`, `ollama:...`). `LIX_MODEL=test` runs a scripted assistant that needs no API key.
See [.env.example](.env.example). `docker compose up` runs the API plus a static server for the
map tiles (`make tiles` builds them).

### Front end

`web/` is a Next.js app (Node 24, see `.nvmrc`):

- a MapLibre map of every England neighbourhood from static PMTiles, coloured by England
  percentile; weights are recomputed in the browser, so moving a slider recolours all 33,755
  areas in about 100 ms
- an assistant chat ([CopilotKit](https://copilotkit.ai) over AG-UI) whose tool calls render as
  components: ranked lists, area profiles, side-by-side comparisons, nearby places, score
  explanations and SQL results. The assistant and the page share state, so it can move the map,
  outline areas, set the weight sliders and save a shortlist, and it sees what you change
- presets (family, young professional, retired, commuter), a "compare like with like" switch for
  urban/rural fairness, a shortlist, shareable URLs, light and dark mode, and an analyst mode with
  a distribution chart, read-only SQL and CSV export

```bash
make web-install   # npm ci (Node 24)
make dev           # API with the scripted assistant + front end on http://localhost:3000
make web-test      # typecheck, lint, unit tests (incl. scoring parity with Python)
make e2e           # browser tests (Playwright) against the local build
```

With a model key in `.env`, `LIX_MODEL=anthropic:claude-opus-5-5 make dev` uses a real LLM.

## Planned

- More open datasets: bus and rail service frequency, surface water flooding, road and rail
  noise, tree cover, life expectancy, CQC ratings, school results, Overture Places (to
  corroborate pubs) and the CDRC's Access to Healthy Assets & Hazards
- Walking-network travel times instead of straight-line distances

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
make install    # uv sync
make fetch      # download every dataset pinned in the lockfile (about 7 GB; Price Paid is 5.5 GB)
make stage      # stage every downloaded dataset to data/staged/*.parquet
make indicators # build the indicator table
make score      # theme/overall scores, browser files and QA report in data/serve/
make validate   # check the staged geography backbone
make test       # pytest (no network access; HTTP is tested against a local server)
make lint       # ruff check + format check
```

Or step by step:

```bash
uv run lix resolve --all              # pick up new upstream versions (updates the lockfile)
uv run lix fetch --theme geography    # or --slug nspl, --priority P0, --all
uv run lix stage --all
uv run lix resolve --check --all      # is every source still reachable?
```

Set `LIX_DATA_DIR` to keep data somewhere other than `./data`.

## Layout

```
config/datasets.yaml    dataset URLs, formats, licences
core/                   lix_core: paths, config, logging, shared code patterns
api/                    lix_api: FastAPI, the AI assistant (AG-UI) and the MCP server
pipeline/               lix_pipeline and the `lix` CLI
web/                    Next.js front end: map, chat and generative UI components
contracts/              JSON Schema of the API models and the scoring golden cases
  fetch/http.py         download engine with caching and resume
  geo/                  NSPL postcode lookup, LSOA boundaries
  stage/                one stager per dataset (nspl, price_paid, iod)
data/                   raw/, staged/, ... (gitignored; rebuilt by the pipeline)
```

The Python side is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
(`core`, `pipeline`, `api`).

## Licence

Code is MIT-licensed (see [LICENSE](LICENSE)).

Data attribution: contains HM Land Registry data, ONS data and MHCLG data, Crown copyright and
database right, licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Contains OS data, Royal Mail data and GeoPlace data © Crown copyright and database right.
