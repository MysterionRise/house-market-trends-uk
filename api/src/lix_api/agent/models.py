# ruff: noqa: E501 (the scripted model's rule table reads best unwrapped)
"""Which LLM drives the assistant, from the environment.

LIX_MODEL            provider:model, e.g. anthropic:claude-opus-5-5 (default),
                     openai:gpt-5, google:gemini-2.5-pro, ollama:llama3.1
                     (with OLLAMA_BASE_URL), or "test" for a scripted model that
                     needs no API key (end-to-end tests and demos)
LIX_FALLBACK_MODELS  comma-separated models to try if the first fails
LIX_EFFORT           reasoning effort for Anthropic models (default "low": the
                     assistant mostly picks and fills in tools)
"""

import json
import os
import re

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.settings import ModelSettings

DEFAULT_MODEL = "anthropic:claude-opus-5-5"


def model_name() -> str:
    return os.environ.get("LIX_MODEL", DEFAULT_MODEL)


def build_model() -> Model | str:
    name = model_name()
    if name == "test":
        return scripted_model()
    fallbacks = [
        m.strip() for m in os.environ.get("LIX_FALLBACK_MODELS", "").split(",") if m.strip()
    ]
    if fallbacks:
        from pydantic_ai.models import infer_model

        return FallbackModel(infer_model(name), *[infer_model(m) for m in fallbacks])
    return name


def model_settings() -> ModelSettings:
    """Provider-specific settings; ignored by providers they don't apply to."""
    settings: dict = {"max_tokens": 4000}
    if model_name().startswith("anthropic:"):
        # Tool definitions are the stable prefix (tools render before the system
        # prompt); per-turn state sits in the instructions after them
        settings["anthropic_cache_tool_definitions"] = True
        settings["anthropic_effort"] = os.environ.get("LIX_EFFORT", "low")
    return settings  # type: ignore[return-value]


# --- scripted model ------------------------------------------------------------------

_RULES: list[tuple[str, str, callable]] = [
    (r"\b(compare)\b(.+?)\band\b(.+)", "compare_areas",
     lambda m: {"areas": [m.group(2).strip(" ,"), m.group(3).strip(" ?.")]}),
    (r"\bwell[- ]run pubs?\b.*\b(?:near|in|around)\b (.+)", "nearest_pois",
     lambda m: {"category": "well_run_pub", "near": m.group(1).strip(" ?."), "max_km": 1.5}),
    (r"\b(family|young professional|retiree|retired|commuter|balanced)\b.*\bweights?\b|"
     r"\bweights?\b.*\b(family|young professional|retiree|retired|commuter|balanced)\b",
     "set_weights",
     lambda m: {"preset": (m.group(1) or m.group(2)).replace(" ", "_").replace("retired", "retiree")}),
    (r"\bwhy\b.*\b(?:in|for|of)\b (.+)", "explain_score",
     lambda m: {"area": m.group(1).strip(" ?.")}),
    (r"\b(?:best|top|rank)\b.*\b(?:in|near|around)\b ([A-Za-z][\w' -]+?)(?: under £?([\d,]+)k?)?[?.]?$",
     "rank_areas",
     lambda m: {"within": m.group(1).strip(), "level": "msoa", "limit": 5,
                **({"max_median_price": float(m.group(2).replace(",", "")) * (1000 if len(m.group(2)) <= 4 else 1)}
                   if m.group(2) else {})}),
    (r"\b(?:tell me about|profile|what is|how is)\b (.+)", "get_area_profile",
     lambda m: {"area": m.group(1).strip(" ?.")}),
]  # fmt: skip


def _scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Deterministic stand-in for an LLM: one tool call per matching request, then a summary."""
    last = messages[-1]
    returns = [p for p in last.parts if isinstance(p, ToolReturnPart)]
    if returns:
        names = ", ".join(p.tool_name for p in returns)
        return ModelResponse(parts=[TextPart(f"Here's what I found ({names}).")])
    prompt = next((p.content for p in last.parts if isinstance(p, UserPromptPart)), "")
    text = prompt if isinstance(prompt, str) else json.dumps(prompt)
    available = {t.name for t in info.function_tools}
    for pattern, tool, args in _RULES:
        m = re.search(pattern, text, flags=re.I)
        if m and tool in available:
            return ModelResponse(parts=[ToolCallPart(tool, args(m))])
    return ModelResponse(
        parts=[TextPart("Ask me to rank areas, profile a place, compare two areas, "
                        "find well-run pubs or change the weights.")]
    )  # fmt: skip


async def _scripted_stream(messages: list[ModelMessage], info: AgentInfo):
    """Streaming form of the scripted model (AG-UI always streams)."""
    response = _scripted(messages, info)
    for part in response.parts:
        if isinstance(part, TextPart):
            for word in part.content.split(" "):
                yield word + " "
        elif isinstance(part, ToolCallPart):
            yield {0: DeltaToolCall(name=part.tool_name, json_args=json.dumps(part.args))}


def scripted_model() -> FunctionModel:
    return FunctionModel(_scripted, stream_function=_scripted_stream, model_name="scripted")
