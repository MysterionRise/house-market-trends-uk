"""Road collisions (STATS19): every reported injury collision with its severity and location."""

import polars as pl

from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.safety")

# collision_severity codes
SEVERITY = {"1": "fatal", "2": "serious", "3": "slight"}


def stage_stats19() -> pl.LazyFrame:
    """Collisions in England with BNG coordinates (a handful without a location dropped)."""
    df = (
        pl.scan_csv(data_dir("raw") / "stats19" / "stats19.csv", infer_schema=False)
        .select(
            "collision_index",
            pl.col("collision_year").cast(pl.Int16).alias("year"),
            pl.col("collision_severity").replace_strict(SEVERITY, default=None).alias("severity"),
            pl.col("location_easting_osgr").cast(pl.Float64, strict=False).alias("x"),
            pl.col("location_northing_osgr").cast(pl.Float64, strict=False).alias("y"),
            pl.col("local_authority_ons_district").alias("lad_cd"),
        )
        .filter(pl.col("lad_cd").str.starts_with("E") & pl.col("x").is_not_null())
        .collect()
    )
    years = df["year"].unique().sort().to_list()
    logger.info(f"{df.height:,} collisions in England, {years[0]}–{years[-1]}")
    return df.lazy()
