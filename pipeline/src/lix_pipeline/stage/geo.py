"""Geography backbone: one row per England LSOA, plus lookups and a place gazetteer.

Every indicator joins onto ``geo_lsoa``; it carries the hierarchy (MSOA, local
authority, region), friendly names, the population-weighted centroid, the urban/rural
class, population and a map bounding box.
"""

from pathlib import Path

import geopandas as gpd
import polars as pl
from pyproj import Transformer

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.boundaries import load_lsoa_boundaries
from lix_pipeline.geo.nspl import load_nspl

logger = setup_logging("stage.geo")

_BNG_TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True)
_WGS84_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)


def bng_to_lonlat(x: pl.Series, y: pl.Series) -> tuple[pl.Series, pl.Series]:
    lon, lat = _BNG_TO_WGS84.transform(x.to_numpy(), y.to_numpy())
    return pl.Series("lon", lon), pl.Series("lat", lat)


def lonlat_to_bng(lon: pl.Series, lat: pl.Series) -> tuple[pl.Series, pl.Series]:
    x, y = _WGS84_TO_BNG.transform(lon.to_numpy(), lat.to_numpy())
    return pl.Series("x", x), pl.Series("y", y)


def _raw(slug: str, suffix: str) -> Path:
    return data_dir("raw") / slug / f"{slug}.{suffix}"


def _nspl_document(pattern: str) -> Path:
    """One of the code→name lookups shipped in the NSPL zip's Documents/ folder."""
    matches = sorted((data_dir("raw") / "nspl" / "Documents").glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No NSPL document matching {pattern!r}")
    return matches[-1]


def _lsoa_pfa_from_nspl(nspl: pl.LazyFrame) -> pl.DataFrame:
    """Police force area per LSOA (majority of its postcodes), with the force's name."""
    pfa = (
        nspl.filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .group_by("lsoa21cd", "pfa_cd")
        .agg(pl.len().alias("n"))
        .sort("n", descending=True)
        .collect()
        .unique("lsoa21cd", keep="first")
        .drop("n")
    )
    doc = pl.read_csv(_nspl_document("PFA*names and codes*.csv"), encoding="utf8-lossy")
    names = doc.select(
        pl.col(next(c for c in doc.columns if c.upper().endswith("CD"))).alias("pfa_cd"),
        pl.col(next(c for c in doc.columns if c.upper().endswith("NM"))).alias("pfa_nm"),
    )
    return pfa.join(names, on="pfa_cd", how="left")


def _lsoa_lad_from_nspl(nspl: pl.LazyFrame) -> pl.DataFrame:
    """Current local authority and region per LSOA: the most common among its postcodes.

    The ONS OA→LAD lookup is frozen at 2022 boundaries; NSPL carries the latest ones.
    """
    counts = (
        nspl.filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .group_by("lsoa21cd", "lad_cd", "rgn_cd")
        .agg(pl.len().alias("n"))
        .collect()
    )
    split = (
        counts.group_by("lsoa21cd")
        .agg(pl.col("lad_cd").n_unique().alias("k"))
        .filter(pl.col("k") > 1)
    )
    if split.height:
        logger.warning(f"{split.height} LSOAs span more than one local authority; using majority")
    return counts.sort("n", descending=True).unique("lsoa21cd", keep="first").drop("n")


def stage_geo_lsoa() -> pl.LazyFrame:
    """Build the per-LSOA geography backbone for England."""
    oa = pl.read_parquet(_raw("oa_lookup", "parquet"))
    lsoa = (
        oa.filter(pl.col("LSOA21CD").str.contains(ENGLAND_LSOA21))
        .select(
            pl.col("LSOA21CD").alias("lsoa21cd"),
            pl.col("LSOA21NM").alias("lsoa21nm"),
            pl.col("MSOA21CD").alias("msoa21cd"),
            pl.col("MSOA21NM").alias("msoa21nm"),
            pl.col("LAD22CD").alias("lad22cd"),
        )
        .unique("lsoa21cd")
    )

    msoa_names = pl.read_csv(_raw("msoa_names", "csv"), encoding="utf8-lossy").select(
        pl.col("msoa21cd"), pl.col("msoa21hclnm").alias("msoa_name")
    )

    # Live postcodes only: terminated ones can carry superseded authority codes
    nspl = load_nspl(nations=("E",), live_only=True)
    lad = _lsoa_lad_from_nspl(nspl)
    lad_names = gpd.read_file(_raw("lad_boundaries", "gpkg"), ignore_geometry=True)
    lad_code_col = next(
        c for c in lad_names.columns if c.upper().startswith("LAD") and c.upper().endswith("CD")
    )
    lad_name_col = lad_code_col[:-2] + "NM"
    lad_names = pl.from_pandas(lad_names[[lad_code_col, lad_name_col]]).rename(
        {lad_code_col: "lad_cd", lad_name_col: "lad_nm"}
    )
    rgn_doc = pl.read_csv(_nspl_document("RGN*names and codes*.csv"), encoding="utf8-lossy")
    rgn_names = rgn_doc.select(
        pl.col(next(c for c in rgn_doc.columns if c.upper().endswith("CD"))).alias("rgn_cd"),
        pl.col(next(c for c in rgn_doc.columns if c.upper().endswith("NM"))).alias("rgn_nm"),
    )

    postcodes = nspl.group_by("lsoa21cd").agg(pl.len().alias("n_postcodes")).collect()

    ruc = pl.read_parquet(_raw("ruc_2021", "parquet")).select(
        pl.col("LSOA21CD").alias("lsoa21cd"),
        pl.col("RUC21CD").alias("ruc21cd"),
        pl.col("RUC21NM").alias("ruc21nm"),
        (pl.col("Urban_rural_flag") == "Urban").alias("urban"),
    )

    centroids = pl.read_parquet(_raw("lsoa_centroids", "parquet")).select(
        pl.col("LSOA21CD").alias("lsoa21cd"), pl.col("x").alias("pwc_x"), pl.col("y").alias("pwc_y")
    )
    lon, lat = bng_to_lonlat(centroids["pwc_x"], centroids["pwc_y"])
    centroids = centroids.with_columns(pwc_lon=lon, pwc_lat=lat)

    # Mid-2022 population, the denominator IoD 2025 uses (from the staged IoD file)
    pop = pl.read_parquet(data_dir("staged") / "iod_2025.parquet").select(
        "lsoa21cd", pl.col("pop_total").alias("population"), pl.col("lad_cd").alias("lad24cd")
    )

    bounds = _lsoa_bounds()

    df = (
        lsoa.join(msoa_names, on="msoa21cd", how="left")
        .join(lad, on="lsoa21cd", how="left")
        .join(lad_names, on="lad_cd", how="left")
        .join(rgn_names, on="rgn_cd", how="left")
        .join(_lsoa_pfa_from_nspl(nspl), on="lsoa21cd", how="left")
        .join(ruc, on="lsoa21cd", how="left")
        .join(centroids, on="lsoa21cd", how="left")
        .join(pop, on="lsoa21cd", how="left")
        .join(postcodes, on="lsoa21cd", how="left")
        .join(bounds, on="lsoa21cd", how="left")
        .with_columns(
            (pl.col("population") / pl.col("area_km2")).alias("density_per_km2"),
            pl.col("n_postcodes").fill_null(0).cast(pl.Int32),
        )
        .sort("lsoa21cd")
    )
    logger.info(f"Geography backbone: {df.height:,} LSOAs")
    return df.lazy()


def _lsoa_bounds() -> pl.DataFrame:
    """Land area (km², from the 20m-generalised clipped polygons) and WGS84 bounding box."""
    gdf = load_lsoa_boundaries("lsoa_boundaries")
    gdf = gdf[gdf.index.str.match(ENGLAND_LSOA21)]
    area = gdf.geometry.area / 1e6
    bbox = gdf.to_crs(4326).geometry.bounds
    return pl.DataFrame(
        {
            "lsoa21cd": gdf.index.to_list(),
            "area_km2": area.to_numpy(),
            "bbox_w": bbox["minx"].to_numpy(),
            "bbox_s": bbox["miny"].to_numpy(),
            "bbox_e": bbox["maxx"].to_numpy(),
            "bbox_n": bbox["maxy"].to_numpy(),
        }
    )


def stage_oa_lookup() -> pl.LazyFrame:
    """England output areas → LSOA → MSOA (for OA-level sources such as Ofcom)."""
    return (
        pl.scan_parquet(_raw("oa_lookup", "parquet"))
        .filter(pl.col("LSOA21CD").str.contains(ENGLAND_LSOA21))
        .select(
            pl.col("OA21CD").alias("oa21cd"),
            pl.col("LSOA21CD").alias("lsoa21cd"),
            pl.col("MSOA21CD").alias("msoa21cd"),
        )
    )


def stage_lsoa11_lsoa21() -> pl.LazyFrame:
    """LSOA 2011 → 2021 for sources still published on 2011 geography.

    ``change``: U unchanged, S 2011 LSOA split into several 2021 ones, M merged,
    X irregular. Converting splits needs a weight (e.g. population share).
    """
    return (
        pl.scan_parquet(_raw("lsoa11_lsoa21", "parquet"))
        .filter(pl.col("LSOA21CD").str.contains(ENGLAND_LSOA21))
        .select(
            pl.col("LSOA11CD").alias("lsoa11cd"),
            pl.col("LSOA21CD").alias("lsoa21cd"),
            pl.col("CHGIND").alias("change"),
        )
    )


# OS Open Names LOCAL_TYPE values that are places people search for
PLACE_TYPES = ["City", "Town", "Village", "Hamlet", "Suburban Area", "Other Settlement"]


def stage_places() -> pl.LazyFrame:
    """England settlements from OS Open Names, located to an LSOA, for place search."""
    root = data_dir("raw") / "os_open_names"
    header = (root / "Doc" / "OS_Open_Names_Header.csv").read_text(encoding="utf-8-sig")
    columns = header.strip().split(",")
    files = sorted((root / "Data").glob("*.csv"))
    places = (
        pl.scan_csv(
            files,
            has_header=False,
            new_columns=columns,
            schema_overrides={c: pl.Utf8 for c in columns},
            encoding="utf8-lossy",
        )
        .filter(
            (pl.col("TYPE") == "populatedPlace")
            & pl.col("LOCAL_TYPE").is_in(PLACE_TYPES)
            & (pl.col("COUNTRY") == "England")
        )
        .select(
            pl.col("ID").str.strip_chars_start("﻿").alias("place_id"),
            pl.col("NAME1").alias("name"),
            pl.col("NAME2").alias("name_alt"),
            pl.col("LOCAL_TYPE").alias("place_type"),
            pl.col("GEOMETRY_X").cast(pl.Float64).alias("x"),
            pl.col("GEOMETRY_Y").cast(pl.Float64).alias("y"),
            pl.col("POSTCODE_DISTRICT").alias("postcode_district"),
            pl.coalesce("DISTRICT_BOROUGH", "COUNTY_UNITARY").alias("local_authority"),
            pl.col("REGION").alias("region"),
        )
        .collect()
    )
    lon, lat = bng_to_lonlat(places["x"], places["y"])
    places = places.with_columns(lon=lon, lat=lat)

    from lix_pipeline.geo.joins import points_to_lsoa

    places = points_to_lsoa(places, x="x", y="y")
    logger.info(f"Places: {places.height:,} settlements")
    return places.lazy()
