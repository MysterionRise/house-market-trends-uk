"""Loading of the YAML files in ``config/``."""

import yaml

from lix_core.paths import get_project_root


def get_config(name: str) -> dict:
    """Load a YAML config file from config/{name}.yaml."""
    config_path = get_project_root() / "config" / f"{name}.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)
