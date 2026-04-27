"""Forge instrumentation event handler for LlamaIndex.

Attaches to the LlamaIndex instrumentation dispatcher to audit agent tool calls
through the Forge /v1/verify API.

Usage:
    from forge_llamaindex import ForgeEventHandler
    import llama_index.core.instrumentation as instrument

    handler = ForgeEventHandler(policy="finance-controls")
    dispatcher = instrument.get_dispatcher()
    dispatcher.add_event_handler(handler)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from veritera import Forge

from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
from llama_index.core.instrumentation.events.base import BaseEvent

logger = logging.getLogger("forge_llamaindex")


class ForgeEventHandler(BaseEventHandler):
    """Instrumentation handler that audits agent tool calls through Forge.

    Intercepts AgentToolCallEvent and verifies the tool call. Can optionally
    raise an exception to block execution if the action is denied.

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Policy to evaluate actions against.
        block_on_deny: If True, raise ValueError when Forge denies an action.
        fail_closed: If True, block when Forge API is unreachable.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://forge.veritera.ai",
        agent_id: str = "llamaindex-agent",
        policy: Optional[str] = None,
        block_on_deny: bool = True,
        fail_closed: bool = True,
    ):
        super().__init__()
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        self._client = Forge(
            api_key=key,
            base_url=base_url,
            fail_closed=fail_closed,
        )
        self._agent_id = agent_id
        self._policy = policy
        self._block_on_deny = block_on_deny
        self._fail_closed = fail_closed

    @classmethod
    def class_name(cls) -> str:
        return "ForgeVerifyEventHandler"

    def handle(self, event: BaseEvent, **kwargs: Any) -> Any:
        """Handle instrumentation events.

        Intercepts tool call events and verifies them through Forge.
        """
        # Check if this is a tool call event
        event_type = type(event).__name__
        if "ToolCall" not in event_type and "tool_call" not in event_type.lower():
            return None

        # Extract tool info from the event.
        # AgentToolCallEvent has: .tool (ToolMetadata with .name) and .arguments (JSON str)
        tool_name = "unknown"
        tool_args: dict = {}

        # Preferred: AgentToolCallEvent — tool metadata holds the name
        if hasattr(event, "tool"):
            tool_meta = getattr(event, "tool")
            if hasattr(tool_meta, "name") and tool_meta.name:
                tool_name = tool_meta.name

        # Fallback: try other common attribute names
        if tool_name == "unknown":
            for attr in ("tool_name", "name", "function_name"):
                if hasattr(event, attr):
                    val = getattr(event, attr)
                    if val:
                        tool_name = val
                        break

        # Extract arguments — AgentToolCallEvent stores them as a JSON string
        if hasattr(event, "arguments"):
            raw = getattr(event, "arguments")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        tool_args = parsed
                except (json.JSONDecodeError, TypeError):
                    tool_args = {"raw": raw}
            elif isinstance(raw, dict):
                tool_args = raw

        # Fallback for other event shapes
        if not tool_args:
            for attr in ("tool_kwargs", "args", "kwargs"):
                if hasattr(event, attr):
                    val = getattr(event, attr)
                    if isinstance(val, dict):
                        tool_args = val
                        break

        try:
            result = self._client.verify_sync(
                action=tool_name,
                agent_id=self._agent_id,
                params=tool_args,
                policy=self._policy,
            )
        except Exception as exc:
            logger.error("Forge event handler error: %s", exc)
            if self._fail_closed and self._block_on_deny:
                raise ValueError(
                    f"Forge: Action '{tool_name}' blocked — verification unavailable."
                ) from exc
            return None

        if result.verified:
            logger.debug("Forge APPROVED: %s (proof=%s)", tool_name, result.proof_id)
            return None

        reason = result.reason or "Policy violation"
        logger.warning("Forge DENIED: %s — %s", tool_name, reason)

        if self._block_on_deny:
            raise ValueError(
                f"Forge: Action '{tool_name}' denied — {reason}"
            )
        return None
