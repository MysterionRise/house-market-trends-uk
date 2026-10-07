"""DfT Transport Connectivity Metric → 0–100 scores per LSOA.

The LSOA sheet has two title rows above the header ("LSOA21CD", "Employment
(walking)", ..., "Overall"). Scores are relative within England and Wales, not
travel times; DfT advises comparing places of the same urban/rural type.
"""

import re

import fastexcel
import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.transport")


def tcm_column(label: str) -> str:
    """'Employment (walking)' → 'tcm_employment_walking'; 'Overall' → 'tcm_overall'."""
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return f"tcm_{name}"


def stage_dft_connectivity() -> pl.LazyFrame:
    reader = fastexcel.read_excel(data_dir("raw") / "dft_connectivity" / "dft_connectivity.ods")
    sheet = reader.load_sheet_by_name("LSOA", header_row=2).to_polars()
    code_col = next(c for c in sheet.columns if c.upper().startswith("LSOA"))
    df = (
        sheet.rename(
            {code_col: "lsoa21cd", **{c: tcm_column(c) for c in sheet.columns if c != code_col}}
        )
        .filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .with_columns(pl.exclude("lsoa21cd").cast(pl.Float64, strict=False))
    )
    logger.info(f"{df.height:,} LSOAs, {df.width - 1} connectivity scores")
    return df.lazy()


# NaPTAN stop types → mode. Rail: station access area, entrance, platform; metro/tram:
# access area, platform, entrance; bus: on-street stop, bus station bay, coach bay
NAPTAN_MODES = {
    "RLY": "rail",
    "RSE": "rail",
    "RPL": "rail",
    "MET": "metro_tram",
    "PLT": "metro_tram",
    "TMU": "metro_tram",
    "BCT": "bus",
    "BCS": "bus",
    "BCQ": "bus",
    "FER": "ferry",
    "FBT": "ferry",
}


def stage_naptan() -> pl.LazyFrame:
    """Active public transport stops in Great Britain with their mode and BNG location."""
    df = (
        pl.scan_csv(data_dir("raw") / "naptan" / "naptan.csv", infer_schema=False)
        .filter(pl.col("Status") == "active")
        .select(
            pl.col("ATCOCode").alias("atco_code"),
            pl.col("CommonName").alias("name"),
            pl.col("LocalityName").alias("locality"),
            pl.col("StopType").alias("stop_type"),
            pl.col("StopType").replace_strict(NAPTAN_MODES, default=None).alias("mode"),
            pl.col("Easting").cast(pl.Float64, strict=False).alias("x"),
            pl.col("Northing").cast(pl.Float64, strict=False).alias("y"),
        )
        .filter(pl.col("mode").is_not_null() & pl.col("x").is_not_null())
        .collect()
    )
    logger.info(f"{df.height:,} active stops: {dict(df['mode'].value_counts().rows())}")
    return df.lazy()


# Ofcom output-area columns (residential premises) → our names
OFCOM_COUNTS = {
    "All Premises": "premises",
    "Number of premises with Gigabit availability": "gigabit",
    "Number of premises with SFBB availability": "superfast",
    "Number of premises unable to receive decent broadband from fixed or FWA": "below_uso",
}


def stage_ofcom_broadband() -> pl.LazyFrame:
    """Residential premises able to get gigabit / superfast broadband, summed to LSOA.

    Superfast is 30 Mbit/s or more; "below USO" is premises that can't get a decent
    connection (10 Mbit/s down, 1 up) from fixed lines or fixed wireless.
    """
    from lix_pipeline.geo.joins import oa_to_lsoa

    path = next((data_dir("raw") / "ofcom_broadband").glob("**/*fixed_oa_res_coverage*.csv"))
    raw = pl.read_csv(path, infer_schema=False)
    df = raw.select(
        pl.col("output_area").alias("oa21cd"),
        *[
            pl.col(src).cast(pl.Float64, strict=False).alias(dst)
            for src, dst in OFCOM_COUNTS.items()
        ],
    ).filter(pl.col("oa21cd").str.starts_with("E"))
    per_lsoa = oa_to_lsoa(df, list(OFCOM_COUNTS.values())).with_columns(
        (pl.col(c) / pl.col("premises") * 100).alias(f"{c}_pct")
        for c in ("gigabit", "superfast", "below_uso")
    )
    logger.info(
        f"{per_lsoa.height:,} LSOAs; gigabit available to "
        f"{per_lsoa['gigabit'].sum() / per_lsoa['premises'].sum():.1%} of homes"
    )
    return per_lsoa.lazy()
