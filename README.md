# UK Liveability Index

> **Being restructured.** This repo started in 2020 as a plan to analyse UK house price trends.
> It is now being rebuilt as a data platform that scores **English** neighbourhoods on safety,
> environment, health access, schools, transport, amenities, affordability and community, using
> open data only. The data pipeline and scoring model work; the API and front end are next.

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
- `lix indicators` builds 43 indicators (24 scored across 8 themes) from
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
| Community | English Indices of Deprivation 2025; Census 2021 (population, density, age, households, health, accommodation, cars, tenure, commuting, qualifications) |
| Housing | HM Land Registry Price Paid (LSOA medians) |
| Safety | police.uk street crime, 36 months (Greater Manchester Police publishes none; flagged) |
| Environment | Defra modelled NO₂, PM2.5 and PM10 (1km, population-weighted to LSOAs) |
| Health | NHS GP practices, patients registered by LSOA (real catchments), GP workforce |
| Education | Get Information About Schools; Ofsted inspections blended across the 2024 and 2025 framework changes |
| Transport | DfT Transport Connectivity Metric |
| Amenities | OpenStreetMap points of interest; Food Standards Agency hygiene ratings |

## Planned

- More open datasets: broadband, flood risk, green space, nurseries, pharmacies, collisions,
  council tax, income, life expectancy, public transport stops, supermarkets and more
- Map tiles, an API and an AI assistant that can rank, compare and explain areas
- A generative-UI front end where an AI assistant answers questions with maps, area cards and comparisons
  (Pydantic AI + AG-UI + CopilotKit, any LLM provider)

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
pipeline/               lix_pipeline and the `lix` CLI
  fetch/http.py         download engine with caching and resume
  geo/                  NSPL postcode lookup, LSOA boundaries
  stage/                one stager per dataset (nspl, price_paid, iod)
data/                   raw/, staged/, ... (gitignored; rebuilt by the pipeline)
```

The repo is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/); `api/`
(FastAPI + AI agent) and `web/` (Next.js front end) will join it.

## Licence

Code is MIT-licensed (see [LICENSE](LICENSE)).

Data attribution: contains HM Land Registry data, ONS data and MHCLG data, Crown copyright and
database right, licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Contains OS data, Royal Mail data and GeoPlace data © Crown copyright and database right.
