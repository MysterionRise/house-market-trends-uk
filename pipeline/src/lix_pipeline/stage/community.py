"""Claimant count (Nomis): people claiming unemployment-related benefits, latest month."""

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.community")


def stage_claimant_count() -> pl.LazyFrame:
    raw = pl.read_csv(data_dir("raw") / "claimant_count" / "claimant_count.csv", infer_schema=False)
    df = raw.select(
        pl.col("GEOGRAPHY_CODE").alias("lsoa21cd"),
        pl.col("DATE_NAME").alias("period"),
        pl.col("OBS_VALUE").cast(pl.Int32, strict=False).alias("claimants"),
    ).filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
    logger.info(f"{df.height:,} LSOAs, {df['period'][0]}: {df['claimants'].sum():,} claimants")
    return df.lazy()
