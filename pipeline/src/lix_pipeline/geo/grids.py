"""Gridded data (e.g. Defra 1km air-quality maps) → LSOA, weighted by where people live.

Each postcode takes the value of the grid cell it falls in; the LSOA value is the mean
over its postcodes. Postcodes follow addresses, so this approximates a
population-weighted average without needing household counts.
"""

import polars as pl


def sample_grid_at_points(
    grid: pl.DataFrame,
    points: pl.DataFrame,
    value: str,
    cell_m: int = 1000,
    grid_xy: tuple[str, str] = ("x", "y"),
    point_xy: tuple[str, str] = ("east1m", "north1m"),
    by: str = "lsoa21cd",
) -> pl.DataFrame:
    """Average a gridded ``value`` over the points in each ``by`` group.

    ``grid`` holds one row per cell, located by its centre (Defra PCM convention, e.g.
    x=500 for the cell spanning 0–1000). Points without a cell value are ignored;
    returns ``by``, ``value`` and ``n_points`` (points that found a cell).
    """
    gx, gy = grid_xy
    px, py = point_xy
    half = cell_m // 2
    cells = grid.select(
        ((pl.col(gx) - half) // cell_m).cast(pl.Int64).alias("_cx"),
        ((pl.col(gy) - half) // cell_m).cast(pl.Int64).alias("_cy"),
        pl.col(value),
    ).filter(pl.col(value).is_not_null())
    pts = points.select(
        pl.col(by),
        (pl.col(px) // cell_m).cast(pl.Int64).alias("_cx"),
        (pl.col(py) // cell_m).cast(pl.Int64).alias("_cy"),
    )
    return (
        pts.join(cells, on=["_cx", "_cy"], how="inner")
        .group_by(by)
        .agg(pl.col(value).mean(), pl.len().alias("n_points"))
        .sort(by)
    )
