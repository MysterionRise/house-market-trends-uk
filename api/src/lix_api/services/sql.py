"""Read-only SQL over the index's tables, for analyst mode.

Guards: a separate in-memory DuckDB holding copies of the public tables, with file and
network access disabled and configuration locked; exactly one SELECT statement; a row
cap; and a timeout that interrupts long queries.
"""

import threading
from dataclasses import dataclass

import duckdb
import polars as pl

from lix_api.store import Store

MAX_ROWS = 5000
TIMEOUT_S = 10.0

TABLES = {
    "lsoa": "Every LSOA in the build: geography (incl. nation), raw__/n__/q__ per indicator, "
    "default scores with country-wide and within-nation percentiles",
    "pois": "Points of interest: category, name, lat, lon, source, licence, detail (JSON)",
    "areas": "MSOAs, local authorities, regions and nations with population and bounding box",
    "places": "Settlements from OS Open Names with their LSOA",
    "indicators": "The indicator catalogue",
}


class SqlError(ValueError):
    pass


@dataclass
class SqlResult:
    columns: list[str]
    rows: list[list]
    truncated: bool


class SqlGuard:
    def __init__(self, store: Store) -> None:
        self.con = duckdb.connect(":memory:")
        catalogue = pl.DataFrame(
            [i.model_dump(exclude={"params"}) for i in store.indicators.values()]
        )
        frames = {
            "lsoa": store.features,
            "pois": store.pois.drop("x", "y"),
            "areas": store.areas,
            "places": store.places,
            "indicators": catalogue,
        }
        for name, df in frames.items():
            self.con.register(f"_{name}", df.to_arrow())
            self.con.execute(f"CREATE TABLE {name} AS SELECT * FROM _{name}")
            self.con.unregister(f"_{name}")
        self.con.execute("SET memory_limit = '1GB'")
        self.con.execute("SET enable_external_access = false")
        self.con.execute("SET lock_configuration = true")
        self.lock = threading.Lock()

    def run(self, sql: str, max_rows: int = MAX_ROWS, timeout_s: float = TIMEOUT_S) -> SqlResult:
        try:
            statements = self.con.extract_statements(sql)
        except duckdb.Error as e:
            raise SqlError(f"Couldn't parse the query: {e}") from e
        if len(statements) != 1:
            raise SqlError("Send exactly one statement")
        if statements[0].type != duckdb.StatementType.SELECT:
            raise SqlError("Only SELECT queries are allowed")

        body = sql.strip().rstrip(";")
        wrapped = f"SELECT * FROM ({body}) AS q LIMIT {max_rows + 1}"
        with self.lock:  # one connection, one query at a time
            timer = threading.Timer(timeout_s, self.con.interrupt)
            timer.start()
            try:
                result = self.con.execute(wrapped)
                columns = [d[0] for d in result.description]
                rows = result.fetchall()
            except duckdb.InterruptException as e:
                raise SqlError(f"Query took longer than {timeout_s:g}s") from e
            except duckdb.Error as e:
                raise SqlError(str(e).split("\n")[0]) from e
            finally:
                timer.cancel()
        truncated = len(rows) > max_rows
        return SqlResult(
            columns=columns,
            rows=[[_jsonable(v) for v in row] for row in rows[:max_rows]],
            truncated=truncated,
        )


def _jsonable(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return str(v)


_guard: SqlGuard | None = None


def get_guard() -> SqlGuard:
    """The shared guard over the current store (built on first use, ~1 s)."""
    global _guard
    if _guard is None:
        from lix_api.store import get_store

        _guard = SqlGuard(get_store())
    return _guard
