"""How much a result depends on the exact weights: a Monte Carlo over plausible weightings.

Theme weights are a judgement call. Nudging each by about a quarter (Dirichlet draws
centred on the chosen weights) and rescoring shows which results are robust: an area
whose England percentile stays within a few points, or that stays in a top-10 under
nearly every weighting, can be stated with more confidence than one that doesn't.

Theme scores don't depend on theme weights, so each draw is one matrix product: the
overall score is the weighted mean of the themes present (as in ``scoring``), null
where less than ``min_coverage`` of the weight is available.
"""

import warnings
from collections.abc import Mapping

import numpy as np

SPREAD = 0.25  # relative spread of a typical theme weight
DRAWS = 200
SEED = 20261007  # fixed, so builds are reproducible


def weight_draws(
    theme_weights: Mapping[str, float], n: int = DRAWS, spread: float = SPREAD, seed: int = SEED
) -> tuple[list[str], np.ndarray]:
    """Themes with weight > 0 and ``n`` weightings of them (rows sum to 1)."""
    names = [t for t, w in theme_weights.items() if w > 0]
    if not names:
        raise ValueError("Every theme has zero weight")
    w = np.array([theme_weights[t] for t in names], dtype=float)
    w /= w.sum()
    if len(names) == 1:
        return names, np.ones((n, 1))
    # Dirichlet(c·w): a component's relative s.d. is sqrt((1 − w) / (w (c + 1))); pick c
    # so a theme of average weight varies by about ``spread``
    mean_w = 1 / len(names)
    concentration = max((1 - mean_w) / (mean_w * spread**2) - 1, 1.0)
    return names, np.random.default_rng(seed).dirichlet(w * concentration, size=n)


def overall_draws(
    theme_scores: np.ndarray, draws: np.ndarray, min_coverage: float = 0.5
) -> np.ndarray:
    """Overall score per row (area) and column (draw); NaN theme scores are missing."""
    present = ~np.isnan(theme_scores)
    num = np.where(present, theme_scores, 0.0) @ draws.T
    available = present.astype(float) @ draws.T  # each draw's weights sum to 1
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(available >= min_coverage, num / available, np.nan)


def percentile_columns(scores: np.ndarray) -> np.ndarray:
    """Each value's percentile (0–100) within its column, average ranks, NaN kept."""
    from scipy.stats import rankdata

    ranks = rankdata(scores, axis=0, method="average", nan_policy="omit")
    n = np.sum(~np.isnan(scores), axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 1, (ranks - 1) / np.maximum(n - 1, 1) * 100, 50.0)


def _matrix(theme_scores: Mapping[str, np.ndarray], names: list[str], rows: int) -> np.ndarray:
    cols = [np.asarray(theme_scores[t], dtype=float) if t in theme_scores else np.full(rows, np.nan)
            for t in names]  # fmt: skip
    return np.column_stack(cols)


def percentile_interval(
    theme_scores: Mapping[str, np.ndarray],
    theme_weights: Mapping[str, float],
    low: float = 5,
    high: float = 95,
    n: int = DRAWS,
) -> tuple[np.ndarray, np.ndarray]:
    """The ``low``–``high`` range of each area's England percentile over plausible weightings."""
    rows = len(next(iter(theme_scores.values())))
    names, draws = weight_draws(theme_weights, n=n)
    pct = percentile_columns(overall_draws(_matrix(theme_scores, names, rows), draws))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN rows stay NaN
        return np.nanpercentile(pct, low, axis=1), np.nanpercentile(pct, high, axis=1)


def top_share(
    theme_scores: Mapping[str, np.ndarray],
    theme_weights: Mapping[str, float],
    top_n: int,
    n: int = DRAWS,
) -> np.ndarray:
    """Share of plausible weightings under which each area is among the best ``top_n``."""
    rows = len(next(iter(theme_scores.values())))
    names, draws = weight_draws(theme_weights, n=n)
    overall = overall_draws(_matrix(theme_scores, names, rows), draws)
    # Rank 1 = best in each draw; missing scores rank last
    order = np.argsort(-np.nan_to_num(overall, nan=-np.inf), axis=0, kind="stable")
    ranks = np.empty_like(order)
    np.put_along_axis(ranks, order, np.arange(rows)[:, None].repeat(overall.shape[1], 1), axis=0)
    return (ranks < top_n).mean(axis=1)
