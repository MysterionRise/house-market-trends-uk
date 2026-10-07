"""Nomis API (ONS labour market statistics): paged CSV queries.

Nomis answers at most 25,000 rows per request, so a query is fetched page by page
with ``recordoffset`` and written out as one CSV.
"""

import csv
import io
from pathlib import Path
from urllib.parse import urlencode

import requests

from lix_core.config import NomisAccess

API = "https://www.nomisweb.co.uk/api/v01/dataset"


def query_url(access: NomisAccess) -> str:
    return f"{API}/{access.dataset}.data.csv?{urlencode(access.params)}"


def resolve_query(access: NomisAccess, session: requests.Session) -> dict:
    """The query URL, versioned by the period it currently returns (e.g. "August 2026")."""
    params = {**access.params, "select": "date_name", "recordlimit": "1"}
    resp = session.get(f"{API}/{access.dataset}.data.csv", params=params, timeout=(30, 120))
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    if not rows:
        raise RuntimeError(f"Nomis {access.dataset} returned no rows for {access.params}")
    return {"url": query_url(access), "version": rows[0]["DATE_NAME"]}


def fetch_query(access: NomisAccess, out_path: Path, session: requests.Session) -> int:
    """Download every page of the query into ``out_path``; returns the number of rows."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".part")
    total = 0
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        offset = 0
        while True:
            params = {
                **access.params,
                "recordoffset": str(offset),
                "recordlimit": str(access.page_size),
            }
            resp = session.get(f"{API}/{access.dataset}.data.csv", params=params, timeout=(30, 300))
            resp.raise_for_status()
            lines = resp.text.splitlines(keepends=True)
            if not lines:
                break
            header, body = lines[0], lines[1:]
            if offset == 0:
                f.write(header)
            f.writelines(body)
            total += len(body)
            if len(body) < access.page_size:
                break
            offset += access.page_size
    tmp.replace(out_path)
    return total
