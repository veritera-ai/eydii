"""EYDII middleware for LangGraph / LangChain.

Two integration approaches:

1. ToolNode wrap_tool_call (recommended) — intercepts ALL tool calls automatically:
     from langgraph.prebuilt import ToolNode, create_react_agent

     middleware = EydiiVerifyMiddleware(policy="finance-controls")
     tool_node = ToolNode(tools, wrap_tool_call=middleware.wrap_tool_call)
     agent = create_react_agent(model, tool_node)

2. Standalone tool — the LLM calls eydii_verify explicitly:
     tool = eydii_verify_tool(policy="finance-controls")
     agent = create_react_agent(model, tools=[send_payment, tool])
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, Optional, Union

from veritera import Eydii

from langchain_core.tools import BaseTool, tool
from langchain_core.messages import ToolMessage

logger = logging.getLogger("eydii_langgraph")


class EydiiVerifyMiddleware:
    """LangGraph/LangChain middleware that verifies every tool call through EYDII.

    Works with LangGraph's ``ToolNode`` via its ``wrap_tool_call`` parameter,
    which can then be passed to ``create_react_agent`` or any ``StateGraph``.

    Usage::

        from langgraph.prebuilt import ToolNode, create_react_agent

        middleware = EydiiVerifyMiddleware(policy="finance-controls")
        tool_node = ToolNode(tools, wrap_tool_call=middleware.wrap_tool_call)
        agent = create_react_agent(model, tool_node)

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Policy to evaluate actions against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: Request timeout in seconds.
        skip_actions: Tool names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://id.veritera.ai",
        agent_id: str = "langgraph-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
        skip_actions: Optional[list[str]] = None,
        on_verified: Optional[Callable] = None,
        on_blocked: Optional[Callable] = None,
    ):
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        if not key:
            raise ValueError(
                "EYDII API key required. Pass api_key= or set VERITERA_API_KEY env var."
            )
        self._client = Eydii(
            api_key=key,
            base_url=base_url,
            timeout=timeout,
            fail_closed=fail_closed,
        )
        self.agent_id = agent_id
        self.policy = policy
        self.fail_closed = fail_closed
        self.skip_actions = set(skip_actions or [])
        self.on_verified = on_verified
        self.on_blocked = on_blocked

    def wrap_tool_call(self, request: Any, handler: Callable) -> Union[ToolMessage, Any]:
        """Middleware entry point — passed to ``ToolNode(wrap_tool_call=...)``.

        Conforms to LangGraph's ``ToolCallWrapper`` protocol::

            Callable[[ToolCallRequest, Callable[[ToolCallRequest], ToolMessage | Command]],
                     ToolMessage | Command]

        If EYDII approves: calls handler(request) to execute the tool.
        If EYDII denies: returns a ToolMessage with the denial reason.
        """
        tool_name = request.tool_call.get("name", "unknown")
        tool_args = request.tool_call.get("args", {})
        tool_call_id = request.tool_call.get("id", "")

        # Skip configured actions
        if tool_name in self.skip_actions:
            return handler(request)

        # Verify through EYDII (sync)
        try:
            result = self._client.verify_sync(
                action=tool_name,
                agent_id=self.agent_id,
                params=tool_args if isinstance(tool_args, dict) else {"raw": str(tool_args)},
                policy=self.policy,
            )
        except Exception as exc:
            logger.error("EYDII verify error for %s: %s", tool_name, exc)
            if self.fail_closed:
                if self.on_blocked:
                    self.on_blocked(tool_name, str(exc))
                return ToolMessage(
                    content=f"Action '{tool_name}' blocked — policy verification unavailable.",
                    tool_call_id=tool_call_id,
                )
            return handler(request)

        if result.verified:
            logger.debug("EYDII APPROVED: %s (proof=%s)", tool_name, result.proof_id)
            if self.on_verified:
                self.on_verified(tool_name, result)
            return handler(request)

        reason = result.reason or "Policy violation"
        logger.warning("EYDII DENIED: %s — %s", tool_name, reason)
        if self.on_blocked:
            self.on_blocked(tool_name, reason)
        return ToolMessage(
            content=f"Action '{tool_name}' denied by EYDII: {reason}",
            tool_call_id=tool_call_id,
        )


def eydii_verify_tool(
    api_key: Optional[str] = None,
    base_url: str = "https://id.veritera.ai",
    agent_id: str = "langgraph-agent",
    policy: Optional[str] = None,
) -> BaseTool:
    """Create a LangChain tool that the LLM can call to verify actions.

    This is an alternative to the middleware approach — the LLM decides
    when to call verification explicitly.

    Usage:
        verify = eydii_verify_tool(policy="finance-controls")
        agent = create_react_agent(model, tools=[send_payment, verify])
    """
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Eydii(api_key=key, base_url=base_url, fail_closed=True)

    @tool
    def eydii_verify(action: str, params: str = "{}") -> str:
        """Verify an AI agent action against EYDII security policies before executing it.

        Args:
            action: The action identifier to verify (e.g. 'payment.create')
            params: JSON string of action parameters
        """
        import json as _json

        try:
            parsed = _json.loads(params)
        except _json.JSONDecodeError:
            parsed = {"raw": params}

        result = client.verify_sync(
            action=action,
            agent_id=agent_id,
            params=parsed,
            policy=policy,
        )
        if result.verified:
            return f"APPROVED: {result.verdict} | proof_id: {result.proof_id} | latency: {result.latency_ms}ms"
        return f"DENIED: {result.reason} | proof_id: {result.proof_id}"

    return eydii_verify
