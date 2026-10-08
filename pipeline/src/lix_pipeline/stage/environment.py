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
NRW_LAYERS = ("nrw_fraw_rivers", "nrw_fraw_sea")


def _nrw_homes_at_risk() -> pl.DataFrame:
    """Welsh homes at each flood likelihood, estimated from NRW's risk areas.

    NRW publishes risk polygons, not postcode counts, so each residential postcode is
    placed in its worst band across rivers and the sea, and an LSOA's dwellings (VOA)
    are split in the proportion of its postcodes per band. Bands match the EA's: High
    above 1 in 30 a year, Medium 1 in 30 to 1 in 100, Low 1 in 100 to 1 in 1000.
    """
    import geopandas as gpd

    from lix_core.codes import nation_of
    from lix_pipeline.geo.access import residential_postcodes

    homes = residential_postcodes().filter(nation_of("lsoa21cd") == "W")
    points = gpd.GeoDataFrame(
        {"postcode": homes["postcode"].to_list(), "lsoa21cd": homes["lsoa21cd"].to_list()},
        geometry=gpd.points_from_xy(homes["east1m"].to_numpy(), homes["north1m"].to_numpy()),
        crs=27700,
    )
    rank = {"High": 3, "Medium": 2, "Low": 1}
    worst = pl.DataFrame(
        {"postcode": [], "band": []}, schema={"postcode": pl.Utf8, "band": pl.Int8}
    )
    for slug in NRW_LAYERS:
        polys = gpd.read_file(data_dir("raw") / slug / f"{slug}.gpkg")[["risk", "geometry"]]
        polys = polys.to_crs(27700)
        hit = gpd.sjoin(points, polys, how="inner", predicate="intersects")
        found = pl.DataFrame(
            {
                "postcode": hit["postcode"].to_list(),
                "band": [rank.get(r, 0) for r in hit["risk"].to_list()],
            },
            schema={"postcode": pl.Utf8, "band": pl.Int8},
        )
        worst = pl.concat([worst, found])
        logger.info(f"{slug}: {hit['postcode'].nunique():,} residential postcodes in risk areas")
    worst = worst.group_by("postcode").agg(pl.col("band").max())
    per_pc = homes.select("postcode", "lsoa21cd").join(worst, on="postcode", how="left")
    shares = per_pc.group_by("lsoa21cd").agg(
        (pl.col("band") == 3).mean().alias("share_high"),
        (pl.col("band") == 2).mean().alias("share_medium"),
        (pl.col("band") == 1).mean().alias("share_low"),
    )
    dwellings = pl.read_parquet(data_dir("staged") / "voa_ctsop.parquet").select(
        "lsoa21cd", "dwellings"
    )
    return (
        shares.join(dwellings, on="lsoa21cd", how="inner")
        .select(
            "lsoa21cd",
            (pl.col("share_high") * pl.col("dwellings")).round().cast(pl.Int64).alias("res_high"),
            (pl.col("share_medium") * pl.col("dwellings"))
            .round()
            .cast(pl.Int64)
            .alias("res_medium"),
            (pl.col("share_low") * pl.col("dwellings")).round().cast(pl.Int64).alias("res_low"),
            pl.lit(0, pl.Int64).alias("res_verylow"),
        )
        .filter((pl.col("res_high") + pl.col("res_medium") + pl.col("res_low")) > 0)
        .sort("lsoa21cd")
    )


def stage_flood() -> pl.LazyFrame:
    """Homes per flood likelihood band per LSOA for every active nation (rivers and sea)."""
    from lix_core.codes import active_nations

    frames = []
    if "E" in active_nations():
        frames.append(pl.read_parquet(data_dir("staged") / "ea_flood_postcodes.parquet"))
    if "W" in active_nations():
        wales = _nrw_homes_at_risk()
        logger.info(f"Wales: {wales.height:,} LSOAs with homes in NRW flood risk areas")
        frames.append(wales)
    return pl.concat(frames, how="diagonal_relaxed").sort("lsoa21cd").lazy()


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
