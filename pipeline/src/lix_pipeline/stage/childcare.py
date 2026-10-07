"""Ofsted-registered nurseries and other group childcare, with places and quality.

Only childcare on non-domestic premises on the Early Years Register (care for under-5s)
is located: childminders' addresses are withheld, and out-of-school clubs serve school
children. Quality uses the same 0–1 scale as schools: the renewed early years
framework's grades (from November 2025) where inspected under it, otherwise the
previous overall effectiveness grade, otherwise "expected standard".
"""

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.stage.health import geocode_postcodes
from lix_pipeline.stage.schools import NEUTRAL, OEIF_SCALE, REPORT_CARD_SCALE

logger = setup_logging("stage.childcare")

REIF_PREFIX = "EYR REIF: Most recent: "
REIF_AREAS = [
    "Inclusion",
    "Curriculum and teaching",
    "Achievement",
    "Behaviour, attitudes and establishing routines",
    "Children's welfare and wellbeing",
    "Leadership and governance",
]
OEIF_OVERALL = "EYR OEIF/CIF: Most recent: Overall effectiveness"


def _read(path) -> pl.DataFrame:
    """The CSV has title lines above the header; find the header by its first column."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        skip = next(i for i, line in enumerate(f) if line.startswith("Web link,Provider URN"))
    return pl.read_csv(path, skip_rows=skip, infer_schema=False, encoding="utf8-lossy")


def stage_ofsted_childcare() -> pl.LazyFrame:
    raw = _read(data_dir("raw") / "ofsted_childcare" / "ofsted_childcare.csv")
    df = raw.filter(
        (pl.col("Provider type") == "Childcare on non-domestic premises")
        & (pl.col("Provider Early Years Register flag") == "Y")
        & (pl.col("Provider subtype") != "Out-of-school day care")
    )
    reif = [
        pl.col(REIF_PREFIX + area).replace_strict(REPORT_CARD_SCALE, default=None)
        for area in REIF_AREAS
        if REIF_PREFIX + area in df.columns
    ]
    oeif = pl.col(OEIF_OVERALL).replace_strict(OEIF_SCALE, default=None)
    df = df.select(
        pl.col("Provider URN").alias("urn"),
        pl.col("Provider name").alias("name"),
        pl.col("Provider subtype").alias("subtype"),
        pl.col("Provider postcode").alias("postcode"),
        pl.col("Places").cast(pl.Int32, strict=False).alias("places"),
        pl.coalesce(pl.mean_horizontal(reif), oeif, pl.lit(NEUTRAL)).alias("quality"),
        pl.when(pl.mean_horizontal(reif).is_not_null())
        .then(pl.lit("renewed framework"))
        .when(oeif.is_not_null())
        .then(pl.lit("previous framework"))
        .otherwise(pl.lit("not yet inspected"))
        .alias("quality_source"),
    )
    df = geocode_postcodes(df).filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
    logger.info(
        f"{df.height:,} nurseries and pre-schools, {df['places'].sum():,} places; "
        f"{dict(df['quality_source'].value_counts().rows())}"
    )
    return df.lazy()
