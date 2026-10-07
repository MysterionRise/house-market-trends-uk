"""Monte Carlo over plausible weightings (lix_core.uncertainty)."""

import numpy as np
import pytest

from lix_core.uncertainty import (
    overall_draws,
    percentile_columns,
    percentile_interval,
    top_share,
    weight_draws,
)


def test_draws_centre_on_the_weights_with_the_asked_spread():
    names, draws = weight_draws({"a": 2, "b": 1, "c": 1, "d": 0}, n=4000)
    assert names == ["a", "b", "c"]
    assert np.allclose(draws.sum(axis=1), 1)
    assert draws.mean(axis=0) == pytest.approx([0.5, 0.25, 0.25], abs=0.01)
    # A theme of average weight (1/3 here) varies by about 25%
    rel_sd = draws.std(axis=0) / draws.mean(axis=0)
    assert 0.15 < rel_sd[1] < 0.35


def test_overall_uses_present_themes_and_coverage():
    scores = np.array([[80.0, 40.0], [np.nan, 60.0], [np.nan, np.nan]])
    draws = np.array([[0.5, 0.5], [0.75, 0.25]])
    out = overall_draws(scores, draws)
    assert out[0] == pytest.approx([60.0, 70.0])
    assert np.isnan(out[1, 1])  # only 25% of the weight available in the second draw
    assert out[1, 0] == pytest.approx(60.0)  # exactly 50% available: allowed
    assert np.isnan(out[2]).all()


def test_percentile_columns_matches_average_rank_scale():
    pct = percentile_columns(np.array([[1.0], [2.0], [2.0], [np.nan]]))
    assert pct[:3, 0] == pytest.approx([0.0, 75.0, 75.0])
    assert np.isnan(pct[3, 0])


def test_dominant_area_is_stable_and_close_calls_are_not():
    themes = {
        "a": np.array([90.0, 60.0, 61.0, 10.0]),
        "b": np.array([90.0, 61.0, 60.0, 10.0]),
    }
    weights = {"a": 1, "b": 1}
    share = top_share(themes, weights, top_n=2)
    assert share[0] == 1.0 and share[3] == 0.0
    assert 0 < share[1] < 1 and share[1] + share[2] == pytest.approx(1.0)
    lo, hi = percentile_interval(themes, weights)
    assert lo[0] == hi[0] == 100.0
    assert lo[1] < hi[1]
