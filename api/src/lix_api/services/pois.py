"""Nearest points of interest of a category around a place."""

import json

from lix_api.models import Poi, Point, PoiResult
from lix_api.services.search import resolve_point
from lix_api.store import Store, to_bng

# "well_run_pub" is pubs filtered to those meeting the well-run definition
CATEGORY_ALIASES = {"well_run_pub": "pub", "school": "primary_school", "doctor": "gp"}


def categories(store: Store) -> list[str]:
    return sorted([*store.poi_trees, "well_run_pub"])


def nearest_pois(
    store: Store, category: str, near: str, max_km: float = 2.0, limit: int = 10
) -> PoiResult:
    base = CATEGORY_ALIASES.get(category, category)
    if base not in store.poi_trees:
        raise ValueError(f"Unknown category {category!r}; choose from {categories(store)}")
    origin, label = resolve_point(store, near)
    x, y = to_bng(origin.lon, origin.lat)
    tree, df = store.poi_trees[base]
    # Over-fetch when filtering to well-run pubs, then trim
    k = min(len(df), limit * 4 if category == "well_run_pub" else limit)
    dist, idx = tree.query([x, y], k=k, distance_upper_bound=max_km * 1000)
    pois = []
    for d, i in zip(list(dist) if k > 1 else [dist], list(idx) if k > 1 else [idx]):
        if d == float("inf"):
            break
        row = df.row(int(i), named=True)
        detail = json.loads(row["detail"]) if row["detail"] else {}
        if category == "well_run_pub" and not detail.get("well_run"):
            continue
        pois.append(
            Poi(
                category=category,
                name=row["name"],
                distance_m=round(float(d)),
                point=Point(lat=row["lat"], lon=row["lon"]),
                source=row["source"],
                licence=row["licence"],
                detail=detail,
            )  # fmt: skip
        )
        if len(pois) >= limit:
            break
    return PoiResult(category=category, origin=origin, origin_label=label, pois=pois)
