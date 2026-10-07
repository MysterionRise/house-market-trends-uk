"""Limits and a log for live assistant runs.

Every AG-UI run is capped (model requests, tool calls, tokens and, where the provider
reports it, cost) and appended to data/logs/agent.jsonl: the model, the tools it
called, latency and usage. That log is how a demo's cost and behaviour are checked.

LIX_REQUEST_LIMIT    model requests per turn (default 8)
LIX_TOOL_CALL_LIMIT  tool calls per turn (default 12)
LIX_TOKEN_LIMIT      total tokens per turn (default 150,000)
LIX_COST_LIMIT       cost per turn in the provider's currency, e.g. 0.50 (OpenRouter)
"""

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.usage import UsageLimits

from lix_api.agent.models import model_name
from lix_core.log import setup_logging
from lix_core.paths import data_dir

logger = setup_logging("agent")


def usage_limits() -> UsageLimits:
    cost = os.environ.get("LIX_COST_LIMIT")
    return UsageLimits(
        request_limit=int(os.environ.get("LIX_REQUEST_LIMIT", 8)),
        tool_calls_limit=int(os.environ.get("LIX_TOOL_CALL_LIMIT", 12)),
        total_tokens_limit=int(os.environ.get("LIX_TOKEN_LIMIT", 150_000)),
        cost_limit=Decimal(cost) if cost else None,
    )


def run_record(result, started: float) -> dict:
    """One JSON-able line describing a finished run."""
    messages = result.new_messages()
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    tools = [p.tool_name for m in responses for p in m.parts if isinstance(p, ToolCallPart)]
    usage = result.usage() if callable(result.usage) else result.usage
    cost = getattr(usage, "cost", None)
    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model_name(),
        "models": sorted({m.model_name for m in responses if m.model_name}),
        "tools": tools,
        "requests": usage.requests,
        "input_tokens": usage.input_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "output_tokens": usage.output_tokens,
        "cost": float(cost) if cost is not None else None,
        "seconds": round(time.monotonic() - started, 2),
    }


def log_run(result, started: float, path: Path | None = None) -> None:
    """Append the run to the JSONL log; never let logging break a reply."""
    try:
        record = run_record(result, started)
        path = path or data_dir("logs") / "agent.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")
        logger.info(
            f"turn: {record['tools'] or 'no tools'} in {record['seconds']}s, "
            f"{record['input_tokens']}+{record['output_tokens']} tokens"
            + (f", cost {record['cost']:.4f}" if record["cost"] is not None else "")
        )
    except Exception:  # pragma: no cover - logging must not fail a run
        logger.exception("Couldn't log the assistant run")
