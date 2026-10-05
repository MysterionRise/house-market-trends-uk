# UK Liveability Index

> **Being restructured.** This repo started in 2020 as a plan to analyse UK house price trends.
> It is now being rebuilt as a data platform that scores UK neighbourhoods on house prices,
> deprivation, transport and schools (England and Wales today; Scotland and Northern Ireland
> planned). The data pipeline below works; the scoring model and the front end are not built yet.

Everything is computed at **LSOA** level (Lower Layer Super Output Area, 1,000 to 3,000 residents each).

## What works today

The Phase 1 pipeline downloads, cleans and joins the open datasets below:

- `src/download.py` downloads and caches each dataset listed in `config/datasets.yaml`
- `src/clean.py` turns each raw file into Parquet
- `src/geocode.py` maps postcodes to LSOAs using the ONS postcode lookup (NSPL)
- `tests/` covers all three steps; CI runs ruff and pytest on every push and PR to `master`

| Dataset | Granularity | Source |
|---------|-------------|--------|
| HM Land Registry Price Paid | Transaction, mapped to LSOA | [Land Registry](https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads) |
| English Indices of Deprivation 2019 | LSOA | [GOV.UK](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019) |
| NSPL postcode lookup | Postcode to LSOA | [ONS Geoportal](https://geoportal.statistics.gov.uk) |
| LSOA 2021 boundaries | LSOA polygons | [ONS Geoportal](https://geoportal.statistics.gov.uk) |

IMD 2019 stands in until IMD 2025 is published (the config slug is already `imd_2025`).

## Planned

- More datasets: transport access and school ratings
- A composite score per LSOA, with the method and weights written down
- A generative-UI front end (CopilotKit or similar) that answers questions with maps and tables built from the scores

## Running it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
make install    # uv sync
make download   # download all datasets (Price Paid alone is about 4.3 GB)
make process    # clean + geocode
make test       # pytest
make lint       # ruff
```

Or step by step:

```bash
uv run python -m src.download --phase 1
uv run python -m src.clean --slug price_paid
uv run python -m src.clean --slug imd_2025
```

## Layout

```
config/datasets.yaml    dataset URLs, formats, licences
src/
  download.py           download engine with caching
  clean.py              dataset-specific cleaners
  geocode.py            NSPL postcode to LSOA mapping
  utils.py              shared helpers
data/                   raw/, processed/ and geo/ (all gitignored)
tests/                  pytest suite
```

## Licence

Code is MIT-licensed (see [LICENSE](LICENSE)).

Data attribution: contains HM Land Registry data, ONS data and MHCLG data, Crown copyright and
database right, licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
