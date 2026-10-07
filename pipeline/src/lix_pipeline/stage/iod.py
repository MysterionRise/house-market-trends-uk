"""English Indices of Deprivation 2025 → one row per England LSOA."""

import re
from pathlib import Path

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.iod")

# IoD 2025 File 7 column labels (before " Score", " Rank", " Decile") → output prefix
IOD_DOMAINS = {
    "Index of Multiple Deprivation (IMD)": "imd",
    "Income": "income",
    "Employment": "employment",
    "Education, Skills and Training": "education",
    "Health Deprivation and Disability": "health",
    "Crime": "crime",
    "Barriers to Housing and Services": "barriers",
    "Living Environment": "living_env",
    "Income Deprivation Affecting Children Index (IDACI)": "idaci",
    "Income Deprivation Affecting Older People (IDAOPI)": "idaopi",
    "Children and Young People Sub-domain": "sub_children_young_people",
    "Adult Skills Sub-domain": "sub_adult_skills",
    "Geographical Barriers Sub-domain": "sub_geographical_barriers",
    "Wider Barriers Sub-domain": "sub_wider_barriers",
    "Indoors Sub-domain": "sub_indoors",
    "Outdoors Sub-domain": "sub_outdoors",
}
IOD_MEASURES = {"Score": "score", "Rank": "rank", "Decile": "decile"}
IOD_ID_COLUMNS = {
    # 2021 only: a 2011-based file must not silently pass as LSOA21
    r"^LSOA code \(2021\)$": "lsoa21cd",
    r"^LSOA name \(2021\)$": "lsoa21nm",
    r"^Local Authority District code \(\d{4}\)$": "lad_cd",
    r"^Local Authority District name \(\d{4}\)$": "lad_nm",
}
IOD_POPULATION = {
    "Total population": "pop_total",
    "Dependent Children aged 0-15": "pop_children_0_15",
    "Older population aged 60 and over": "pop_60_plus",
    "Working age population 18-66": "pop_working_age",
}


def _iod_rename_map(columns: list[str]) -> dict[str, str]:
    """Map IoD 2025 File 7 headers to snake_case names.

    Matches on label prefixes rather than full headers, because some headers are
    truncated in the published file (e.g. "...most deprived 10% of LSO").
    """
    rename = {}
    for col in columns:
        name = col.strip()
        for pattern, out in IOD_ID_COLUMNS.items():
            if re.match(pattern, name):
                rename[col] = out
        for label, prefix in IOD_DOMAINS.items():
            for measure, suffix in IOD_MEASURES.items():
                if name.startswith(f"{label} {measure}"):
                    rename[col] = f"{prefix}_{suffix}"
        for label, out in IOD_POPULATION.items():
            if name.startswith(label):
                rename[col] = out
    return rename


def stage_iod(raw_path: Path | None = None) -> pl.LazyFrame:
    """Clean English Indices of Deprivation 2025 (File 7: all ranks, scores, deciles).

    Keeps every domain and sub-domain plus the mid-2022 population denominators.
    """
    if raw_path is None:
        raw_dir = data_dir("raw") / "iod_2025"
        csv_files = sorted(raw_dir.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No IoD data files found in {raw_dir}")
        raw_path = csv_files[0]

    logger.info(f"Reading IoD data from {raw_path}")
    df = pl.read_csv(raw_path, infer_schema_length=0)

    rename = _iod_rename_map(df.columns)
    if "lsoa21cd" not in rename.values():
        raise ValueError(f"No 'LSOA code (2021)' column in IoD file; header: {df.columns}")
    unmapped = [c for c in df.columns if c not in rename]
    if unmapped:
        logger.warning(f"Ignoring unrecognised IoD columns: {unmapped}")

    df = df.select(list(rename)).rename(rename)
    numeric = {
        c: pl.Int32 if c.endswith(("_rank", "_decile")) or c.startswith("pop_") else pl.Float64
        for c in df.columns
        if c not in IOD_ID_COLUMNS.values()
    }
    df = df.with_columns(pl.col(c).cast(t) for c, t in numeric.items())
    df = df.filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))

    logger.info(f"IoD cleaned: {len(df):,} LSOAs, {len(df.columns)} columns")
    return df.lazy()
