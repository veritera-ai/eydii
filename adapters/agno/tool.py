"""EYDII tools for Agno (formerly Phidata) agents.

Three integration approaches:

1. EydiiVerifyTool — a callable tool the agent can invoke to verify actions:
     from eydii_agno import EydiiVerifyTool
     eydii = EydiiVerifyTool(policy="finance-controls")
     agent = Agent(tools=[eydii])

2. eydii_wrap_tool — decorator that wraps any tool function with pre-execution verification:
     @eydii_wrap_tool(policy="finance-controls")
     def send_payment(amount: float, recipient: str) -> str:
         return process_payment(amount, recipient)

3. EydiiToolkit — an Agno Toolkit that exposes verify_action and list_policies:
     agent = Agent(tools=[EydiiToolkit(policy="production-safety")])
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
from typing import Any, Callable, Optional

from agno.tools import Toolkit
from veritera import Eydii

logger = logging.getLogger("eydii_agno")


# ---------------------------------------------------------------------------
# Shared client factory
# ---------------------------------------------------------------------------

def _make_client(
    api_key: Optional[str],
    base_url: str,
    timeout: float,
    fail_closed: bool,
) -> EydiiClient:
    """Create and return a configured EYDII client."""
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    if not key:
        raise ValueError(
            "EYDII API key required. Pass api_key= or set VERITERA_API_KEY env var."
        )
    return Eydii(
        api_key=key,
        base_url=base_url,
        timeout=timeout,
        fail_closed=fail_closed,
    )


# ---------------------------------------------------------------------------
# 1. EydiiVerifyTool — standalone verification tool
# ---------------------------------------------------------------------------

class EydiiVerifyTool:
    """A callable tool that verifies agent actions through EYDII policies.

    Agno agents accept any callable as a tool. This class is callable and
    can be passed directly to ``Agent(tools=[...])``.

    Usage::

        from eydii_agno import EydiiVerifyTool
        from agno.agent import Agent

        eydii = EydiiVerifyTool(policy="finance-controls")
        agent = Agent(tools=[eydii])

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: HTTP timeout in seconds for EYDII API calls.
        skip_actions: Action names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://veritera.ai",
        agent_id: str = "agno-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
        skip_actions: Optional[list[str]] = None,
        on_verified: Optional[Callable] = None,
        on_blocked: Optional[Callable] = None,
    ):
        self._client = _make_client(api_key, base_url, timeout, fail_closed)
        self._agent_id = agent_id
        self._policy = policy
        self._fail_closed = fail_closed
        self._skip_actions = set(skip_actions or [])
        self._on_verified = on_verified
        self._on_blocked = on_blocked

        # Agno uses the function name and docstring for tool metadata
        self.__name__ = "eydii_verify"
        self.__doc__ = (
            "Verify an AI agent action against security policies before executing it. "
            "Call this BEFORE performing any sensitive action (payments, emails, deletions, API calls). "
            "Returns APPROVED or DENIED with a reason.\n\n"
            "Args:\n"
            "    action: The action to verify (e.g. 'payment.create', 'email.send', 'db.delete')\n"
            "    params: JSON string of action parameters "
            "(e.g. '{\"amount\": 100, \"to\": \"user@example.com\"}')\n"
        )

    def __call__(self, action: str, params: str = "{}") -> str:
        """Verify an action against EYDII policies.

        Args:
            action: The action identifier (e.g. 'payment.create').
            params: JSON string of action parameters.

        Returns:
            Verification result string (APPROVED or DENIED with details).
        """
        if action in self._skip_actions:
            return f"SKIPPED: Action '{action}' is in the skip list."

        try:
            parsed_params = json.loads(params) if isinstance(params, str) else params
        except (json.JSONDecodeError, TypeError):
            parsed_params = {"raw": str(params)}

        try:
            result = self._client.verify_sync(
                action=action,
                agent_id=self._agent_id,
                params=parsed_params,
                policy=self._policy,
            )
        except Exception as exc:
            logger.error("EYDII verify error: %s", exc)
            if self._on_blocked:
                self._on_blocked(action, str(exc))
            if self._fail_closed:
                return f"DENIED: Verification unavailable — {exc}. Action blocked (fail-closed)."
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("EYDII APPROVED: %s (proof=%s)", action, result.proof_id)
            if self._on_verified:
                self._on_verified(action, result)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        reason = result.reason or "Policy violation"
        logger.warning("EYDII DENIED: %s — %s", action, reason)
        if self._on_blocked:
            self._on_blocked(action, reason)
        return (
            f"DENIED: {reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    async def averify(self, action: str, params: str = "{}") -> str:
        """Async version of verify. Runs the sync call in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.__call__, action, params)


# ---------------------------------------------------------------------------
# 2. eydii_wrap_tool — decorator for wrapping tool functions
# ---------------------------------------------------------------------------

def eydii_wrap_tool(
    api_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
    agent_id: str = "agno-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
    on_verified: Optional[Callable] = None,
    on_blocked: Optional[Callable] = None,
) -> Callable:
    """Decorator that wraps an Agno tool function with pre-execution EYDII verification.

    Before the wrapped function executes, a verification request is sent to
    EYDII. If the action is denied, the function is NOT called and a denial
    message is returned instead.

    Usage::

        from eydii_agno import eydii_wrap_tool

        @eydii_wrap_tool(policy="finance-controls")
        def send_payment(amount: float, recipient: str) -> str:
            return process_payment(amount, recipient)

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Policy to evaluate actions against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: Request timeout in seconds.
        skip_actions: Action names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.
    """
    client = _make_client(api_key, base_url, timeout, fail_closed)
    skip_set = set(skip_actions or [])

    def decorator(func: Callable) -> Callable:
        action_name = func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip configured actions
            if action_name in skip_set:
                return func(*args, **kwargs)

            # Build params from kwargs for verification
            verify_params = dict(kwargs)
            if args:
                verify_params["_positional_args"] = [str(a) for a in args]

            # Verify through EYDII
            try:
                result = client.verify_sync(
                    action=action_name,
                    agent_id=agent_id,
                    params=verify_params,
                    policy=policy,
                )
            except Exception as exc:
                logger.error("EYDII verify error for %s: %s", action_name, exc)
                if on_blocked:
                    on_blocked(action_name, str(exc))
                if fail_closed:
                    return f"DENIED: Action '{action_name}' blocked — verification unavailable."
                return func(*args, **kwargs)

            if result.verified:
                logger.debug("EYDII APPROVED: %s (proof=%s)", action_name, result.proof_id)
                if on_verified:
                    on_verified(action_name, result)
                return func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("EYDII DENIED: %s — %s", action_name, reason)
            if on_blocked:
                on_blocked(action_name, reason)
            return f"DENIED: Action '{action_name}' blocked by EYDII: {reason}"

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip configured actions
            if action_name in skip_set:
                return await func(*args, **kwargs)

            verify_params = dict(kwargs)
            if args:
                verify_params["_positional_args"] = [str(a) for a in args]

            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: client.verify_sync(
                        action=action_name,
                        agent_id=agent_id,
                        params=verify_params,
                        policy=policy,
                    ),
                )
            except Exception as exc:
                logger.error("EYDII verify error for %s: %s", action_name, exc)
                if on_blocked:
                    on_blocked(action_name, str(exc))
                if fail_closed:
                    return f"DENIED: Action '{action_name}' blocked — verification unavailable."
                return await func(*args, **kwargs)

            if result.verified:
                logger.debug("EYDII APPROVED: %s (proof=%s)", action_name, result.proof_id)
                if on_verified:
                    on_verified(action_name, result)
                return await func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("EYDII DENIED: %s — %s", action_name, reason)
            if on_blocked:
                on_blocked(action_name, reason)
            return f"DENIED: Action '{action_name}' blocked by EYDII: {reason}"

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# 3. EydiiToolkit — Agno Toolkit class
# ---------------------------------------------------------------------------

class EydiiToolkit(Toolkit):
    """Agno Toolkit that provides EYDII verification tools to agents.

    Exposes ``verify_action`` and ``list_policies`` as agent-callable tools.

    Usage::

        from eydii_agno import EydiiToolkit
        from agno.agent import Agent

        agent = Agent(tools=[EydiiToolkit(policy="production-safety")])

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: HTTP timeout in seconds for EYDII API calls.
        skip_actions: Action names to skip verification for.
        on_verified: Callback(action, result) when approved.
        on_blocked: Callback(action, reason) when denied.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://veritera.ai",
        agent_id: str = "agno-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
        skip_actions: Optional[list[str]] = None,
        on_verified: Optional[Callable] = None,
        on_blocked: Optional[Callable] = None,
    ):
        super().__init__(name="eydii_toolkit")
        self._client = _make_client(api_key, base_url, timeout, fail_closed)
        self._agent_id = agent_id
        self._policy = policy
        self._fail_closed = fail_closed
        self._skip_actions = set(skip_actions or [])
        self._on_verified = on_verified
        self._on_blocked = on_blocked

        # Register tools with the toolkit
        self.register(self.verify_action)
        self.register(self.list_policies)

    def verify_action(self, action: str, params: str = "{}") -> str:
        """Verify an AI agent action against EYDII security policies before executing it.

        Call this BEFORE performing any sensitive action (payments, emails, deletions, API calls).
        Returns APPROVED or DENIED with a reason.

        Args:
            action: The action to verify (e.g. 'payment.create', 'email.send', 'db.delete').
            params: JSON string of action parameters.

        Returns:
            str: Verification result — APPROVED or DENIED with details.
        """
        if action in self._skip_actions:
            return f"SKIPPED: Action '{action}' is in the skip list."

        try:
            parsed_params = json.loads(params) if isinstance(params, str) else params
        except (json.JSONDecodeError, TypeError):
            parsed_params = {"raw": str(params)}

        try:
            result = self._client.verify_sync(
                action=action,
                agent_id=self._agent_id,
                params=parsed_params,
                policy=self._policy,
            )
        except Exception as exc:
            logger.error("EYDII verify error: %s", exc)
            if self._on_blocked:
                self._on_blocked(action, str(exc))
            if self._fail_closed:
                return f"DENIED: Verification unavailable — {exc}. Action blocked (fail-closed)."
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("EYDII APPROVED: %s (proof=%s)", action, result.proof_id)
            if self._on_verified:
                self._on_verified(action, result)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        reason = result.reason or "Policy violation"
        logger.warning("EYDII DENIED: %s — %s", action, reason)
        if self._on_blocked:
            self._on_blocked(action, reason)
        return (
            f"DENIED: {reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    def list_policies(self) -> str:
        """List available EYDII verification policies.

        Returns:
            str: A formatted list of available policies, or an error message.
        """
        try:
            policies = self._client.list_policies_sync()
            if not policies:
                return "No policies found. Create one at id.veritera.ai/dashboard."
            lines = []
            for p in policies:
                name = getattr(p, "name", str(p))
                desc = getattr(p, "description", "")
                lines.append(f"- {name}: {desc}" if desc else f"- {name}")
            return "Available policies:\n" + "\n".join(lines)
        except Exception as exc:
            logger.error("Failed to list policies: %s", exc)
            return f"ERROR: Could not list policies — {exc}"
