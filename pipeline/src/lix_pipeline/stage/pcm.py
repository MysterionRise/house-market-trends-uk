"""Defra PCM 1km background air-quality grids → tidy cells, then LSOA means.

The CSVs start with a few lines of metadata (pollutant, year, units) before the
``gridcode,x,y,<pollutant><year>`` header; x/y are cell centres in BNG metres.
Each LSOA gets the mean over its residential postcodes of the cell they sit in,
which approximates a population-weighted average.
"""

import re

import polars as pl

from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.access import residential_postcodes
from lix_pipeline.geo.grids import sample_grid_at_points

logger = setup_logging("stage.pcm")


def read_pcm(path) -> tuple[pl.DataFrame, int]:
    """Return (cells with x, y, value) and the data year."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_at = next(i for i, line in enumerate(lines) if line.startswith("gridcode,"))
    value_col = lines[header_at].split(",")[3]
    # "no22024" or "pm252024g": the year is the last four digits, not the first ("2202")
    year = int(re.search(r"(\d{4})g?$", value_col).group(1))
    df = pl.read_csv(path, skip_rows=header_at, infer_schema_length=0).select(
        pl.col("x").cast(pl.Int64),
        pl.col("y").cast(pl.Int64),
        # Cells outside the modelled area are "MISSING"
        pl.col(value_col).cast(pl.Float64, strict=False).alias("value"),
    )
    return df.filter(pl.col("value").is_not_null()), year


def stage_pcm(slug: str) -> pl.LazyFrame:
    """LSOA population-weighted mean of one pollutant (µg/m³)."""
    path = data_dir("raw") / slug / f"{slug}.csv"
    cells, year = read_pcm(path)
    out = sample_grid_at_points(cells, residential_postcodes(), "value").with_columns(
        pl.lit(year).alias("year")
    )
    logger.info(f"[{slug}] {year}: {out.height:,} LSOAs from {cells.height:,} cells")
    return out.lazy()
