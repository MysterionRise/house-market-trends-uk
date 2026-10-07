"""Scoring maths shared by the pipeline, the API and (mirrored in TypeScript) the browser.

Per indicator, raw values become a 0–100 score where higher is always better, by one
of three methods (chosen per indicator in config/indicators.yaml):

- ``rank``: England percentile. For relative measures with no natural "good enough"
  level (crime rates, prices, deprivation scores).
- ``scale``: the value's own scale (an access index 0–1, a DfT score 0–100) mapped to
  0–100. Access indices already saturate, so a dense suburb and a city centre that both
  have plenty of cafés both score near 100.
- ``threshold``: 100 at or better than ``good``, 0 at or worse than ``bad``, linear
  between (on a log scale when ``log1p``). For distances ("a GP within 1km is fine")
  and pollution against health guidelines.

Ranking everything would turn trivial differences (a GP 300m vs 900m away) into big
score gaps and push every rural area to the bottom; saturating scales avoid that.

Per theme: weighted mean of its indicators' scores over those the LSOA has; null when
less than ``MIN_THEME_COVERAGE`` of the theme's weight is present. Overall: weighted
mean of theme scores. Both are 0–100 scores; percentiles ("better than N% of
England's neighbourhoods") are reported alongside, not instead.
"""

from collections.abc import Mapping

import polars as pl

MIN_THEME_COVERAGE = 0.5


def percentile_rank(values: pl.Expr) -> pl.Expr:
    """0–100 percentile with ties averaged; nulls stay null.

    The lowest value gets 0 and the highest 100 (for n > 1).
    """
    rank = values.rank(method="average")
    n = values.count()
    return pl.when(n > 1).then((rank - 1) / (n - 1) * 100).otherwise(50.0)


def normalise(
    values: pl.Expr,
    direction: str,
    method: str = "rank",
    log1p: bool = False,
    good: float | None = None,
    bad: float | None = None,
    scale_max: float = 1.0,
) -> pl.Expr:
    """Raw indicator values → 0–100 where higher is always better."""
    if direction not in ("higher_better", "lower_better"):
        raise ValueError(f"direction must be higher_better or lower_better, not {direction!r}")
    if method == "rank":
        v = values.log1p() if log1p else values
        return percentile_rank(-v if direction == "lower_better" else v)
    if method == "scale":
        score = (values / scale_max * 100).clip(0, 100)
        # neg().add() rather than 100 - score, which would rename the column "literal"
        return score.neg().add(100) if direction == "lower_better" else score
    if method == "threshold":
        if good is None or bad is None or good == bad:
            raise ValueError("threshold needs distinct good and bad levels")
        if (direction == "lower_better") != (good < bad):
            raise ValueError(f"good/bad ({good}, {bad}) contradict direction {direction}")
        if log1p:
            import math

            v, g, b = values.log1p(), math.log1p(good), math.log1p(bad)
        else:
            v, g, b = values, good, bad
        return ((v - b) / (g - b) * 100).clip(0, 100)
    raise ValueError(f"Unknown normalisation method {method!r}")


def weighted_score(
    df: pl.DataFrame,
    weights: Mapping[str, float],
    min_coverage: float = MIN_THEME_COVERAGE,
) -> tuple[pl.Series, pl.Series]:
    """Weighted mean of 0–100 columns, ignoring nulls; returns (score, coverage).

    ``score`` is null where the available weight share is below ``min_coverage``.
    Zero-weight columns are ignored entirely.
    """
    active = {c: w for c, w in weights.items() if w > 0}
    if not active:
        raise ValueError("At least one weight must be positive")
    total = sum(active.values())
    num = pl.sum_horizontal(pl.col(c).fill_null(0) * w for c, w in active.items())
    avail = pl.sum_horizontal(
        pl.col(c).is_not_null().cast(pl.Float64) * w for c, w in active.items()
    )
    out = df.select(
        pl.when(avail / total >= min_coverage).then(num / avail).alias("score"),
        (avail / total).alias("coverage"),
    )
    return out["score"], out["coverage"]


def percentile_of(scores: pl.Series) -> pl.Series:
    """England percentile (0–100) of a score column, keeping nulls."""
    return pl.DataFrame({"s": scores}).select(percentile_rank(pl.col("s")))["s"]


def band(percentile: pl.Expr) -> pl.Expr:
    """Consumer-facing band from a percentile: 1 (bottom fifth of England) … 5 (top fifth)."""
    return (percentile / 20).floor().clip(0, 4).cast(pl.Int8) + 1


def score_lsoas(
    norms: pl.DataFrame,
    indicators: list[tuple[str, str, float]],
    theme_weights: Mapping[str, float],
    indicator_multipliers: Mapping[str, float] | None = None,
    min_coverage: float = MIN_THEME_COVERAGE,
) -> pl.DataFrame:
    """Theme and overall scores from per-indicator 0–100 scores.

    ``norms``: one row per LSOA with a ``n__{indicator_id}`` column for each scored
    indicator. ``indicators``: (id, theme, base weight) for the scored ones.
    Returns per theme ``theme__{t}`` (score), ``theme_pct__{t}`` (percentile) and
    ``theme_coverage__{t}``; then ``overall``, ``overall_pct`` and ``coverage``.
    """
    mult = indicator_multipliers or {}
    columns: dict[str, pl.Series] = {}
    themes = sorted({theme for _, theme, _ in indicators})
    for theme in themes:
        weights = {f"n__{iid}": w * mult.get(iid, 1.0) for iid, t, w in indicators if t == theme}
        if not any(w > 0 for w in weights.values()):
            continue
        score, coverage = weighted_score(norms, weights, min_coverage)
        columns[f"theme__{theme}"] = score
        columns[f"theme_pct__{theme}"] = percentile_of(score)
        columns[f"theme_coverage__{theme}"] = coverage
    themes_df = pl.DataFrame(columns)
    overall, coverage = weighted_score(
        themes_df,
        {f"theme__{t}": theme_weights.get(t, 0.0) for t in themes if f"theme__{t}" in columns},
        min_coverage,
    )
    return themes_df.with_columns(
        overall=overall, overall_pct=percentile_of(overall), coverage=coverage
    )
