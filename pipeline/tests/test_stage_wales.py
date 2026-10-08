"""Welsh sources staged into the concept tables (schools, council tax, deprivation)."""

import polars as pl
import pytest

from lix_pipeline.stage.housing import BAND_RATIOS
from lix_pipeline.stage.schools import WG_SECTOR_PHASE, wg_phase


class TestWelshSchools:
    def test_sector_and_type_map_to_gias_phases(self):
        df = pl.DataFrame(
            {
                "sector": ["Cynradd", "Uwchradd", "Canol", "Meithrin", "Arbennig", "???", "???"],
                "school_type": [
                    "Nursery, Infants & Juniors",
                    "Secondary (ages 11-19)",
                    "Middle (ages 3-16)",
                    "Nursery",
                    "Special (with post-16 provision)",
                    "Juniors",
                    "Something else",
                ],
            }
        )
        out = df.with_columns(wg_phase(pl.col("sector"), pl.col("school_type")).alias("phase"))
        assert out["phase"].to_list() == [
            "Primary", "Secondary", "All-through", "Nursery", "Special", "Primary", None,
        ]  # fmt: skip

    def test_every_known_sector_has_a_phase(self):
        assert set(WG_SECTOR_PHASE.values()) <= {
            "Nursery", "Primary", "Secondary", "All-through", "Special",
        }  # fmt: skip


class TestWelshCouncilTax:
    def test_bands_follow_the_statutory_ninths(self):
        assert BAND_RATIOS["d"] == 9 and BAND_RATIOS["a"] == 6 and BAND_RATIOS["h"] == 18
        band_d = 2260.73
        assert round(band_d * BAND_RATIOS["a"] / 9, 2) == pytest.approx(1507.15, abs=0.01)
        assert round(band_d * BAND_RATIOS["h"] / 9, 2) == pytest.approx(4521.46, abs=0.01)


class TestWimdDeciles:
    def test_decile_within_the_nation(self):
        # The formula used in stage/deprivation.py: rank 1 → decile 1, rank n → decile 10
        n = 1917
        ranks = pl.DataFrame({"imd_rank": [1, 191, 192, 959, 1917]})
        decile = ((pl.col("imd_rank") - 1) * 10 // n + 1).cast(pl.Int32)
        assert ranks.select(decile)["imd_rank"].to_list() == [1, 1, 1, 5, 10]
        assert ranks.select(decile)["imd_rank"].max() <= 10
