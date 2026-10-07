"""One area's profile: scores, strengths, weaknesses, key facts and caveats."""

import polars as pl

from lix_api.models import AreaProfile, IndicatorValue, Point, ThemeScore
from lix_api.services.scoring import ThemeWeights, resolve_weights, scores_for
from lix_api.services.search import resolve_lsoa
from lix_api.store import Store

KEY_FACTS = ["house_price", "council_tax", "crime_violence", "no2", "flood_risk",
             "gp_distance", "station_distance", "gigabit_broadband", "well_run_pubs",
             "households_with_children"]  # fmt: skip

FLAG_TEXT = {
    "imputed": "Crime figures here are estimated: Greater Manchester Police publishes no "
    "street-level data.",
    "low_n": "Few homes sold here in the last year, so the price is steadied towards the "
    "surrounding area.",
}


def _round(v: float | None, digits: int = 1) -> float | None:
    return None if v is None else round(v, digits)


def indicator_value(store: Store, row: dict, indicator_id: str) -> IndicatorValue:
    spec = store.indicators[indicator_id]
    return IndicatorValue(
        id=spec.id, label=spec.label, theme=spec.theme, unit=spec.unit,
        value=_round(row.get(f"raw__{spec.id}"), 3), score=_round(row.get(f"n__{spec.id}")),
        quality=str(row.get(f"q__{spec.id}") or "ok"), role=spec.role,
    )  # fmt: skip


def area_profile(
    store: Store,
    ref: str,
    preset: str | None = None,
    theme_weights: ThemeWeights | None = None,
) -> AreaProfile:
    code = resolve_lsoa(store, ref)
    row = store.features.row(store.lsoa_index[code], named=True)
    name, themes, multipliers = resolve_weights(store, preset, theme_weights)
    every = scores_for(store, themes, multipliers)
    scores = every.row(store.lsoa_index[code], named=True)
    local = every.filter(store.features["lad_cd"] == row["lad_cd"])

    def median(df: pl.DataFrame, col: str) -> float | None:
        return _round(df[col].median()) if col in df.columns else None

    theme_scores = [
        ThemeScore(
            theme=t,
            label=spec.label,
            score=_round(scores.get(f"theme__{t}")),
            percentile=_round(scores.get(f"theme_pct__{t}"), 0),
            england_median=median(every, f"theme__{t}"),
            local_median=median(local, f"theme__{t}"),
        )  # fmt: skip
        for t, spec in store.themes.items()
    ]
    scored = [indicator_value(store, row, i.id) for i in store.scored]
    ranked = sorted((v for v in scored if v.score is not None), key=lambda v: v.score)
    flags = sorted(
        {FLAG_TEXT[v.quality] for v in scored if v.quality in FLAG_TEXT}
        | ({FLAG_TEXT["low_n"]} if row.get("q__house_price") == "low_n" else set())
    )
    pct = scores.get("overall_pct")
    # Precomputed per preset at build time; custom weights have no range
    preset_id = None if theme_weights else name
    lo, hi = row.get(f"pct_lo__{preset_id}"), row.get(f"pct_hi__{preset_id}")
    return AreaProfile(
        lsoa21cd=code,
        lsoa_name=row["lsoa21nm"],
        neighbourhood=row["msoa_name"],
        msoa21cd=row["msoa21cd"],
        local_authority=row["lad_nm"],
        region=row["rgn_nm"],
        urban_rural=row["ruc21nm"],
        population=row["population"],
        overall=_round(scores.get("overall")),
        overall_percentile=_round(pct, 0),
        band=None if pct is None else min(int(pct // 20) + 1, 5),
        overall_percentile_range=None if lo is None or hi is None else [round(lo), round(hi)],
        coverage=_round(scores.get("coverage"), 2),
        preset=name,
        themes=theme_scores,
        strengths=list(reversed(ranked[-3:])),
        weaknesses=ranked[:3],
        key_facts=[indicator_value(store, row, i) for i in KEY_FACTS if i in store.indicators],
        flags=flags,
        centre=Point(lat=row["pwc_lat"], lon=row["pwc_lon"]),
        bbox=(row["bbox_w"], row["bbox_s"], row["bbox_e"], row["bbox_n"]),
    )


def lsoas_in(store: Store, level: str, code: str) -> pl.Series:
    column = {"msoa": "msoa21cd", "lad": "lad_cd", "region": "rgn_cd", "lsoa": "lsoa21cd"}[level]
    return store.features.filter(pl.col(column) == code)["lsoa21cd"]
