"""Coordinate transforms between British National Grid (EPSG:27700) and WGS84."""

import polars as pl
from pyproj import Transformer

_BNG_TO_WGS84 = Transformer.from_crs(27700, 4326, always_xy=True)
_WGS84_TO_BNG = Transformer.from_crs(4326, 27700, always_xy=True)


def bng_to_lonlat(x: pl.Series, y: pl.Series) -> tuple[pl.Series, pl.Series]:
    lon, lat = _BNG_TO_WGS84.transform(x.to_numpy(), y.to_numpy())
    return pl.Series("lon", lon), pl.Series("lat", lat)


def lonlat_to_bng(lon: pl.Series, lat: pl.Series) -> tuple[pl.Series, pl.Series]:
    x, y = _WGS84_TO_BNG.transform(lon.to_numpy(), lat.to_numpy())
    return pl.Series("x", x), pl.Series("y", y)
