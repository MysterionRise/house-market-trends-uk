"""House prices from Land Registry sales, steadied where an LSOA has few sales."""

import polars as pl

# Sales-equivalent weight of the MSOA median in the blend (empirical-Bayes style)
PRIOR_SALES = 5


def median_price(ctx) -> pl.DataFrame:
    """Median 12-month price, shrunk towards the MSOA's median when sales are few.

    value = (n × LSOA median + k × MSOA median) / (n + k), with n the LSOA's sales in
    the last 12 months and k = ``PRIOR_SALES``. LSOAs with no sales in 12 months take
    the MSOA median; if that's missing too, their own 5-year median.
    """
    pp = ctx.staged("price_paid").join(
        ctx.geo.select("lsoa21cd", "msoa21cd"), on="lsoa21cd", how="right"
    )
    msoa = pp.group_by("msoa21cd").agg(pl.col("median_price_12m").median().alias("msoa_median"))
    pp = pp.join(msoa, on="msoa21cd", how="left")
    n = pl.col("transaction_count_12m").fill_null(0)
    own = pl.col("median_price_12m")
    blended = (
        pl.when(own.is_not_null() & pl.col("msoa_median").is_not_null())
        .then((n * own + PRIOR_SALES * pl.col("msoa_median")) / (n + PRIOR_SALES))
        .otherwise(pl.coalesce(own, pl.col("msoa_median"), pl.col("median_price_5y")))
    )
    return pp.select(
        "lsoa21cd",
        blended.alias("value"),
        pl.when(n < PRIOR_SALES).then(pl.lit("low_n")).otherwise(pl.lit("ok")).alias("quality"),
    )
