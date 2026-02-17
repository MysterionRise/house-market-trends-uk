"""Tests for the geocode module."""

import polars as pl

from src.geocode import load_nspl, log_match_rate, postcode_to_lsoa


class TestLoadNspl:
    def test_loads_live_postcodes_only(self, nspl_csv):
        lf = load_nspl(nspl_csv)
        df = lf.collect()

        # E1 6AN has doterm set, should be filtered out
        assert len(df) == 5
        assert "E16AN" not in df["postcode_norm"].to_list()

    def test_normalises_postcodes(self, nspl_csv):
        lf = load_nspl(nspl_csv)
        df = lf.collect()

        # All postcodes should be uppercase, no spaces
        norms = df["postcode_norm"].to_list()
        assert "SW1A1AA" in norms
        assert "EC1A1BB" in norms

    def test_has_expected_columns(self, nspl_csv):
        lf = load_nspl(nspl_csv)
        df = lf.collect()

        assert set(df.columns) == {"postcode", "postcode_norm", "lsoa21cd", "lat", "long"}

    def test_returns_lazyframe_without_collecting(self, nspl_csv):
        """load_nspl should return a LazyFrame, not eagerly collect."""
        lf = load_nspl(nspl_csv)
        assert isinstance(lf, pl.LazyFrame)


class TestPostcodeToLsoa:
    def test_joins_correctly(self, nspl_csv):
        nspl = load_nspl(nspl_csv)

        input_df = pl.DataFrame({
            "postcode": ["SW1A 1AA", "EC1A 1BB"],
            "value": [100, 200],
        }).lazy()

        result = postcode_to_lsoa(input_df, nspl=nspl).collect()
        assert "lsoa21cd" in result.columns
        assert result["lsoa21cd"][0] == "E01000001"
        assert result["lsoa21cd"][1] == "E01000002"

    def test_normalisation_variants(self, nspl_csv):
        """Various postcode formats should all match."""
        nspl = load_nspl(nspl_csv)

        variants = pl.DataFrame({
            "postcode": ["SW1A 1AA", "sw1a1aa", "  SW1A  1AA ", "Sw1a 1Aa"],
        }).lazy()

        result = postcode_to_lsoa(variants, nspl=nspl).collect()

        # All should match E01000001
        for lsoa in result["lsoa21cd"].to_list():
            assert lsoa == "E01000001"

    def test_unmatched_postcodes_dont_crash(self, nspl_csv):
        """Unmatched postcodes should return null, not error."""
        nspl = load_nspl(nspl_csv)

        input_df = pl.DataFrame({
            "postcode": ["ZZ99 9ZZ", "SW1A 1AA"],
        }).lazy()

        result = postcode_to_lsoa(input_df, nspl=nspl).collect()
        assert result["lsoa21cd"][0] is None
        assert result["lsoa21cd"][1] == "E01000001"

    def test_preserves_original_columns(self, nspl_csv):
        nspl = load_nspl(nspl_csv)

        input_df = pl.DataFrame({
            "postcode": ["SW1A 1AA"],
            "price": [500000],
            "type": ["D"],
        }).lazy()

        result = postcode_to_lsoa(input_df, nspl=nspl).collect()
        assert "price" in result.columns
        assert "type" in result.columns
        assert result["price"][0] == 500000

    def test_returns_lazyframe(self, nspl_csv):
        """postcode_to_lsoa should return a LazyFrame without eagerly collecting."""
        nspl = load_nspl(nspl_csv)

        input_df = pl.DataFrame({
            "postcode": ["SW1A 1AA"],
        }).lazy()

        result = postcode_to_lsoa(input_df, nspl=nspl)
        assert isinstance(result, pl.LazyFrame)


class TestLogMatchRate:
    def test_logs_match_rate(self, nspl_csv, caplog):
        """log_match_rate should log the correct match/unmatched stats."""
        import logging

        nspl = load_nspl(nspl_csv)
        input_df = pl.DataFrame({
            "postcode": ["SW1A 1AA", "ZZ99 9ZZ"],
        }).lazy()

        result = postcode_to_lsoa(input_df, nspl=nspl).collect()

        with caplog.at_level(logging.INFO, logger="geocode"):
            log_match_rate(result)

        assert "1/2 matched" in caplog.text or "1/2" in caplog.text

    def test_handles_empty_dataframe(self):
        """log_match_rate should not crash on empty DataFrames."""
        df = pl.DataFrame({"lsoa21cd": pl.Series([], dtype=pl.Utf8)})
        log_match_rate(df)  # Should not raise
