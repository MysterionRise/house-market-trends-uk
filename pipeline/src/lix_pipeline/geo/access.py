"""Access to points of interest (GPs, schools, pubs, ...) from where people live.

Origins are residential postcodes (NSPL small users), so an LSOA's figure is the
average experience of its addresses rather than of one centroid. Distances are
straight-line in British National Grid metres; walking-network routing comes later.

For each origin we compute:

- ``nearest_m``: distance to the nearest POI
- ``count``: POIs within ``radius_m``
- ``score``: a distance-decayed count, ``Σ exp(-d²/2σ²)`` over POIs within the radius,
  squashed to 0–1 with ``log1p(score) / log1p(cap)`` so the 20th pub adds less than the 2nd
"""

import numpy as np
import polars as pl
from scipy.spatial import cKDTree


def poi_access(
    origins: pl.DataFrame,
    pois: pl.DataFrame,
    radius_m: float,
    sigma_m: float | None = None,
    cap: float = 10.0,
    weight: str | None = None,
    origin_xy: tuple[str, str] = ("east1m", "north1m"),
    poi_xy: tuple[str, str] = ("x", "y"),
    by: str = "lsoa21cd",
    max_nearest_m: float = 50_000,
) -> pl.DataFrame:
    """Per-``by`` group means of nearest distance, count within radius and access score.

    ``weight`` scales each POI's contribution (e.g. a quality multiplier for a school
    or the number of nursery places). ``sigma_m`` defaults to half the radius.
    """
    sigma = sigma_m if sigma_m is not None else radius_m / 2
    ox, oy = origin_xy
    px, py = poi_xy
    pois = pois.filter(pl.col(px).is_not_null() & pl.col(py).is_not_null())
    origins = origins.filter(pl.col(ox).is_not_null() & pl.col(oy).is_not_null())
    o_xy = np.column_stack([origins[ox].to_numpy(), origins[oy].to_numpy()]).astype(float)
    n = len(o_xy)

    if pois.height == 0:
        nearest = np.full(n, np.nan)
        count = np.zeros(n)
        score = np.zeros(n)
    else:
        p_xy = np.column_stack([pois[px].to_numpy(), pois[py].to_numpy()]).astype(float)
        w = pois[weight].to_numpy().astype(float) if weight else np.ones(len(p_xy))
        poi_tree = cKDTree(p_xy)

        nearest, _ = poi_tree.query(o_xy, k=1, distance_upper_bound=max_nearest_m)
        nearest = np.where(np.isinf(nearest), np.nan, nearest)

        pairs = cKDTree(o_xy).sparse_distance_matrix(
            poi_tree, max_distance=radius_m, output_type="coo_matrix"
        )
        decay = np.exp(-(pairs.data**2) / (2 * sigma**2)) * w[pairs.col]
        count = np.bincount(pairs.row, minlength=n).astype(float)
        raw = np.bincount(pairs.row, weights=decay, minlength=n)
        score = np.minimum(np.log1p(raw) / np.log1p(cap), 1.0)

    per_origin = pl.DataFrame(
        {
            by: origins[by],
            "nearest_m": nearest,
            "count": count,
            "score": score,
        },
        nan_to_null=True,
    )
    return (
        per_origin.group_by(by)
        .agg(
            pl.col("nearest_m").mean(),
            pl.col("count").mean(),
            pl.col("score").mean(),
            (pl.col("count") > 0).mean().alias("share_with_any"),
            pl.len().alias("n_origins"),
        )
        .sort(by)
    )


def residential_postcodes() -> pl.DataFrame:
    """Live England small-user postcodes (mostly homes) with BNG coordinates and LSOA."""
    from lix_core.paths import data_dir

    path = data_dir("staged") / "nspl.parquet"
    # usrtypind 0 = small user (<25 items of mail a day), i.e. mostly residential
    return (
        pl.scan_parquet(path)
        .filter(
            pl.col("live")
            & (pl.col("usrtypind") == "0")
            & pl.col("ctry_cd").str.starts_with("E")
            & pl.col("lsoa21cd").is_not_null()
            & pl.col("east1m").is_not_null()
        )
        .select("postcode", "lsoa21cd", "east1m", "north1m")
        .collect()
    )
