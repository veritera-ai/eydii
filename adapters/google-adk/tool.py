"""Forge Verify tools and callbacks for Google ADK.

Three integration approaches:

1. ForgeVerifyTool — explicit verification tool the agent can call:
     from forge_google_adk import ForgeVerifyTool
     from google.adk import Agent

     forge = ForgeVerifyTool(policy="finance-controls")
     agent = Agent(tools=[forge.as_tool()])

2. forge_before_tool_callback — intercepts ALL tool calls automatically:
     from forge_google_adk import forge_before_tool_callback
     agent = Agent(
         tools=[...],
         before_tool_callback=forge_before_tool_callback(policy="finance-controls"),
     )

3. forge_wrap_tool — decorator wrapping individual tools:
     from forge_google_adk import forge_wrap_tool

     @forge_wrap_tool(policy="finance-controls")
     def send_payment(amount: float, recipient: str) -> str:
         return process_payment(amount, recipient)
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

from veritera import Forge

logger = logging.getLogger("forge_google_adk")


class ForgeVerifyTool:
    """Google ADK tool that verifies agent actions through Forge policies.

    Provides an explicit verification tool that agents can call before
    performing sensitive operations.

    Usage::

        from forge_google_adk import ForgeVerifyTool
        from google.adk import Agent

        forge = ForgeVerifyTool(policy="finance-controls")
        agent = Agent(
            name="finance-bot",
            tools=[forge.as_tool()],
        )

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when Forge API is unreachable.
        timeout: HTTP timeout in seconds for Forge API calls.
        skip_actions: Action names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://veritera.ai",
        agent_id: str = "google-adk-agent",
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

    def verify_sync(self, action: str, params: Optional[dict] = None) -> str:
        """Verify an action synchronously.

        Args:
            action: The action identifier (e.g. 'payment.create').
            params: Action parameters dict.

        Returns:
            Verification result string (APPROVED or DENIED with details).
        """
        if action in self.skip_actions:
            return f"APPROVED: {action} skipped (configured bypass)"

        safe_params = params if isinstance(params, dict) else {}

        try:
            result = self._client.verify_sync(
                action=action,
                agent_id=self.agent_id,
                params=safe_params,
                policy=self.policy,
            )
        except Exception as exc:
            logger.error("Forge verify error: %s", exc)
            if self.on_blocked:
                self.on_blocked(action, str(exc))
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("Forge APPROVED: %s (proof=%s)", action, result.proof_id)
            if self.on_verified:
                self.on_verified(action, result)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        reason = result.reason or "Policy violation"
        logger.warning("Forge DENIED: %s — %s", action, reason)
        if self.on_blocked:
            self.on_blocked(action, reason)
        return (
            f"DENIED: {reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    async def verify_async(self, action: str, params: Optional[dict] = None) -> str:
        """Verify an action asynchronously.

        Args:
            action: The action identifier (e.g. 'payment.create').
            params: Action parameters dict.

        Returns:
            Verification result string (APPROVED or DENIED with details).
        """
        if action in self.skip_actions:
            return f"APPROVED: {action} skipped (configured bypass)"

        safe_params = params if isinstance(params, dict) else {}

        try:
            result = await self._client.verify_decision(
                action=action,
                agent_id=self.agent_id,
                params=safe_params,
                policy=self.policy,
            )
        except Exception as exc:
            logger.error("Forge verify error: %s", exc)
            if self.on_blocked:
                self.on_blocked(action, str(exc))
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("Forge APPROVED: %s (proof=%s)", action, result.proof_id)
            if self.on_verified:
                self.on_verified(action, result)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        reason = result.reason or "Policy violation"
        logger.warning("Forge DENIED: %s — %s", action, reason)
        if self.on_blocked:
            self.on_blocked(action, reason)
        return (
            f"DENIED: {reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    def as_tool(self) -> Callable:
        """Return a Google ADK-compatible tool function for explicit verification.

        The returned function can be passed directly to ``Agent(tools=[...])``.

        Usage::

            forge = ForgeVerifyTool(policy="finance-controls")
            agent = Agent(name="bot", tools=[forge.as_tool()])
        """

        def forge_verify(action: str, params: str = "{}") -> str:
            """Verify an AI agent action against security policies before executing it.

            Call this BEFORE performing any sensitive action (payments, emails,
            deletions, API calls). Returns APPROVED or DENIED with a reason.

            Args:
                action: The action to verify (e.g. 'payment.create', 'email.send', 'db.delete').
                params: JSON string of action parameters
                    (e.g. '{"amount": 100, "to": "user@example.com"}').

            Returns:
                Verification result: APPROVED or DENIED with details and proof_id.
            """
            try:
                parsed_params = json.loads(params) if isinstance(params, str) else params
            except (json.JSONDecodeError, TypeError):
                parsed_params = {"raw": str(params)}

            return self.verify_sync(action=action, params=parsed_params)

        return forge_verify


def forge_before_tool_callback(
    api_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
    agent_id: str = "google-adk-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
    on_verified: Optional[Callable] = None,
    on_blocked: Optional[Callable] = None,
) -> Callable:
    """Create a Google ADK before_tool_callback that verifies tool calls through Forge.

    Intercepts every tool call before execution. If Forge denies the action,
    the callback returns a dict with an error message instead of executing the tool.

    Usage::

        from forge_google_adk import forge_before_tool_callback

        agent = Agent(
            name="finance-bot",
            tools=[send_payment, check_balance],
            before_tool_callback=forge_before_tool_callback(
                policy="finance-controls",
                skip_actions=["check_balance"],
            ),
        )

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Policy to evaluate actions against.
        fail_closed: If True (default), deny when Forge API is unreachable.
        timeout: Request timeout in seconds.
        skip_actions: Tool names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.

    Returns:
        A callback function compatible with Google ADK's before_tool_callback.
    """
    forge = ForgeVerifyTool(
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

    def _before_tool(
        tool_name: str,
        tool_args: dict,
        tool_context: Any = None,
    ) -> Optional[dict]:
        """Pre-tool callback for Google ADK.

        Returns None to allow execution, or a dict to short-circuit
        with a response (blocking the tool).
        """
        if tool_name in forge.skip_actions:
            logger.debug("Forge: skipping verification for %s", tool_name)
            return None

        safe_args = tool_args if isinstance(tool_args, dict) else {"raw": str(tool_args)}

        try:
            result = forge._client.verify_sync(
                action=tool_name,
                agent_id=forge.agent_id,
                params=safe_args,
                policy=forge.policy,
            )
        except Exception as exc:
            logger.error("Forge verify error for %s: %s", tool_name, exc)
            if forge.fail_closed:
                if forge.on_blocked:
                    forge.on_blocked(tool_name, str(exc))
                return {
                    "error": f"Action '{tool_name}' blocked — policy verification unavailable.",
                    "forge_status": "error",
                }
            return None  # Fail open — allow execution

        if result.verified:
            logger.debug("Forge APPROVED: %s (proof=%s)", tool_name, result.proof_id)
            if forge.on_verified:
                forge.on_verified(tool_name, result)
            return None  # Allow execution

        reason = result.reason or "Policy violation"
        logger.warning("Forge DENIED: %s — %s", tool_name, reason)
        if forge.on_blocked:
            forge.on_blocked(tool_name, reason)
        return {
            "error": f"Action '{tool_name}' denied by Forge: {reason}",
            "forge_status": "denied",
            "proof_id": result.proof_id,
        }

    return _before_tool


def forge_after_tool_callback(
    api_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
    agent_id: str = "google-adk-agent",
    policy: Optional[str] = None,
) -> Callable:
    """Create a Google ADK after_tool_callback that audits tool results through Forge.

    Logs every tool execution result to the Forge audit trail.
    This callback is non-blocking — it never prevents execution.

    Usage::

        from forge_google_adk import forge_after_tool_callback

        agent = Agent(
            name="finance-bot",
            tools=[...],
            after_tool_callback=forge_after_tool_callback(policy="audit-trail"),
        )

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Policy to evaluate against.

    Returns:
        A callback function compatible with Google ADK's after_tool_callback.
    """
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Forge(api_key=key, base_url=base_url, fail_closed=False)

    def _after_tool(
        tool_name: str,
        tool_args: dict,
        tool_result: Any,
        tool_context: Any = None,
    ) -> Optional[dict]:
        """Post-tool callback for Google ADK.

        Audits the tool execution through Forge. Non-blocking.
        Returns None to keep the original result.
        """
        result_preview = str(tool_result)[:2000] if tool_result else ""

        try:
            client.verify_sync(
                action=f"tool.result.{tool_name}",
                agent_id=agent_id,
                params={
                    "tool_name": tool_name,
                    "tool_args": tool_args if isinstance(tool_args, dict) else {"raw": str(tool_args)},
                    "result_preview": result_preview[:500],
                },
                policy=policy,
            )
        except Exception as exc:
            logger.debug("Forge after_tool audit error (non-blocking): %s", exc)

        return None  # Keep original result

    return _after_tool


def forge_wrap_tool(
    api_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
    agent_id: str = "google-adk-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
    on_verified: Optional[Callable] = None,
    on_blocked: Optional[Callable] = None,
) -> Callable:
    """Decorator that wraps a Google ADK tool function with Forge verification.

    The original function is only called if Forge approves the action.
    If denied, returns a denial message without executing the function.

    Usage::

        from forge_google_adk import forge_wrap_tool

        @forge_wrap_tool(policy="finance-controls")
        def send_payment(amount: float, recipient: str) -> str:
            \"\"\"Send a payment to a recipient.\"\"\"
            return process_payment(amount, recipient)

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Policy to evaluate actions against.
        fail_closed: If True (default), deny when Forge API is unreachable.
        timeout: Request timeout in seconds.
        skip_actions: Action names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.

    Returns:
        A decorator that wraps tool functions with Forge verification.
    """
    forge = ForgeVerifyTool(
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

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = func.__name__

            if tool_name in forge.skip_actions:
                logger.debug("Forge: skipping verification for %s", tool_name)
                return func(*args, **kwargs)

            # Build params from kwargs (or positional args)
            params = dict(kwargs) if kwargs else {}
            if args:
                params["_positional_args"] = [str(a) for a in args]

            try:
                result = forge._client.verify_sync(
                    action=tool_name,
                    agent_id=forge.agent_id,
                    params=params,
                    policy=forge.policy,
                )
            except Exception as exc:
                logger.error("Forge verify error for %s: %s", tool_name, exc)
                if forge.fail_closed:
                    if forge.on_blocked:
                        forge.on_blocked(tool_name, str(exc))
                    return f"Action '{tool_name}' blocked — policy verification unavailable."
                return func(*args, **kwargs)

            if result.verified:
                logger.debug("Forge APPROVED: %s (proof=%s)", tool_name, result.proof_id)
                if forge.on_verified:
                    forge.on_verified(tool_name, result)
                return func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("Forge DENIED: %s — %s", tool_name, reason)
            if forge.on_blocked:
                forge.on_blocked(tool_name, reason)
            return f"Action '{tool_name}' denied by Forge: {reason}"

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tool_name = func.__name__

            if tool_name in forge.skip_actions:
                logger.debug("Forge: skipping verification for %s", tool_name)
                return await func(*args, **kwargs)

            params = dict(kwargs) if kwargs else {}
            if args:
                params["_positional_args"] = [str(a) for a in args]

            try:
                result = await forge._client.verify_decision(
                    action=tool_name,
                    agent_id=forge.agent_id,
                    params=params,
                    policy=forge.policy,
                )
            except Exception as exc:
                logger.error("Forge verify error for %s: %s", tool_name, exc)
                if forge.fail_closed:
                    if forge.on_blocked:
                        forge.on_blocked(tool_name, str(exc))
                    return f"Action '{tool_name}' blocked — policy verification unavailable."
                return await func(*args, **kwargs)

            if result.verified:
                logger.debug("Forge APPROVED: %s (proof=%s)", tool_name, result.proof_id)
                if forge.on_verified:
                    forge.on_verified(tool_name, result)
                return await func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("Forge DENIED: %s — %s", tool_name, reason)
            if forge.on_blocked:
                forge.on_blocked(tool_name, reason)
            return f"Action '{tool_name}' denied by Forge: {reason}"

        # Return async or sync wrapper based on the original function
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
