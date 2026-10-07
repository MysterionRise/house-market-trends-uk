"""Shares of residents or households from Census 2021 tables."""

import polars as pl


def census_share(ctx, table: str, numerator: list[str], denominator: str = "total") -> pl.DataFrame:
    """sum(numerator columns) / denominator × 100."""
    df = ctx.staged(table)
    return df.select(
        "lsoa21cd",
        (pl.sum_horizontal(numerator) / pl.col(denominator) * 100).alias("value"),
    )
