"""Checks on staged outputs, run with ``lix validate <target>`` on a full build.

Each validator returns a list of human-readable problems (empty means OK).
"""

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.paths import data_dir

# England LSOAs (December 2021)
ENGLAND_LSOA_COUNT = 33_755


def validate_geo() -> list[str]:
    problems = []
    staged = data_dir("staged")
    geo = pl.read_parquet(staged / "geo_lsoa.parquet")

    if geo.height != ENGLAND_LSOA_COUNT:
        problems.append(f"geo_lsoa has {geo.height:,} rows, expected {ENGLAND_LSOA_COUNT:,}")
    if geo["lsoa21cd"].n_unique() != geo.height:
        problems.append("geo_lsoa has duplicate lsoa21cd")
    if not geo["lsoa21cd"].str.contains(ENGLAND_LSOA21).all():
        problems.append("geo_lsoa has non-England LSOA codes")

    required = [
        "lsoa21nm",
        "msoa21cd",
        "msoa21nm",
        "msoa_name",
        "lad_cd",
        "lad_nm",
        "rgn_cd",
        "rgn_nm",
        "ruc21cd",
        "urban",
        "pwc_x",
        "pwc_y",
        "pwc_lat",
        "pwc_lon",
        "population",
        "area_km2",
        "bbox_w",
        "bbox_s",
        "bbox_e",
        "bbox_n",
    ]
    for col in required:
        if col not in geo.columns:
            problems.append(f"geo_lsoa is missing column {col}")
        elif (n := geo[col].null_count()) > 0:
            problems.append(f"geo_lsoa.{col} has {n:,} nulls")

    # Centroids must sit inside England's bounding box, and inside their own LSOA's bbox
    outside = geo.filter(
        (pl.col("pwc_lon") < pl.col("bbox_w"))
        | (pl.col("pwc_lon") > pl.col("bbox_e"))
        | (pl.col("pwc_lat") < pl.col("bbox_s"))
        | (pl.col("pwc_lat") > pl.col("bbox_n"))
    )
    if outside.height:
        problems.append(f"{outside.height} centroids fall outside their LSOA's bounding box")

    nspl = pl.scan_parquet(staged / "nspl.parquet")
    nspl_lsoas = set(
        nspl.filter(pl.col("live") & pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .select("lsoa21cd")
        .unique()
        .collect()["lsoa21cd"]
    )
    missing = nspl_lsoas - set(geo["lsoa21cd"])
    if missing:
        problems.append(
            f"{len(missing)} NSPL LSOAs missing from geo_lsoa, e.g. {sorted(missing)[:3]}"
        )

    pop = geo["population"].sum()
    if not 55_000_000 < pop < 60_000_000:
        problems.append(f"England population {pop:,} is implausible")
    return problems


VALIDATORS = {"geo": validate_geo}
