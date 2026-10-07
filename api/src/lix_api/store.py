"""In-memory data store the API answers from, loaded once from data/serve/.

Everything is small enough to hold in memory (about 100 MB): per-LSOA features,
postcodes, places, named areas and points of interest, plus a KD-tree per POI
category for nearest-place queries.
"""

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import polars as pl
from pyproj import Transformer
from scipy.spatial import cKDTree

from lix_core.config import IndicatorSpec, Preset, ThemeSpec
from lix_core.paths import data_dir

_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)


def to_bng(lon: float, lat: float) -> tuple[float, float]:
    return _TO_BNG.transform(lon, lat)


@dataclass
class Store:
    serve_dir: Path = field(default_factory=lambda: data_dir("serve"))
    score_cache: dict = field(default_factory=dict, repr=False)

    @cached_property
    def manifest(self) -> dict:
        return json.loads((self.serve_dir / "manifest.json").read_text())

    @cached_property
    def indicators(self) -> dict[str, IndicatorSpec]:
        return {i["id"]: IndicatorSpec.model_validate(i) for i in self.manifest["indicators"]}

    @cached_property
    def themes(self) -> dict[str, ThemeSpec]:
        return {k: ThemeSpec.model_validate(v) for k, v in self.manifest["themes"].items()}

    @cached_property
    def presets(self) -> dict[str, Preset]:
        return {k: Preset.model_validate(v) for k, v in self.manifest["presets"].items()}

    @property
    def default_preset(self) -> str:
        return self.manifest["default_preset"]

    @cached_property
    def scored(self) -> list[IndicatorSpec]:
        return [self.indicators[i] for i in self.manifest["scored_indicators"]]

    @cached_property
    def features(self) -> pl.DataFrame:
        return pl.read_parquet(self.serve_dir / "lsoa_features.parquet")

    @cached_property
    def base_features(self) -> pl.DataFrame:
        """Features without the default preset's scores, for re-scoring with any weights."""
        return self.features.select(
            pl.exclude(r"^theme__.*$", r"^theme_pct__.*$", r"^theme_coverage__.*$",
                       "overall", "overall_pct", "coverage", "band")
        )  # fmt: skip

    @cached_property
    def lsoa_index(self) -> dict[str, int]:
        return {code: i for i, code in enumerate(self.features["lsoa21cd"].to_list())}

    @cached_property
    def postcodes(self) -> pl.DataFrame:
        return pl.read_parquet(self.serve_dir / "postcodes.parquet")

    @cached_property
    def places(self) -> pl.DataFrame:
        return pl.read_parquet(self.serve_dir / "places.parquet")

    @cached_property
    def areas(self) -> pl.DataFrame:
        return pl.read_parquet(self.serve_dir / "areas.parquet")

    @cached_property
    def pois(self) -> pl.DataFrame:
        return pl.read_parquet(self.serve_dir / "pois.parquet")

    @cached_property
    def poi_trees(self) -> dict[str, tuple[cKDTree, pl.DataFrame]]:
        trees = {}
        for (category,), df in self.pois.partition_by("category", as_dict=True).items():
            xy = np.column_stack([df["x"].to_numpy(), df["y"].to_numpy()])
            trees[category] = (cKDTree(xy), df)
        return trees

    def warm(self) -> "Store":
        """Load everything up front so the first request isn't slow."""
        for attr in ("manifest", "features", "lsoa_index", "postcodes", "places", "areas"):
            getattr(self, attr)
        self.poi_trees  # noqa: B018
        return self


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def set_store(store: Store) -> None:
    """Swap the store (tests point it at fixture data)."""
    global _store
    _store = store
