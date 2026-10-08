"""Backbone population: ONS mid-year estimates for every LSOA in England and Wales.

The workbook has one ``Mid-YYYY LSOA 2021`` sheet per year (broad age groups by sex)
and a median-age sheet; the latest year is kept. These are the denominators of every
per-head indicator, in both nations alike (IoD 2025's own figures cover England only).
"""

import re

import fastexcel
import polars as pl

from lix_core.codes import in_scope
from lix_core.log import setup_logging
from lix_core.paths import raw_file

logger = setup_logging("stage.population")

SHEET = re.compile(r"Mid-(\d{4}) LSOA 2021")


def latest_sheet(names: list[str]) -> tuple[str, int]:
    """The ``Mid-YYYY LSOA 2021`` sheet with the latest year, and that year."""
    found = [(int(m.group(1)), n) for n in names if (m := SHEET.fullmatch(n))]
    if not found:
        raise ValueError(f"No 'Mid-YYYY LSOA 2021' sheet among {names}")
    year, name = max(found)
    return name, year


def _header_row(reader: fastexcel.ExcelReader, sheet: str) -> int:
    probe = reader.load_sheet_by_name(sheet, header_row=None, n_rows=20).to_polars()
    first = probe[probe.columns[0]].to_list()
    return next(i for i, v in enumerate(first) if v and str(v).startswith("LAD"))


def tidy_population(df: pl.DataFrame, year: int) -> pl.DataFrame:
    """A year's sheet (header row applied) → one row per LSOA with the counts we keep."""
    code = next(c for c in df.columns if c.startswith("LSOA 2021 Code"))

    def count(col: str) -> pl.Expr:
        return pl.col(col).cast(pl.Float64, strict=False).round().cast(pl.Int32)

    return df.select(
        pl.col(code).str.strip_chars().alias("lsoa21cd"),
        count("Total").alias("population"),
        (count("F0 to 15") + count("M0 to 15")).alias("pop_children_0_15"),
        (count("F65 and over") + count("M65 and over")).alias("pop_65_plus"),
        pl.lit(year, dtype=pl.Int16).alias("pop_year"),
    ).filter(pl.col("lsoa21cd").is_not_null())


def tidy_median_age(df: pl.DataFrame, year: int) -> pl.DataFrame:
    """The median-age sheet → ``median_age`` for ``year`` per LSOA."""
    code = next(c for c in df.columns if c.startswith("LSOA 2021 Code"))
    col = next(c for c in df.columns if c.strip() == f"Median age mid-{year}")
    return df.select(
        pl.col(code).str.strip_chars().alias("lsoa21cd"),
        pl.col(col).cast(pl.Float32, strict=False).alias("median_age"),
    )


def stage_population() -> pl.LazyFrame:
    reader = fastexcel.read_excel(raw_file("pop_lsoa_mye", "xlsx"))
    sheet, year = latest_sheet(reader.sheet_names)
    frame = reader.load_sheet_by_name(sheet, header_row=_header_row(reader, sheet)).to_polars()
    out = tidy_population(frame, year)
    median = next((n for n in reader.sheet_names if n.startswith("Median age")), None)
    if median:
        frame = reader.load_sheet_by_name(median, header_row=_header_row(reader, median))
        out = out.join(tidy_median_age(frame.to_polars(), year), on="lsoa21cd", how="left")
    out = out.filter(in_scope("lsoa21cd")).sort("lsoa21cd")
    logger.info(f"Population mid-{year}: {out.height:,} LSOAs, {out['population'].sum():,} people")
    return out.lazy()
