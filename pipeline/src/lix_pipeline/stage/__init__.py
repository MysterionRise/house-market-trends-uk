"""Stagers turn raw downloads into tidy, typed Parquet in data/staged/{slug}.parquet."""

from collections.abc import Callable
from pathlib import Path

import polars as pl

from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage")

# Raw datasets each stager reads, when that isn't just its own slug
STAGE_INPUTS: dict[str, list[str]] = {
    "price_paid": ["price_paid", "nspl"],
    "geo_lsoa": [
        "oa_lookup",
        "msoa_names",
        "nspl",
        "lad_boundaries",
        "ruc_2021",
        "lsoa_centroids",
        "iod_2025",
        "lsoa_boundaries",
    ],
    "places": ["os_open_names", "lsoa_boundaries"],
    "defra_pcm_no2": ["defra_pcm_no2", "nspl"],
    "defra_pcm_pm25": ["defra_pcm_pm25", "nspl"],
    "defra_pcm_pm10": ["defra_pcm_pm10", "nspl"],
    "ods_gp": ["ods_gp", "nspl"],
    "gias": ["gias", "lsoa_boundaries"],
    "fsa_fhrs": ["fsa_fhrs", "nspl", "lsoa_boundaries"],
    "osm_pois": ["osm_england"],
}


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
    """Slug → stager, in run order (later stagers read earlier staged outputs)."""
    from functools import partial

    from lix_core.config import load_registry
    from lix_pipeline.stage import geo, health, schools
    from lix_pipeline.stage.census import stage_census_table
    from lix_pipeline.stage.fsa import stage_fsa
    from lix_pipeline.stage.iod import stage_iod
    from lix_pipeline.stage.nspl import stage_nspl
    from lix_pipeline.stage.osm import stage_osm
    from lix_pipeline.stage.pcm import stage_pcm
    from lix_pipeline.stage.police import stage_police
    from lix_pipeline.stage.price_paid import stage_price_paid
    from lix_pipeline.stage.transport import stage_dft_connectivity

    registry = load_registry()
    census = {s: partial(stage_census_table, s) for s in registry if s.startswith("census_")}
    pcm = {s: partial(stage_pcm, s) for s in registry if s.startswith("defra_pcm_")}

    return {
        "nspl": stage_nspl,
        "iod_2025": stage_iod,
        "oa_lookup": geo.stage_oa_lookup,
        "lsoa11_lsoa21": geo.stage_lsoa11_lsoa21,
        "geo_lsoa": geo.stage_geo_lsoa,  # needs staged nspl and iod_2025
        "places": geo.stage_places,
        "price_paid": stage_price_paid,
        **census,
        "police_crime": stage_police,
        **pcm,  # needs staged nspl
        "ods_gp": health.stage_ods_gp,
        "gp_registrations": health.stage_gp_registrations,
        "gp_workforce": health.stage_gp_workforce,
        "gias": schools.stage_gias,
        "ofsted_schools": schools.stage_ofsted_schools,
        "dft_connectivity": stage_dft_connectivity,
        "fsa_fhrs": stage_fsa,
        "osm_pois": stage_osm,
    }
