"""Census 2021 topic summaries (Nomis bulk files) → one tidy table per topic.

Bulk files label columns like "Tenure of household: Owned: Owns outright" or
"Residence type: Total; measures: Value". Labels become snake_case names without the
topic prefix (``owned_owns_outright``); the all-categories column becomes ``total``.
Values are counts (density is persons/km²). Census counts are perturbed for
disclosure control, so use shares of ``total`` rather than small raw counts.
"""

import re

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.census")


def census_column_name(label: str) -> str:
    """'Tenure of household: Owned: Owns outright' → 'owned_owns_outright'."""
    label = label.replace("; measures: Value", "")
    parts = [p.strip() for p in label.split(":")]
    rest = parts[1:] if len(parts) > 1 else parts
    if rest[0].lower() == "total":
        return "total"
    name = "_".join(rest).lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return name


def stage_census_table(slug: str) -> pl.LazyFrame:
    """Stage one census_tsNNN table at LSOA level for England."""
    files = sorted((data_dir("raw") / slug).glob("*-lsoa.csv"))
    if not files:
        raise FileNotFoundError(f"No LSOA file for {slug}")
    df = pl.read_csv(files[0], infer_schema_length=0)

    rename = {"geography code": "lsoa21cd"}
    seen: dict[str, int] = {}
    for col in df.columns:
        if col in ("date", "geography", "geography code"):
            continue
        name = census_column_name(col)
        if name in seen:  # keep names unique if two labels collapse to the same slug
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        rename[col] = name

    out = (
        df.select(list(rename))
        .rename(rename)
        .filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
        .with_columns(pl.exclude("lsoa21cd").cast(pl.Float64))
        .sort("lsoa21cd")
    )
    logger.info(f"[{slug}] {out.height:,} LSOAs, {out.width - 1} measures")
    return out.lazy()
