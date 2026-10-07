"""GP access: distance to the nearest practice and GP capacity of the practices used."""

import polars as pl

# Practices reporting less than this many qualified GP FTE are left out of the ratio:
# they are usually staffed through other organisations, and dividing by ~0 explodes
MIN_QUALIFIED_GP_FTE = 1.0
MIN_PATIENT_COVERAGE = 0.5


def nearest_gp(ctx) -> pl.DataFrame:
    access = ctx.access(ctx.staged("ods_gp"), radius_m=1)
    return access.select("lsoa21cd", pl.col("nearest_m").alias("value"))


def patients_per_gp(ctx) -> pl.DataFrame:
    """Patients per qualified GP FTE, averaged over the practices an LSOA's residents use.

    Each practice's ratio is its registered list (England residents) over its qualified
    GP FTE; an LSOA's value weights those ratios by how many of its residents are
    registered at each practice. Null if less than half its patients are at practices
    with a usable ratio.
    """
    reg = ctx.staged("gp_registrations")
    lists = reg.group_by("practice_code").agg(pl.col("patients").sum().alias("list_size"))
    ratio = (
        lists.join(ctx.staged("gp_workforce"), on="practice_code", how="inner")
        .filter(pl.col("qualified_gp_fte") >= MIN_QUALIFIED_GP_FTE)
        .select("practice_code", (pl.col("list_size") / pl.col("qualified_gp_fte")).alias("ratio"))
    )
    per_lsoa = (
        reg.join(ratio, on="practice_code", how="left")
        .group_by("lsoa21cd")
        .agg(
            (pl.col("ratio") * pl.col("patients")).sum().alias("num"),
            pl.col("patients").filter(pl.col("ratio").is_not_null()).sum().alias("covered"),
            pl.col("patients").sum().alias("total"),
        )
    )
    return per_lsoa.select(
        "lsoa21cd",
        pl.when(pl.col("covered") / pl.col("total") >= MIN_PATIENT_COVERAGE)
        .then(pl.col("num") / pl.col("covered"))
        .alias("value"),
    )
