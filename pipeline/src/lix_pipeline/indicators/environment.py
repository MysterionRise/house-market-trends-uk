"""Air quality from the staged Defra grids (already population-weighted per LSOA)."""

import polars as pl


def pcm(ctx, slug: str) -> pl.DataFrame:
    return ctx.staged(slug).select("lsoa21cd", "value")
