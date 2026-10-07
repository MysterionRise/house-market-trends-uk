"""Tests for the stagers."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from lix_pipeline.geo.nspl import load_nspl
from lix_pipeline.stage import save_staged
from lix_pipeline.stage.iod import _iod_rename_map, stage_iod
from lix_pipeline.stage.price_paid import PP_COLUMNS, stage_price_paid


class TestSaveStaged:
    def test_writes_valid_parquet(self, tmp_path: Path):
        """save_staged should write a valid Parquet file."""
        df = pl.DataFrame(
            {
                "lsoa21cd": ["E01000001", "E01000002"],
                "value": [100, 200],
            }
        )

        with pytest.MonkeyPatch.context() as m:
            m.setenv("LIX_DATA_DIR", str(tmp_path))

            out = save_staged(df, "test_output")

            assert out.exists()
            assert out.suffix == ".parquet"

            # Read back and verify
            loaded = pl.read_parquet(out)
            assert len(loaded) == 2
            assert loaded.columns == ["lsoa21cd", "value"]

    def test_writes_lazyframe(self, tmp_path: Path):
        """save_staged should handle LazyFrames by collecting them."""
        lf = pl.DataFrame(
            {
                "lsoa21cd": ["E01000001"],
                "score": [42.0],
            }
        ).lazy()

        with pytest.MonkeyPatch.context() as m:
            m.setenv("LIX_DATA_DIR", str(tmp_path))

            out = save_staged(lf, "test_lazy")
            loaded = pl.read_parquet(out)
            assert len(loaded) == 1
            assert loaded["score"][0] == pytest.approx(42.0)


class TestPricePaidColumns:
    def test_column_count(self):
        """Price Paid CSV should have 16 columns."""
        assert len(PP_COLUMNS) == 16

    def test_key_columns_present(self):
        for col in (
            "transaction_id",
            "price",
            "postcode",
            "date_of_transfer",
            "ppd_category",
            "record_status",
        ):
            assert col in PP_COLUMNS


def _pp_row(txn: int, price: int, day: str, postcode: str, category="A", status="A") -> str:
    values = [
        f"{{TXN-{txn:06d}}}",
        str(price),
        f"{day} 00:00",
        postcode,
        "T",
        "N",
        "F",
        "1",
        "",
        "TEST ST",
        "",
        "LONDON",
        "WESTMINSTER",
        "GREATER LONDON",
        category,
        status,
    ]
    return ",".join(f'"{v}"' for v in values)


@pytest.fixture
def price_paid_csv(tmp_path: Path) -> Path:
    """Headerless Price Paid CSV exercising the filters and time windows."""
    rows = [
        # SW1A 1AA → E01000001: 3 sales in the last 12 months, 1 in the 12 months before
        _pp_row(1, 300_000, "2026-08-01", "SW1A 1AA"),
        _pp_row(2, 400_000, "2026-03-15", "sw1a1aa"),
        _pp_row(3, 500_000, "2025-11-20", "SW1A  1AA"),
        _pp_row(4, 200_000, "2025-01-10", "SW1A 1AA"),
        # Non-market (category B) and deleted records are excluded
        _pp_row(5, 9_000_000, "2026-08-01", "SW1A 1AA", category="B"),
        _pp_row(6, 9_000_000, "2026-08-01", "SW1A 1AA", status="D"),
        # Terminated postcode E1 6AN → E01000006 still geocodes
        _pp_row(7, 250_000, "2026-06-01", "E1 6AN"),
        # Only a sale 3 years ago: in the 5-year stats, absent from 12m
        _pp_row(8, 150_000, "2023-09-01", "EC1A 1BB"),
        # Older than 5 years: no row at all for N1 9GU
        _pp_row(9, 100_000, "2015-01-01", "N1 9GU"),
        # Welsh sale geocodes (counts towards match rate) but is dropped from output
        _pp_row(10, 180_000, "2026-08-29", "CF10 1AA"),
        # Unknown postcode
        _pp_row(11, 210_000, "2026-07-01", "ZZ99 9ZZ"),
    ]
    path = tmp_path / "price_paid.csv"
    path.write_text("\n".join(rows) + "\n")
    return path


class TestStagePricePaid:
    def _run(self, price_paid_csv, nspl_csv, as_of=None) -> pl.DataFrame:
        nspl = load_nspl(nspl_csv, live_only=False, nations=None)
        return stage_price_paid(price_paid_csv, nspl=nspl, as_of=as_of).collect()

    def test_england_lsoas_only(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv)
        assert df["lsoa21cd"].to_list() == ["E01000001", "E01000002", "E01000006"]

    def test_as_of_defaults_to_latest_sale(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv)
        # Latest standard sale is the Welsh one on 2026-08-29
        assert df["as_of"].unique().to_list() == [date(2026, 8, 29)]

    def test_windows_and_filters(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv)
        sw1 = df.filter(pl.col("lsoa21cd") == "E01000001").row(0, named=True)

        # Category B and deleted £9m sales are excluded
        assert sw1["transaction_count_12m"] == 3
        assert sw1["median_price_12m"] == 400_000
        assert sw1["transaction_count_5y"] == 4
        assert sw1["median_price_5y"] == 350_000
        # 12m median 400k vs previous 12m median 200k
        assert sw1["yoy_change_pct"] == pytest.approx(100.0)

    def test_area_with_only_older_sales(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv)
        ec1 = df.filter(pl.col("lsoa21cd") == "E01000002").row(0, named=True)
        assert ec1["transaction_count_12m"] == 0
        assert ec1["median_price_12m"] is None
        assert ec1["median_price_5y"] == 150_000

    def test_terminated_postcode_geocodes(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv)
        assert "E01000006" in df["lsoa21cd"].to_list()

    def test_explicit_as_of_excludes_later_sales(self, price_paid_csv, nspl_csv):
        df = self._run(price_paid_csv, nspl_csv, as_of=date(2026, 1, 15))
        sw1 = df.filter(pl.col("lsoa21cd") == "E01000001").row(0, named=True)
        # Only the 2025-11-20 sale falls in the 12 months to 2026-01-15
        assert sw1["transaction_count_12m"] == 1
        assert sw1["median_price_12m"] == 500_000

    def test_logs_match_rate(self, price_paid_csv, nspl_csv, caplog):
        import logging

        with caplog.at_level(logging.INFO, logger="lix.stage.price_paid"):
            self._run(price_paid_csv, nspl_csv)
        # 7 standard sales in the 24 months to 2026-08-29; only ZZ99 9ZZ fails to match
        assert "6/7 matched" in caplog.text


# Real IoD 2025 File 7 header (subset), including the truncated one
IOD_HEADER = [
    "LSOA code (2021)",
    "LSOA name (2021)",
    "Local Authority District code (2024)",
    "Local Authority District name (2024)",
    "Index of Multiple Deprivation (IMD) Score",
    "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)",
    "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)",
    "Income Score (rate)",
    "Income Rank (where 1 is most deprived)",
    "Crime Score",
    "Income Deprivation Affecting Children Index (IDACI) Score (rate)",
    "Children and Young People Sub-domain Decile (where 1 is most deprived 10% of LSO",
    "Outdoors Sub-domain Score",
    "Total population: mid 2022",
    "Working age population 18-66 (for use with Employment Deprivation Domain): mid 2022",
]


@pytest.fixture
def iod_csv(tmp_path: Path) -> Path:
    rows = [
        [
            "E01000001",
            "City of London 001A",
            "E09000001",
            "City of London",
            "8.742",
            "26525",
            "8",
            "0.013",
            "33730",
            "-2.22",
            "0.039",
            "10",
            "1.414",
            "1795",
            "1248",
        ],
        [
            "E01000002",
            "City of London 001B",
            "E09000001",
            "City of London",
            "6.1",
            "29000",
            "9",
            "0.010",
            "33000",
            "-1.5",
            "0.020",
            "9",
            "0.9",
            "1600",
            "1100",
        ],
        # Non-England rows (should never appear, but must be filtered if they do)
        [
            "W01000001",
            "Somewhere",
            "W06000001",
            "Anglesey",
            "1",
            "1",
            "1",
            "0",
            "1",
            "0",
            "0",
            "1",
            "0",
            "1",
            "1",
        ],
    ]
    path = tmp_path / "iod.csv"
    pl.DataFrame(rows, schema=IOD_HEADER, orient="row").write_csv(path)
    return path


class TestStageIod:
    def test_rename_map(self):
        rename = _iod_rename_map(IOD_HEADER)
        assert rename["LSOA code (2021)"] == "lsoa21cd"
        assert rename["Local Authority District code (2024)"] == "lad_cd"
        assert (
            rename[
                "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)"
            ]
            == "imd_decile"
        )
        # "Income Score" must not be confused with the IDACI "Income Deprivation..." label
        assert rename["Income Score (rate)"] == "income_score"
        assert rename["Income Deprivation Affecting Children Index (IDACI) Score (rate)"] == (
            "idaci_score"
        )
        assert rename[IOD_HEADER[11]] == "sub_children_young_people_decile"
        assert rename["Total population: mid 2022"] == "pop_total"
        assert len(rename) == len(IOD_HEADER)

    def test_stage_iod(self, iod_csv):
        df = stage_iod(iod_csv).collect()

        assert df["lsoa21cd"].to_list() == ["E01000001", "E01000002"]
        row = df.row(0, named=True)
        assert row["imd_score"] == pytest.approx(8.742)
        assert row["imd_rank"] == 26525
        assert row["crime_score"] == pytest.approx(-2.22)
        assert row["pop_total"] == 1795
        assert df.schema["imd_decile"] == pl.Int32
        assert df.schema["lad_nm"] == pl.Utf8

    def test_rejects_file_without_lsoa21_column(self, tmp_path: Path):
        path = tmp_path / "old.csv"
        pl.DataFrame({"LSOA code (2011)": ["E01000001"]}).write_csv(path)
        # IoD 2019 uses 2011 LSOAs: must fail loudly rather than mis-join
        with pytest.raises(ValueError):
            stage_iod(path)
