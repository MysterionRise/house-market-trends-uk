"""Well-run pubs: OpenStreetMap pubs matched to Food Standards Agency hygiene ratings.

A pub counts as well run when:

- it is mapped in OpenStreetMap as ``amenity=pub`` (so nightclubs and bars, which share
  the FSA's "Pub/bar/nightclub" type, are left out), and
- it matches an FSA record rated 4 or 5 at an inspection in the last three years.

Matching uses the OSM ``fhrs:id`` tag where mappers added one (about 63% of pubs),
whatever the FSA business type (food-led pubs often register as restaurants and inns
as hotels); otherwise the nearest pub, restaurant or hotel within 75m whose name is
similar enough. Requiring both
sources also drops pubs that have closed but linger in one of them. Pubs advertising
real ale, food, outdoor seating or a microbrewery count a little more (never less).

Hygiene ratings say how well a pub is run, not how good the beer is, so the UI calls
these "well-run pubs".
"""

from datetime import date, timedelta

import numpy as np
import polars as pl
from rapidfuzz import fuzz, process
from scipy.spatial import cKDTree

from lix_core.paths import data_dir

PUB_BAR_NIGHTCLUB = 7843
# Food-led pubs often register as restaurants, and inns as hotels
PUB_LIKE_TYPES = [PUB_BAR_NIGHTCLUB, 1, 7842]  # + Restaurant/Cafe/Canteen, Hotel/B&B
MATCH_RADIUS_M = 75
NAME_SIMILARITY = 80
RATING_MAX_AGE_DAYS = 3 * 365
CHARACTER_TAGS = ["real_ale", "food", "outdoor_seating", "beer_garden", "microbrewery"]
CHARACTER_BONUS = 0.1  # per tag, up to MAX_BONUS
MAX_BONUS = 0.3

_STOPWORDS = r"\b(the|ye olde|ye|pub|inn|tavern|bar|public house|ph|and|ltd|limited)\b"


def normalise_name(name: pl.Expr) -> pl.Expr:
    return (
        name.str.to_lowercase()
        .str.replace_all("&", " and ")
        .str.replace_all(r"[’']", "")
        .str.replace_all(_STOPWORDS, " ")
        .str.replace_all(r"[^a-z0-9]+", " ")
        .str.strip_chars()
    )


def match_pubs(
    osm: pl.DataFrame, fsa: pl.DataFrame, spatial_fsa: pl.DataFrame | None = None
) -> pl.DataFrame:
    """Attach the matching FSA record to each OSM pub (by fhrs:id, else near + similar name).

    ``osm``: osm_id, name, x, y, fhrs_id (string, may hold several ids separated by ";").
    ``fsa``: fhrs_id (int), name, x, y, rating, rating_date — every business, since an
    explicit fhrs:id link is trusted whatever the business type.
    ``spatial_fsa``: the subset eligible for name + distance matching (default ``fsa``).
    Returns ``osm`` with fsa_id, rating, rating_date and match ("fhrs_id", "spatial", None).
    """
    spatial_fsa = fsa if spatial_fsa is None else spatial_fsa
    # 1. Explicit links from OSM's fhrs:id tag
    links = (
        osm.select("osm_id", pl.col("fhrs_id").str.split(";"))
        .explode("fhrs_id")
        .with_columns(pl.col("fhrs_id").str.strip_chars().cast(pl.Int64, strict=False))
        .join(fsa.select(pl.col("fhrs_id"), "rating", "rating_date"), on="fhrs_id")
        .sort("rating_date", descending=True, nulls_last=True)
        .unique("osm_id", keep="first")
        .rename({"fhrs_id": "fsa_id"})
        .with_columns(pl.lit("fhrs_id").alias("match"))
    )
    matched = osm.join(links, on="osm_id", how="left")

    # 2. Spatial + name match for the rest
    todo = matched.filter(pl.col("match").is_null() & pl.col("x").is_not_null())
    cand = spatial_fsa.filter(pl.col("x").is_not_null()).with_columns(
        normalise_name(pl.col("name")).alias("_norm")
    )
    if todo.height and cand.height:
        tree = cKDTree(np.column_stack([cand["x"].to_numpy(), cand["y"].to_numpy()]))
        names = todo.select(normalise_name(pl.col("name").fill_null(""))).to_series().to_list()
        near = tree.query_ball_point(
            np.column_stack([todo["x"].to_numpy(), todo["y"].to_numpy()]), r=MATCH_RADIUS_M
        )
        cand_norm = cand["_norm"].to_list()
        found = {"osm_id": [], "fsa_id": [], "rating": [], "rating_date": []}
        for osm_id, name, idx in zip(todo["osm_id"].to_list(), names, near):
            if not name or not idx:
                continue
            best = process.extractOne(
                name, {i: cand_norm[i] for i in idx}, scorer=fuzz.token_set_ratio,
                score_cutoff=NAME_SIMILARITY,
            )  # fmt: skip
            if best:
                row = cand.row(best[2], named=True)
                found["osm_id"].append(osm_id)
                found["fsa_id"].append(row["fhrs_id"])
                found["rating"].append(row["rating"])
                found["rating_date"].append(row["rating_date"])
        spatial = pl.DataFrame(
            found,
            schema={
                "osm_id": pl.Int64,
                "fsa_id": pl.Int64,
                "rating": pl.Int8,
                "rating_date": pl.Date,
            },
        ).with_columns(pl.lit("spatial").alias("match"))
        matched = matched.update(spatial, on="osm_id", how="left")
    return matched


def build_pubs(ctx, as_of: date | None = None) -> pl.DataFrame:
    """Every OSM pub in England with its FSA match and whether it counts as well run."""
    as_of = as_of or date.today()
    osm = (
        ctx.staged("osm_pois")
        .filter(pl.col("value") == "pub")
        .select("osm_type", "osm_id", "name", "x", "y", "lon", "lat", "fhrs_id", *CHARACTER_TAGS)
        .with_columns(pl.concat_str("osm_type", "osm_id").alias("pub_id"))
    )
    # Ids are unique per OSM type only; key on the combined id while matching
    osm_keyed = osm.with_row_index("_key").with_columns(pl.col("_key").cast(pl.Int64))
    fsa = ctx.staged("fsa_fhrs").select(
        "fhrs_id", "name", "x", "y", "rating", "rating_date", "business_type_id"
    )
    matched = match_pubs(
        osm_keyed.select(pl.col("_key").alias("osm_id"), "name", "x", "y", "fhrs_id"),
        fsa,
        spatial_fsa=fsa.filter(pl.col("business_type_id").is_in(PUB_LIKE_TYPES)),
    ).select(pl.col("osm_id").alias("_key"), "fsa_id", "rating", "rating_date", "match")

    pubs = osm_keyed.join(matched, on="_key", how="left").drop("_key")
    recent = pl.col("rating_date") >= pl.lit(as_of - timedelta(days=RATING_MAX_AGE_DAYS))
    character = pl.sum_horizontal(
        pl.col(t).is_in(["yes", "only", "real_ale"]).cast(pl.Int8) for t in CHARACTER_TAGS
    )
    pubs = pubs.with_columns(
        ((pl.col("rating") >= 4) & recent).fill_null(False).alias("well_run"),
        (1 + (character * CHARACTER_BONUS).clip(0, MAX_BONUS)).alias("weight"),
    )
    return pubs


def well_run_pub_access(ctx, radius_m: float, cap: float) -> pl.DataFrame:
    """Distance-decayed access to well-run pubs; also saves the pub list for the API."""
    pubs = build_pubs(ctx)
    out = data_dir("indicators") / "pubs.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pubs.write_parquet(out)
    well_run = pubs.filter(pl.col("well_run"))
    access = ctx.access(well_run, radius_m=radius_m, cap=cap, weight="weight")
    return access.select("lsoa21cd", pl.col("score").alias("value"))
