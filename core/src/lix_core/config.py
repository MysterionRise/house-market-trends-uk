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
    """A fixed URL.

    For files published under a dated name, put ``{date}`` in the URL and set
    ``date_format``; the resolver tries today and then each earlier day, up to
    ``lookback_days``, until a file exists.
    """

    type: Literal["http"]
    url: str
    date_format: str | None = None
    lookback_days: int = 7


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
    """An attachment on a GOV.UK publication page, found via the content API.

    ``pick: one`` requires exactly one match. ``pick: latest`` is for pages that keep
    every past release (e.g. monthly Ofsted files): it takes the match with the latest
    date in its file name, such as "as_at_31_August_2026".
    """

    type: Literal["govuk_attachment"]
    path: str
    attachment_regex: str
    pick: Literal["one", "latest"] = "one"


class LinkStep(_Strict):
    """One hop of an ``html_link`` resolver: a regex whose first group is a URL."""

    pattern: str
    # page: document order · desc: highest match first (e.g. a year in the name) ·
    # date_desc: newest date in the URL first ("july-2026", "31-august-2026")
    order: Literal["page", "desc", "date_desc"] = "page"


class HtmlLinkAccess(_Strict):
    """A file found by following links from a landing page.

    Each step searches the current page for links; non-final steps are tried in order
    until one leads to a page where the next step matches (so an announced release
    without files yet is skipped).
    """

    type: Literal["html_link"]
    page: str
    steps: list[LinkStep]


class ManualAccess(_Strict):
    """A file the user downloads by hand (e.g. behind a free login) into data/manual/{slug}/."""

    type: Literal["manual"]
    instructions: str
    expect: list[str]


Access = Annotated[
    HttpAccess | ArcgisItemAccess | GovukAttachmentAccess | HtmlLinkAccess | ManualAccess,
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
    format: Literal["csv", "zip", "gpkg", "xlsx", "ods", "parquet", "json", "geojson", "pbf"]
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
