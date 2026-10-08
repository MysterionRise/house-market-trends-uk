"""One deprivation table for every nation: IoD 2025 in England, WIMD 2025 in Wales.

The indices are built the same way (income and employment domains are rates of people
affected; the others are weighted combinations) but by different governments on
different inputs, so values are only comparable within a nation: the indicators that
read this table are benchmarked ``nation``. Columns are harmonised by concept:

    imd_score, imd_rank, imd_decile          overall index (rank and decile within the nation)
    income_score, employment_score           share of people deprived (both nations)
    health_score, education_score            domain scores
    crime_score                              IoD crime domain / WIMD community safety
    housing_score                            IoD indoors sub-domain / WIMD housing domain
    outdoors_score                           IoD outdoors sub-domain / WIMD physical environment
"""

import fastexcel
import polars as pl

from lix_core.codes import active_nations
from lix_core.log import setup_logging
from lix_core.paths import data_dir, raw_file

logger = setup_logging("stage.deprivation")

COLUMNS = [
    "lsoa21cd", "imd_score", "imd_rank", "imd_decile", "income_score", "employment_score",
    "health_score", "education_score", "crime_score", "housing_score", "outdoors_score",
]  # fmt: skip

# WIMD sheet headers (stripped) → harmonised names
WIMD_SCORES = {
    "WIMD 2025": "imd_score", "Income": "income_score", "Employment": "employment_score",
    "Health": "health_score", "Education": "education_score", "Housing": "housing_score",
    "Community Safety": "crime_score", "Physical Environment": "outdoors_score",
}  # fmt: skip


def _sheet(path, sheet: str, first_col: str) -> pl.DataFrame:
    reader = fastexcel.read_excel(path)
    probe = reader.load_sheet_by_name(sheet, header_row=None, n_rows=12).to_polars()
    first = probe[probe.columns[0]].to_list()
    header = next(i for i, v in enumerate(first) if str(v).startswith(first_col))
    df = reader.load_sheet_by_name(sheet, header_row=header).to_polars()
    return df.rename({c: c.strip() for c in df.columns})


def _england() -> pl.DataFrame:
    iod = pl.read_parquet(data_dir("staged") / "iod_2025.parquet")
    return iod.select(
        "lsoa21cd",
        "imd_score",
        "imd_rank",
        "imd_decile",
        "income_score",
        "employment_score",
        "health_score",
        "education_score",
        "crime_score",
        pl.col("sub_indoors_score").alias("housing_score"),
        pl.col("sub_outdoors_score").alias("outdoors_score"),
    )


def _wales() -> pl.DataFrame:
    scores = _sheet(raw_file("wimd_2025_scores", "ods"), "Data", "LSOA code")
    missing = [c for c in WIMD_SCORES if c not in scores.columns]
    if missing:
        raise ValueError(f"WIMD scores sheet lacks columns {missing}; has {scores.columns}")
    out = scores.select(
        pl.col("LSOA code").alias("lsoa21cd"),
        *[
            pl.col(src).cast(pl.Float64, strict=False).alias(dst)
            for src, dst in WIMD_SCORES.items()
        ],
    )
    ranks = _sheet(raw_file("wimd_2025_ranks", "ods"), "WIMD_2025_ranks", "LSOA code")
    rank_col = next(c for c in ranks.columns if c.startswith("WIMD 2025"))
    ranks = ranks.select(
        pl.col("LSOA code").alias("lsoa21cd"),
        pl.col(rank_col).cast(pl.Int32, strict=False).alias("imd_rank"),
    )
    out = out.join(ranks, on="lsoa21cd", how="left").with_columns(
        # Decile within Wales, 1 = most deprived, as the IoD's is within England
        ((pl.col("imd_rank") - 1) * 10 // pl.col("imd_rank").count() + 1)
        .cast(pl.Int32)
        .alias("imd_decile")
    )
    return out.select(COLUMNS)


def stage_deprivation() -> pl.LazyFrame:
    frames = []
    if "E" in active_nations():
        frames.append(_england())
    if "W" in active_nations():
        frames.append(_wales())
    df = pl.concat(frames, how="vertical_relaxed").sort("lsoa21cd")
    logger.info(f"Deprivation: {df.height:,} LSOAs across {active_nations()}")
    return df.lazy()
