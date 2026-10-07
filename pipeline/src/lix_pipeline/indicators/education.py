"""Access to good state schools (quality-weighted) and to nurseries."""

import polars as pl

from lix_pipeline.stage.schools import NEUTRAL


def school_access(ctx, phases: list[str], radius_m: float, cap: float) -> pl.DataFrame:
    """State schools of ``phases`` within ``radius_m``, each weighted by inspection quality.

    Schools not yet inspected count as average (``NEUTRAL``). Independent schools
    are left out: they charge fees and aren't in Ofsted's state-funded data.
    """
    schools = (
        ctx.staged("gias")
        .filter(pl.col("phase").is_in(phases) & (pl.col("type_group") != "Independent schools"))
        .join(ctx.staged("ofsted_schools").select("urn", "quality"), on="urn", how="left")
        .with_columns(pl.col("quality").fill_null(NEUTRAL))
    )
    access = ctx.access(schools, radius_m=radius_m, cap=cap, weight="quality")
    return access.select("lsoa21cd", pl.col("score").alias("value"))


def nursery_access(ctx, radius_m: float, cap: float) -> pl.DataFrame:
    """Nursery schools, schools with nursery classes, and OSM nurseries/childcare."""
    gias = ctx.staged("gias").filter(
        (pl.col("phase") == "Nursery") | (pl.col("nursery_provision") == "Has Nursery Classes")
    )
    osm = ctx.staged("osm_pois").filter(pl.col("value").is_in(["kindergarten", "childcare"]))
    pois = pl.concat([gias.select("x", "y"), osm.select("x", "y")])
    access = ctx.access(pois, radius_m=radius_m, cap=cap)
    return access.select("lsoa21cd", pl.col("score").alias("value"))
