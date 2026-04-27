"""EYDII tools and middleware for Pydantic AI.

Three integration approaches:

1. EydiiVerifyTool — explicit verification tool the agent calls:
     from eydii_pydantic_ai import EydiiVerifyTool
     eydii_tool = EydiiVerifyTool(policy="finance-controls")
     agent.tool(eydii_tool.verify)

2. eydii_tool_wrapper — decorator that wraps any tool with verification:
     @eydii_tool_wrapper(policy="finance-controls")
     async def send_payment(ctx, amount: float, recipient: str) -> str:
         return process_payment(amount, recipient)

3. EydiiMiddleware — intercepts all tool calls during agent.run():
     middleware = EydiiMiddleware(policy="finance-controls")
     result = await middleware.run(agent, "Send $500 to vendor")
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

from veritera import Eydii

logger = logging.getLogger("eydii_pydantic_ai")


class EydiiVerifyTool:
    """Pydantic AI tool that verifies agent actions through EYDII policies.

    Create an instance and register its ``verify`` method as a tool on your
    Pydantic AI agent. The agent calls it before executing sensitive actions.

    Usage::

        from pydantic_ai import Agent
        from eydii_pydantic_ai import EydiiVerifyTool

        agent = Agent('openai:gpt-4o')
        eydii_tool = EydiiVerifyTool(policy="finance-controls")
        agent.tool(eydii_tool.verify)

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: HTTP timeout in seconds for EYDII API calls.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://veritera.ai",
        agent_id: str = "pydantic-ai-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
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
        self._agent_id = agent_id
        self._policy = policy
        self._fail_closed = fail_closed

    async def verify(self, ctx: Any, action: str, params: str = "{}") -> str:
        """Verify an AI agent action against EYDII security policies before executing it.

        Call this BEFORE performing any sensitive action (payments, emails, deletions, API calls).
        Returns APPROVED or DENIED with a reason.

        Args:
            ctx: Pydantic AI RunContext (injected automatically).
            action: The action to verify (e.g. 'payment.create', 'email.send').
            params: JSON string of action parameters.
        """
        try:
            parsed_params = json.loads(params) if isinstance(params, str) else params
        except (json.JSONDecodeError, TypeError):
            parsed_params = {"raw": str(params)}

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.verify_sync(
                    action=action,
                    agent_id=self._agent_id,
                    params=parsed_params,
                    policy=self._policy,
                ),
            )
        except Exception as exc:
            logger.error("EYDII verify error: %s", exc)
            if self._fail_closed:
                return f"DENIED: Verification unavailable — {exc}. Do NOT proceed with this action."
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("EYDII APPROVED: %s", action)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        logger.warning("EYDII DENIED: %s — %s", action, result.reason)
        return (
            f"DENIED: {result.reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    def verify_sync(self, action: str, params: str = "{}") -> str:
        """Synchronous version of verify (without RunContext).

        Use this for direct verification calls outside the agent context.
        """
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
            if self._fail_closed:
                return f"DENIED: Verification unavailable — {exc}. Do NOT proceed with this action."
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("EYDII APPROVED: %s", action)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms"
            )

        logger.warning("EYDII DENIED: %s — %s", action, result.reason)
        return (
            f"DENIED: {result.reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )


def eydii_tool_wrapper(
    api_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
    agent_id: str = "pydantic-ai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    timeout: float = 10.0,
    skip_actions: Optional[list[str]] = None,
    on_verified: Optional[Callable] = None,
    on_blocked: Optional[Callable] = None,
):
    """Decorator that wraps any Pydantic AI tool with EYDII verification.

    The wrapped tool is verified against EYDII policies before execution.
    If the action is denied, the tool returns a denial message instead of executing.

    Usage::

        @eydii_tool_wrapper(policy="finance-controls")
        async def send_payment(ctx, amount: float, recipient: str) -> str:
            return process_payment(amount, recipient)

        agent = Agent('openai:gpt-4o', tools=[send_payment])

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
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    if not key:
        raise ValueError(
            "EYDII API key required. Pass api_key= or set VERITERA_API_KEY env var."
        )
    client = Eydii(
        api_key=key,
        base_url=base_url,
        timeout=timeout,
        fail_closed=fail_closed,
    )
    skip_set = set(skip_actions or [])

    def decorator(func: Callable) -> Callable:
        tool_name = getattr(func, "__name__", "unknown")

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip configured actions
            if tool_name in skip_set:
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            # Build params from kwargs for verification
            verify_params = {k: v for k, v in kwargs.items() if k != "ctx"}

            # Verify through EYDII
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.verify_sync(
                        action=tool_name,
                        agent_id=agent_id,
                        params=verify_params if isinstance(verify_params, dict) else {"raw": str(verify_params)},
                        policy=policy,
                    ),
                )
            except Exception as exc:
                logger.error("EYDII verify error for %s: %s", tool_name, exc)
                if fail_closed:
                    if on_blocked:
                        on_blocked(tool_name, str(exc))
                    return f"Action '{tool_name}' blocked — policy verification unavailable."
                # fail_open: execute the tool
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            if result.verified:
                logger.debug("EYDII APPROVED: %s (proof=%s)", tool_name, result.proof_id)
                if on_verified:
                    on_verified(tool_name, result)
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("EYDII DENIED: %s — %s", tool_name, reason)
            if on_blocked:
                on_blocked(tool_name, reason)
            return f"Action '{tool_name}' denied by EYDII: {reason}"

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Skip configured actions
            if tool_name in skip_set:
                return func(*args, **kwargs)

            # Build params from kwargs for verification
            verify_params = {k: v for k, v in kwargs.items() if k != "ctx"}

            # Verify through EYDII
            try:
                result = client.verify_sync(
                    action=tool_name,
                    agent_id=agent_id,
                    params=verify_params if isinstance(verify_params, dict) else {"raw": str(verify_params)},
                    policy=policy,
                )
            except Exception as exc:
                logger.error("EYDII verify error for %s: %s", tool_name, exc)
                if fail_closed:
                    if on_blocked:
                        on_blocked(tool_name, str(exc))
                    return f"Action '{tool_name}' blocked — policy verification unavailable."
                return func(*args, **kwargs)

            if result.verified:
                logger.debug("EYDII APPROVED: %s (proof=%s)", tool_name, result.proof_id)
                if on_verified:
                    on_verified(tool_name, result)
                return func(*args, **kwargs)

            reason = result.reason or "Policy violation"
            logger.warning("EYDII DENIED: %s — %s", tool_name, reason)
            if on_blocked:
                on_blocked(tool_name, reason)
            return f"Action '{tool_name}' denied by EYDII: {reason}"

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class EydiiMiddleware:
    """Middleware that intercepts all Pydantic AI tool calls through EYDII.

    Wraps ``agent.run()`` to verify every tool invocation against EYDII policies.
    If a tool call is denied, it returns a denial message instead of executing.

    Usage::

        from pydantic_ai import Agent
        from eydii_pydantic_ai import EydiiMiddleware

        agent = Agent('openai:gpt-4o', tools=[send_payment, check_balance])
        middleware = EydiiMiddleware(policy="finance-controls")

        # Verified run — all tool calls go through EYDII
        result = await middleware.run(agent, "Send $500 to vendor")

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
        base_url: str = "https://veritera.ai",
        agent_id: str = "pydantic-ai-agent",
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

    def _verify_action(self, action: str, params: dict) -> tuple[bool, str]:
        """Verify a single action through EYDII.

        Returns:
            (approved: bool, message: str)
        """
        if action in self.skip_actions:
            return (True, "")

        try:
            result = self._client.verify_sync(
                action=action,
                agent_id=self.agent_id,
                params=params if isinstance(params, dict) else {"raw": str(params)},
                policy=self.policy,
            )
        except Exception as exc:
            logger.error("EYDII verify error for %s: %s", action, exc)
            if self.fail_closed:
                if self.on_blocked:
                    self.on_blocked(action, str(exc))
                return (False, f"Action '{action}' blocked — policy verification unavailable.")
            return (True, "")

        if result.verified:
            logger.debug("EYDII APPROVED: %s (proof=%s)", action, result.proof_id)
            if self.on_verified:
                self.on_verified(action, result)
            return (True, "")

        reason = result.reason or "Policy violation"
        logger.warning("EYDII DENIED: %s — %s", action, reason)
        if self.on_blocked:
            self.on_blocked(action, reason)
        return (False, f"Action '{action}' denied by EYDII: {reason}")

    async def run(
        self,
        agent: Any,
        prompt: str,
        *,
        deps: Any = None,
        message_history: Any = None,
        model: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Run a Pydantic AI agent with EYDII verification on all tool calls.

        Wraps each registered tool with EYDII verification before calling
        ``agent.run()``. After execution, the original tools are restored.

        Args:
            agent: The Pydantic AI Agent instance.
            prompt: The user prompt to send to the agent.
            deps: Optional dependencies to pass to the agent.
            message_history: Optional message history.
            model: Optional model override.
            **kwargs: Additional arguments passed to agent.run().

        Returns:
            The agent run result.
        """
        # Store original tools and wrap them
        original_tools = {}
        for tool_def in getattr(agent, "_function_tools", {}).values():
            tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)
            original_fn = tool_def.function if hasattr(tool_def, "function") else None
            if original_fn is None:
                continue
            original_tools[tool_name] = original_fn

            middleware = self

            if asyncio.iscoroutinefunction(original_fn):
                @functools.wraps(original_fn)
                async def wrapped(*args: Any, _orig=original_fn, _name=tool_name, **kw: Any) -> Any:
                    verify_params = {k: v for k, v in kw.items() if k != "ctx"}
                    approved, msg = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: middleware._verify_action(_name, verify_params),
                    )
                    if not approved:
                        return msg
                    return await _orig(*args, **kw)
            else:
                @functools.wraps(original_fn)
                def wrapped(*args: Any, _orig=original_fn, _name=tool_name, **kw: Any) -> Any:
                    verify_params = {k: v for k, v in kw.items() if k != "ctx"}
                    approved, msg = middleware._verify_action(_name, verify_params)
                    if not approved:
                        return msg
                    return _orig(*args, **kw)

            tool_def.function = wrapped

        try:
            run_kwargs: dict[str, Any] = {}
            if deps is not None:
                run_kwargs["deps"] = deps
            if message_history is not None:
                run_kwargs["message_history"] = message_history
            if model is not None:
                run_kwargs["model"] = model
            run_kwargs.update(kwargs)

            result = await agent.run(prompt, **run_kwargs)
            return result
        finally:
            # Restore original tools
            for tool_def in getattr(agent, "_function_tools", {}).values():
                tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)
                if tool_name in original_tools:
                    tool_def.function = original_tools[tool_name]

    def run_sync(
        self,
        agent: Any,
        prompt: str,
        *,
        deps: Any = None,
        message_history: Any = None,
        model: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Synchronous version of run().

        Wraps each registered tool with EYDII verification before calling
        ``agent.run_sync()``. After execution, the original tools are restored.
        """
        original_tools = {}
        for tool_def in getattr(agent, "_function_tools", {}).values():
            tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)
            original_fn = tool_def.function if hasattr(tool_def, "function") else None
            if original_fn is None:
                continue
            original_tools[tool_name] = original_fn

            middleware = self

            @functools.wraps(original_fn)
            def wrapped(*args: Any, _orig=original_fn, _name=tool_name, **kw: Any) -> Any:
                verify_params = {k: v for k, v in kw.items() if k != "ctx"}
                approved, msg = middleware._verify_action(_name, verify_params)
                if not approved:
                    return msg
                return _orig(*args, **kw)

            tool_def.function = wrapped

        try:
            run_kwargs: dict[str, Any] = {}
            if deps is not None:
                run_kwargs["deps"] = deps
            if message_history is not None:
                run_kwargs["message_history"] = message_history
            if model is not None:
                run_kwargs["model"] = model
            run_kwargs.update(kwargs)

            result = agent.run_sync(prompt, **run_kwargs)
            return result
        finally:
            for tool_def in getattr(agent, "_function_tools", {}).values():
                tool_name = tool_def.name if hasattr(tool_def, "name") else str(tool_def)
                if tool_name in original_tools:
                    tool_def.function = original_tools[tool_name]
