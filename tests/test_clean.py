"""Tests for the clean module."""

from pathlib import Path

import duckdb
import polars as pl
import pytest

from src.clean import PP_COLUMNS, clean_imd, save_processed


class TestSaveProcessed:
    def test_writes_valid_parquet(self, tmp_path: Path):
        """save_processed should write a valid Parquet file."""
        df = pl.DataFrame({
            "lsoa21cd": ["E01000001", "E01000002"],
            "value": [100, 200],
        })

        with pytest.MonkeyPatch.context() as m:
            m.setattr("src.clean.get_project_root", lambda: tmp_path)

            out = save_processed(df, "test_output")

            assert out.exists()
            assert out.suffix == ".parquet"

            # Read back and verify
            loaded = pl.read_parquet(out)
            assert len(loaded) == 2
            assert loaded.columns == ["lsoa21cd", "value"]

    def test_writes_lazyframe(self, tmp_path: Path):
        """save_processed should handle LazyFrames by collecting them."""
        lf = pl.DataFrame({
            "lsoa21cd": ["E01000001"],
            "score": [42.0],
        }).lazy()

        with pytest.MonkeyPatch.context() as m:
            m.setattr("src.clean.get_project_root", lambda: tmp_path)

            out = save_processed(lf, "test_lazy")
            loaded = pl.read_parquet(out)
            assert len(loaded) == 1
            assert loaded["score"][0] == pytest.approx(42.0)


class TestPricePaidColumns:
    def test_column_count(self):
        """Price Paid CSV should have 16 columns."""
        assert len(PP_COLUMNS) == 16

    def test_key_columns_present(self):
        assert "transaction_id" in PP_COLUMNS
        assert "price" in PP_COLUMNS
        assert "postcode" in PP_COLUMNS
        assert "date_of_transfer" in PP_COLUMNS
        assert "record_status" in PP_COLUMNS
        assert "property_type" in PP_COLUMNS


class TestCleanPricePaidDuckDB:
    """Test that the DuckDB query correctly reads and filters the Price Paid CSV."""

    def _build_col_aliases(self):
        """Build column aliases matching production code's zero-padding logic."""
        n_cols = len(PP_COLUMNS)
        pad_width = len(str(n_cols - 1))
        return ", ".join(
            f"column{i:0{pad_width}d} AS {name}" for i, name in enumerate(PP_COLUMNS)
        )

    def test_record_status_filter_via_duckdb(self, tmp_path: Path):
        """DuckDB query should filter to record_status='A' using column15."""
        # Write a headerless CSV matching the Price Paid format
        csv_path = tmp_path / "pp_test.csv"
        lines = []
        # record_status is column index 15 (the 16th column)
        base = [
            "{TXN-000001}", "250000", "2024-01-15 00:00", "SW1A 1AA",
            "D", "N", "F", "1", "", "TEST ST", "", "LONDON",
            "WESTMINSTER", "GREATER LONDON", "A",
        ]
        # 3 rows with record_status='A'
        for i in range(3):
            row = base.copy()
            row[0] = f"{{TXN-{i:06d}}}"
            row.append("A")
            lines.append(",".join(f'"{v}"' for v in row))
        # 2 rows with record_status='D'
        for i in range(3, 5):
            row = base.copy()
            row[0] = f"{{TXN-{i:06d}}}"
            row.append("D")
            lines.append(",".join(f'"{v}"' for v in row))

        csv_path.write_text("\n".join(lines) + "\n")

        # Run the same DuckDB query that clean_price_paid uses
        con = duckdb.connect()
        col_aliases = self._build_col_aliases()
        con.execute("SET VARIABLE csv_path = ?", [str(csv_path)])
        query = f"""
            SELECT {col_aliases}
            FROM read_csv_auto(getvariable('csv_path'), header=false, all_varchar=true)
            WHERE column15 = 'A'
        """
        result = con.execute(query)
        df = pl.from_arrow(result.fetch_arrow_table())
        con.close()

        assert len(df) == 3
        assert (df["record_status"] == "A").all()
        assert "transaction_id" in df.columns
        assert "price" in df.columns
        assert "postcode" in df.columns

    def test_column_aliases_match_duckdb_naming(self):
        """Column aliases should use zero-padded names matching DuckDB convention."""
        col_aliases = self._build_col_aliases()
        # 16 columns → pad to 2 digits: column00, column01, ..., column15
        assert "column00 AS transaction_id" in col_aliases
        assert "column15 AS record_status" in col_aliases


class TestCleanImd:
    """Test clean_imd by calling it with actual test data files."""

    def test_clean_imd_with_csv(self, tmp_path: Path):
        """clean_imd should process a CSV with IMD-like column names."""
        # Create a test CSV mimicking the normalised IMD column structure
        csv_path = tmp_path / "imd_test.csv"
        df = pl.DataFrame({
            "LSOA code (2011)": ["E01000001", "E01000002", "E01000003"],
            "LSOA name (2011)": ["Area A", "Area B", "Area C"],
            "Index of Multiple Deprivation (IMD) Score": [10.5, 20.3, 30.1],
            "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": [
                100, 200, 300
            ],
            "Income Score (rate)": [0.1, 0.2, 0.3],
            "Employment Score (rate)": [0.05, 0.10, 0.15],
        })
        df.write_csv(csv_path)

        result = clean_imd(csv_path).collect()

        assert len(result) == 3
        assert "lsoa_code" in result.columns
        assert "imd_score" in result.columns
        assert "imd_rank" in result.columns
        assert "income_score" in result.columns
        assert "employment_score" in result.columns
        # Original column "LSOA name" should not appear in output
        assert "lsoa_name_2011" not in result.columns

    def test_clean_imd_column_values(self, tmp_path: Path):
        """clean_imd should preserve data values correctly."""
        csv_path = tmp_path / "imd_values.csv"
        df = pl.DataFrame({
            "LSOA code (2011)": ["E01000001"],
            "Index of Multiple Deprivation (IMD) Score": [42.5],
        })
        df.write_csv(csv_path)

        result = clean_imd(csv_path).collect()

        assert result["imd_score"][0] == pytest.approx(42.5)
        assert result["lsoa_code"][0] == "E01000001"
