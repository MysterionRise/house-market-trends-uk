"""Why an area scores what it does: each theme's share of the score and its indicators."""

from lix_api.models import Contribution, Explanation
from lix_api.services.areas import indicator_value
from lix_api.services.scoring import ThemeWeights, resolve_weights, scores_for
from lix_api.services.search import resolve_lsoa
from lix_api.store import Store


def explain_score(
    store: Store,
    ref: str,
    theme: str | None = None,
    preset: str | None = None,
    theme_weights: ThemeWeights | None = None,
) -> Explanation:
    code = resolve_lsoa(store, ref)
    i = store.lsoa_index[code]
    row = store.features.row(i, named=True)
    name, themes, multipliers = resolve_weights(store, preset, theme_weights)
    scores = scores_for(store, themes, multipliers).row(i, named=True)

    available = {t: w for t, w in themes.items() if scores.get(f"theme__{t}") is not None}
    total = sum(w for w in available.values() if w > 0) or 1.0
    contributions = []
    for t, spec in store.themes.items():
        if theme and t != theme:
            continue
        share = max(available.get(t, 0.0), 0.0) / total
        score = scores.get(f"theme__{t}")
        indicators = [
            indicator_value(store, row, ind.id)
            for ind in store.indicators.values()
            if ind.theme == t and ind.role in ("scored", "context")
        ]
        contributions.append(
            Contribution(
                theme=t,
                label=spec.label,
                weight_share=round(share, 3),
                score=None if score is None else round(score, 1),
                contribution=None if score is None else round(share * score, 1),
                indicators=indicators,
            )  # fmt: skip
        )
    contributions.sort(key=lambda c: c.contribution or 0, reverse=True)

    used = {s for c in contributions for v in c.indicators for s in store.indicators[v.id].sources}
    caveats = sorted(
        {store.indicators[v.id].caveats for c in contributions for v in c.indicators
         if store.indicators[v.id].caveats and v.role == "scored"}
    )  # fmt: skip
    sources = sorted(
        store.manifest["sources"][s]["attribution"] for s in used if s in store.manifest["sources"]
    )
    return Explanation(
        lsoa21cd=code, name=f"{row['lsoa21nm']} ({row['msoa_name']})", preset=name,
        overall=None if scores.get("overall") is None else round(scores["overall"], 1),
        overall_percentile=None
        if scores.get("overall_pct") is None
        else round(scores["overall_pct"]),
        contributions=contributions, caveats=caveats, sources=sorted(set(sources)),
    )  # fmt: skip
