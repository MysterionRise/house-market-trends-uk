"""Stagers turn raw downloads into tidy, typed Parquet in data/staged/{slug}.parquet."""

from collections.abc import Callable
from pathlib import Path

import polars as pl

from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage")


def save_staged(df: pl.LazyFrame | pl.DataFrame, slug: str) -> Path:
    """Write a DataFrame to data/staged/{slug}.parquet with Snappy compression."""
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    out_path = data_dir("staged") / f"{slug}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df.write_parquet(out_path, compression="snappy")
    logger.info(f"Saved {len(df):,} rows to {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")

    return out_path


def stagers() -> dict[str, Callable[[], pl.LazyFrame]]:
    """Slug → stager, in run order (price_paid geocodes against the staged NSPL)."""
    from lix_pipeline.stage.iod import stage_iod
    from lix_pipeline.stage.nspl import stage_nspl
    from lix_pipeline.stage.price_paid import stage_price_paid

    return {
        "nspl": stage_nspl,
        "price_paid": stage_price_paid,
        "iod_2025": stage_iod,
    }
