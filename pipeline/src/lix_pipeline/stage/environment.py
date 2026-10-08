"""Green space access points (OS Open Greenspace) and flood risk by postcode (EA)."""

import polars as pl
import pyogrio

from lix_core.codes import in_scope
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.stage.health import geocode_postcodes

logger = setup_logging("stage.environment")


def stage_os_greenspace() -> pl.LazyFrame:
    """Every way into a green space, with the site's function and name.

    Access points rather than polygons: a park is only as close as its nearest
    entrance, and a big park has more entrances, so counting entrances within
    walking distance favours larger spaces without extra weighting. Kept for all of
    Great Britain so English homes near the borders see Welsh and Scottish parks.
    """
    gpkg = next((data_dir("raw") / "os_greenspace").glob("**/*.gpkg"))
    sites = pl.from_pandas(
        pyogrio.read_dataframe(
            gpkg,
            layer="greenspace_site",
            columns=["id", "function", "distinctive_name_1"],
            read_geometry=False,
        )
    ).rename({"id": "site_id", "distinctive_name_1": "site_name"})
    points = pyogrio.read_dataframe(
        gpkg, layer="access_point", columns=["access_type", "ref_to_greenspace_site"]
    )
    if points.crs is not None and points.crs.to_epsg() != 27700:
        points = points.to_crs(27700)
    access = pl.DataFrame(
        {
            "site_id": points["ref_to_greenspace_site"].to_numpy(),
            "access_type": points["access_type"].to_numpy(),
            "x": points.geometry.x.to_numpy(),
            "y": points.geometry.y.to_numpy(),
        }
    )
    df = access.join(sites, on="site_id", how="inner").filter(
        pl.col("access_type").str.contains("Pedestrian")
    )
    logger.info(
        f"{df.height:,} pedestrian access points to {df['site_id'].n_unique():,} green spaces"
    )
    return df.lazy()


FLOOD_BANDS = ("High", "Medium", "Low", "VeryLow")


def stage_ea_flood_postcodes() -> pl.LazyFrame:
    """Residential properties at each flood likelihood, summed per LSOA.

    The file lists only postcodes with at least one property in a risk area (any
    likelihood); LSOAs with none listed have no property at risk from rivers or sea.
    High = at least 3.3% a year, Medium = 1–3.3%, Low = 0.1–1%, Very low = under 0.1%.
    """
    path = next((data_dir("raw") / "ea_flood_postcodes").glob("**/*Postcodes_AtRisk.csv"))
    raw = pl.read_csv(path, infer_schema=False, encoding="utf8-lossy")
    df = raw.select(
        pl.col("PC").alias("postcode"),
        *[pl.col(f"RES_CNT_{b}").cast(pl.Int64).alias(f"res_{b.lower()}") for b in FLOOD_BANDS],
    )
    df = geocode_postcodes(df)
    # Unmatched rows are mostly pseudo-postcodes (e.g. "VPO01148") with very-low-risk
    # property counts, so coverage is judged on the high and medium bands
    at_risk = pl.col("res_high") + pl.col("res_medium")
    located = df.filter(pl.col("lsoa21cd").is_not_null()).select(at_risk.sum()).item()
    located_share = located / max(df.select(at_risk.sum()).item(), 1)
    per_lsoa = (
        df.filter(in_scope("lsoa21cd"))
        .group_by("lsoa21cd")
        .agg(pl.col(f"res_{b.lower()}").sum() for b in FLOOD_BANDS)
        .sort("lsoa21cd")
    )
    logger.info(
        f"{per_lsoa.height:,} LSOAs with properties in flood risk areas; "
        f"{located_share:.2%} of homes at high or medium risk located"
    )
    return per_lsoa.lazy()
