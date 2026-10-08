"""The multi-nation backbone: builders per nation, population from the ONS workbook,
nation-aware validation."""

from pathlib import Path

import polars as pl
import pytest

from lix_pipeline.qa.validate import validate_geo
from lix_pipeline.stage import geo, geo_ew
from lix_pipeline.stage.population import latest_sheet, tidy_median_age, tidy_population


@pytest.fixture
def data(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("LIX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LIX_NATIONS", "E,W")
    return tmp_path


class TestPopulation:
    def test_latest_sheet(self):
        names = ["Cover sheet", "Mid-2022 LSOA 2021", "Mid-2024 LSOA 2021", "Median age LSOA"]
        assert latest_sheet(names) == ("Mid-2024 LSOA 2021", 2024)
        with pytest.raises(ValueError, match="Mid-YYYY"):
            latest_sheet(["Cover sheet"])

    def test_tidy_population_sums_sexes(self):
        sheet = pl.DataFrame(
            {
                "LAD 2021 Code": ["E06000001", "W06000015"],
                "LAD 2021 Name": ["Hartlepool", "Cardiff"],
                "LSOA 2021 Code": ["E01011949", "W01001880"],
                "LSOA 2021 Name": ["Hartlepool 009A", "Cardiff 032B"],
                "Total": [1898.0, 1500.0],
                "F0 to 15": [170.0, 100.0],
                "M0 to 15": [160.0, 110.0],
                "F65 and over": [200.0, 50.0],
                "M65 and over": [150.0, 40.0],
            }
        )
        out = tidy_population(sheet, 2024)
        assert out["population"].to_list() == [1898, 1500]
        assert out["pop_children_0_15"].to_list() == [330, 210]
        assert out["pop_65_plus"].to_list() == [350, 90]
        assert out["pop_year"].to_list() == [2024, 2024]
        assert out.schema["population"] == pl.Int32

    def test_tidy_median_age_picks_the_year(self):
        sheet = pl.DataFrame(
            {
                "LSOA 2021 Code": ["E01011949"],
                "Median age mid-2024": [39.4],
                "Median age mid-2023": [38.1],
            }
        )
        assert tidy_median_age(sheet, 2023)["median_age"].to_list() == pytest.approx([38.1])


class TestNationColumns:
    def test_nation_and_country_codes(self):
        df = pl.DataFrame({"lsoa21cd": ["E01000001", "W01000001"]})
        out = df.with_columns(geo_ew.nation_columns(("E", "W")))
        assert out["nation"].to_list() == ["E", "W"]
        assert out["ctry_cd"].to_list() == ["E92000001", "W92000004"]
        assert out["area_type"].to_list() == ["lsoa21", "lsoa21"]

    def test_ruc_class_harmonises_the_six_codes(self):
        df = pl.DataFrame({"ruc21cd": ["UN1", "UF1", "RLN1", "RLF1", "RSN1", "RSF1", "ZZ9"]})
        out = df.with_columns(geo_ew.ruc_class_expr(("E",)))
        assert out["ruc_class"].to_list() == [
            "urban", "urban", "town", "town", "rural", "rural", None
        ]  # fmt: skip

    def test_wales_region_is_the_nation(self):
        df = pl.DataFrame(
            {
                "nation": ["E", "W"],
                "ctry_cd": ["E92000001", "W92000004"],
                "rgn_cd": ["E12000007", "W99999999"],
                "rgn_nm": ["London", "(pseudo) Wales"],
            }
        )
        out = df.with_columns(geo_ew.region_columns(("E", "W")))
        assert out["rgn_cd"].to_list() == ["E12000007", "W92000004"]
        assert out["rgn_nm"].to_list() == ["London", "Wales"]
        # England alone: untouched
        assert df.with_columns(geo_ew.region_columns(("E",)))["rgn_nm"].to_list() == [
            "London",
            "(pseudo) Wales",
        ]

    def test_build_refuses_other_nations(self):
        with pytest.raises(ValueError, match="not \\['S'\\]"):
            geo_ew.build(("E", "S"))


class TestOrchestrator:
    def test_one_call_per_builder_with_its_nations(self, monkeypatch):
        calls = []

        def fake(nations):
            calls.append(nations)
            return pl.DataFrame({"lsoa21cd": [f"{n}01000001" for n in nations]})

        monkeypatch.setattr(geo, "_builders", lambda: {"geo_ew": fake})
        monkeypatch.setenv("LIX_NATIONS", "W,E")
        out = geo.stage_geo_lsoa().collect()
        assert calls == [("E", "W")]
        assert out["lsoa21cd"].to_list() == ["E01000001", "W01000001"]

    def test_unknown_builder_is_an_error(self, monkeypatch):
        monkeypatch.setattr(geo, "_builders", lambda: {})
        with pytest.raises(ValueError, match="geo_ew"):
            geo.stage_geo_lsoa()


def _geo_rows(codes: list[str]) -> pl.DataFrame:
    n = len(codes)
    return pl.DataFrame(
        {
            "lsoa21cd": codes,
            "lsoa21nm": ["x"] * n,
            "msoa21cd": [c.replace("01", "02", 1) for c in codes],
            "msoa21nm": ["x"] * n,
            "msoa_name": ["x"] * n,
            "lad_cd": ["x"] * n,
            "lad_nm": ["x"] * n,
            "rgn_cd": ["x"] * n,
            "rgn_nm": ["x"] * n,
            "nation": [c[0] for c in codes],
            "ctry_cd": ["E92000001" if c[0] == "E" else "W92000004" for c in codes],
            "area_type": ["lsoa21"] * n,
            "ruc21cd": ["UN1"] * n,
            "ruc_class": ["urban"] * n,
            "urban": [True] * n,
            "pwc_x": [1.0] * n,
            "pwc_y": [1.0] * n,
            "pwc_lat": [51.5] * n,
            "pwc_lon": [-0.1] * n,
            "population": [1500] * n,
            "area_km2": [1.0] * n,
            "bbox_w": [-1.0] * n,
            "bbox_s": [51.0] * n,
            "bbox_e": [0.0] * n,
            "bbox_n": [52.0] * n,
        }
    )


class TestValidateGeo:
    def test_reports_per_nation_counts_and_population(self, data: Path):
        staged = data / "staged"
        staged.mkdir()
        _geo_rows(["E01000001", "E01000002", "W01000001"]).write_parquet(
            staged / "geo_lsoa.parquet"
        )
        pl.DataFrame(
            {"lsoa21cd": ["E01000001", "W01000001", "W01000002"], "live": [True, True, True]}
        ).write_parquet(staged / "nspl.parquet")
        problems = validate_geo()
        assert "geo_lsoa has 3 rows, expected 35,672" in problems
        assert any(p.startswith("England: 2 LSOAs, expected 33,755") for p in problems)
        assert any(p.startswith("Wales: 1 LSOAs, expected 1,917") for p in problems)
        assert any("England population 3,000 is outside" in p for p in problems)
        assert any("1 NSPL LSOAs missing from geo_lsoa" in p for p in problems)
        assert not any("duplicate" in p or "missing column" in p for p in problems)

    def test_codes_outside_scope_and_nulls(self, data: Path, monkeypatch):
        monkeypatch.setenv("LIX_NATIONS", "E")
        staged = data / "staged"
        staged.mkdir()
        geo = _geo_rows(["E01000001", "W01000001"]).with_columns(
            pl.Series("ruc_class", ["urban", None])
        )
        geo.write_parquet(staged / "geo_lsoa.parquet")
        pl.DataFrame({"lsoa21cd": ["E01000001"], "live": [True]}).write_parquet(
            staged / "nspl.parquet"
        )
        problems = validate_geo()
        assert "geo_lsoa has codes outside the active nations ['E']" in problems
        assert "geo_lsoa.ruc_class has 1 nulls" in problems
