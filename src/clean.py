"""Dataset-specific cleaners for the UK Liveability Index pipeline.

Usage:
    python -m src.clean --slug price_paid
    python -m src.clean --slug imd_2025
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import duckdb
import polars as pl

from src.geocode import load_nspl, log_match_rate, postcode_to_lsoa
from src.utils import ensure_dirs, get_project_root, setup_logging

logger = setup_logging("clean")

# Price Paid CSV has no headers; these are the official column names
PP_COLUMNS = [
    "transaction_id",
    "price",
    "date_of_transfer",
    "postcode",
    "property_type",
    "old_new",
    "duration",
    "paon",
    "saon",
    "street",
    "locality",
    "town_city",
    "district",
    "county",
    "ppd_category",
    "record_status",
]


def clean_price_paid(raw_path: Path | None = None) -> pl.LazyFrame:
    """Clean Price Paid data: read via DuckDB, geocode, aggregate to LSOA level."""
    if raw_path is None:
        raw_path = get_project_root() / "data" / "raw" / "price_paid" / "price_paid.csv"

    logger.info(f"Reading Price Paid data from {raw_path}")

    # Use DuckDB to read the large CSV efficiently
    con = duckdb.connect()

    # Build column aliases for the headerless CSV
    # DuckDB zero-pads column names based on total column count (column00..column15 for 16 cols)
    n_cols = len(PP_COLUMNS)
    pad_width = len(str(n_cols - 1))
    col_aliases = ", ".join(
        f"column{i:0{pad_width}d} AS {name}" for i, name in enumerate(PP_COLUMNS)
    )

    # Use parameterised path via DuckDB variable to avoid SQL injection
    con.execute("SET VARIABLE csv_path = ?", [str(raw_path)])
    query = f"""
        SELECT {col_aliases}
        FROM read_csv_auto(getvariable('csv_path'), header=false, all_varchar=true)
        WHERE column15 = 'A'
    """

    logger.info("Querying Price Paid via DuckDB (this may take a few minutes)...")
    result = con.execute(query)
    df = pl.from_arrow(result.fetch_arrow_table())
    con.close()

    logger.info(f"Loaded {len(df):,} completed transactions")

    # Cast types
    # Land Registry dates are formatted as "2024-01-15 00:00"
    df = df.with_columns(
        pl.col("price").cast(pl.Int64),
        pl.col("date_of_transfer").str.strptime(pl.Date, "%Y-%m-%d %H:%M"),
    )

    # Geocode: postcode → LSOA
    logger.info("Geocoding postcodes to LSOA...")
    nspl = load_nspl()
    lf = postcode_to_lsoa(df.lazy(), postcode_col="postcode", nspl=nspl)
    df = lf.collect()

    # Log match rate on the collected DataFrame (no extra collect needed)
    log_match_rate(df)

    # Drop rows without LSOA match
    before = len(df)
    df = df.filter(pl.col("lsoa21cd").is_not_null())
    logger.info(f"Dropped {before - len(df):,} rows without LSOA match")

    # Aggregate to LSOA level
    # Use timedelta to avoid crash on Feb 29 in leap years
    today = date.today()
    one_year_ago = today - timedelta(days=365)
    five_years_ago = today - timedelta(days=5 * 365)
    two_years_ago = today - timedelta(days=2 * 365)

    logger.info("Aggregating to LSOA level...")

    # Last 12 months stats
    recent_12m = df.filter(pl.col("date_of_transfer") >= one_year_ago)
    agg_12m = recent_12m.group_by("lsoa21cd").agg(
        pl.col("price").median().alias("median_price_12m"),
        pl.col("price").count().alias("transaction_count_12m"),
    )

    # Last 5 years stats
    recent_5y = df.filter(pl.col("date_of_transfer") >= five_years_ago)
    agg_5y = recent_5y.group_by("lsoa21cd").agg(
        pl.col("price").median().alias("median_price_5y"),
    )

    # Year-on-year change: median price in last 12m vs 12-24 months ago
    prev_year = df.filter(
        (pl.col("date_of_transfer") >= two_years_ago)
        & (pl.col("date_of_transfer") < one_year_ago)
    )
    agg_prev = prev_year.group_by("lsoa21cd").agg(
        pl.col("price").median().alias("median_price_prev_year"),
    )

    # Join all aggregates
    result = agg_12m.join(agg_5y, on="lsoa21cd", how="outer_coalesce")
    result = result.join(agg_prev, on="lsoa21cd", how="outer_coalesce")

    # Calculate YoY change
    result = result.with_columns(
        (
            (pl.col("median_price_12m") - pl.col("median_price_prev_year"))
            / pl.col("median_price_prev_year")
            * 100
        ).alias("yoy_change_pct")
    ).drop("median_price_prev_year")

    logger.info(f"Aggregated to {len(result):,} LSOAs")

    return result.lazy()


def clean_imd(raw_path: Path | None = None) -> pl.LazyFrame:
    """Clean IMD data (already at LSOA level)."""
    if raw_path is None:
        raw_dir = get_project_root() / "data" / "raw" / "imd_2025"
        # Try XLSX first, then CSV
        xlsx_files = list(raw_dir.glob("*.xlsx"))
        if xlsx_files:
            raw_path = xlsx_files[0]
        else:
            csv_files = list(raw_dir.glob("*.csv"))
            if csv_files:
                raw_path = csv_files[0]
            else:
                raise FileNotFoundError(f"No IMD data files found in {raw_dir}")

    logger.info(f"Reading IMD data from {raw_path}")

    if raw_path.suffix == ".xlsx":
        # IMD 2019 File 1 has the main index in the first sheet (sheet_id=1 is 1-indexed)
        df = pl.read_excel(raw_path, sheet_id=1)
    else:
        df = pl.read_csv(raw_path)

    logger.info(f"Loaded {len(df):,} rows from IMD")

    # Normalise column names: lowercase, replace spaces with underscores
    rename_map = {}
    for col in df.columns:
        new_name = col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
        rename_map[col] = new_name
    df = df.rename(rename_map)

    # Identify key columns (IMD 2019 uses specific names)
    col_mapping = {
        "lsoa_code_2011": "lsoa11cd",
        "lsoa21cd": "lsoa21cd",
        "index_of_multiple_deprivation_imd_score": "imd_score",
        "index_of_multiple_deprivation_imd_rank_where_1_is_most_deprived": "imd_rank",
        "index_of_multiple_deprivation_imd_decile_where_1_is_most_deprived_10%_of_lsoas":
            "imd_decile",
        "income_score_rate": "income_score",
        "employment_score_rate": "employment_score",
        "education,_skills_and_training_score": "education_score",
        "health_deprivation_and_disability_score": "health_score",
        "crime_score": "crime_score",
        "barriers_to_housing_and_services_score": "housing_score",
        "living_environment_score": "living_environment_score",
    }

    # Apply available renames
    available_renames = {}
    for old, new in col_mapping.items():
        if old in df.columns:
            available_renames[old] = new

    if available_renames:
        df = df.rename(available_renames)

    # Log available columns for debugging
    logger.info(f"IMD columns after rename: {df.columns}")

    # Select output columns (take what's available)
    desired_cols = [
        "lsoa11cd", "lsoa21cd",
        "imd_score", "imd_rank", "imd_decile",
        "income_score", "employment_score", "education_score",
        "health_score", "crime_score", "housing_score", "living_environment_score",
    ]
    available_cols = [c for c in desired_cols if c in df.columns]

    if not available_cols:
        logger.warning(f"No expected columns found. Available: {df.columns}")
        return df.lazy()

    df = df.select(available_cols)

    # Use whichever LSOA code column is available as the index
    if "lsoa21cd" not in df.columns and "lsoa11cd" in df.columns:
        logger.info("IMD uses LSOA 2011 codes — will need LSOA11→LSOA21 mapping in future")
        df = df.rename({"lsoa11cd": "lsoa_code"})
    elif "lsoa21cd" in df.columns:
        df = df.rename({"lsoa21cd": "lsoa_code"})

    logger.info(f"IMD cleaned: {len(df):,} LSOAs, columns: {df.columns}")

    return df.lazy()


def save_processed(df: pl.LazyFrame | pl.DataFrame, slug: str) -> Path:
    """Write a DataFrame to data/processed/{slug}.parquet with Snappy compression."""
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    out_path = get_project_root() / "data" / "processed" / f"{slug}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df.write_parquet(out_path, compression="snappy")
    logger.info(
        f"Saved {len(df):,} rows to {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)"
    )

    return out_path


CLEANERS = {
    "price_paid": clean_price_paid,
    "imd_2025": clean_imd,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean and process UK Liveability Index datasets"
    )
    parser.add_argument("--slug", type=str, required=True, help="Dataset slug to clean")
    args = parser.parse_args()

    ensure_dirs()

    if args.slug not in CLEANERS:
        raise ValueError(
            f"Unknown slug: {args.slug!r}. Available: {list(CLEANERS.keys())}"
        )

    cleaner = CLEANERS[args.slug]
    df = cleaner()
    save_processed(df, args.slug)


if __name__ == "__main__":
    main()
