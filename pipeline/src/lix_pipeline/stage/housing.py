"""Household income (ONS, MSOA), council tax (MHCLG, billing authority) and the
housing stock by council tax band and build period (VOA, LSOA)."""

import fastexcel
import polars as pl

from lix_core.codes import active_nations, in_scope
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.housing")

# Workbook sheet → our column. Each sheet: MSOA code, names, then the estimate
INCOME_SHEETS = {
    "Total annual income": "income_total",
    "Net annual income": "income_net",
    "Net income before housing costs": "income_net_bhc_equivalised",
    "Net income after housing costs": "income_net_ahc_equivalised",
}


def _header_row(reader: fastexcel.ExcelReader, sheet: str, first_col: str) -> int:
    probe = reader.load_sheet_by_name(sheet, header_row=None, n_rows=20).to_polars()
    col = probe[probe.columns[0]].to_list()
    return next(i for i, v in enumerate(col) if v and str(v).startswith(first_col))


def stage_msoa_income() -> pl.LazyFrame:
    """Mean household income per MSOA (£ a year), model-based estimates."""
    reader = fastexcel.read_excel(data_dir("raw") / "msoa_income" / "msoa_income.xlsx")
    out = None
    for sheet, name in INCOME_SHEETS.items():
        header = _header_row(reader, sheet, "MSOA code")
        df = reader.load_sheet_by_name(sheet, header_row=header).to_polars()
        df = df.select(
            pl.col(df.columns[0]).alias("msoa21cd"),
            pl.col(df.columns[6]).cast(pl.Float64, strict=False).alias(name),
        ).filter(in_scope("msoa21cd", "mid"))
        out = df if out is None else out.join(df, on="msoa21cd", how="full", coalesce=True)
    logger.info(f"{out.height:,} MSOAs with income estimates")
    return out.lazy()


BANDS = ["A", "B", "C", "D", "E", "F", "G", "H"]


def stage_council_tax() -> pl.LazyFrame:
    """Council tax per band for each billing authority, all precepts included.

    Table 9 is the bill for two adults in the authority's area (county, police, fire and
    an average parish precept), i.e. what a typical household actually pays.
    """
    reader = fastexcel.read_excel(data_dir("raw") / "council_tax" / "council_tax.ods")
    header = _header_row(reader, "Table_9", "E Code")
    df = reader.load_sheet_by_name("Table_9", header_row=header).to_polars()
    df = df.rename({c: c.strip() for c in df.columns})
    out = df.select(
        pl.col("ONS Code").alias("lad_cd"),
        pl.col("Authority").alias("authority"),
        *[pl.col(f"Band {b}").cast(pl.Float64).alias(f"band_{b.lower()}") for b in BANDS],
    ).filter(in_scope("lad_cd", "upper"))
    wales = data_dir("raw") / "wg_council_tax" / "wg_council_tax.xlsx"
    if "W" in active_nations() and wales.exists():
        out = pl.concat([out, _wg_council_tax(wales)], how="vertical_relaxed")
    logger.info(f"{out.height} billing authorities; Band D median £{out['band_d'].median():,.0f}")
    return out.lazy()


# Council tax bands are fixed multiples of band D (ninths); Wales's band I (21/9) is left out
BAND_RATIOS = {"a": 6, "b": 7, "c": 8, "d": 9, "e": 11, "f": 13, "g": 15, "h": 18}


def _wg_council_tax(path) -> pl.DataFrame:
    """Welsh authorities' average band D (all precepts) from the Welsh Government release,
    the other bands derived from the statutory ratios."""
    reader = fastexcel.read_excel(path)
    header = _header_row(reader, "Table1", "Authority")
    df = reader.load_sheet_by_name("Table1", header_row=header).to_polars()
    band_d = next(c for c in df.columns if c.startswith("Overall average band D"))
    df = df.select(
        pl.col("Authority").str.strip_chars().alias("authority"),
        pl.col(band_d).cast(pl.Float64, strict=False).alias("band_d"),
    ).filter(pl.col("band_d").is_not_null())
    lads = (
        pl.read_parquet(data_dir("staged") / "geo_lsoa.parquet")
        .filter(in_scope("lad_cd", "upper", nations=("W",)))
        .select("lad_cd", pl.col("lad_nm").alias("authority"))
        .unique()
    )
    out = df.join(lads, on="authority", how="inner")
    if out.height != lads.height:
        logger.warning(f"{lads.height - out.height} Welsh authorities missing from council tax")
    return out.select(
        "lad_cd",
        "authority",
        *[(pl.col("band_d") * r / 9).round(2).alias(f"band_{b}") for b, r in BAND_RATIOS.items()],
    )


BUILD_PERIODS = {
    "pre_1919": ["bp_pre_1900", "bp_1900_1918"],
    "1919_1944": ["bp_1919_1929", "bp_1930_1939"],
    "1945_1999": [
        "bp_1945_1954",
        "bp_1955_1964",
        "bp_1965_1972",
        "bp_1973_1982",
        "bp_1983_1992",
        "bp_1993_1999",
    ],
}


def _total(df: pl.DataFrame, cols: list[str]) -> pl.Expr:
    """Row sum of whichever of ``cols`` the file has (0 if none)."""
    present = [c for c in cols if c in df.columns]
    return pl.sum_horizontal(present) if present else pl.lit(0.0)


def stage_voa_ctsop() -> pl.LazyFrame:
    """Dwellings per LSOA by council tax band and by build period.

    Counts are rounded to the nearest 10 and small cells suppressed ("-"), so shares
    are approximate in small LSOAs. Build periods 2000 onwards are summed as new builds.
    """
    path = next((data_dir("raw") / "voa_ctsop").glob("**/CTSOP4_1_*.csv"))
    raw = pl.read_csv(path, infer_schema=False, encoding="utf8-lossy")
    raw = raw.filter((pl.col("geography") == "LSOA") & in_scope("ecode"))
    num = [c for c in raw.columns if c.startswith("bp_") or c == "all_properties"]
    raw = raw.with_columns(pl.col(num).cast(pl.Float64, strict=False))
    new_build = [
        c for c in raw.columns if c.startswith("bp_") and c[3:7].isdigit() and int(c[3:7]) >= 2000
    ]

    totals = raw.filter(pl.col("band") == "All").select(
        pl.col("ecode").alias("lsoa21cd"),
        pl.col("all_properties").alias("dwellings"),
        *[_total(raw, cols).alias(f"built_{name}") for name, cols in BUILD_PERIODS.items()],
        _total(raw, new_build).alias("built_2000_on"),
        pl.col("bp_unkw").alias("built_unknown"),
    )
    bands = (
        raw.filter(pl.col("band").is_in(BANDS))
        .select(pl.col("ecode").alias("lsoa21cd"), "band", "all_properties")
        .pivot(on="band", index="lsoa21cd", values="all_properties")
        .rename({b: f"band_{b.lower()}" for b in BANDS}, strict=False)
    )
    out = totals.join(bands, on="lsoa21cd", how="left").sort("lsoa21cd")
    logger.info(f"{out.height:,} LSOAs, {out['dwellings'].sum():,.0f} dwellings")
    return out.lazy()
