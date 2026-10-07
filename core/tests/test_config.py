"""Tests for registry loading and validation."""

import pytest
from pydantic import ValidationError

from lix_core.config import DatasetSpec, load_registry

BASE = dict(
    title="T",
    theme="geography",
    format="csv",
    description="d",
    licence="OGL-3.0",
    attribution="a",
    cadence="static",
)


def test_real_registry_is_valid():
    registry = load_registry()
    assert "nspl" in registry
    # YAML anchors live under x- keys and are not datasets
    assert not any(slug.startswith("x-") for slug in registry)


def test_every_dataset_has_open_licence_and_attribution():
    open_licences = ("OGL", "ODbL", "CC-BY", "CC0", "CDLA", "Apache", "OPL")
    for slug, spec in load_registry().items():
        assert spec.licence.startswith(open_licences), f"{slug}: {spec.licence}"
        assert spec.attribution.strip(), slug


def test_access_types_are_discriminated():
    spec = DatasetSpec(**BASE, access={"type": "http", "url": "https://x"})
    assert spec.access.url == "https://x"
    with pytest.raises(ValidationError):
        DatasetSpec(**BASE, access={"type": "ftp", "url": "x"})


def test_unknown_fields_rejected():
    # A typo such as "extracts" must fail loudly rather than be ignored
    with pytest.raises(ValidationError):
        DatasetSpec(**BASE, access={"type": "http", "url": "u"}, extracts=["*.csv"])


def test_arcgis_defaults():
    spec = DatasetSpec(**BASE, access={"type": "arcgis_item", "pin": "abc"})
    assert spec.access.mode == "data"
    assert spec.access.out_sr == 27700
