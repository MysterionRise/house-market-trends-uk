# UK Liveability Index

> **Being restructured.** This repo started in 2020 as a plan to analyse UK house price trends.
> It is now being rebuilt as a data platform that scores **English** neighbourhoods on safety,
> environment, health access, schools, transport, amenities, affordability and community, using
> open data only. The data pipeline below works; the scoring model and the front end are not built yet.

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
- CI runs ruff and pytest on every push and PR to `master` (tests never touch the network);
  a nightly job checks every source is still reachable

| Dataset | Granularity | Source |
|---------|-------------|--------|
| HM Land Registry Price Paid | Transaction, aggregated to LSOA medians | [Land Registry](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads) |
| English Indices of Deprivation 2025 | LSOA 2021 | [GOV.UK](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025) |
| NSPL postcode lookup (Aug 2026) | Postcode to OA/LSOA/MSOA/LAD | [ONS Geoportal](https://geoportal.statistics.gov.uk) |
| LSOA, MSOA and local authority boundaries | Polygons | [ONS Geoportal](https://geoportal.statistics.gov.uk) |
| LSOA population-weighted centroids, OA lookup, LSOA 2011→2021, rural–urban class | LSOA / OA | [ONS Geoportal](https://geoportal.statistics.gov.uk) |
| MSOA names | MSOA | [House of Commons Library](https://houseofcommonslibrary.github.io/msoanames/) |
| OS Open Names (settlements) | Place | [Ordnance Survey](https://www.ordnancesurvey.co.uk/products/os-open-names) |

## Planned

- About 30 more open datasets: police.uk crime, Defra air quality, NHS GP access, schools and
  nurseries (Ofsted), DfT transport connectivity, broadband, flood risk, green space, and
  "well-run pubs" from OpenStreetMap and Food Standards Agency hygiene ratings
- A composite score per LSOA, with persona presets and weights users can tune, and the method written down
- A generative-UI front end where an AI assistant answers questions with maps, area cards and comparisons
  (Pydantic AI + AG-UI + CopilotKit, any LLM provider)

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
make install    # uv sync
make fetch      # download every dataset pinned in the lockfile (about 7 GB; Price Paid is 5.5 GB)
make stage      # stage every downloaded dataset to data/staged/*.parquet
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
