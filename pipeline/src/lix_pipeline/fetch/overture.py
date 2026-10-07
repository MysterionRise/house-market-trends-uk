"""Overture Maps: query a release in place with DuckDB (httpfs), save the rows as Parquet.

Releases live under s3://overturemaps-us-west-2/release/<YYYY-MM-DD.n>/ and are listed
through the bucket's public HTTPS endpoint; the newest is used unless one is pinned.
Row groups carry bbox statistics, so a bounding-box filter reads a small part of the
global files.
"""

import re
from pathlib import Path

import requests

from lix_core.config import OvertureAccess

BUCKET_HTTPS = "https://overturemaps-us-west-2.s3.amazonaws.com"
BUCKET_S3 = "s3://overturemaps-us-west-2"


def latest_release(session: requests.Session) -> str:
    resp = session.get(
        BUCKET_HTTPS, params={"list-type": "2", "prefix": "release/", "delimiter": "/"}, timeout=60
    )
    resp.raise_for_status()
    releases = re.findall(r"<Prefix>release/(\d{4}-\d{2}-\d{2}\.\d+)/</Prefix>", resp.text)
    if not releases:
        raise RuntimeError("No Overture releases listed")
    return max(releases, key=lambda r: (r.split(".")[0], int(r.split(".")[1])))


def resolve_query(access: OvertureAccess, session: requests.Session) -> dict:
    release = access.release or latest_release(session)
    url = f"{BUCKET_S3}/release/{release}/theme={access.theme}/type={access.kind}/*"
    return {"url": url, "version": release}


def build_sql(access: OvertureAccess, url: str) -> str:
    xmin, ymin, xmax, ymax = access.bbox
    where = [
        f"bbox.xmin BETWEEN {xmin} AND {xmax}",
        f"bbox.ymin BETWEEN {ymin} AND {ymax}",
    ]
    if access.where:
        where.append(f"({access.where})")
    return (
        f"SELECT {', '.join(access.select)} "
        f"FROM read_parquet('{url}', hive_partitioning=1) WHERE {' AND '.join(where)}"
    )


def fetch_query(access: OvertureAccess, url: str, out_path: Path) -> int:
    """Run the query and write the rows to ``out_path`` (Parquet); returns the row count."""
    import duckdb

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".part.parquet")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    con.execute(f"COPY ({build_sql(access, url)}) TO '{tmp}' (FORMAT parquet)")
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{tmp}')").fetchone()[0]
    tmp.replace(out_path)
    return rows
