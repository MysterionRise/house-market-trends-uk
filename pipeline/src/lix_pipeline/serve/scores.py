"""Turn the indicator table into the files the API and browser use.

    data/serve/lsoa_features.parquet  every LSOA: geography, raw__/n__/q__ per indicator,
                                      theme__ percentiles, overall and band (default preset)
    data/serve/scores.parquet         compact copy for the browser: n__ percentiles as
                                      uint16 (×100; 65535 = missing) + a quality bitmask
    data/serve/manifest.json          indicators, themes, presets, source versions,
                                      attribution and file checksums

The browser recomputes themes and the overall score from ``scores.parquet`` with
the same maths as ``lix_core.scoring`` whenever weights change.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from lix_core.config import load_indicators, load_registry, load_weights
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_core.scoring import band, normalise, score_lsoas
from lix_pipeline.fetch.lock import read_lock

logger = setup_logging("serve.scores")

MISSING_U16 = 65535
GEO_COLUMNS = [
    "lsoa21cd", "lsoa21nm", "msoa21cd", "msoa_name", "lad_cd", "lad_nm", "rgn_cd", "rgn_nm",
    "pfa_nm", "ruc21cd", "ruc21nm", "urban", "population", "area_km2", "pwc_lon", "pwc_lat",
    "pwc_x", "pwc_y", "bbox_w", "bbox_s", "bbox_e", "bbox_n",
]  # fmt: skip


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_features() -> pl.DataFrame:
    """Wide per-LSOA table with raw values, percentiles, quality flags and default scores."""
    catalogue = load_indicators()
    weights = load_weights()
    preset = weights.presets[weights.default_preset]
    long = pl.read_parquet(data_dir("indicators") / "long.parquet")
    geo = pl.read_parquet(data_dir("staged") / "geo_lsoa.parquet").select(GEO_COLUMNS)

    raw = long.pivot(on="indicator_id", index="lsoa21cd", values="value")
    quality = long.pivot(on="indicator_id", index="lsoa21cd", values="quality")
    df = geo.join(raw.rename(lambda c: c if c == "lsoa21cd" else f"raw__{c}"), on="lsoa21cd")
    df = df.join(quality.rename(lambda c: c if c == "lsoa21cd" else f"q__{c}"), on="lsoa21cd")

    df = df.with_columns(
        normalise(
            pl.col(f"raw__{i.id}"),
            i.direction,
            method=i.normalise,
            log1p=i.log1p,
            good=i.good,
            bad=i.bad,
            scale_max=i.scale_max,
        ).alias(f"n__{i.id}")
        for i in catalogue.indicators
    )
    scored = [(i.id, i.theme, i.weight) for i in catalogue.scored()]
    scores = score_lsoas(df, scored, preset.themes, preset.indicators)
    df = pl.concat([df, scores], how="horizontal").with_columns(
        band(pl.col("overall_pct")).alias("band")
    )
    return df.sort("lsoa21cd")


def compact_scores(features: pl.DataFrame) -> pl.DataFrame:
    """Browser copy: uint16 percentiles for scored indicators plus a quality bitmask."""
    catalogue = load_indicators()
    scored = [i.id for i in catalogue.scored()]
    # 32 bits keeps the mask a plain number in JavaScript (64-bit would be a BigInt)
    if len(scored) > 32:
        raise ValueError("Quality bitmask holds at most 32 scored indicators")
    flags = pl.sum_horizontal(
        pl.when(pl.col(f"q__{iid}") != "ok").then(pl.lit(1 << bit, pl.UInt32)).otherwise(0)
        for bit, iid in enumerate(scored)
    )
    return features.select(
        "lsoa21cd",
        # For colouring the zoomed-out MSOA and local authority layers in the browser
        "msoa21cd",
        "lad_cd",
        "ruc21cd",
        "urban",
        pl.col("population").cast(pl.UInt32),
        *[
            (pl.col(f"n__{iid}") * 100).round().fill_null(MISSING_U16).cast(pl.UInt16).alias(iid)
            for iid in scored
        ],
        flags.cast(pl.UInt32).alias("quality_flags"),
    )


def manifest(files: dict[str, Path]) -> dict:
    catalogue = load_indicators()
    weights = load_weights()
    registry = load_registry()
    lock = read_lock()
    used = sorted(
        {s for i in catalogue.indicators for s in i.sources} | {"nspl", "lsoa_boundaries"}
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lsoas": "England LSOA 2021",
        "scored_indicators": [i.id for i in catalogue.scored()],
        "indicators": [i.model_dump() for i in catalogue.indicators],
        "themes": {k: v.model_dump() for k, v in catalogue.themes.items()},
        "default_preset": weights.default_preset,
        "presets": {k: v.model_dump() for k, v in weights.presets.items()},
        "sources": {
            slug: {
                "title": registry[slug].title,
                "licence": registry[slug].licence,
                "attribution": registry[slug].attribution,
                "version": lock.get(slug, {}).get("resolved", {}).get("version"),
                "fetched_at": lock.get(slug, {}).get("fetched", {}).get("fetched_at"),
            }
            for slug in used
        },
        "files": {
            name: {"sha256": _sha256(p), "bytes": p.stat().st_size} for name, p in files.items()
        },
        "encoding": {
            "scores.parquet": "percentiles × 100 as uint16; 65535 = missing; quality_flags bit i "
            "set when scored_indicators[i] is imputed, low-sample, broadcast or missing"
        },
    }


def build_serve() -> dict[str, Path]:
    out = data_dir("serve")
    out.mkdir(parents=True, exist_ok=True)
    features = build_features()
    files = {
        "lsoa_features.parquet": out / "lsoa_features.parquet",
        "scores.parquet": out / "scores.parquet",
    }
    features.write_parquet(files["lsoa_features.parquet"])
    # Snappy: the browser's parquet reader (hyparquet) decodes it without plugins
    compact_scores(features).write_parquet(files["scores.parquet"], compression="snappy")
    from lix_pipeline.serve.lookups import build_lookups

    files.update(build_lookups(features))
    (out / "manifest.json").write_text(json.dumps(manifest(files), indent=2, default=str))
    files["manifest.json"] = out / "manifest.json"
    for name, path in files.items():
        logger.info(f"{name}: {path.stat().st_size / 1e6:.1f} MB")
    return files
