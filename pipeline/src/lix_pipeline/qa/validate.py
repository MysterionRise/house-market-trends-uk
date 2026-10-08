"""Checks on staged outputs, run with ``lix validate <target>`` on a full build.

Each validator returns a list of human-readable problems (empty means OK).
"""

import hashlib
import json
from pathlib import Path

import polars as pl

from lix_core.codes import ENGLAND_LSOA21, active_nations, area_code_regex, in_scope
from lix_core.config import load_indicators, load_nations
from lix_core.paths import data_dir

# England LSOAs (December 2021); validate_serve still assumes England until the serve
# format carries nations (v0.3.0 step 6)
ENGLAND_LSOA_COUNT = 33_755


def validate_geo() -> list[str]:
    """The backbone has every area of every active nation, once, with its columns filled."""
    problems = []
    staged = data_dir("staged")
    geo = pl.read_parquet(staged / "geo_lsoa.parquet")
    nations = active_nations()
    cfg = load_nations().nations

    expected = sum(cfg[n].levels["low"].count or 0 for n in nations)
    if geo.height != expected:
        problems.append(f"geo_lsoa has {geo.height:,} rows, expected {expected:,}")
    if geo["lsoa21cd"].n_unique() != geo.height:
        problems.append("geo_lsoa has duplicate lsoa21cd")
    if not geo["lsoa21cd"].str.contains(area_code_regex()).all():
        problems.append(f"geo_lsoa has codes outside the active nations {list(nations)}")

    required = [
        "lsoa21nm",
        "msoa21cd",
        "msoa21nm",
        "msoa_name",
        "lad_cd",
        "lad_nm",
        "rgn_cd",
        "rgn_nm",
        "nation",
        "ctry_cd",
        "area_type",
        "ruc21cd",
        "ruc_class",
        "urban",
        "pwc_x",
        "pwc_y",
        "pwc_lat",
        "pwc_lon",
        "population",
        "area_km2",
        "bbox_w",
        "bbox_s",
        "bbox_e",
        "bbox_n",
    ]
    missing_columns = [c for c in required if c not in geo.columns]
    problems += [f"geo_lsoa is missing column {c}" for c in missing_columns]
    for col in required:
        if col in geo.columns and (n := geo[col].null_count()) > 0:
            problems.append(f"geo_lsoa.{col} has {n:,} nulls")
    if missing_columns:
        return problems  # the per-nation checks below assume the columns exist

    for code in nations:
        spec = cfg[code]
        rows = geo.filter(in_scope("lsoa21cd", nations=(code,)))
        if (count := spec.levels["low"].count) and rows.height != count:
            problems.append(f"{spec.name}: {rows.height:,} LSOAs, expected {count:,}")
        if (count := spec.levels["mid"].count) and rows["msoa21cd"].n_unique() != count:
            found = rows["msoa21cd"].n_unique()
            problems.append(f"{spec.name}: {found:,} MSOAs, expected {count:,}")
        if not (rows["nation"] == code).all() or not (rows["ctry_cd"] == spec.ctry_cd).all():
            problems.append(f"{spec.name}: nation/ctry_cd columns disagree with the codes")
        low, high = spec.population
        pop = rows["population"].sum()
        if not low < pop < high:
            problems.append(f"{spec.name} population {pop:,} is outside {low:,}–{high:,}")

    # Centroids must sit inside their own LSOA's bbox
    outside = geo.filter(
        (pl.col("pwc_lon") < pl.col("bbox_w"))
        | (pl.col("pwc_lon") > pl.col("bbox_e"))
        | (pl.col("pwc_lat") < pl.col("bbox_s"))
        | (pl.col("pwc_lat") > pl.col("bbox_n"))
    )
    if outside.height:
        problems.append(f"{outside.height} centroids fall outside their LSOA's bounding box")

    nspl = pl.scan_parquet(staged / "nspl.parquet")
    nspl_lsoas = set(
        nspl.filter(pl.col("live") & in_scope("lsoa21cd"))
        .select("lsoa21cd")
        .unique()
        .collect()["lsoa21cd"]
    )
    missing = nspl_lsoas - set(geo["lsoa21cd"])
    if missing:
        problems.append(
            f"{len(missing)} NSPL LSOAs missing from geo_lsoa, e.g. {sorted(missing)[:3]}"
        )
    return problems


# Scored indicators must have a value for at least this share of LSOAs
MIN_SCORED_COVERAGE = 0.99
# ...except where the gaps are understood: GP ratings need at least half an LSOA's
# patients at a rated practice (new and unrated practices leave about 1% short)
COVERAGE_EXCEPTIONS = {"gp_quality": 0.98}
MISSING_U16 = 65535
SERVE_FILES = [
    "lsoa_features.parquet",
    "scores.parquet",
    "postcodes.parquet",
    "places.parquet",
    "areas.parquet",
    "pois.parquet",
    "manifest.json",
    "tiles/lsoa.pmtiles",
    "tiles/msoa.pmtiles",
    "tiles/lad.pmtiles",
]


def validate_serve(serve_dir: Path | None = None) -> list[str]:
    """The files the API and browser read: complete, consistent and as the manifest says.

    Works on a full build (33,755 LSOAs) and on a demo cut (``demo: true`` in the
    manifest, with its own ``lsoa_count``).
    """
    serve = serve_dir or data_dir("serve")
    missing = [f for f in SERVE_FILES if not (serve / f).is_file()]
    if missing:
        return [f"missing {', '.join(missing)} in {serve}"]
    problems = []
    manifest = json.loads((serve / "manifest.json").read_text())
    catalogue = load_indicators()
    scored = [i.id for i in catalogue.scored()]
    expected = manifest.get("lsoa_count") if manifest.get("demo") else ENGLAND_LSOA_COUNT

    features = pl.read_parquet(serve / "lsoa_features.parquet")
    codes = features["lsoa21cd"]
    if features.height != expected:
        problems.append(f"lsoa_features has {features.height:,} rows, expected {expected:,}")
    if codes.n_unique() != features.height:
        problems.append("lsoa_features has duplicate lsoa21cd")
    if not codes.str.contains(ENGLAND_LSOA21).all():
        problems.append("lsoa_features has non-England LSOA codes")

    for iid in scored:
        col = f"n__{iid}"
        if col not in features.columns:
            problems.append(f"scored indicator {iid} is missing from lsoa_features")
            continue
        coverage = features[col].is_not_null().mean()
        minimum = COVERAGE_EXCEPTIONS.get(iid, MIN_SCORED_COVERAGE)
        if coverage < minimum:
            problems.append(f"{iid} covers {coverage:.1%} of LSOAs (< {minimum:.0%})")
    overall = features["overall"]
    if overall.null_count() or not overall.is_between(0, 100).all():
        problems.append("overall score has nulls or values outside 0–100")

    scores = pl.read_parquet(serve / "scores.parquet")
    if set(scores["lsoa21cd"]) != set(codes):
        problems.append("scores.parquet and lsoa_features have different LSOAs")
    if manifest.get("scored_indicators") != scored:
        problems.append("manifest scored_indicators differ from config/indicators.yaml")
    if set(manifest.get("themes", {})) != set(catalogue.themes):
        problems.append("manifest themes differ from config/indicators.yaml")
    absent = [i for i in scored if i not in scores.columns]
    if absent:
        problems.append(f"scores.parquet lacks scored indicators {absent}")
    for iid in scored:
        if iid in scores.columns:
            bad = scores.filter((pl.col(iid) > 10_000) & (pl.col(iid) != MISSING_U16)).height
            if bad:
                problems.append(f"scores.parquet {iid} has {bad} values above 100.00")

    for name, meta in manifest.get("files", {}).items():
        path = serve / name
        if not path.is_file():
            problems.append(f"manifest lists {name}, which doesn't exist")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != meta.get("sha256"):
            problems.append(f"{name} doesn't match its manifest checksum")

    for tiles in ("lsoa", "msoa", "lad"):
        path = serve / "tiles" / f"{tiles}.pmtiles"
        if path.read_bytes()[:7] != b"PMTiles":
            problems.append(f"tiles/{tiles}.pmtiles isn't a PMTiles file")
    return problems


def validate_places() -> list[str]:
    from lix_pipeline.qa.places import anchor_problems

    return anchor_problems()


def validate_config() -> list[str]:
    """Every theme keeps enough scored weight in each active nation (see coverage_problems)."""
    from lix_core.config import coverage_problems, load_registry

    return coverage_problems(load_indicators(), load_registry(), active_nations())


VALIDATORS = {
    "config": validate_config,
    "geo": validate_geo,
    "serve": validate_serve,
    "places": validate_places,
}
