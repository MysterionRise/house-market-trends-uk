"""Loading and validation of the YAML files in ``config/``."""

from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from lix_core.paths import get_project_root


def get_config(name: str) -> dict:
    """Load a YAML config file from config/{name}.yaml."""
    config_path = get_project_root() / "config" / f"{name}.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HttpAccess(_Strict):
    """A fixed URL."""

    type: Literal["http"]
    url: str


class ArcgisItemAccess(_Strict):
    """An ArcGIS Online item (ONS Open Geography Portal).

    ONS deletes an item when it publishes a new version, so the item is found by
    searching for ``query`` and taking the newest result whose title matches
    ``title_regex`` (and ``item_type``). ``pin`` is the item last known to work; it is
    used when search finds nothing.
    """

    type: Literal["arcgis_item"]
    pin: str
    query: str | None = None
    title_regex: str | None = None
    item_type: str | None = None
    # data: the item's file (CSV Collection zips) · hub_export: Hub-generated file of a
    # feature layer · featureserver: page through the layer's query API
    mode: Literal["data", "hub_export", "featureserver"] = "data"
    export_format: Literal["csv", "geoPackage", "geojson"] | None = None
    layer: int = 0
    # featureserver only: fields to keep, and the CRS for geometry (27700 = British National Grid)
    fields: list[str] | None = None
    geometry: Literal["none", "point", "polygon"] = "none"
    out_sr: int = 27700


class GovukAttachmentAccess(_Strict):
    """An attachment on a GOV.UK publication page, found via the content API."""

    type: Literal["govuk_attachment"]
    path: str
    attachment_regex: str


class ManualAccess(_Strict):
    """A file the user downloads by hand (e.g. behind a free login) into data/manual/{slug}/."""

    type: Literal["manual"]
    instructions: str
    expect: list[str]


Access = Annotated[
    HttpAccess | ArcgisItemAccess | GovukAttachmentAccess | ManualAccess,
    Field(discriminator="type"),
]

Theme = Literal[
    "geography",
    "safety",
    "environment",
    "health",
    "education",
    "transport",
    "amenities",
    "housing",
    "community",
]


class DatasetSpec(_Strict):
    """One entry of config/datasets.yaml."""

    title: str
    theme: Theme
    priority: Literal["P0", "P1", "P2"] = "P0"
    access: Access
    format: Literal["csv", "zip", "gpkg", "xlsx", "ods", "parquet", "json", "geojson"]
    # zip only: glob patterns of members to extract (everything if omitted)
    extract: list[str] | None = None
    landing_page: str | None = None
    description: str
    licence: str
    licence_verified: bool = True
    attribution: str
    cadence: Literal["daily", "weekly", "monthly", "quarterly", "annual", "adhoc", "static"]
    size_hint: str | None = None
    notes: str | None = None


def load_registry() -> dict[str, DatasetSpec]:
    """Load and validate config/datasets.yaml, keyed by dataset slug.

    Top-level keys starting with ``x-`` hold YAML anchors (shared attribution text etc.)
    and are not datasets.
    """
    return {
        slug: DatasetSpec.model_validate(raw)
        for slug, raw in get_config("datasets").items()
        if not slug.startswith("x-")
    }
