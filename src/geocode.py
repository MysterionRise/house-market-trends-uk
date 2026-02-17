"""NSPL postcode-to-LSOA geocoder and boundary loader.

Usage:
    python -m src.geocode   # no standalone action yet; used as a library
"""

from pathlib import Path

import geopandas as gpd
import polars as pl

from src.utils import get_config, get_project_root, setup_logging

logger = setup_logging("geocode")


def _find_nspl_csv(nspl_dir: Path) -> Path:
    """Locate the NSPL CSV inside the extracted directory."""
    config = get_config("datasets")
    inner = config["nspl"].get("inner_path")
    if inner:
        candidate = nspl_dir / inner
        if candidate.exists():
            return candidate
        logger.warning(f"Configured inner_path {inner!r} not found, falling back to glob")

    # Fallback: find any CSV matching NSPL pattern
    for csv in sorted(nspl_dir.rglob("NSPL*.csv")):
        return csv

    raise FileNotFoundError(f"No NSPL CSV found in {nspl_dir}")


def load_nspl(nspl_path: Path | None = None) -> pl.LazyFrame:
    """Load NSPL CSV and return a LazyFrame with postcode, lsoa21cd, lat, long.

    Only live postcodes (doterm is null) are included.
    """
    if nspl_path is None:
        nspl_path = _find_nspl_csv(get_project_root() / "data" / "raw" / "nspl")

    logger.info(f"Loading NSPL from {nspl_path}")

    lf = pl.scan_csv(nspl_path, infer_schema_length=10000)

    # Select and rename relevant columns
    lf = lf.select([
        pl.col("pcds").alias("postcode_raw"),
        pl.col("lsoa21"),
        pl.col("doterm"),
        pl.col("lat"),
        pl.col("long"),
    ])

    # Filter to live postcodes only (doterm is null)
    lf = lf.filter(pl.col("doterm").is_null())

    # Normalise postcode: strip all whitespace, uppercase
    lf = lf.with_columns(
        pl.col("postcode_raw")
        .str.strip_chars()
        .str.replace_all(r"\s", "")
        .str.to_uppercase()
        .alias("postcode_norm"),
    ).select([
        pl.col("postcode_raw").alias("postcode"),
        pl.col("postcode_norm"),
        pl.col("lsoa21").alias("lsoa21cd"),
        pl.col("lat"),
        pl.col("long"),
    ])

    # No eager collect here — let the caller decide when to materialise
    return lf


def postcode_to_lsoa(
    df: pl.LazyFrame,
    postcode_col: str = "postcode",
    nspl: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
    """Join a LazyFrame to NSPL to append lsoa21cd.

    The postcode column is normalised (strip whitespace, uppercase) before joining.
    """
    if nspl is None:
        nspl = load_nspl()

    # Normalise the input postcode column (strip all whitespace, uppercase)
    df = df.with_columns(
        pl.col(postcode_col)
        .str.strip_chars()
        .str.replace_all(r"\s", "")
        .str.to_uppercase()
        .alias("_pc_norm"),
    )

    # Left join on normalised postcode
    nspl_lookup = nspl.select([
        pl.col("postcode_norm"),
        pl.col("lsoa21cd"),
    ]).unique(subset=["postcode_norm"], keep="first")

    result = df.join(nspl_lookup, left_on="_pc_norm", right_on="postcode_norm", how="left")

    # Drop temporary column
    result = result.drop("_pc_norm")

    return result


def log_match_rate(df: pl.DataFrame, lsoa_col: str = "lsoa21cd") -> None:
    """Log postcode-to-LSOA match rate on an already-collected DataFrame."""
    total = len(df)
    if total == 0:
        return
    unmatched = df.filter(pl.col(lsoa_col).is_null()).height
    pct = unmatched / total * 100
    msg = f"Postcode matching: {total - unmatched:,}/{total:,} matched ({pct:.1f}% unmatched)"
    if pct > 5:
        logger.warning(msg)
    else:
        logger.info(msg)


def load_lsoa_boundaries(simplify_tolerance: float = 50.0) -> gpd.GeoDataFrame:
    """Load LSOA 2021 boundary GeoPackage and simplify for web rendering."""
    geo_dir = get_project_root() / "data" / "geo"

    # Find the GeoPackage file
    gpkg_files = list(geo_dir.glob("*.gpkg"))
    if not gpkg_files:
        raise FileNotFoundError(f"No GeoPackage files found in {geo_dir}")

    gpkg_path = gpkg_files[0]
    logger.info(f"Loading LSOA boundaries from {gpkg_path}")

    gdf = gpd.read_file(gpkg_path)

    # Identify the LSOA code column
    lsoa_col = None
    for candidate in ["LSOA21CD", "lsoa21cd"]:
        if candidate in gdf.columns:
            lsoa_col = candidate
            break

    if lsoa_col is None:
        # Try any column ending in 'CD'
        cd_cols = [c for c in gdf.columns if c.upper().endswith("CD")]
        if cd_cols:
            lsoa_col = cd_cols[0]
        else:
            raise ValueError(f"Cannot find LSOA code column in {gdf.columns.tolist()}")

    if lsoa_col != "lsoa21cd":
        gdf = gdf.rename(columns={lsoa_col: "lsoa21cd"})

    # Simplify geometry for performance
    if simplify_tolerance > 0:
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=simplify_tolerance)

    gdf = gdf.set_index("lsoa21cd")
    logger.info(f"Loaded {len(gdf):,} LSOA boundaries")

    return gdf
