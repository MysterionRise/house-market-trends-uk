"""Filesystem layout shared by every package.

Config lives in the repository (``config/``). Data lives under ``data/`` by default;
set ``LIX_DATA_DIR`` to keep it elsewhere (e.g. a bigger disk), and ``LIX_ROOT`` to
point at the repository when the packages are installed outside a checkout.
"""

import os
from pathlib import Path

# raw: as downloaded · manual: login-gated files placed by hand · staged: tidy Parquet per
# source · indicators: per-LSOA indicator table · serve: files the API and browser load
DATA_KINDS = ("raw", "manual", "staged", "indicators", "serve", "logs")


def get_project_root() -> Path:
    """Repository root: ``$LIX_ROOT`` if set, else the checkout this file lives in."""
    if env := os.environ.get("LIX_ROOT"):
        return Path(env).resolve()
    # core/src/lix_core/paths.py → repo root
    return Path(__file__).resolve().parents[3]


def data_root() -> Path:
    """Root of all data: ``$LIX_DATA_DIR`` if set, else ``<repo>/data``."""
    if env := os.environ.get("LIX_DATA_DIR"):
        return Path(env).resolve()
    return get_project_root() / "data"


def data_dir(kind: str) -> Path:
    """Directory for one data layer, e.g. ``data_dir("staged")``."""
    if kind not in DATA_KINDS:
        raise ValueError(f"Unknown data kind {kind!r}; expected one of {DATA_KINDS}")
    return data_root() / kind


def ensure_dirs() -> None:
    """Create the data directories if they don't exist."""
    for kind in DATA_KINDS:
        data_dir(kind).mkdir(parents=True, exist_ok=True)
