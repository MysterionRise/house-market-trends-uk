"""config/datasets.lock.json: which concrete file each dataset slug resolved to.

Committed to git, so a build records exactly which source versions it used and a
diff shows when an upstream file changed. Per slug it holds:

- ``resolved``: URL plus version info from ``lix resolve`` (item id, title, modified, ...)
- ``fetched``: sha256, size and validators of the last successful ``lix fetch``
"""

import json
from pathlib import Path

from lix_core.paths import get_project_root


def lock_path() -> Path:
    return get_project_root() / "config" / "datasets.lock.json"


def read_lock() -> dict[str, dict]:
    path = lock_path()
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def write_lock(lock: dict[str, dict]) -> None:
    path = lock_path()
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(dict(sorted(lock.items())), f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def update_entry(slug: str, section: str, values: dict) -> None:
    """Replace one section ("resolved" or "fetched") of a slug's lock entry."""
    lock = read_lock()
    lock.setdefault(slug, {})[section] = values
    write_lock(lock)
