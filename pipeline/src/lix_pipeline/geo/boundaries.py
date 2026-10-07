"""LSOA 2021 boundary polygons."""

import geopandas as gpd

from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("geo")


def load_lsoa_boundaries(
    slug: str = "lsoa_boundaries", simplify_tolerance: float = 0.0
) -> gpd.GeoDataFrame:
    """Load an LSOA 2021 boundary GeoPackage downloaded under ``data/raw/{slug}``.

    ``lsoa_boundaries`` is the 20m generalised (BGC) set; ``lsoa_boundaries_bsc`` is the
    lighter 200m (BSC) set. Pass ``simplify_tolerance`` (metres) to simplify further.
    """
    gpkg_dir = data_dir("raw") / slug
    gpkg_files = sorted(gpkg_dir.glob("*.gpkg"))
    if not gpkg_files:
        raise FileNotFoundError(f"No GeoPackage files found in {gpkg_dir}")

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

    if simplify_tolerance > 0:
        gdf["geometry"] = gdf["geometry"].simplify(tolerance=simplify_tolerance)

    gdf = gdf.set_index("lsoa21cd")
    logger.info(f"Loaded {len(gdf):,} LSOA boundaries")

    return gdf
