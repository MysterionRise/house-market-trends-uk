"""FastAPI app: REST under /api/v1, the assistant over AG-UI at /agent, MCP at /mcp.

    uv run lix-api                      # http://localhost:8000 (LIX_MODEL picks the LLM)
    LIX_MODEL=test uv run lix-api       # scripted assistant, no API key needed

In development /data serves data/serve/ (map tiles and the browser's score file); in
docker compose a static file server does that instead.
"""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_ai.ui import StateDeps
from pydantic_ai.ui.ag_ui import AGUIAdapter

from lix_api.agent.agent import agent
from lix_api.agent.state import LiveabilityState
from lix_api.mcp_server import mcp
from lix_api.models import (
    AreaProfile,
    Comparison,
    Explanation,
    IndicatorInfo,
    Level,
    Place,
    PoiResult,
    RankResult,
)
from lix_api.services import areas, catalogue, compare, explain, pois, ranking, search
from lix_api.services.sql import SqlError, get_guard
from lix_api.store import get_store

mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store().warm()
    async with mcp_app.lifespan(app):
        yield


app = FastAPI(
    title="UK Liveability Index API",
    version="0.1.0",
    description="Scores for England's neighbourhoods from open data. "
    "See /api/v1/sources for attribution.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("LIX_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LookupError)
async def not_found(request: Request, exc: LookupError):
    return Response(
        content=f'{{"detail": "{exc}"}}', status_code=404, media_type="application/json"
    )


@app.exception_handler(ValueError)
async def bad_request(request: Request, exc: ValueError):
    return Response(
        content=f'{{"detail": "{str(exc)}"}}', status_code=400, media_type="application/json"
    )


@app.get("/health")
def health() -> dict:
    store = get_store()
    return {"status": "ok", "lsoas": len(store.lsoa_index), "built": store.manifest["generated_at"]}


api = "/api/v1"


@app.get(f"{api}/search")
def search_place(q: str, limit: int = 8) -> list[Place]:
    return search.search_place(get_store(), q, limit=min(limit, 20))


@app.get(f"{api}/areas/{{ref}}")
def area_profile(ref: str, preset: str | None = None) -> AreaProfile:
    return areas.area_profile(get_store(), ref, preset=preset)


class RankRequest(BaseModel):
    within: str | None = None
    radius_km: float | None = None
    level: Level = "msoa"
    preset: str | None = None
    theme_weights: dict[str, float] | None = None
    indicator_weights: dict[str, float] | None = None
    max_median_price: float | None = None
    min_theme_scores: dict[str, float] | None = None
    urban: bool | None = None
    limit: int = 10


@app.post(f"{api}/rank")
def rank_areas(req: RankRequest) -> RankResult:
    return ranking.rank_areas(get_store(), **{**req.model_dump(), "limit": min(req.limit, 50)})


@app.get(f"{api}/compare")
def compare_areas(
    areas_: Annotated[list[str], Query(alias="areas")], preset: str | None = None
) -> Comparison:
    return compare.compare_areas(get_store(), areas_, preset=preset)


@app.get(f"{api}/pois")
def nearest_pois(category: str, near: str, max_km: float = 2.0, limit: int = 10) -> PoiResult:
    return pois.nearest_pois(get_store(), category, near, min(max_km, 20), min(limit, 50))


@app.get(f"{api}/explain/{{ref}}")
def explain_score(ref: str, theme: str | None = None, preset: str | None = None) -> Explanation:
    return explain.explain_score(get_store(), ref, theme=theme, preset=preset)


@app.get(f"{api}/indicators")
def list_indicators(theme: str | None = None) -> list[IndicatorInfo]:
    return catalogue.list_indicators(get_store(), theme)


@app.get(f"{api}/presets")
def presets() -> dict:
    return catalogue.presets(get_store())


@app.get(f"{api}/sources")
def sources() -> dict:
    return catalogue.sources(get_store())


@app.post(f"{api}/sql")
def run_sql(query: Annotated[str, Body(embed=True)]) -> dict:
    try:
        result = get_guard().run(query)
    except SqlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"columns": result.columns, "rows": result.rows, "truncated": result.truncated}


@app.post("/agent")
async def run_agent(request: Request) -> Response:
    """AG-UI endpoint: streams the assistant's messages, tool calls and state snapshots."""
    return await AGUIAdapter.dispatch_request(
        request, agent=agent, deps=StateDeps(LiveabilityState())
    )


app.mount("/mcp", mcp_app)
if os.environ.get("LIX_SERVE_DATA", "1") == "1":
    app.mount("/data", StaticFiles(directory=get_store().serve_dir, check_dir=False), name="data")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "lix_api.main:app",
        host=os.environ.get("LIX_HOST", "127.0.0.1"),
        port=int(os.environ.get("LIX_PORT", "8000")),
        reload=os.environ.get("LIX_RELOAD") == "1",
    )
