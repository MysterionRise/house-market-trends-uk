"""Air quality (Defra grids, already population-weighted per LSOA) and flood risk."""

import polars as pl


def pcm(ctx, slug: str) -> pl.DataFrame:
    return ctx.staged(slug).select("lsoa21cd", "value")


def flood_risk(ctx, bands: list[str]) -> pl.DataFrame:
    """Share of homes (%) in the given flood likelihood bands, from rivers or the sea.

    Numerator: residential properties at risk (EA, by postcode); denominator: the
    LSOA's dwellings (VOA). LSOAs with no listed postcode have no homes at risk.
    """
    at_risk = ctx.staged("ea_flood_postcodes").select(
        "lsoa21cd", pl.sum_horizontal(f"res_{b}" for b in bands).alias("at_risk")
    )
    df = (
        ctx.staged("voa_ctsop")
        .select("lsoa21cd", "dwellings")
        .join(at_risk, on="lsoa21cd", how="left")
    )
    return df.select(
        "lsoa21cd",
        (pl.col("at_risk").fill_null(0) / pl.col("dwellings") * 100).clip(0, 100).alias("value"),
    )
