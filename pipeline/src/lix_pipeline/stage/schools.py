"""Schools: every open establishment (GIAS) and a blended inspection quality per school.

Ofsted changed frameworks twice in two years:

- to Sept 2024: graded inspections with an overall grade (1 Outstanding … 4 Inadequate)
- Sept 2024 – Nov 2025: graded sub-judgements but overall effectiveness "Not judged"
- from Nov 2025: report cards grading each area on a five-point scale

so each school is scored from whichever is newest, on one 0–1 scale, and the score
fades towards the national middle as the inspection ages (some "Outstanding" grades
are over a decade old). The scale is a modelling choice documented in methodology.md.
"""

from datetime import date

import polars as pl

from lix_core.codes import ENGLAND_LSOA21
from lix_core.log import setup_logging
from lix_core.paths import data_dir
from lix_pipeline.geo.joins import points_to_lsoa

logger = setup_logging("stage.schools")

REPORT_CARD_SCALE = {
    "Exceptional": 1.0,
    "Strong standard": 0.8,
    "Expected standard": 0.6,
    "Needs attention": 0.35,
    "Urgent improvement": 0.1,
}
REPORT_CARD_AREAS = {
    "Inclusion": "rc_inclusion",
    "Curriculum and teaching": "rc_curriculum_teaching",
    "Achievement": "rc_achievement",
    "Attendance and behaviour": "rc_attendance_behaviour",
    "Personal development and wellbeing": "rc_personal_development",
    "Leadership and governance": "rc_leadership",
}
# Legacy grades: 1 Outstanding, 2 Good, 3 Requires improvement, 4 Inadequate
OEIF_SCALE = {"1": 0.95, "2": 0.7, "3": 0.4, "4": 0.15}
OEIF_SUB = {
    "Latest OEIF quality of education": "oeif_quality_of_education",
    "Latest OEIF behaviour and attitudes": "oeif_behaviour",
    "Latest OEIF personal development": "oeif_personal_development",
    "Latest OEIF effectiveness of leadership and management": "oeif_leadership",
}
# Later ungraded inspections nudge the last graded result
UNGRADED_ADJUSTMENT = {
    "Improved significantly": 0.1,
    "School remains Good (Improving) - S5 Next": 0.05,
    "School remains Outstanding (Concerns) - S5 Next": -0.1,
    "School remains Good (Concerns) - S5 Next": -0.1,
    "Standards maintained": 0.0,
    "School remains Good": 0.0,
    "School remains Outstanding": 0.0,
}
NEUTRAL = 0.6  # "expected standard"
HALF_LIFE_YEARS = 6.0

SCHOOL_TYPES_EXCLUDED = ("Welsh schools", "Universities", "Online provider")


def stage_gias() -> pl.LazyFrame:
    """Open schools and colleges in England with phase, ages, size and location."""
    raw = pl.read_csv(
        data_dir("raw") / "gias" / "gias.csv", encoding="cp1252", infer_schema_length=0
    )
    df = raw.filter(
        pl.col("EstablishmentStatus (name)").str.starts_with("Open")
        & ~pl.col("EstablishmentTypeGroup (name)").is_in(SCHOOL_TYPES_EXCLUDED)
        & (pl.col("Easting").str.len_chars() > 0)
    ).select(
        pl.col("URN").cast(pl.Int64).alias("urn"),
        pl.col("EstablishmentName").alias("name"),
        pl.col("PhaseOfEducation (name)").alias("phase"),
        pl.col("TypeOfEstablishment (name)").alias("type"),
        pl.col("EstablishmentTypeGroup (name)").alias("type_group"),
        pl.col("StatutoryLowAge").cast(pl.Int16, strict=False).alias("low_age"),
        pl.col("StatutoryHighAge").cast(pl.Int16, strict=False).alias("high_age"),
        pl.col("Gender (name)").alias("gender"),
        pl.col("AdmissionsPolicy (name)").alias("admissions_policy"),
        pl.col("NurseryProvision (name)").alias("nursery_provision"),
        pl.col("OfficialSixthForm (name)").alias("sixth_form"),
        pl.col("SchoolCapacity").cast(pl.Int32, strict=False).alias("capacity"),
        pl.col("NumberOfPupils").cast(pl.Int32, strict=False).alias("pupils"),
        pl.col("Postcode").alias("postcode"),
        pl.col("Easting").cast(pl.Float64).alias("x"),
        pl.col("Northing").cast(pl.Float64).alias("y"),
    )
    # GIAS carries an LSOA code, but recompute it so the vintage is certainly 2021
    df = points_to_lsoa(df).filter(pl.col("lsoa21cd").str.contains(ENGLAND_LSOA21))
    logger.info(f"{df.height:,} open schools and colleges in England")
    return df.lazy()


def _date(col: str) -> pl.Expr:
    return pl.col(col).replace("NULL", None).str.to_date("%d/%m/%Y", strict=False)


def _grade(col: str, scale: dict[str, float]) -> pl.Expr:
    return pl.col(col).replace_strict(scale, default=None, return_dtype=pl.Float64)


def school_quality(df: pl.DataFrame, as_of: date) -> pl.DataFrame:
    """Add ``quality`` (0–1), ``framework`` and ``inspection_date`` to staged Ofsted rows."""
    rc_cols = list(REPORT_CARD_AREAS.values())
    sub_cols = list(OEIF_SUB.values())
    df = df.with_columns(
        pl.mean_horizontal(rc_cols).alias("_rc"),
        pl.mean_horizontal(sub_cols).alias("_sub"),
    )
    base = (
        pl.when(pl.col("_rc").is_not_null())
        .then(
            # Unmet safeguarding outweighs everything else
            pl.when(pl.col("rc_safeguarding_met") == False)  # noqa: E712
            .then(pl.min_horizontal(pl.col("_rc"), pl.lit(0.2)))
            .otherwise(pl.col("_rc"))
        )
        .when(pl.col("oeif_overall").is_not_null())
        .then(pl.col("oeif_overall"))
        .otherwise(pl.col("_sub"))
    )
    framework = (
        pl.when(pl.col("_rc").is_not_null())
        .then(pl.lit("report_card"))
        .when(pl.col("oeif_overall").is_not_null())
        .then(pl.lit("oeif"))
        .when(pl.col("_sub").is_not_null())
        .then(pl.lit("oeif_not_judged"))
    )
    graded_date = pl.when(pl.col("_rc").is_not_null()).then("rc_date").otherwise("oeif_date")
    # An ungraded inspection only counts if it came after the graded one
    later_ungraded = pl.col("ungraded_date") > graded_date
    adjust = (
        pl.when(later_ungraded & pl.col("_rc").is_null())
        .then(pl.col("ungraded_outcome").replace_strict(UNGRADED_ADJUSTMENT, default=0.0))
        .otherwise(0.0)
    )
    inspected = pl.when(later_ungraded).then("ungraded_date").otherwise(graded_date)
    age_years = (pl.lit(as_of) - inspected).dt.total_days() / 365.25
    fade = (2.0 ** (-age_years / HALF_LIFE_YEARS)).fill_null(0.0)
    quality = (NEUTRAL + ((base + adjust).clip(0, 1) - NEUTRAL) * fade).clip(0, 1)
    return df.with_columns(
        quality.alias("quality"),
        framework.alias("framework"),
        inspected.alias("inspection_date"),
        age_years.alias("inspection_age_years"),
    ).drop("_rc", "_sub")


def stage_ofsted_schools(as_of: date | None = None) -> pl.LazyFrame:
    """Latest inspection per state-funded school with a blended quality score."""
    raw = pl.read_csv(
        data_dir("raw") / "ofsted_schools" / "ofsted_schools.csv",
        infer_schema_length=0,
        encoding="utf8-lossy",
    )
    rc_dates = [f"{label} - date of grade" for label in REPORT_CARD_AREAS]
    df = raw.select(
        pl.col("URN").cast(pl.Int64).alias("urn"),
        pl.col("Ofsted phase").alias("ofsted_phase"),
        *[
            _grade(label, REPORT_CARD_SCALE).alias(name)
            for label, name in REPORT_CARD_AREAS.items()
        ],
        pl.col("Safeguarding standards")
        .replace({"NULL": None})
        .eq("Met")
        .alias("rc_safeguarding_met"),
        pl.max_horizontal(_date(c) for c in rc_dates).alias("rc_date"),
        _grade("Latest OEIF overall effectiveness", OEIF_SCALE).alias("oeif_overall"),
        *[_grade(label, OEIF_SCALE).alias(name) for label, name in OEIF_SUB.items()],
        _date("Inspection start date of latest OEIF graded inspection").alias("oeif_date"),
        pl.col("Ungraded inspection overall outcome")
        .replace("NULL", None)
        .alias("ungraded_outcome"),
        _date("Date of latest ungraded inspection").alias("ungraded_date"),
        pl.col("Category of concern").replace("NULL", None).alias("category_of_concern"),
    )
    df = school_quality(df, as_of or date.today())
    summary = df.group_by("framework").agg(pl.len(), pl.col("quality").mean().round(3))
    logger.info(f"{df.height:,} inspected schools; by framework: {summary.rows()}")
    return df.lazy()
