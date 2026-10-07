"""Find what a user means: a postcode, an LSOA/MSOA/LAD code, a place or an area name."""

import re

import polars as pl
from rapidfuzz import fuzz, process

from lix_api.models import Place, Point
from lix_api.store import Store

POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\d[A-Z]{2}$")
GSS = re.compile(r"^E0[1-2]\d{6}$|^E0[6-9]\d{6}$|^E1[0-2]\d{6}$")

# Higher wins when names score equally: "Leeds" the city beats Leeds village in Kent
# WRatio similarity a name must reach: typos ("Headingly", "Mancheser") score ~95,
# while unrelated names sharing a suffix ("Nowheresville" vs "Teesville") score ~80
MIN_SIMILARITY = 88

KIND_PRIORITY = {"lad": 6, "region": 5, "City": 5, "Town": 4, "msoa": 3, "Suburban Area": 3,
                 "Village": 2, "Other Settlement": 1, "Hamlet": 0}  # fmt: skip


def normalise_postcode(text: str) -> str:
    return re.sub(r"\s", "", text).upper()


def _bbox(row: dict) -> tuple[float, float, float, float] | None:
    if row.get("bbox_w") is None:
        return None
    return (row["bbox_w"], row["bbox_s"], row["bbox_e"], row["bbox_n"])


def lookup_postcode(store: Store, text: str) -> Place | None:
    norm = normalise_postcode(text)
    if not POSTCODE.match(norm):
        return None
    hit = store.postcodes.filter(pl.col("postcode_norm") == norm)
    if hit.is_empty():
        return None
    row = hit.row(0, named=True)
    return Place(
        kind="postcode", name=row["postcode"], code=row["postcode"], lsoa21cd=row["lsoa21cd"],
        centre=Point(lat=row["lat"], lon=row["lon"]),
    )  # fmt: skip


def lookup_code(store: Store, text: str) -> Place | None:
    code = text.strip().upper()
    if not GSS.match(code):
        return None
    if code in store.lsoa_index:
        row = store.features.row(store.lsoa_index[code], named=True)
        return Place(
            kind="lsoa", name=row["lsoa21nm"], code=code, lsoa21cd=code,
            detail=row["msoa_name"], centre=Point(lat=row["pwc_lat"], lon=row["pwc_lon"]),
            bbox=_bbox(row),
        )  # fmt: skip
    hit = store.areas.filter(pl.col("code") == code)
    if hit.is_empty():
        return None
    row = hit.row(0, named=True)
    return _area_place(row)


def _area_place(row: dict) -> Place:
    bbox = _bbox(row)
    centre = Point(lat=(bbox[1] + bbox[3]) / 2, lon=(bbox[0] + bbox[2]) / 2) if bbox else None
    detail = row["lad_nm"] if row["level"] == "msoa" else None
    return Place(kind=row["level"], name=row["name"], code=row["code"], detail=detail,
                 centre=centre, bbox=bbox)  # fmt: skip


def search_place(store: Store, query: str, limit: int = 8) -> list[Place]:
    """Rank candidate places for free text, best first."""
    query = query.strip()
    if not query:
        return []
    for exact in (lookup_postcode(store, query), lookup_code(store, query)):
        if exact:
            return [exact]

    candidates: list[tuple[float, Place]] = []
    names = store.places["name"].to_list()
    for _, score, idx in process.extract(
        query, names, scorer=fuzz.WRatio, limit=40, score_cutoff=MIN_SIMILARITY
    ):
        row = store.places.row(idx, named=True)
        place = Place(
            kind="place", name=row["name"], code=row["place_id"], lsoa21cd=row["lsoa21cd"],
            detail=f"{row['place_type']}, {row['local_authority']}",
            centre=Point(lat=row["lat"], lon=row["lon"]),
        )  # fmt: skip
        candidates.append((score + KIND_PRIORITY.get(row["place_type"], 0), place))

    area_names = store.areas["name"].to_list()
    for _, score, idx in process.extract(
        query, area_names, scorer=fuzz.WRatio, limit=20, score_cutoff=MIN_SIMILARITY
    ):
        row = store.areas.row(idx, named=True)
        candidates.append((score + KIND_PRIORITY.get(row["level"], 0), _area_place(row)))

    candidates.sort(key=lambda c: c[0], reverse=True)
    seen, out = set(), []
    for _, place in candidates:
        key = (place.kind, place.name, place.detail)
        if key not in seen:
            seen.add(key)
            out.append(place)
    return out[:limit]


def resolve_point(store: Store, ref: str) -> tuple[Point, str]:
    """A location for "near X": postcode, code or place name → (point, label)."""
    places = search_place(store, ref, limit=1)
    if not places or places[0].centre is None:
        raise LookupError(f"Couldn't find a place called {ref!r}")
    place = places[0]
    return place.centre, place.name if not place.detail else f"{place.name} ({place.detail})"


def resolve_lsoa(store: Store, ref: str) -> str:
    """An LSOA for a postcode, LSOA code or place name (the LSOA it sits in).

    A local authority or region resolves through its namesake place ("Manchester" the
    city, whose point is the city centre) rather than the middle of its bounding box,
    which is often a suburb.
    """
    places = search_place(store, ref, limit=6)
    if not places:
        raise LookupError(f"Couldn't find an area for {ref!r}")
    top = places[0]
    if top.lsoa21cd:
        return top.lsoa21cd
    namesake = next(
        (p for p in places[1:] if p.lsoa21cd and p.name.lower() == top.name.lower()), None
    )
    if namesake:
        return namesake.lsoa21cd
    if top.centre:
        return nearest_lsoa(store, top.centre)
    raise LookupError(f"Couldn't find an area for {ref!r}")


def nearest_lsoa(store: Store, point: Point) -> str:
    f = store.features
    d = (f["pwc_lat"] - point.lat) ** 2 + ((f["pwc_lon"] - point.lon) * 0.62) ** 2
    return f["lsoa21cd"][int(d.arg_min())]
