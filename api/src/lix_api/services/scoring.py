"""Scores for any weighting: preset, custom theme weights and indicator multipliers."""

import polars as pl

from lix_api.store import Store
from lix_core.scoring import score_lsoas

ThemeWeights = dict[str, float]
MAX_CACHED = 64


def resolve_weights(
    store: Store,
    preset: str | None = None,
    theme_weights: ThemeWeights | None = None,
    indicator_weights: dict[str, float] | None = None,
) -> tuple[str, ThemeWeights, dict[str, float]]:
    """Start from a preset, then apply any custom theme weights and indicator multipliers."""
    name = preset or store.default_preset
    if name not in store.presets:
        raise ValueError(f"Unknown preset {name!r}; choose from {sorted(store.presets)}")
    base = store.presets[name]
    themes = {**base.themes, **(theme_weights or {})}
    unknown = set(themes) - set(store.themes)
    if unknown:
        raise ValueError(f"Unknown themes {sorted(unknown)}; themes are {sorted(store.themes)}")
    multipliers = {**base.indicators, **(indicator_weights or {})}
    if theme_weights or indicator_weights:
        name = f"{name} (adjusted)"
    return name, themes, multipliers


def scores_for(store: Store, themes: ThemeWeights, multipliers: dict[str, float]) -> pl.DataFrame:
    """Per-LSOA theme scores, overall and percentiles for these weights.

    Computing all 33,755 LSOAs takes a few milliseconds; results are cached on the
    store per weighting, since a conversation reuses the same few.
    """
    key = (tuple(sorted(themes.items())), tuple(sorted(multipliers.items())))
    cache = store.score_cache
    if key not in cache:
        if len(cache) >= MAX_CACHED:
            cache.pop(next(iter(cache)))
        scored = [(i.id, i.theme, i.weight) for i in store.scored]
        out = score_lsoas(store.features, scored, themes, multipliers)
        cache[key] = pl.concat([store.features.select("lsoa21cd"), out], how="horizontal")
    return cache[key]
