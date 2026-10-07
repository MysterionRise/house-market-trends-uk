"""Tests for indicator builders, on hand-made staged tables."""

from datetime import date

import polars as pl
import pytest

from lix_core.config import IndicatorSpec
from lix_pipeline.indicators import build_indicator
from lix_pipeline.indicators.common import impute_by_proxy
from lix_pipeline.indicators.health import patients_per_gp
from lix_pipeline.indicators.housing import PRIOR_SALES, median_price
from lix_pipeline.indicators.pubs import match_pubs, normalise_name
from lix_pipeline.indicators.safety import GREATER_MANCHESTER, crime_rate


class FakeContext:
    """Stands in for indicators.Context with in-memory staged tables."""

    def __init__(self, **tables: pl.DataFrame):
        self.tables = tables

    @property
    def geo(self) -> pl.DataFrame:
        return self.tables["geo_lsoa"]

    def staged(self, slug: str) -> pl.DataFrame:
        return self.tables[slug]


GEO = pl.DataFrame({
    "lsoa21cd": ["E01000001", "E01000002", "E01000003", "E01000004"],
    "msoa21cd": ["E02000001", "E02000001", "E02000002", "E02000002"],
    "population": [1000, 2000, 1500, 1000],
    "pfa_cd": ["E23000034", "E23000034", GREATER_MANCHESTER, "E23000034"],
})  # fmt: skip


class TestCrimeRate:
    def _ctx(self):
        police = pl.DataFrame({
            "lsoa21cd": ["E01000001", "E01000002", "E01000002", "E01000003"],
            "crime_type": ["Burglary", "Burglary", "Burglary", "Burglary"],
            "force": ["Kent Police", "Kent Police", "Essex Police", "Lancashire Constabulary"],
            "n": [36, 12, 6, 3],
            "force_months": [36, 36, 18, 36],
        })  # fmt: skip
        iod = pl.DataFrame({
            "lsoa21cd": GEO["lsoa21cd"], "crime_score": [0.5, -1.0, 0.2, -1.5],
        })  # fmt: skip
        return FakeContext(geo_lsoa=GEO, police_crime=police, iod_2025=iod)

    def test_annualised_per_force_months(self):
        df = crime_rate(self._ctx(), types=["Burglary"]).sort("lsoa21cd")
        rows = {r["lsoa21cd"]: r for r in df.to_dicts()}
        # 36 crimes over 36 months = 12 a year among 1,000 people
        assert rows["E01000001"]["value"] == pytest.approx(12.0)
        # 12/36×12 + 6/18×12 = 4 + 4 = 8 a year among 2,000
        assert rows["E01000002"]["value"] == pytest.approx(4.0)
        # No recorded crime in a covered area is a true zero
        assert rows["E01000004"]["value"] == 0.0

    def test_greater_manchester_is_imputed_not_counted(self):
        df = crime_rate(self._ctx(), types=["Burglary"])
        gm = df.filter(pl.col("lsoa21cd") == "E01000003").row(0, named=True)
        assert gm["quality"] == "imputed"
        # Stray border records (3 crimes → 2 a year per 1,000) are ignored; the value
        # comes from the proxy fit, which lies within the training range
        assert 0.0 <= gm["value"] <= 12.0
        assert gm["value"] != pytest.approx(2.0)


def test_impute_by_proxy_is_monotone():
    df = pl.DataFrame({
        "v": [1.0, 2.0, 3.0, 4.0, 5.0, None, None],
        "proxy": [1.0, 2.0, 3.0, 4.0, 5.0, 1.5, 4.5],
        "gap": [False] * 5 + [True, True],
    })  # fmt: skip
    filled = impute_by_proxy(df, "v", "proxy", pl.col("gap"), bins=5, log=False)
    low, high = filled.to_list()[5:]
    assert 1.0 <= low < high <= 5.0


class TestMedianPrice:
    def test_shrinks_small_samples_towards_msoa(self):
        pp = pl.DataFrame({
            "lsoa21cd": ["E01000001", "E01000002", "E01000003"],
            "median_price_12m": [200_000.0, 400_000.0, None],
            "transaction_count_12m": [20, 1, 0],
            "median_price_5y": [190_000.0, 380_000.0, 250_000.0],
        })  # fmt: skip
        df = median_price(FakeContext(geo_lsoa=GEO, price_paid=pp)).sort("lsoa21cd")
        rows = {r["lsoa21cd"]: r for r in df.to_dicts()}
        msoa1 = 300_000  # median of 200k and 400k
        assert rows["E01000001"]["value"] == pytest.approx((20 * 200_000 + 5 * msoa1) / 25)
        assert rows["E01000002"]["value"] == pytest.approx((1 * 400_000 + 5 * msoa1) / 6)
        assert rows["E01000002"]["quality"] == "low_n"
        # No 12-month sales and no MSOA median: fall back to the 5-year median
        assert rows["E01000003"]["value"] == 250_000
        # An LSOA missing from Price Paid entirely stays null
        assert rows["E01000004"]["value"] is None
        assert PRIOR_SALES == 5


class TestPatientsPerGp:
    def test_weights_practices_by_where_patients_live(self):
        reg = pl.DataFrame({
            "practice_code": ["P1", "P1", "P2", "P3"],
            "lsoa21cd": ["E01000001", "E01000002", "E01000001", "E01000002"],
            "patients": [1000, 1000, 3000, 500],
        })  # fmt: skip
        wf = pl.DataFrame({
            "practice_code": ["P1", "P2", "P3"],
            "qualified_gp_fte": [1.0, 2.0, 0.2],  # P3 is below the 1 FTE minimum
        })  # fmt: skip
        df = patients_per_gp(FakeContext(gp_registrations=reg, gp_workforce=wf))
        rows = {r["lsoa21cd"]: r["value"] for r in df.to_dicts()}
        # P1: 2,000 patients / 1 FTE; P2: 3,000 / 2 FTE = 1,500
        assert rows["E01000001"] == pytest.approx((1000 * 2000 + 3000 * 1500) / 4000)
        # E01000002: P1 (1,000 patients) usable, P3 (500) not → 67% coverage, use P1 only
        assert rows["E01000002"] == pytest.approx(2000)


class TestPubMatching:
    def test_normalise_name(self):
        out = pl.DataFrame({"n": ["The Fox & Hounds", "Ye Olde Cheshire Cheese Inn"]}).select(
            normalise_name(pl.col("n"))
        )
        # "&" and "and" both vanish, so "Fox & Hounds" equals "Fox and Hounds"
        assert out["n"].to_list() == ["fox hounds", "cheshire cheese"]

    def test_fhrs_id_then_spatial_name_match(self):
        osm = pl.DataFrame({
            "osm_id": [1, 2, 3, 4],
            "name": ["The Red Lion", "Fox and Hounds", "The Crown", "Kings Head"],
            "x": [0.0, 1000.0, 2000.0, 3000.0],
            "y": [0.0, 0.0, 0.0, 0.0],
            "fhrs_id": ["111", None, None, None],
        })  # fmt: skip
        fsa = pl.DataFrame({
            "fhrs_id": [111, 222, 333, 444],
            "name": ["Red Lion (registered as restaurant)", "FOX & HOUNDS PH", "The Crown",
                     "Totally Different Ltd"],
            "x": [5000.0, 1030.0, 2500.0, 3010.0],  # The Crown is 500m away: too far
            "y": [0.0, 0.0, 0.0, 0.0],
            "rating": [5, 4, 5, 5],
            "rating_date": [date(2025, 1, 1)] * 4,
        })  # fmt: skip
        out = match_pubs(osm, fsa).sort("osm_id")
        assert out["match"].to_list() == ["fhrs_id", "spatial", None, None]
        assert out["fsa_id"].to_list() == [111, 222, None, None]


def test_build_indicator_fills_every_lsoa_and_flags_missing():
    spec = IndicatorSpec(
        id="x", theme="housing", label="X", description="d", unit="u",
        direction="higher_better", sources=["price_paid"], builder="common:column",
        params={"slug": "t", "column": "c"},
    )  # fmt: skip
    table = pl.DataFrame({"lsoa21cd": ["E01000001", "E01000002"], "c": [1.0, float("nan")]})
    ctx = FakeContext(geo_lsoa=GEO, t=table)
    out = build_indicator(spec, ctx).sort("lsoa21cd")
    assert out.height == GEO.height
    assert out["value"].to_list() == [1.0, None, None, None]
    assert out["quality"].to_list() == ["ok", "missing", "missing", "missing"]
