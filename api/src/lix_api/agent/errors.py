"""Failed assistant runs become a plain chat message, not an error banner.

AG-UI's default turns any exception into RUN_ERROR, which CopilotKit shows as a red
toast with the raw exception text. Here the user gets a short explanation of what to
do (as an assistant message) and the run finishes normally; the real error is logged.
"""

import asyncio
from collections.abc import AsyncIterator

from ag_ui.core import (
    BaseEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from pydantic_ai.exceptions import (
    FallbackExceptionGroup,
    ModelAPIError,
    ModelHTTPError,
    ToolRetryError,
    UsageLimitExceeded,
)
from pydantic_ai.ui.ag_ui import AGUIAdapter, AGUIEventStream

from lix_api.agent.messages import message
from lix_core.log import setup_logging

logger = setup_logging("agent.errors")


def friendly_message(error: BaseException, locale: str = "en") -> str:
    """What to tell the user about a failed run, in the page's language."""
    if isinstance(error, FallbackExceptionGroup) and error.exceptions:
        # Every model failed; explain the first model's problem
        return friendly_message(error.exceptions[0], locale)
    if isinstance(error, UsageLimitExceeded):
        key = "usage_limit"
    elif isinstance(error, ToolRetryError):
        key = "tool_retry"
    elif isinstance(error, ModelHTTPError):
        key = {401: "key_rejected", 403: "key_rejected", 402: "out_of_credit", 429: "busy"}.get(
            error.status_code, "model_problem"
        )
    elif isinstance(error, (ModelAPIError, TimeoutError, asyncio.TimeoutError, ConnectionError)):
        key = "no_response"
    else:
        key = "unknown"
    return message(key, locale)


def _locale(run_input) -> str:
    """The page's language from the AG-UI state it sent with the run."""
    state = getattr(run_input, "state", None)
    locale = state.get("locale") if isinstance(state, dict) else getattr(state, "locale", None)
    return locale if isinstance(locale, str) else "en"


class FriendlyEventStream(AGUIEventStream):
    async def on_error(self, error: Exception) -> AsyncIterator[BaseEvent]:
        logger.error(f"Assistant run failed: {type(error).__name__}: {error}")
        self._error = True  # after_stream then adds nothing; we finish the run here
        message_id = self.new_message_id()
        yield TextMessageStartEvent(message_id=message_id, role="assistant")
        yield TextMessageContentEvent(
            message_id=message_id, delta=friendly_message(error, _locale(self.run_input))
        )
        yield TextMessageEndEvent(message_id=message_id)
        yield RunFinishedEvent(
            thread_id=self.thread_id, run_id=self.run_id, timestamp=self._get_timestamp()
        )


class FriendlyAGUIAdapter(AGUIAdapter):
    def build_event_stream(self) -> FriendlyEventStream:
        return FriendlyEventStream(
            self.run_input, accept=self.accept, ag_ui_version=self.ag_ui_version
        )
