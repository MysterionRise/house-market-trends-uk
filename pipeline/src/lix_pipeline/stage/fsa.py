"""Food Standards Agency hygiene ratings → England food businesses with location.

Ratings run 0–5 in England (Scotland's scheme uses Pass/Improvement Required and is
dropped with the rest of Scotland). Non-numeric states such as "AwaitingInspection" or
"Exempt" keep a null ``rating`` and are kept in ``rating_status``. The component
scores (hygiene, structural, confidence in management) are penalty points: lower is
better.
"""

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.joins import points_to_lsoa
from lix_pipeline.stage.geo import lonlat_to_bng
from lix_pipeline.stage.health import geocode_postcodes

logger = setup_logging("stage.fsa")

PUB_BAR_NIGHTCLUB = 7843


def stage_fsa() -> pl.LazyFrame:
    raw = pl.read_csv(data_dir("raw") / "fsa_fhrs" / "fsa_fhrs.csv", infer_schema_length=0)
    df = raw.filter(pl.col("SchemeType") == "FHRS").select(
        pl.col("FHRSID").cast(pl.Int64).alias("fhrs_id"),
        pl.col("BusinessName").alias("name"),
        pl.col("BusinessTypeID").cast(pl.Int32).alias("business_type_id"),
        pl.col("BusinessType").alias("business_type"),
        pl.col("RatingValue").cast(pl.Int8, strict=False).alias("rating"),
        pl.col("RatingValue").alias("rating_status"),
        pl.col("RatingDate").str.to_date(strict=False).alias("rating_date"),
        pl.col("Hygiene").cast(pl.Int16, strict=False).alias("score_hygiene"),
        pl.col("Structural").cast(pl.Int16, strict=False).alias("score_structural"),
        pl.col("ConfidenceInManagement").cast(pl.Int16, strict=False).alias("score_management"),
        pl.col("PostCode").alias("postcode"),
        pl.col("LocalAuthorityName").alias("local_authority"),
        pl.col("Longitude").cast(pl.Float64, strict=False).alias("lon"),
        pl.col("Latitude").cast(pl.Float64, strict=False).alias("lat"),
    )

    # Prefer the FSA's own coordinates; fall back to the postcode centroid
    x, y = lonlat_to_bng(df["lon"].fill_null(0), df["lat"].fill_null(0))
    has_xy = df["lon"].is_not_null() & df["lat"].is_not_null()
    df = df.with_columns(
        x=pl.when(has_xy).then(x), y=pl.when(has_xy).then(y), location_source=pl.lit("fsa")
    )
    fallback = geocode_postcodes(df.filter(~has_xy).drop("x", "y")).with_columns(
        pl.lit("postcode").alias("location_source")
    )
    df = pl.concat([df.filter(has_xy), fallback.drop("lsoa21cd")], how="diagonal_relaxed")
    df = points_to_lsoa(df).filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))

    pubs = df.filter(pl.col("business_type_id") == PUB_BAR_NIGHTCLUB).height
    logger.info(f"{df.height:,} England food businesses ({pubs:,} pubs, bars and nightclubs)")
    return df.lazy()
