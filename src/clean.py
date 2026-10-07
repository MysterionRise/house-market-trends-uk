"""Dataset-specific cleaners for the UK Liveability Index pipeline.

Usage:
    python -m src.clean --slug nspl          # must run before price_paid
    python -m src.clean --slug price_paid
    python -m src.clean --slug iod_2025
    python -m src.clean --all                # every cleaner whose raw data is present
"""

import argparse
import re
from datetime import date
from pathlib import Path

import duckdb
import polars as pl

from src.geocode import default_nspl_path, find_nspl_csv, load_nspl, read_nspl_raw
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

# England LSOA 2021 codes
ENGLAND_LSOA_PATTERN = r"^E01\d{6}$"


def _pp_column_aliases() -> str:
    """SELECT list mapping DuckDB's zero-padded column names to PP_COLUMNS."""
    # DuckDB zero-pads column names based on total column count (column00..column15 for 16 cols)
    pad_width = len(str(len(PP_COLUMNS) - 1))
    return ", ".join(f"column{i:0{pad_width}d} AS {name}" for i, name in enumerate(PP_COLUMNS))


def clean_nspl(raw_path: Path | None = None) -> pl.LazyFrame:
    """Stage the full NSPL (all nations, live and terminated) with stable column names."""
    if raw_path is None:
        raw_path = find_nspl_csv(get_project_root() / "data" / "raw" / "nspl")
    logger.info(f"Staging NSPL from {raw_path}")
    return read_nspl_raw(raw_path)


def clean_price_paid(
    raw_path: Path | None = None,
    nspl: pl.LazyFrame | None = None,
    as_of: date | None = None,
) -> pl.LazyFrame:
    """Aggregate Price Paid sales to England LSOA medians in a single DuckDB pass.

    Only standard market sales (PPD category A) count. Postcodes are matched against
    the full NSPL including terminated postcodes, since older sales use retired ones.

    Args:
        as_of: end of the 12-month window. Defaults to the latest transfer date in the
            data, so results don't shift with the day the pipeline happens to run.
    """
    if raw_path is None:
        raw_path = get_project_root() / "data" / "raw" / "price_paid" / "price_paid.csv"
    if nspl is None:
        nspl = load_nspl(default_nspl_path(), live_only=False, nations=None)

    logger.info(f"Reading Price Paid data from {raw_path}")

    lookup = (
        nspl.select("postcode_norm", "lsoa21cd")
        .unique(subset=["postcode_norm"], keep="first")
        .collect()
        .to_arrow()
    )

    con = duckdb.connect()
    con.execute("SET memory_limit = '8GB'")
    con.register("nspl_lookup", lookup)
    # Use parameterised path via DuckDB variable to avoid SQL injection
    con.execute("SET VARIABLE csv_path = ?", [str(raw_path)])

    logger.info("Geocoding and filtering sales via DuckDB (this may take a few minutes)...")
    con.execute(f"""
        CREATE TEMP TABLE sales AS
        WITH pp AS (
            SELECT {_pp_column_aliases()}
            FROM read_csv(getvariable('csv_path'), header=false, all_varchar=true)
            WHERE column15 = 'A' AND column14 = 'A'
        )
        SELECT
            CAST(pp.price AS BIGINT) AS price,
            CAST(strptime(pp.date_of_transfer, '%Y-%m-%d %H:%M') AS DATE) AS date_of_transfer,
            n.lsoa21cd
        FROM pp
        LEFT JOIN nspl_lookup n
            ON n.postcode_norm = upper(regexp_replace(pp.postcode, '\\s', '', 'g'))
    """)

    if as_of is None:
        as_of = con.execute("SELECT max(date_of_transfer) FROM sales").fetchone()[0]
    logger.info(f"Price Paid as-of date: {as_of}")

    matched, total = con.execute(
        """
        SELECT count(lsoa21cd), count(*) FROM sales
        WHERE date_of_transfer > ?::DATE - INTERVAL 24 MONTH
        """,
        [as_of],
    ).fetchone()
    if total:
        pct = matched / total * 100
        msg = f"Price Paid geocoding (last 24 months): {matched:,}/{total:,} matched ({pct:.2f}%)"
        (logger.warning if pct < 99 else logger.info)(msg)

    logger.info("Aggregating to LSOA level...")
    result = con.execute(
        """
        WITH windows AS (
            SELECT
                lsoa21cd,
                price,
                date_of_transfer > ?::DATE - INTERVAL 12 MONTH AS in_12m,
                date_of_transfer <= ?::DATE - INTERVAL 12 MONTH
                    AND date_of_transfer > ?::DATE - INTERVAL 24 MONTH AS in_prev_12m,
                date_of_transfer > ?::DATE - INTERVAL 5 YEAR AS in_5y
            FROM sales
            WHERE regexp_matches(lsoa21cd, ?) AND date_of_transfer <= ?::DATE
        ),
        agg AS (
            SELECT
                lsoa21cd,
                median(price) FILTER (WHERE in_12m) AS median_price_12m,
                count(*) FILTER (WHERE in_12m) AS transaction_count_12m,
                median(price) FILTER (WHERE in_5y) AS median_price_5y,
                count(*) FILTER (WHERE in_5y) AS transaction_count_5y,
                median(price) FILTER (WHERE in_prev_12m) AS median_price_prev_12m
            FROM windows
            GROUP BY lsoa21cd
        )
        SELECT
            lsoa21cd,
            median_price_12m,
            transaction_count_12m,
            median_price_5y,
            transaction_count_5y,
            (median_price_12m - median_price_prev_12m) / median_price_prev_12m * 100
                AS yoy_change_pct,
            ?::DATE AS as_of
        FROM agg
        WHERE transaction_count_5y > 0
        ORDER BY lsoa21cd
        """,
        [as_of, as_of, as_of, as_of, ENGLAND_LSOA_PATTERN, as_of, as_of],
    ).fetch_arrow_table()
    con.close()

    df = pl.from_arrow(result)
    logger.info(f"Aggregated to {len(df):,} LSOAs")
    return df.lazy()


# IoD 2025 File 7 column labels (before " Score", " Rank", " Decile") → output prefix
IOD_DOMAINS = {
    "Index of Multiple Deprivation (IMD)": "imd",
    "Income": "income",
    "Employment": "employment",
    "Education, Skills and Training": "education",
    "Health Deprivation and Disability": "health",
    "Crime": "crime",
    "Barriers to Housing and Services": "barriers",
    "Living Environment": "living_env",
    "Income Deprivation Affecting Children Index (IDACI)": "idaci",
    "Income Deprivation Affecting Older People (IDAOPI)": "idaopi",
    "Children and Young People Sub-domain": "sub_children_young_people",
    "Adult Skills Sub-domain": "sub_adult_skills",
    "Geographical Barriers Sub-domain": "sub_geographical_barriers",
    "Wider Barriers Sub-domain": "sub_wider_barriers",
    "Indoors Sub-domain": "sub_indoors",
    "Outdoors Sub-domain": "sub_outdoors",
}
IOD_MEASURES = {"Score": "score", "Rank": "rank", "Decile": "decile"}
IOD_ID_COLUMNS = {
    # 2021 only: a 2011-based file must not silently pass as LSOA21
    r"^LSOA code \(2021\)$": "lsoa21cd",
    r"^LSOA name \(2021\)$": "lsoa21nm",
    r"^Local Authority District code \(\d{4}\)$": "lad_cd",
    r"^Local Authority District name \(\d{4}\)$": "lad_nm",
}
IOD_POPULATION = {
    "Total population": "pop_total",
    "Dependent Children aged 0-15": "pop_children_0_15",
    "Older population aged 60 and over": "pop_60_plus",
    "Working age population 18-66": "pop_working_age",
}


def _iod_rename_map(columns: list[str]) -> dict[str, str]:
    """Map IoD 2025 File 7 headers to snake_case names.

    Matches on label prefixes rather than full headers, because some headers are
    truncated in the published file (e.g. "...most deprived 10% of LSO").
    """
    rename = {}
    for col in columns:
        name = col.strip()
        for pattern, out in IOD_ID_COLUMNS.items():
            if re.match(pattern, name):
                rename[col] = out
        for label, prefix in IOD_DOMAINS.items():
            for measure, suffix in IOD_MEASURES.items():
                if name.startswith(f"{label} {measure}"):
                    rename[col] = f"{prefix}_{suffix}"
        for label, out in IOD_POPULATION.items():
            if name.startswith(label):
                rename[col] = out
    return rename


def clean_iod(raw_path: Path | None = None) -> pl.LazyFrame:
    """Clean English Indices of Deprivation 2025 (File 7: all ranks, scores, deciles).

    Keeps every domain and sub-domain plus the mid-2022 population denominators.
    """
    if raw_path is None:
        raw_dir = get_project_root() / "data" / "raw" / "iod_2025"
        csv_files = sorted(raw_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No IoD data files found in {raw_dir}")
        raw_path = csv_files[0]

    logger.info(f"Reading IoD data from {raw_path}")
    df = pl.read_csv(raw_path, infer_schema_length=0)

    rename = _iod_rename_map(df.columns)
    if "lsoa21cd" not in rename.values():
        raise ValueError(f"No 'LSOA code (2021)' column in IoD file; header: {df.columns}")
    unmapped = [c for c in df.columns if c not in rename]
    if unmapped:
        logger.warning(f"Ignoring unrecognised IoD columns: {unmapped}")

    df = df.select(list(rename)).rename(rename)
    numeric = {
        c: pl.Int32 if c.endswith(("_rank", "_decile")) or c.startswith("pop_") else pl.Float64
        for c in df.columns
        if c not in IOD_ID_COLUMNS.values()
    }
    df = df.with_columns(pl.col(c).cast(t) for c, t in numeric.items())
    df = df.filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA_PATTERN))

    logger.info(f"IoD cleaned: {len(df):,} LSOAs, {len(df.columns)} columns")
    return df.lazy()


def save_processed(df: pl.LazyFrame | pl.DataFrame, slug: str) -> Path:
    """Write a DataFrame to data/processed/{slug}.parquet with Snappy compression."""
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    out_path = get_project_root() / "data" / "processed" / f"{slug}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df.write_parquet(out_path, compression="snappy")
    logger.info(f"Saved {len(df):,} rows to {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")

    return out_path


# Order matters for --all: price_paid geocodes against the staged NSPL
CLEANERS = {
    "nspl": clean_nspl,
    "price_paid": clean_price_paid,
    "iod_2025": clean_iod,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean and process UK Liveability Index datasets")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", type=str, help="Dataset slug to clean")
    group.add_argument(
        "--all", action="store_true", help="Clean every dataset whose raw data is present"
    )
    args = parser.parse_args()

    ensure_dirs()

    if args.slug and args.slug not in CLEANERS:
        raise ValueError(f"Unknown slug: {args.slug!r}. Available: {list(CLEANERS.keys())}")

    slugs = [args.slug] if args.slug else list(CLEANERS)
    raw_root = get_project_root() / "data" / "raw"
    for slug in slugs:
        if args.all and not (raw_root / slug / ".meta.json").exists():
            logger.info(f"[{slug}] No raw data — skipping (run `make download` first)")
            continue
        save_processed(CLEANERS[slug](), slug)


if __name__ == "__main__":
    main()
