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
    """Nurseries and pre-schools (Ofsted) plus school nursery classes (GIAS), by quality.

    Ofsted settings carry their inspection quality; nursery schools and classes count
    as average, since their grade is the whole school's.
    """
    ofsted = ctx.staged("ofsted_childcare").select("x", "y", "quality")
    gias = (
        ctx.staged("gias")
        .filter(
            (pl.col("phase") == "Nursery") | (pl.col("nursery_provision") == "Has Nursery Classes")
        )
        .select("x", "y", pl.lit(NEUTRAL).alias("quality"))
    )
    pois = pl.concat([ofsted, gias], how="vertical_relaxed")
    access = ctx.access(pois, radius_m=radius_m, cap=cap, weight="quality")
    return access.select("lsoa21cd", pl.col("score").alias("value"))
