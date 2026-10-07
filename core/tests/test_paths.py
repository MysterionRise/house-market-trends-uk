"""Tests for the shared filesystem layout."""

from pathlib import Path

import pytest

from lix_core.config import get_config
from lix_core.paths import DATA_KINDS, data_dir, data_root, ensure_dirs, get_project_root


def test_project_root_is_the_checkout():
    assert (get_project_root() / "config" / "datasets.yaml").exists()


def test_config_loads_registry():
    assert "nspl" in get_config("datasets")


def test_data_root_defaults_under_repo(monkeypatch):
    monkeypatch.delenv("LIX_DATA_DIR", raising=False)
    assert data_root() == get_project_root() / "data"


def test_data_dir_env_override(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LIX_DATA_DIR", str(tmp_path))
    assert data_dir("staged") == tmp_path / "staged"
    ensure_dirs()
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(DATA_KINDS)


def test_unknown_data_kind():
    with pytest.raises(ValueError, match="Unknown data kind"):
        data_dir("processed")
