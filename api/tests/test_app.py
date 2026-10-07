"""HTTP, AG-UI and MCP tests against the synthetic store."""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(store):
    from lix_api.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json()["lsoas"] == 6


def test_rest_routes(client):
    assert client.get("/api/v1/search", params={"q": "LS6 3HN"}).json()[0]["kind"] == "postcode"
    assert client.get("/api/v1/areas/LS6 3HN").json()["neighbourhood"] == "Headingley"
    r = client.post("/api/v1/rank", json={"within": "Leeds", "level": "lsoa", "limit": 2})
    assert len(r.json()["results"]) == 2
    assert (
        client.get(
            "/api/v1/compare", params=[("areas", "LS6 3HN"), ("areas", "BN2 9QA")]
        ).status_code
        == 200
    )
    assert client.get("/api/v1/pois", params={"category": "gp", "near": "LS6 3HN"}).json()["pois"]
    assert client.get("/api/v1/presets").json()["default"] == "balanced"


def test_errors_map_to_status_codes(client):
    assert client.get("/api/v1/areas/Nowheresville XYZ").status_code == 404
    assert client.post("/api/v1/rank", json={"preset": "hermit"}).status_code == 400
    r = client.post("/api/v1/sql", json={"query": "COPY lsoa TO '/tmp/x'"})
    assert r.status_code == 400 and "SELECT" in r.json()["detail"]


def _agui(client, text: str, state: dict | None = None) -> list[dict]:
    body = {
        "threadId": "t", "runId": "r", "state": state or {"preset": "balanced"},
        "messages": [{"id": "m1", "role": "user", "content": text}],
        "tools": [], "context": [], "forwardedProps": {},
    }  # fmt: skip
    events = []
    with client.stream("POST", "/agent", json=body, headers={"accept": "text/event-stream"}) as r:
        for line in r.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    return events


def test_agent_streams_tool_result_and_state(client):
    events = _agui(client, "Use family weights please")
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert "RUN_ERROR" not in types
    start = next(e for e in events if e["type"] == "TOOL_CALL_START")
    assert start["toolCallName"] == "set_weights"
    snapshot = next(e for e in events if e["type"] == "STATE_SNAPSHOT")["snapshot"]
    assert snapshot["preset"] == "family"


def test_agent_ranking_highlights_map(client):
    events = _agui(client, "What are the best areas in Leeds?")
    result = json.loads(next(e for e in events if e["type"] == "TOOL_CALL_RESULT")["content"])
    snapshot = next(e for e in events if e["type"] == "STATE_SNAPSHOT")["snapshot"]
    assert snapshot["map"]["highlighted"] == [r["code"] for r in result["results"]]


def test_sql_tool_only_in_analyst_mode(store):
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel
    from pydantic_ai.ui import StateDeps

    from lix_api.agent.agent import agent
    from lix_api.agent.state import LiveabilityState

    seen: dict[str, set[str]] = {}

    def record(messages, info: AgentInfo):
        seen["tools"] = {t.name for t in info.function_tools}
        return ModelResponse(parts=[TextPart("ok")])

    model = FunctionModel(record)
    agent.run_sync("hi", model=model, deps=StateDeps(LiveabilityState(mode="consumer")))
    assert "run_sql" not in seen["tools"]
    agent.run_sync("hi", model=model, deps=StateDeps(LiveabilityState(mode="analyst")))
    assert "run_sql" in seen["tools"]


async def test_mcp_lists_and_calls_tools(store):
    from fastmcp import Client

    from lix_api.mcp_server import mcp

    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
        assert {"search_place", "get_area_profile", "rank_areas", "explain_score"} <= names
        result = await c.call_tool("get_area_profile", {"area": "LS6 3HN"})
        assert result.structured_content["neighbourhood"] == "Headingley"
