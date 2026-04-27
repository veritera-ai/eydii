"""Forge Verify guardrails for OpenAI Agents SDK.

Provides ToolInputGuardrail (pre-tool) and InputGuardrail (pre-agent)
that call the Forge /v1/verify API before execution proceeds.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Optional

from veritera import Forge

from agents import (
    Agent,
    FunctionTool,
    GuardrailFunctionOutput,
    InputGuardrail,
    RunContextWrapper,
    ToolInputGuardrail,
    ToolInputGuardrailData,
    ToolGuardrailFunctionOutput,
)

logger = logging.getLogger("forge_openai")


class ForgeGuardrail:
    """Configurable Forge verification client for OpenAI Agents SDK.

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny actions when Forge API is unreachable.
        timeout: Request timeout in seconds.
        skip_actions: Tool names to skip verification for (e.g. read-only tools).
        on_verified: Callback(action, result) when a tool call is approved.
        on_blocked: Callback(action, reason, result) when a tool call is denied.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://forge.veritera.ai",
        agent_id: str = "openai-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
        skip_actions: Optional[list[str]] = None,
        on_verified: Optional[Any] = None,
        on_blocked: Optional[Any] = None,
    ):
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        if not key:
            raise ValueError(
                "Forge API key required. Pass api_key= or set VERITERA_API_KEY env var."
            )
        self._client = Forge(
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

    def tool_guardrail(self, policy_override: Optional[str] = None) -> ToolInputGuardrail:
        """Create a ToolInputGuardrail that verifies each tool call through Forge.

        Attach to individual tools:
            @function_tool(tool_input_guardrails=[guard.tool_guardrail()])
            def send_email(...): ...

        Or use forge_protect() to attach to multiple tools at once.

        Args:
            policy_override: If provided, this guardrail uses this policy
                instead of the instance default.
        """
        # Capture policy at creation time so the closure is not affected
        # by later mutations of self.policy.
        effective_policy = policy_override or self.policy

        async def _verify_tool(
            data: ToolInputGuardrailData,
        ) -> ToolGuardrailFunctionOutput:
            tool_name = data.context.tool_name

            # Skip configured actions
            if tool_name in self.skip_actions:
                return ToolGuardrailFunctionOutput.allow(
                    output_info={"skipped": True, "action": tool_name}
                )

            # Parse tool arguments
            try:
                params = (
                    json.loads(data.context.tool_arguments)
                    if data.context.tool_arguments
                    else {}
                )
            except (json.JSONDecodeError, TypeError):
                params = {"raw": data.context.tool_arguments}

            # Call Forge /v1/verify
            try:
                result = await self._client.verify_decision(
                    agent_id=self.agent_id,
                    action=tool_name,
                    params=params,
                    policy=effective_policy,
                )
            except Exception as exc:
                logger.error("Forge verify error for %s: %s", tool_name, exc)
                if self.fail_closed:
                    if self.on_blocked:
                        self.on_blocked(tool_name, str(exc), None)
                    return ToolGuardrailFunctionOutput.reject_content(
                        message=f"Action '{tool_name}' blocked — policy verification unavailable.",
                        output_info={"error": str(exc), "fail_mode": "closed"},
                    )
                return ToolGuardrailFunctionOutput.allow(
                    output_info={"error": str(exc), "fail_mode": "open"}
                )

            if result.verified:
                logger.debug("Forge APPROVED: %s (proof=%s)", tool_name, result.proof_id)
                if self.on_verified:
                    self.on_verified(tool_name, result)
                return ToolGuardrailFunctionOutput.allow(
                    output_info={
                        "verified": True,
                        "proof_id": result.proof_id,
                        "latency_ms": result.latency_ms,
                    }
                )

            reason = result.reason or "Policy violation"
            logger.warning("Forge DENIED: %s — %s", tool_name, reason)
            if self.on_blocked:
                self.on_blocked(tool_name, reason, result)
            return ToolGuardrailFunctionOutput.reject_content(
                message=f"Action '{tool_name}' denied by Forge: {reason}",
                output_info={
                    "verified": False,
                    "reason": reason,
                    "proof_id": result.proof_id,
                    "latency_ms": result.latency_ms,
                },
            )

        return ToolInputGuardrail(
            guardrail_function=_verify_tool,
            name="forge_verify",
        )

    def input_guardrail(self) -> InputGuardrail:
        """Create an InputGuardrail that screens agent input through Forge.

        Useful for blocking entire conversation turns based on policy.
        """

        async def _screen_input(
            ctx: RunContextWrapper, agent: Agent, input: Any
        ) -> GuardrailFunctionOutput:
            input_text = str(input) if input else ""
            try:
                result = await self._client.verify_decision(
                    agent_id=self.agent_id,
                    action="agent.input",
                    params={"input": input_text[:2000]},
                    policy=self.policy,
                )
                return GuardrailFunctionOutput(
                    output_info={
                        "verified": result.verified,
                        "reason": result.reason,
                    },
                    tripwire_triggered=not result.verified,
                )
            except Exception as exc:
                logger.error("Forge input guardrail error: %s", exc)
                return GuardrailFunctionOutput(
                    output_info={"error": str(exc)},
                    tripwire_triggered=self.fail_closed,
                )

        return InputGuardrail(
            guardrail_function=_screen_input,
            name="forge_input_screen",
        )

    def protect(self, *tools: FunctionTool, policy: Optional[str] = None) -> list[FunctionTool]:
        """Attach Forge guardrail to multiple tools at once.

        Returns new tool instances — originals are not mutated.
        """
        guardrail = self.tool_guardrail(policy_override=policy)

        protected = []
        for tool in tools:
            t = copy.copy(tool)
            existing = list(t.tool_input_guardrails or [])
            existing.append(guardrail)
            t.tool_input_guardrails = existing
            protected.append(t)
        return protected


# ── Convenience functions ──


def forge_tool_guardrail(
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "openai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
    on_verified: Optional[Any] = None,
    on_blocked: Optional[Any] = None,
) -> ToolInputGuardrail:
    """Create a ToolInputGuardrail that verifies tool calls through Forge.

    Usage:
        guardrail = forge_tool_guardrail(policy="finance-controls")

        @function_tool(tool_input_guardrails=[guardrail])
        def send_payment(amount: float, recipient: str) -> str:
            \"\"\"Send a payment.\"\"\"
            return process_payment(amount, recipient)
    """
    guard = ForgeGuardrail(
        api_key=api_key,
        base_url=base_url,
        agent_id=agent_id,
        policy=policy,
        fail_closed=fail_closed,
        timeout=timeout,
        skip_actions=skip_actions,
        on_verified=on_verified,
        on_blocked=on_blocked,
    )
    return guard.tool_guardrail()


def forge_input_guardrail(
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "openai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
) -> InputGuardrail:
    """Create an InputGuardrail that screens agent input through Forge.

    Usage:
        agent = Agent(
            name="my-agent",
            input_guardrails=[forge_input_guardrail(policy="content-policy")],
            tools=[...],
        )
    """
    guard = ForgeGuardrail(
        api_key=api_key,
        base_url=base_url,
        agent_id=agent_id,
        policy=policy,
        fail_closed=fail_closed,
    )
    return guard.input_guardrail()


def forge_protect(
    *tools: FunctionTool,
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "openai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
) -> list[FunctionTool]:
    """Attach Forge verification to multiple tools at once.

    Usage:
        agent = Agent(
            name="finance-bot",
            tools=forge_protect(
                send_payment, read_balance, delete_record,
                policy="finance-controls",
            ),
        )
    """
    guard = ForgeGuardrail(
        api_key=api_key,
        base_url=base_url,
        agent_id=agent_id,
        policy=policy,
        fail_closed=fail_closed,
        timeout=timeout,
        skip_actions=skip_actions,
    )
    return guard.protect(*tools)
