"""NHS GP practices: locations (ODS), real catchments (registrations by LSOA) and staffing.

Joining registrations to staffing gives each LSOA the GP capacity of the practices its
residents actually use, rather than of whichever practice happens to be nearest.
"""

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.nspl import load_nspl

logger = setup_logging("stage.health")

# Positions in the headerless ODS DSE "epraccur" report (1-based in NHS documentation)
EPRACCUR_COLUMNS = {
    1: "practice_code",
    2: "name",
    10: "postcode",
    11: "open_date",
    12: "close_date",
    13: "status",
    15: "commissioner",
    26: "role",
}
GP_PRACTICE_ROLE = "RO76"


def geocode_postcodes(df: pl.DataFrame, postcode_col: str = "postcode") -> pl.DataFrame:
    """Add BNG ``x``/``y`` and ``lsoa21cd`` from NSPL (terminated postcodes included)."""
    nspl = (
        load_nspl(live_only=False, nations=None)
        .select("postcode_norm", "east1m", "north1m", "lsoa21cd")
        .unique("postcode_norm", keep="first")
        .collect()
    )
    norm = pl.col(postcode_col).str.replace_all(r"\s", "").str.to_uppercase()
    return (
        df.with_columns(norm.alias("_pc"))
        .join(nspl, left_on="_pc", right_on="postcode_norm", how="left")
        .rename({"east1m": "x", "north1m": "y"})
        .drop("_pc")
    )


def stage_ods_gp() -> pl.LazyFrame:
    """Active GP practices in England with their location."""
    raw = pl.read_csv(
        data_dir("raw") / "ods_gp" / "ods_gp.csv", has_header=False, infer_schema=False
    )
    df = raw.select(
        pl.col(f"column_{i}").alias(name) for i, name in EPRACCUR_COLUMNS.items()
    ).filter((pl.col("status") == "ACTIVE") & (pl.col("role") == GP_PRACTICE_ROLE))
    df = geocode_postcodes(df).filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
    logger.info(f"{df.height:,} active GP practices in England")
    return df.drop("role", "status").lazy()


def stage_gp_registrations() -> pl.LazyFrame:
    """Registered patients by practice and the LSOA they live in."""
    path = data_dir("raw") / "gp_registrations" / "gp-reg-pat-prac-lsoa-all.csv"
    df = (
        pl.read_csv(path, infer_schema_length=0)
        .filter((pl.col("SEX") == "ALL") & pl.col("LSOA_CODE").str.contains(ENGLAND_LSOA21))
        .select(
            pl.col("PRACTICE_CODE").alias("practice_code"),
            pl.col("LSOA_CODE").alias("lsoa21cd"),
            pl.col("NUMBER_OF_PATIENTS").cast(pl.Int32).alias("patients"),
            pl.col("EXTRACT_DATE").str.to_date().alias("extract_date"),
        )
    )
    logger.info(f"{df['patients'].sum():,} patients in {df['lsoa21cd'].n_unique():,} LSOAs")
    return df.lazy()


def stage_gp_workforce() -> pl.LazyFrame:
    """Full-time-equivalent staff per practice (GPs excluding trainees, nurses, others)."""
    files = sorted((data_dir("raw") / "gp_workforce").glob("*High level.csv"))
    if not files:
        raise FileNotFoundError("No high-level practice CSV in data/raw/gp_workforce")
    df = pl.read_csv(files[-1], infer_schema_length=0).filter(pl.col("MEASURE") == "FTE")
    value = pl.col("VALUE").cast(pl.Float64, strict=False)  # "NA" for suppressed values
    role = pl.col("DETAILED_STAFF_ROLE")
    group = pl.col("STAFF_GROUP")
    # Sum individual roles: the published "Total" row is 0 for some staffed practices
    roles = group.is_not_null() & (role != "Total")
    trainee = role.str.starts_with("GP in Training")
    out = df.group_by(pl.col("PRAC_CODE").alias("practice_code")).agg(
        value.filter(roles & (group == "GP")).sum().alias("gp_fte"),
        value.filter(roles & (group == "GP") & ~trainee).sum().alias("qualified_gp_fte"),
        value.filter(roles & (group == "Nurses")).sum().alias("nurse_fte"),
        value.filter(roles & (group == "Direct Patient Care")).sum().alias("direct_care_fte"),
        pl.lit(files[-1].stem).first().alias("source_file"),
    )
    logger.info(f"{out.height:,} practices, {out['qualified_gp_fte'].sum():,.0f} qualified GP FTE")
    return out.lazy()
