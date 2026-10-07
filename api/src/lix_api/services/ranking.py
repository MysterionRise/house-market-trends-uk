"""Rank areas for a weighting, within a place or radius, with optional filters."""

import math

import numpy as np
import polars as pl

from lix_api.models import Level, Point, RankedArea, RankResult
from lix_api.services.scoring import ThemeWeights, resolve_weights, scores_for
from lix_api.services.search import search_place
from lix_api.store import Store
from lix_core.uncertainty import top_share

DEFAULT_RADIUS_KM = 10.0


def _within(store: Store, within: str | None, radius_km: float | None):
    """Filter expression and label for "within" (an area or a place + radius)."""
    if not within:
        return pl.lit(True), None, None
    places = search_place(store, within, limit=1)
    if not places:
        raise LookupError(f"Couldn't find {within!r}")
    place = places[0]
    if place.kind in ("lad", "region", "msoa") and radius_km is None:
        column = {"lad": "lad_cd", "region": "rgn_cd", "msoa": "msoa21cd"}[place.kind]
        return pl.col(column) == place.code, place.name, place.bbox
    centre = place.centre
    km = radius_km or DEFAULT_RADIUS_KM
    dlat = km / 111.0
    dlon = km / (111.0 * math.cos(math.radians(centre.lat)))
    dist_km = (
        ((pl.col("pwc_lat") - centre.lat) * 111.0) ** 2
        + ((pl.col("pwc_lon") - centre.lon) * 111.0 * math.cos(math.radians(centre.lat))) ** 2
    ).sqrt()
    bbox = (centre.lon - dlon, centre.lat - dlat, centre.lon + dlon, centre.lat + dlat)
    return dist_km <= km, f"within {km:g} km of {place.name}", bbox


def rank_areas(
    store: Store,
    within: str | None = None,
    radius_km: float | None = None,
    level: Level = "lsoa",
    preset: str | None = None,
    theme_weights: ThemeWeights | None = None,
    indicator_weights: dict[str, float] | None = None,
    max_median_price: float | None = None,
    min_theme_scores: dict[str, float] | None = None,
    urban: bool | None = None,
    limit: int = 10,
) -> RankResult:
    """Best areas first. At MSOA level, scores are population-weighted LSOA means."""
    name, themes, multipliers = resolve_weights(store, preset, theme_weights, indicator_weights)
    scores = scores_for(store, themes, multipliers)
    df = pl.concat(
        [
            store.features.select(
                "lsoa21cd",
                "lsoa21nm",
                "msoa21cd",
                "msoa_name",
                "lad_cd",
                "rgn_cd",
                "lad_nm",
                "population",
                "pwc_lat",
                "pwc_lon",
                "urban",
                "raw__house_price",
            ),  # fmt: skip
            scores.drop("lsoa21cd"),
        ],
        how="horizontal",
    )
    where, label, bbox = _within(store, within, radius_km)
    df = df.filter(where)
    if urban is not None:
        df = df.filter(pl.col("urban") == urban)

    theme_cols = [f"theme__{t}" for t in store.themes]
    if level == "msoa":
        w = pl.col("population")
        df = df.group_by("msoa21cd").agg(
            pl.col("msoa_name").first().alias("name"),
            pl.col("lad_nm").first(),
            w.sum().alias("population"),
            *[((pl.col(c) * w).sum() / w.filter(pl.col(c).is_not_null()).sum()).alias(c)
              for c in ["overall", *theme_cols]],
            pl.col("raw__house_price").median(),
            ((pl.col("pwc_lat") * w).sum() / w.sum()).alias("pwc_lat"),
            ((pl.col("pwc_lon") * w).sum() / w.sum()).alias("pwc_lon"),
        ).rename({"msoa21cd": "code"})  # fmt: skip
        # MSOA percentiles among MSOAs in the result set would mislead; use LSOA's scale
        df = df.with_columns(pl.lit(None, pl.Float64).alias("overall_pct"))
    else:
        df = df.rename({"lsoa21cd": "code"}).with_columns(
            pl.concat_str(pl.col("lsoa21nm"), pl.lit(" ("), pl.col("msoa_name"), pl.lit(")")).alias(
                "name"
            )
        )

    if max_median_price is not None:
        df = df.filter(pl.col("raw__house_price") <= max_median_price)
    for theme, minimum in (min_theme_scores or {}).items():
        df = df.filter(pl.col(f"theme__{theme}") >= minimum)

    candidates = df.height
    df = df.sort("overall", descending=True, nulls_last=True)
    # How robust the top results are to the exact weights (lix_core.uncertainty)
    present = [t for t in store.themes if f"theme__{t}" in df.columns and themes.get(t, 0) > 0]
    if df.height > limit and present:
        theme_scores = {t: df[f"theme__{t}"].to_numpy().astype(float) for t in present}
        shares = top_share(theme_scores, {t: themes[t] for t in present}, top_n=limit)
    else:
        shares = np.ones(df.height)
    top = df.head(limit).with_columns(pl.Series("stability", shares[:limit]))
    results = [
        RankedArea(
            rank=i + 1,
            level=level,
            code=r["code"],
            name=r["name"],
            local_authority=r["lad_nm"],
            overall=None if r["overall"] is None else round(r["overall"], 1),
            overall_percentile=None if r["overall_pct"] is None else round(r["overall_pct"]),
            themes={
                t: None if r[f"theme__{t}"] is None else round(r[f"theme__{t}"], 1)
                for t in store.themes
            },
            median_price=r["raw__house_price"],
            population=int(r["population"]),
            centre=Point(lat=r["pwc_lat"], lon=r["pwc_lon"]),
            stability=round(float(r["stability"]), 2),
        )  # fmt: skip
        for i, r in enumerate(top.iter_rows(named=True))
    ]
    return RankResult(
        level=level, within=label, preset=name, theme_weights=themes,
        candidates=candidates, results=results, bbox=bbox,
    )  # fmt: skip
