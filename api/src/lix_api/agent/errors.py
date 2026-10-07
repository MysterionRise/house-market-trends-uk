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

from lix_core.log import setup_logging

logger = setup_logging("agent.errors")

STILL_WORKS = "The map, weights and area pages still work."


def friendly_message(error: BaseException) -> str:
    """What to tell the user about a failed run."""
    if isinstance(error, FallbackExceptionGroup) and error.exceptions:
        # Every model failed; explain the first model's problem
        return friendly_message(error.exceptions[0])
    if isinstance(error, UsageLimitExceeded):
        return (
            "That needed more steps than I'm allowed for one question, so I stopped. "
            "Try asking for one thing at a time."
        )
    if isinstance(error, ToolRetryError):
        return (
            "I couldn't get the data I needed for that. Try rephrasing, or name a town or postcode."
        )
    if isinstance(error, ModelHTTPError):
        if error.status_code in (401, 403):
            return f"The assistant's API key was rejected; check it in .env. {STILL_WORKS}"
        if error.status_code == 402:
            return f"The assistant's model account is out of credit. {STILL_WORKS}"
        if error.status_code == 429:
            return f"The language model is busy right now; try again in a minute. {STILL_WORKS}"
        return f"The language model service had a problem; try again. {STILL_WORKS}"
    if isinstance(error, (ModelAPIError, TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return f"The language model didn't respond; try again in a moment. {STILL_WORKS}"
    return f"Something went wrong while I was answering; try asking again. {STILL_WORKS}"


class FriendlyEventStream(AGUIEventStream):
    async def on_error(self, error: Exception) -> AsyncIterator[BaseEvent]:
        logger.error(f"Assistant run failed: {type(error).__name__}: {error}")
        self._error = True  # after_stream then adds nothing; we finish the run here
        message_id = self.new_message_id()
        yield TextMessageStartEvent(message_id=message_id, role="assistant")
        yield TextMessageContentEvent(message_id=message_id, delta=friendly_message(error))
        yield TextMessageEndEvent(message_id=message_id)
        yield RunFinishedEvent(
            thread_id=self.thread_id, run_id=self.run_id, timestamp=self._get_timestamp()
        )


class FriendlyAGUIAdapter(AGUIAdapter):
    def build_event_stream(self) -> FriendlyEventStream:
        return FriendlyEventStream(
            self.run_input, accept=self.accept, ag_ui_version=self.ag_ui_version
        )
