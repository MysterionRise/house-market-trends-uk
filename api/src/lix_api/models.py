"""Response models shared by the REST API, the agent's tools and the MCP server.

These are the contract with the front end: `make schemas` exports them as JSON Schema
and TypeScript types, so the UI renders exactly what the tools return.
"""

from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["lsoa", "msoa", "lad", "region"]
PlaceKind = Literal["postcode", "place", "lsoa", "msoa", "lad", "region"]


class Point(BaseModel):
    lat: float
    lon: float


class Place(BaseModel):
    """A search result: something a user might mean by a name, postcode or code."""

    kind: PlaceKind
    name: str
    detail: str | None = Field(None, description="Disambiguation, e.g. the local authority")
    code: str | None = None
    lsoa21cd: str | None = None
    centre: Point | None = None
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="west, south, east, north"
    )


class ThemeScore(BaseModel):
    theme: str
    label: str
    score: float | None = Field(None, description="0–100, higher is better")
    percentile: float | None = Field(None, description="Better than this % of England's LSOAs")


class IndicatorValue(BaseModel):
    id: str
    label: str
    theme: str
    unit: str
    value: float | None = Field(None, description="Raw value in `unit`")
    score: float | None = Field(None, description="0–100, higher is better")
    quality: str = "ok"
    role: str = "scored"


class AreaProfile(BaseModel):
    lsoa21cd: str
    lsoa_name: str
    neighbourhood: str | None = Field(None, description="Friendly MSOA name")
    msoa21cd: str
    local_authority: str
    region: str
    urban_rural: str
    population: int
    overall: float | None
    overall_percentile: float | None
    band: int | None = Field(None, description="1 (bottom fifth of England) … 5 (top fifth)")
    overall_percentile_range: list[float] | None = Field(
        None,
        min_length=2,
        max_length=2,
        description="5–95% range of the England percentile when each theme weight is "
        "nudged by about a quarter (for presets; None with custom weights)",
    )
    coverage: float | None
    preset: str
    themes: list[ThemeScore]
    strengths: list[IndicatorValue]
    weaknesses: list[IndicatorValue]
    key_facts: list[IndicatorValue]
    flags: list[str] = Field(default_factory=list, description="Caveats that apply to this area")
    centre: Point
    bbox: tuple[float, float, float, float]


class RankedArea(BaseModel):
    rank: int
    level: Level
    code: str
    name: str
    local_authority: str
    overall: float | None
    overall_percentile: float | None
    themes: dict[str, float | None]
    median_price: float | None = None
    population: int
    centre: Point
    stability: float | None = Field(
        None,
        description="Share of plausible weightings (each theme weight nudged by about a "
        "quarter) under which this area stays in these top results, 0–1",
    )


class RankResult(BaseModel):
    level: Level
    within: str | None = Field(None, description="The area or place the ranking was limited to")
    preset: str
    theme_weights: dict[str, float]
    candidates: int = Field(description="Areas that passed the filters")
    results: list[RankedArea]
    bbox: tuple[float, float, float, float] | None = None


class ComparedArea(BaseModel):
    code: str
    name: str
    level: Level
    overall: float | None
    overall_percentile: float | None
    themes: dict[str, float | None]
    indicators: dict[str, float | None] = Field(description="Raw indicator values")


class Comparison(BaseModel):
    preset: str
    areas: list[ComparedArea]
    indicator_labels: dict[str, str]
    theme_labels: dict[str, str]


class Poi(BaseModel):
    category: str
    name: str | None
    distance_m: float
    point: Point
    source: str
    licence: str
    detail: dict = Field(default_factory=dict)


class PoiResult(BaseModel):
    category: str
    origin: Point
    origin_label: str
    pois: list[Poi]


class Contribution(BaseModel):
    theme: str
    label: str
    weight_share: float = Field(description="Share of the overall weight, 0–1")
    score: float | None
    contribution: float | None = Field(None, description="weight_share × score")
    indicators: list[IndicatorValue]


class SourceRef(BaseModel):
    id: str
    title: str
    licence: str
    attribution: str
    version: str | None = Field(None, description="The upstream version the build used")
    fetched_at: str | None = Field(None, description="When the build downloaded it (ISO 8601)")
    stale: bool = Field(False, description="Older than the source's publishing cadence allows")


class Explanation(BaseModel):
    lsoa21cd: str
    name: str
    preset: str
    overall: float | None
    overall_percentile: float | None
    contributions: list[Contribution]
    caveats: list[str]
    sources: list[SourceRef]


class IndicatorInfo(BaseModel):
    id: str
    theme: str
    label: str
    description: str
    unit: str
    direction: str
    role: str
    normalise: str
    weight: float
    caveats: str | None = None
    sources: list[str]
