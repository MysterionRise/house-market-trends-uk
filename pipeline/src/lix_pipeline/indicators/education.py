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


def school_results(ctx, slug: str, column: str, phases: list[str], radius_m: float) -> pl.DataFrame:
    """Distance-weighted average result of the state mainstream schools near homes."""
    from lix_pipeline.geo.access import nearby_mean

    schools = (
        ctx.staged("gias")
        .filter(
            pl.col("phase").is_in(phases)
            & (pl.col("type_group") != "Independent schools")
            & (pl.col("type_group") != "Special schools")
        )
        .join(ctx.staged(slug).select("urn", column), on="urn", how="inner")
    )
    return nearby_mean(ctx.origins, schools, column, radius_m=radius_m)


# Share of a school's quality that comes from its results (the rest is Ofsted)
RESULTS_WEIGHT = 0.4


def state_schools(ctx, phases: list[str]) -> pl.DataFrame:
    """State mainstream schools of these phases with their Ofsted quality (0–1)."""
    return (
        ctx.staged("gias")
        .filter(
            pl.col("phase").is_in(phases)
            & (pl.col("type_group") != "Independent schools")
            & (pl.col("type_group") != "Special schools")
        )
        .join(ctx.staged("ofsted_schools").select("urn", "quality"), on="urn", how="left")
        .with_columns(pl.col("quality").fill_null(NEUTRAL))
    )


def school_quality_nearby(
    ctx,
    phases: list[str],
    results_slug: str,
    results_column: str,
    k: int,
    sigma_m: float,
    max_m: float,
) -> pl.DataFrame:
    """Quality of the ``k`` nearest state schools, nearer ones counting more.

    Each school's quality blends its Ofsted judgement (0–1) with its results, as a
    percentile among schools of the same phase: (1 − RESULTS_WEIGHT) × Ofsted +
    RESULTS_WEIGHT × results. Schools without published results use Ofsted alone.
    """
    from lix_pipeline.geo.access import nearest_k_mean

    results = ctx.staged(results_slug).select("urn", pl.col(results_column).alias("_result"))
    schools = state_schools(ctx, phases).join(results, on="urn", how="left")
    pct = (pl.col("_result").rank("average") - 1) / (pl.col("_result").count() - 1)
    schools = schools.with_columns(
        pl.when(pl.col("_result").is_not_null())
        .then((1 - RESULTS_WEIGHT) * pl.col("quality") + RESULTS_WEIGHT * pct)
        .otherwise(pl.col("quality"))
        .alias("combined")
    )
    return nearest_k_mean(ctx.origins, schools, "combined", k=k, sigma_m=sigma_m, max_m=max_m)


def school_choice(ctx, cap: float) -> pl.DataFrame:
    """Choice of good state schools: the mean of primary (2km) and secondary (5km) access."""
    primary = school_access(ctx, ["Primary", "All-through", "Middle deemed primary"], 2000, cap)
    secondary = school_access(
        ctx, ["Secondary", "All-through", "Middle deemed secondary"], 5000, cap
    )
    both = primary.join(secondary, on="lsoa21cd", how="full", coalesce=True, suffix="_s")
    return both.select("lsoa21cd", ((pl.col("value") + pl.col("value_s")) / 2).alias("value"))
