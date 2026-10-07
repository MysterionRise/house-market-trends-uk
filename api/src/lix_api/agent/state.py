"""State shared between the assistant and the page over AG-UI.

The page sends it with every run (so the assistant sees slider moves, the selected
area and the shortlist); tools that change it push a snapshot back, and the map,
weight sliders and shortlist re-render from it.
"""

from typing import Literal

from pydantic import BaseModel, Field

from lix_api.models import Poi, Point


class MapView(BaseModel):
    bbox: tuple[float, float, float, float] | None = Field(
        None, description="west, south, east, north"
    )
    layer: str = Field("overall", description='"overall", "theme:<theme>" or "indicator:<id>"')
    highlighted: list[str] = Field(default_factory=list, description="LSOA/MSOA codes to outline")
    selected: str | None = Field(None, description="LSOA code of the open area profile")
    pois: list[Poi] = Field(default_factory=list, description="Markers to show")


class ShortlistItem(BaseModel):
    code: str
    name: str
    note: str | None = None
    centre: Point | None = None


class LiveabilityState(BaseModel):
    preset: str = "balanced"
    theme_weights: dict[str, float] = Field(
        default_factory=dict, description="Overrides on top of the preset's theme weights"
    )
    indicator_weights: dict[str, float] = Field(
        default_factory=dict, description="Multipliers on individual indicators"
    )
    compare_within_urban_rural: bool = False
    mode: Literal["consumer", "analyst"] = "consumer"
    map: MapView = Field(default_factory=MapView)
    shortlist: list[ShortlistItem] = Field(default_factory=list)
