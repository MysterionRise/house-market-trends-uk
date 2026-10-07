"""NSPL → staged Parquet (all nations, live and terminated postcodes)."""

from pathlib import Path

import polars as pl

from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.nspl import find_nspl_csv, read_nspl_raw

logger = setup_logging("stage.nspl")


def stage_nspl(raw_path: Path | None = None) -> pl.LazyFrame:
    """Stage the full NSPL (all nations, live and terminated) with stable column names."""
    if raw_path is None:
        raw_path = find_nspl_csv(data_dir("raw") / "nspl")
    logger.info(f"Staging NSPL from {raw_path}")
    return read_nspl_raw(raw_path)
