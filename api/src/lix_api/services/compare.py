"""Side-by-side comparison of 2–5 areas (LSOAs, or MSOAs / local authorities as averages)."""

import polars as pl

from lix_api.models import ComparedArea, Comparison
from lix_api.services.scoring import ThemeWeights, resolve_weights, scores_for
from lix_api.services.search import resolve_lsoa, search_place
from lix_api.store import Store

COMPARE_INDICATORS = [
    "house_price", "crime_violence", "crime_burglary", "no2", "gp_distance",
    "patients_per_gp", "primary_school_quality", "well_run_pubs", "supermarket_distance",
    "connectivity_overall", "income_deprivation", "population_density",
]  # fmt: skip


def compare_areas(
    store: Store,
    refs: list[str],
    preset: str | None = None,
    theme_weights: ThemeWeights | None = None,
) -> Comparison:
    if not 2 <= len(refs) <= 5:
        raise ValueError("Compare between 2 and 5 areas")
    name, themes, multipliers = resolve_weights(store, preset, theme_weights)
    scored = pl.concat(
        [store.base_features, scores_for(store, themes, multipliers).drop("lsoa21cd")],
        how="horizontal",
    )
    indicators = [i for i in COMPARE_INDICATORS if i in store.indicators]
    areas = []
    for ref in refs:
        place = (search_place(store, ref, limit=1) or [None])[0]
        if place and place.kind in ("msoa", "lad"):
            column = "msoa21cd" if place.kind == "msoa" else "lad_cd"
            rows = scored.filter(pl.col(column) == place.code)
            label, level, code = place.name, place.kind, place.code
        elif place and place.kind == "place" and place.lsoa21cd:
            # A named suburb or village means its neighbourhood, not one LSOA of it
            home = scored.filter(pl.col("lsoa21cd") == place.lsoa21cd).row(0, named=True)
            code, level = home["msoa21cd"], "msoa"
            rows = scored.filter(pl.col("msoa21cd") == code)
            same = home["msoa_name"].lower().startswith(place.name.lower())
            label = home["msoa_name"] if same else f"{place.name} ({home['msoa_name']})"
        else:
            code = resolve_lsoa(store, ref)
            rows = scored.filter(pl.col("lsoa21cd") == code)
            r = rows.row(0, named=True)
            label, level = f"{r['lsoa21nm']} ({r['msoa_name']})", "lsoa"
        w = rows["population"].cast(pl.Float64)

        def wmean(col: str) -> float | None:
            vals = rows[col]
            ok = vals.is_not_null()
            if not ok.any():
                return None
            return round(float((vals.filter(ok) * w.filter(ok)).sum() / w.filter(ok).sum()), 2)

        areas.append(
            ComparedArea(
                code=code,
                name=label,
                level=level,
                overall=wmean("overall"),
                overall_percentile=wmean("overall_pct") if level == "lsoa" else None,
                themes={t: wmean(f"theme__{t}") for t in store.themes},
                indicators={i: wmean(f"raw__{i}") for i in indicators},
            )  # fmt: skip
        )
    return Comparison(
        preset=name,
        areas=areas,
        indicator_labels={i: store.indicators[i].label for i in indicators},
        theme_labels={t: s.label for t, s in store.themes.items()},
    )
