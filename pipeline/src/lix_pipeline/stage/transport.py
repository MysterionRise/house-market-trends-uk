"""DfT Transport Connectivity Metric → 0–100 scores per LSOA.

The LSOA sheet has two title rows above the header ("LSOA21CD", "Employment
(walking)", ..., "Overall"). Scores are relative within England and Wales, not
travel times; DfT advises comparing places of the same urban/rural type.
"""

import re

import fastexcel
import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.transport")


def tcm_column(label: str) -> str:
    """'Employment (walking)' → 'tcm_employment_walking'; 'Overall' → 'tcm_overall'."""
    name = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return f"tcm_{name}"


def stage_dft_connectivity() -> pl.LazyFrame:
    reader = fastexcel.read_excel(data_dir("raw") / "dft_connectivity" / "dft_connectivity.ods")
    sheet = reader.load_sheet_by_name("LSOA", header_row=2).to_polars()
    code_col = next(c for c in sheet.columns if c.upper().startswith("LSOA"))
    df = (
        sheet.rename(
            {code_col: "lsoa21cd", **{c: tcm_column(c) for c in sheet.columns if c != code_col}}
        )
        .filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .with_columns(pl.exclude("lsoa21cd").cast(pl.Float64, strict=False))
    )
    logger.info(f"{df.height:,} LSOAs, {df.width - 1} connectivity scores")
    return df.lazy()
