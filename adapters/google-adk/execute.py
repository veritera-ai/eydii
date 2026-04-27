"""EYDII Execute receipt hooks for Google ADK.

Automatically signs and submits receipts when Google ADK tools are invoked.

Usage:
    from eydii_google_adk import EydiiExecuteHook, eydii_execute_wrap_tool

    # Option 1: Hook for manual receipt emission
    hook = EydiiExecuteHook(task_id="task_abc...", agent_id="finance-agent")
    hook.on_tool_use("payment.create")

    # Option 2: Decorator wrapping tools with receipt emission
    @eydii_execute_wrap_tool(task_id="task_abc...", agent_id="finance-agent")
    def send_payment(amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

from veritera import Eydii, EydiiSigner

logger = logging.getLogger("eydii_google_adk.execute")


class EydiiExecuteHook:
    """Hook that emits signed receipts for Google ADK tool invocations.

    Attach this to your Google ADK workflow to automatically track execution.

    Usage::

        hook = EydiiExecuteHook(task_id="task_abc...", agent_id="finance-agent")

        # Call when a tool is invoked
        hook.on_tool_use("payment.create")

        # Or use as before/after callbacks
        agent = Agent(
            tools=[...],
            after_tool_callback=hook.after_tool_callback(),
        )
    """

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        api_key: Optional[str] = None,
        signing_key: Optional[str] = None,
        base_url: str = "https://veritera.ai",
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        self._client = Eydii(api_key=key, base_url=base_url, fail_closed=False)
        self._signer = EydiiSigner(signing_key=signing_key or key)

    def on_tool_use(self, action_type: str) -> dict:
        """Call this when a tool is invoked. Signs and submits a receipt.

        Returns the receipt response dict or an error dict.
        """
        try:
            receipt_data = self._signer.sign_and_build(action_type, self.agent_id, self.task_id)
            result = self._client.execute_receipt_sync(**receipt_data)
            logger.debug(
                "Receipt submitted: %s (chain_index=%d)",
                result.receipt_id,
                result.chain_index,
            )
            return {"receipt_id": result.receipt_id, "chain_index": result.chain_index}
        except Exception as exc:
            logger.warning("Failed to submit receipt: %s", exc)
            return {"error": str(exc)}

    def after_tool_callback(self) -> Callable:
        """Return a Google ADK after_tool_callback that emits receipts.

        Usage::

            hook = EydiiExecuteHook(task_id="task_abc...", agent_id="agent")
            agent = Agent(
                tools=[...],
                after_tool_callback=hook.after_tool_callback(),
            )
        """

        def _after_tool(
            tool_name: str,
            tool_args: dict,
            tool_result: Any,
            tool_context: Any = None,
        ) -> Optional[dict]:
            """Post-tool callback that emits a receipt. Non-blocking."""
            try:
                receipt_data = self._signer.sign_and_build(
                    tool_name, self.agent_id, self.task_id
                )
                receipt = self._client.execute_receipt_sync(**receipt_data)
                logger.debug(
                    "Receipt for %s: %s (chain=%d)",
                    tool_name,
                    receipt.receipt_id,
                    receipt.chain_index,
                )
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", tool_name, exc)

            return None  # Keep original result

        return _after_tool

    def emit_receipt(self, action_type: str) -> dict:
        """Manually emit a receipt for a custom action.

        Use this for actions not captured by tool wrapping (e.g., LLM calls).
        """
        try:
            receipt_data = self._signer.sign_and_build(action_type, self.agent_id, self.task_id)
            result = self._client.execute_receipt_sync(**receipt_data)
            return {"receipt_id": result.receipt_id, "chain_index": result.chain_index}
        except Exception as exc:
            logger.warning("Failed to emit receipt: %s", exc)
            return {"error": str(exc)}


def eydii_execute_wrap_tool(
    task_id: str,
    agent_id: str,
    api_key: Optional[str] = None,
    signing_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
) -> Callable:
    """Decorator that wraps a Google ADK tool with Execute receipt emission.

    The receipt is emitted AFTER the tool executes successfully.

    Usage::

        @eydii_execute_wrap_tool(task_id="task_abc...", agent_id="finance-agent")
        def send_payment(amount: float, recipient: str) -> str:
            \"\"\"Send a payment to a recipient.\"\"\"
            return process_payment(amount, recipient)

    Args:
        task_id: Task identifier for the receipt chain.
        agent_id: Agent identifier for the receipt.
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        signing_key: Key used to sign receipts (defaults to api_key).
        base_url: EYDII API endpoint.

    Returns:
        A decorator that wraps tool functions with receipt emission.
    """
    hook = EydiiExecuteHook(
        task_id=task_id,
        agent_id=agent_id,
        api_key=api_key,
        signing_key=signing_key,
        base_url=base_url,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            result = func(*args, **kwargs)

            # Emit receipt after successful execution
            tool_name = func.__name__
            try:
                receipt_data = hook._signer.sign_and_build(
                    tool_name, hook.agent_id, hook.task_id
                )
                receipt = hook._client.execute_receipt_sync(**receipt_data)
                logger.debug(
                    "Receipt for %s: %s (chain=%d)",
                    tool_name,
                    receipt.receipt_id,
                    receipt.chain_index,
                )
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", tool_name, exc)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            result = await func(*args, **kwargs)

            # Emit receipt after successful execution
            tool_name = func.__name__
            try:
                receipt_data = hook._signer.sign_and_build(
                    tool_name, hook.agent_id, hook.task_id
                )
                receipt = hook._client.execute_receipt_sync(**receipt_data)
                logger.debug(
                    "Receipt for %s: %s (chain=%d)",
                    tool_name,
                    receipt.receipt_id,
                    receipt.chain_index,
                )
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", tool_name, exc)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
