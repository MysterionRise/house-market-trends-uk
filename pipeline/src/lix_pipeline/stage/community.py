"""Claimant count (Nomis): people claiming unemployment-related benefits, latest month."""

import polars as pl

from lix_core.codes import in_scope
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.community")


def stage_claimant_count() -> pl.LazyFrame:
    raw = pl.read_csv(data_dir("raw") / "claimant_count" / "claimant_count.csv", infer_schema=False)
    df = raw.select(
        pl.col("GEOGRAPHY_CODE").alias("lsoa21cd"),
        pl.col("DATE_NAME").alias("period"),
        pl.col("OBS_VALUE").cast(pl.Int32, strict=False).alias("claimants"),
    ).filter(in_scope("lsoa21cd"))
    logger.info(f"{df.height:,} LSOAs, {df['period'][0]}: {df['claimants'].sum():,} claimants")
    return df.lazy()


def stage_life_expectancy() -> pl.LazyFrame:
    """Life expectancy at birth per MSOA (2021 codes), men, women and their mean."""
    raw = pl.read_csv(
        data_dir("raw") / "life_expectancy" / "life_expectancy.csv", infer_schema=False
    )
    msoa = raw.filter(in_scope("Area Code", "mid") & pl.col("Category").is_null()).with_columns(
        pl.col("Value").cast(pl.Float64, strict=False)
    )
    df = (
        msoa.pivot(
            on="Sex", index=["Area Code", "Time period"], values="Value", aggregate_function="first"
        )
        .rename(
            {
                "Area Code": "msoa21cd",
                "Time period": "period",
                "Male": "le_male",
                "Female": "le_female",
            }
        )
        .with_columns(((pl.col("le_male") + pl.col("le_female")) / 2).alias("le_mean"))
    )
    logger.info(
        f"{df.height:,} MSOAs, {df['period'][0]}: median {df['le_mean'].median():.1f} years"
    )
    return df.lazy()
