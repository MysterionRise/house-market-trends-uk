"""Shared utilities for the UK Liveability Index pipeline."""

import logging
from pathlib import Path

import yaml


def get_project_root() -> Path:
    """Return the project root directory (parent of src/)."""
    return Path(__file__).resolve().parent.parent


def get_config(name: str) -> dict:
    """Load a YAML config file from config/{name}.yaml."""
    config_path = get_project_root() / "config" / f"{name}.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    """Create data and output directories if they don't exist."""
    root = get_project_root()
    for d in ["data/raw", "data/processed", "outputs/maps"]:
        (root / d).mkdir(parents=True, exist_ok=True)


def setup_logging(name: str) -> logging.Logger:
    """Configure and return a logger with console output."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
