"""police.uk street-level crime → counts per LSOA, crime type and force.

The archive holds the latest 36 months, but forces don't all report every month
(Gloucestershire stopped in January 2026; Greater Manchester Police hasn't reported
since 2019). Each row therefore carries ``force_months``, the number of months its
force reported, so rates can be annualised fairly. British Transport Police records
crime on the railway rather than where people live, so it is excluded.
"""

import duckdb
import polars as pl

from lix_core.codes import area_code_regex
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("stage.police")

EXCLUDED_FORCES = ("British Transport Police",)


def stage_police() -> pl.LazyFrame:
    files = str(data_dir("raw") / "police_crime" / "*" / "*-street.csv")
    con = duckdb.connect()
    con.execute("SET VARIABLE files = ?", [files])
    df = con.execute(
        """
        WITH crimes AS (
            SELECT "LSOA code" AS lsoa21cd, "Crime type" AS crime_type,
                   "Reported by" AS force, "Month" AS month
            FROM read_csv(getvariable('files'), union_by_name = true, all_varchar = true)
            WHERE "Reported by" NOT IN (SELECT unnest(?::VARCHAR[]))
        ),
        force_months AS (
            SELECT force, count(DISTINCT month) AS force_months,
                   min(month) AS first_month, max(month) AS last_month
            FROM crimes GROUP BY force
        )
        SELECT c.lsoa21cd, c.crime_type, c.force, count(*) AS n,
               f.force_months, f.first_month, f.last_month
        FROM crimes c JOIN force_months f USING (force)
        WHERE regexp_matches(c.lsoa21cd, ?)
        GROUP BY ALL
        ORDER BY c.lsoa21cd, c.crime_type, c.force
        """,
        [list(EXCLUDED_FORCES), area_code_regex()],
    ).pl()
    con.close()

    short = (
        df.select("force", "force_months", "last_month")
        .unique()
        .filter(pl.col("force_months") < pl.col("force_months").max())
    )
    for row in short.iter_rows(named=True):
        logger.warning(
            f"{row['force']} reported only {row['force_months']} months (last {row['last_month']})"
        )
    logger.info(f"{df['n'].sum():,} crimes in {df['lsoa21cd'].n_unique():,} LSOAs")
    return df.with_columns(pl.col("n").cast(pl.Int32), pl.col("force_months").cast(pl.Int16)).lazy()
