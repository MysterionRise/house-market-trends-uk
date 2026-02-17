# UK Liveability Index

A data-driven liveability scoring system for neighbourhoods across England and Wales, built at **LSOA** (Lower Layer Super Output Area) level.

The project downloads, cleans, and joins multiple open datasets — house prices, deprivation indices, transport links, school ratings, and more — to produce a composite liveability score for every neighbourhood. Results are served via an interactive Streamlit dashboard with map visualisations.

## Data Sources (Phase 1)

| Dataset | Granularity | Source |
|---------|-------------|--------|
| HM Land Registry Price Paid | Transaction → LSOA | [Land Registry](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads) |
| English Indices of Deprivation (IMD) | LSOA | [GOV.UK](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019) |
| NSPL Postcode Lookup | Postcode → LSOA | [ONS Geoportal](https://geoportal.statistics.gov.uk) |
| LSOA 2021 Boundaries | LSOA polygons | [ONS Geoportal](https://geoportal.statistics.gov.uk) |

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync                          # install all dependencies
uv run python -m src.download --phase 1   # download Phase 1 datasets
uv run python -m src.clean --slug price_paid
uv run python -m src.clean --slug imd_2025
```

Or use the Makefile:

```bash
make install    # uv sync
make download   # download all datasets
make process    # clean + geocode
make test       # run pytest
make lint       # run ruff
```

## Project Structure

```
config/datasets.yaml    # dataset URLs, formats, metadata
src/
  download.py           # download engine with caching
  clean.py              # dataset-specific cleaners
  geocode.py            # NSPL postcode → LSOA mapping
  utils.py              # shared helpers
data/
  raw/                  # downloaded files (gitignored)
  processed/            # cleaned Parquet files (gitignored)
  geo/                  # boundary files (gitignored)
tests/                  # pytest suite
```

## Licence

Code in this repository is MIT-licensed (see [LICENSE](LICENSE)).

**Data attribution**: Contains HM Land Registry data, ONS data, and MHCLG data. All Crown copyright and database right. Licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
