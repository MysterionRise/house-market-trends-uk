# ruff: noqa: E501 (fixture tables read best unwrapped)
"""A tiny synthetic data/serve/ directory for API tests (no real data needed).

Six LSOAs in two MSOAs: four in Leeds, two in Brighton. Indicator values follow the
real catalogue in config/, so every service sees the shapes it sees in production.
"""

import json
import os

# The assistant reads LIX_MODEL when lix_api.agent is imported: use the scripted model
os.environ["LIX_MODEL"] = "test"
os.environ.setdefault("LIX_SERVE_DATA", "0")

import polars as pl  # noqa: E402
import pytest  # noqa: E402
from pyproj import Transformer  # noqa: E402

from lix_api.store import Store, set_store  # noqa: E402
from lix_core.config import load_indicators, load_weights  # noqa: E402
from lix_core.scoring import band, normalise, score_lsoas  # noqa: E402

TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)

LSOAS = [
    # code, lsoa name, msoa, msoa name, lad, lad name, region, lat, lon, urban, price
    ("E01000001", "Leeds 044A", "E02000001", "Headingley", "E08000035", "Leeds", "E12000003", 53.8196, -1.5766, True, 260_000),
    ("E01000002", "Leeds 044B", "E02000001", "Headingley", "E08000035", "Leeds", "E12000003", 53.8230, -1.5800, True, 340_000),
    ("E01000003", "Leeds 034A", "E02000002", "Chapel Allerton", "E08000035", "Leeds", "E12000003", 53.8290, -1.5390, True, 380_000),
    ("E01000004", "Leeds 034B", "E02000002", "Chapel Allerton", "E08000035", "Leeds", "E12000003", 53.8320, -1.5350, False, 200_000),
    ("E01000005", "Brighton and Hove 010A", "E02000003", "Hanover", "E06000043", "Brighton and Hove", "E12000008", 50.8290, -0.1260, True, 450_000),
    ("E01000006", "Brighton and Hove 010B", "E02000003", "Hanover", "E06000043", "Brighton and Hove", "E12000008", 50.8310, -0.1230, True, 520_000),
]  # fmt: skip


def _raw_value(ind_id: str, i: int) -> float:
    """Deterministic, varied raw values; E01000003 is the safest and E01000006 the least."""
    if ind_id.startswith("crime_"):
        return [40.0, 25.0, 5.0, 12.0, 30.0, 60.0][i]
    if ind_id == "house_price":
        return float(LSOAS[i][10])
    if ind_id in ("no2",):
        return [18.0, 16.0, 12.0, 9.0, 14.0, 15.0][i]
    if ind_id.endswith("_distance"):
        return [300.0, 450.0, 800.0, 2500.0, 350.0, 400.0][i]
    return float((i * 7 + len(ind_id)) % 10) / 10 + 0.05


def build_serve_dir(path) -> None:
    catalogue, weights = load_indicators(), load_weights()
    rows = []
    for i, (code, name, msoa, msoa_nm, lad, lad_nm, rgn, lat, lon, urban, _) in enumerate(LSOAS):
        x, y = TO_BNG.transform(lon, lat)
        row = {
            "lsoa21cd": code, "lsoa21nm": name, "msoa21cd": msoa, "msoa_name": msoa_nm,
            "lad_cd": lad, "lad_nm": lad_nm, "rgn_cd": rgn,
            "rgn_nm": "Yorkshire and The Humber" if rgn == "E12000003" else "South East",
            "pfa_nm": "x", "ruc21cd": "UN1" if urban else "RSN1",
            "ruc21nm": "Urban" if urban else "Smaller rural", "urban": urban,
            "population": 1500 + 100 * i, "area_km2": 0.5, "pwc_lon": lon, "pwc_lat": lat,
            "pwc_x": x, "pwc_y": y, "bbox_w": lon - 0.01, "bbox_s": lat - 0.005,
            "bbox_e": lon + 0.01, "bbox_n": lat + 0.005,
        }  # fmt: skip
        for ind in catalogue.indicators:
            row[f"raw__{ind.id}"] = _raw_value(ind.id, i)
            imputed = ind.id.startswith("crime_") and code == "E01000004"
            row[f"q__{ind.id}"] = "imputed" if imputed else "ok"
        rows.append(row)
    df = pl.DataFrame(rows)
    df = df.with_columns(
        normalise(pl.col(f"raw__{i.id}"), i.direction, method=i.normalise, log1p=i.log1p,
                  good=i.good, bad=i.bad, scale_max=i.scale_max).alias(f"n__{i.id}")
        for i in catalogue.indicators
    )  # fmt: skip
    preset = weights.presets[weights.default_preset]
    scores = score_lsoas(df, [(i.id, i.theme, i.weight) for i in catalogue.scored()],
                         preset.themes, preset.indicators)  # fmt: skip
    df = pl.concat([df, scores], how="horizontal").with_columns(
        band(pl.col("overall_pct")).alias("band")
    )
    # Percentile ranges over plausible weightings, as the pipeline writes them
    from lix_pipeline.serve.scores import uncertainty_columns

    df = df.with_columns(
        uncertainty_columns(df, [(i.id, i.theme, i.weight) for i in catalogue.scored()], weights)
    )
    df.write_parquet(path / "lsoa_features.parquet")

    manifest = {
        "generated_at": "2026-10-07T00:00:00+00:00",
        "scored_indicators": [i.id for i in catalogue.scored()],
        "indicators": [i.model_dump() for i in catalogue.indicators],
        "themes": {k: v.model_dump() for k, v in catalogue.themes.items()},
        "default_preset": weights.default_preset,
        "presets": {k: v.model_dump() for k, v in weights.presets.items()},
        "sources": {s: {"title": s, "licence": "OGL-3.0", "attribution": f"Source {s}"}
                    for i in catalogue.indicators for s in i.sources},
    }  # fmt: skip
    (path / "manifest.json").write_text(json.dumps(manifest, default=str))

    pl.DataFrame({
        "postcode": ["LS6 3HN", "LS7 4PL", "BN2 9QA"],
        "postcode_norm": ["LS63HN", "LS74PL", "BN29QA"],
        "lsoa21cd": ["E01000001", "E01000003", "E01000005"],
        "lat": [53.8196, 53.8290, 50.8290], "lon": [-1.5766, -1.5390, -0.1260],
    }).write_parquet(path / "postcodes.parquet")  # fmt: skip

    pl.DataFrame({
        "place_id": ["p1", "p2", "p3", "p4"],
        "name": ["Headingley", "Leeds", "Leeds", "Brighton"],
        "name_alt": [None] * 4,
        "place_type": ["Suburban Area", "City", "Village", "Other Settlement"],
        "postcode_district": ["LS6", "LS1", "ME17", "BN1"],
        "local_authority": ["Leeds", "Leeds", "Maidstone", "Brighton and Hove"],
        "region": ["Yorkshire", "Yorkshire", "South East", "South East"],
        "lon": [-1.5766, -1.5500, 0.6070, -0.1370], "lat": [53.8196, 53.8000, 51.2467, 50.8220],
        "lsoa21cd": ["E01000001", "E01000002", "E01000002", "E01000005"],
    }).write_parquet(path / "places.parquet")  # fmt: skip

    areas = []
    for level, code_col, name_col in (("msoa", "msoa21cd", "msoa_name"), ("lad", "lad_cd", "lad_nm"),
                                      ("region", "rgn_cd", "rgn_nm")):  # fmt: skip
        areas.append(
            df.group_by(code_col).agg(
                pl.col(name_col).first().alias("name"), pl.col("lad_nm").first(),
                pl.col("population").sum(), pl.len().alias("lsoas"),
                pl.col("bbox_w").min(), pl.col("bbox_s").min(),
                pl.col("bbox_e").max(), pl.col("bbox_n").max(),
            ).rename({code_col: "code"}).with_columns(pl.lit(level).alias("level"))
        )  # fmt: skip
    pl.concat(areas, how="vertical_relaxed").write_parquet(path / "areas.parquet")

    pois = [
        ("pub", "Well Run Arms", 53.8200, -1.5770, {"well_run": True, "rating": 5}),
        ("pub", "Grubby Tavern", 53.8197, -1.5767, {"well_run": False, "rating": 2}),
        ("pub", "Far Away Inn", 53.8600, -1.6500, {"well_run": True, "rating": 5}),
        ("gp", "Headingley Surgery", 53.8210, -1.5760, {"practice_code": "B86001"}),
        ("primary_school", "Shire Oak Primary", 53.8190, -1.5780, {"quality": 0.7}),
    ]
    p = []
    for k, (cat, name, lat, lon, detail) in enumerate(pois):
        x, y = TO_BNG.transform(lon, lat)
        p.append({"category": cat, "poi_id": f"x{k}", "name": name, "x": x, "y": y, "lon": lon,
                  "lat": lat, "source": "test", "licence": "ODbL-1.0",
                  "detail": json.dumps(detail)})  # fmt: skip
    pl.DataFrame(p).write_parquet(path / "pois.parquet")


@pytest.fixture(scope="session")
def serve_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("serve")
    build_serve_dir(path)
    return path


@pytest.fixture
def store(serve_dir) -> Store:
    s = Store(serve_dir=serve_dir)
    set_store(s)
    import lix_api.services.sql as sql

    sql._guard = None
    return s
