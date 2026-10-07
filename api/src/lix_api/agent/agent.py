"""The assistant: a provider-agnostic pydantic-ai agent served over AG-UI.

Every tool returns a typed result the page renders as a component (ranked list, area
card, comparison table, POI list, explainer, ...). Tools that change what the page
shows (weights, map, shortlist) also update the shared state and push a snapshot,
so the sliders move and the map recolours as the assistant works.
"""

from ag_ui.core import EventType, StateSnapshotEvent
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.ui import StateDeps

from lix_api.agent.models import build_model, model_settings
from lix_api.agent.state import LiveabilityState, ShortlistItem
from lix_api.models import (
    AreaProfile,
    Comparison,
    Explanation,
    IndicatorInfo,
    Level,
    Place,
    PoiResult,
    RankResult,
)
from lix_api.services import areas, catalogue, compare, explain, pois, ranking, search
from lix_api.services.scoring import resolve_weights
from lix_api.store import get_store

Deps = StateDeps[LiveabilityState]

INSTRUCTIONS = """\
You help people find and understand neighbourhoods in England using the UK Liveability
Index: open data scored for each of England's 33,755 neighbourhoods (LSOAs, about
1,600 residents each) across eight themes — safety, environment, health services,
schools & childcare, transport, amenities & nightlife, housing & affordability, and
community & wellbeing. Scores are 0–100 (higher is better) with an England percentile.

How to work:
- Use the tools for every fact and number. Never estimate scores, prices or distances.
- The page renders each tool result as a card, table or map, so don't repeat the
  numbers in prose. Reply in one to three sentences that interpret the result:
  what stands out, trade-offs, and a sensible next step.
- Names can be ambiguous ("Clapham" is in London and in North Yorkshire). If a tool
  picks a place the user probably didn't mean, say which one you used.
- When the user describes priorities ("we have two kids", "I commute to Manchester"),
  call set_weights before ranking so the sliders and map reflect them.
- Rank at "msoa" level (neighbourhoods of ~8,000 people) for broad questions and at
  "lsoa" level when the user wants street-scale detail.
- Mention caveats the tools return (estimated crime for Greater Manchester, few house
  sales, distances being straight-line) when they matter to the answer.
- Coverage is England only. Scotland, Wales and Northern Ireland aren't scored yet.
- Never rank or describe areas by ethnicity, religion or any other protected
  characteristic, and decline requests to steer people towards or away from areas on
  those grounds. The index doesn't contain such data.
- "Well-run pubs" means pubs with a food hygiene rating of 4–5 from the last three
  years; it says nothing about the beer or atmosphere.
"""

agent = Agent(
    build_model(),
    deps_type=Deps,
    instructions=INSTRUCTIONS,
    model_settings=model_settings(),
    name="liveability",
)


@agent.instructions
def current_state(ctx: RunContext[Deps]) -> str:
    """Per-turn state, after the static instructions (so the cached prefix holds)."""
    s = ctx.deps.state
    lines = [f"Current weighting: preset '{s.preset}'"]
    if s.theme_weights:
        lines.append(f"  theme weights adjusted by the user: {s.theme_weights}")
    if s.indicator_weights:
        lines.append(f"  indicator multipliers: {s.indicator_weights}")
    lines.append(f"Mode: {s.mode}" + (" (SQL and charts available)" if s.mode == "analyst" else ""))
    if s.map.selected:
        lines.append(f"Area open on the page: {s.map.selected}")
    if s.shortlist:
        lines.append("Shortlist: " + ", ".join(f"{i.name} ({i.code})" for i in s.shortlist))
    return "\n".join(lines)


def _weights(ctx: RunContext[Deps]) -> dict:
    s = ctx.deps.state
    return {"preset": s.preset, "theme_weights": s.theme_weights or None}


def _with_state(ctx: RunContext[Deps], value) -> ToolReturn:
    snapshot = StateSnapshotEvent(
        type=EventType.STATE_SNAPSHOT, snapshot=ctx.deps.state.model_dump(mode="json")
    )
    return ToolReturn(return_value=value, metadata=[snapshot])


@agent.tool
def search_place(ctx: RunContext[Deps], query: str) -> list[Place]:
    """Find places matching a name, postcode or area code (best first)."""
    return search.search_place(get_store(), query, limit=6)


@agent.tool
def get_area_profile(ctx: RunContext[Deps], area: str) -> ToolReturn:
    """Profile one neighbourhood: overall and theme scores, strengths, weaknesses, key facts.

    Args:
        area: a postcode, place name or LSOA code (a place resolves to the neighbourhood
            it sits in)
    """
    profile: AreaProfile = areas.area_profile(get_store(), area, **_weights(ctx))
    ctx.deps.state.map.selected = profile.lsoa21cd
    ctx.deps.state.map.bbox = profile.bbox
    return _with_state(ctx, profile)


@agent.tool
def rank_areas(
    ctx: RunContext[Deps],
    within: str | None = None,
    radius_km: float | None = None,
    level: Level = "msoa",
    max_median_price: float | None = None,
    min_theme_scores: dict[str, float] | None = None,
    urban: bool | None = None,
    limit: int = 8,
) -> ToolReturn:
    """Rank areas by the current weighting, best first, and highlight them on the map.

    Args:
        within: a local authority, region, neighbourhood or place; with a place, areas
            within radius_km of it (default 10 km)
        radius_km: search radius around a place
        level: "msoa" (neighbourhoods of ~8,000 people) or "lsoa" (~1,600)
        max_median_price: only areas whose typical house price is at most this (£)
        min_theme_scores: e.g. {"safety": 60} to require a minimum theme score
        urban: True for towns and cities only, False for rural areas only
        limit: how many to return (max 20)
    """
    result: RankResult = ranking.rank_areas(
        get_store(), within=within, radius_km=radius_km, level=level,
        max_median_price=max_median_price, min_theme_scores=min_theme_scores, urban=urban,
        limit=min(limit, 20), **_weights(ctx),
    )  # fmt: skip
    ctx.deps.state.map.highlighted = [r.code for r in result.results]
    if result.bbox:
        ctx.deps.state.map.bbox = result.bbox
    return _with_state(ctx, result)


@agent.tool
def compare_areas(ctx: RunContext[Deps], areas: list[str]) -> ToolReturn:
    """Compare 2–5 areas side by side (postcodes, places, neighbourhoods or local authorities)."""
    result: Comparison = compare.compare_areas(get_store(), areas, **_weights(ctx))
    ctx.deps.state.map.highlighted = [a.code for a in result.areas]
    return _with_state(ctx, result)


@agent.tool
def nearest_pois(
    ctx: RunContext[Deps], category: str, near: str, max_km: float = 2.0, limit: int = 8
) -> ToolReturn:
    """Find the nearest places of a category and show them on the map.

    Args:
        category: well_run_pub, pub, gp, primary_school, secondary_school, nursery,
            supermarket, convenience_store, pharmacy, dentist, cafe, restaurant, bar, park,
            playground, gym, sports_centre, library, cinema, theatre, museum, post_office,
            bakery, ev_charging, ...
        near: a postcode, place or area
        max_km: search radius
    """
    result: PoiResult = pois.nearest_pois(get_store(), category, near, max_km, min(limit, 25))
    ctx.deps.state.map.pois = result.pois
    return _with_state(ctx, result)


@agent.tool
def explain_score(ctx: RunContext[Deps], area: str, theme: str | None = None) -> Explanation:
    """Explain an area's score: each theme's share and the indicators behind it.

    Args:
        area: a postcode, place name or LSOA code
        theme: limit the explanation to one theme (e.g. "safety")
    """
    return explain.explain_score(get_store(), area, theme=theme, **_weights(ctx))


@agent.tool
def set_weights(
    ctx: RunContext[Deps],
    preset: str | None = None,
    theme_weights: dict[str, float] | None = None,
    indicator_weights: dict[str, float] | None = None,
) -> ToolReturn:
    """Change how themes are weighted; the sliders and map update immediately.

    Args:
        preset: balanced, family, young_professional, retiree or commuter
        theme_weights: per-theme weights on top of the preset, e.g. {"safety": 3, "amenities": 0.5};
            0 ignores a theme
        indicator_weights: multipliers on single indicators, e.g. {"well_run_pubs": 2}
    """
    store = get_store()
    s = ctx.deps.state
    if preset:
        s.preset = preset
        s.theme_weights, s.indicator_weights = {}, {}
    if theme_weights:
        s.theme_weights = {**s.theme_weights, **theme_weights}
    if indicator_weights:
        s.indicator_weights = {**s.indicator_weights, **indicator_weights}
    name, themes, multipliers = resolve_weights(
        store, s.preset, s.theme_weights, s.indicator_weights
    )
    return _with_state(
        ctx, {"preset": name, "theme_weights": themes, "indicator_weights": multipliers}
    )


@agent.tool
def show_on_map(
    ctx: RunContext[Deps], area: str | None = None, layer: str | None = None
) -> ToolReturn:
    """Move the map to an area and/or colour it by a layer.

    Args:
        area: a place, postcode or area to zoom to
        layer: "overall", "theme:<theme>" (e.g. "theme:safety") or "indicator:<id>"
    """
    s = ctx.deps.state
    if area:
        places = search.search_place(get_store(), area, limit=1)
        if places and places[0].bbox:
            s.map.bbox = places[0].bbox
        elif places and places[0].centre:
            c = places[0].centre
            s.map.bbox = (c.lon - 0.03, c.lat - 0.02, c.lon + 0.03, c.lat + 0.02)
    if layer:
        s.map.layer = layer
    return _with_state(ctx, {"bbox": s.map.bbox, "layer": s.map.layer})


@agent.tool
def add_to_shortlist(ctx: RunContext[Deps], area: str, note: str | None = None) -> ToolReturn:
    """Save an area to the user's shortlist."""
    place = (search.search_place(get_store(), area, limit=1) or [None])[0]
    if place is None:
        raise ValueError(f"Couldn't find {area!r}")
    code = place.lsoa21cd if place.kind in ("postcode", "place", "lsoa") else place.code
    s = ctx.deps.state
    if all(i.code != code for i in s.shortlist):
        s.shortlist.append(
            ShortlistItem(code=code, name=place.name, note=note, centre=place.centre)
        )
    return _with_state(ctx, s.shortlist)


@agent.tool
def remove_from_shortlist(ctx: RunContext[Deps], code: str) -> ToolReturn:
    """Remove an area from the shortlist by its code."""
    s = ctx.deps.state
    s.shortlist = [i for i in s.shortlist if i.code != code]
    return _with_state(ctx, s.shortlist)


@agent.tool
def list_indicators(ctx: RunContext[Deps], theme: str | None = None) -> list[IndicatorInfo]:
    """What the index measures, with units, sources and caveats (optionally for one theme)."""
    return catalogue.list_indicators(get_store(), theme)


async def _analyst_only(ctx: RunContext[Deps], tool_def: ToolDefinition) -> ToolDefinition | None:
    return tool_def if ctx.deps.state.mode == "analyst" else None


@agent.tool(prepare=_analyst_only)
def run_sql(ctx: RunContext[Deps], query: str) -> dict:
    """Run one read-only SELECT (DuckDB SQL) over the index's tables; at most 5,000 rows.

    Tables: lsoa (every LSOA with raw__<indicator>, n__<indicator> 0–100 scores,
    q__<indicator> quality flags, theme__<theme>, overall, overall_pct, lad_nm, rgn_nm,
    msoa_name, population, ...), pois (category, name, lat, lon, source, detail),
    areas (msoa/lad/region with population and bbox), places, indicators.
    """
    from lix_api.services.sql import get_guard

    result = get_guard().run(query)
    return {"columns": result.columns, "rows": result.rows, "truncated": result.truncated}
