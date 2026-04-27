"""EYDII Execute receipt middleware for Pydantic AI.

Automatically signs and submits receipts when Pydantic AI tools are invoked.

Usage:
    from eydii_pydantic_ai import eydii_execute_wrapper

    # Wrap a tool to automatically emit receipts
    @eydii_execute_wrapper(task_id="task_abc...", agent_id="finance-agent")
    async def send_payment(ctx, amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)

Or use the lower-level receipt hook:
    from eydii_pydantic_ai import EydiiExecuteHook

    hook = EydiiExecuteHook(task_id="task_abc...", agent_id="finance-agent")
    # Call hook.on_tool_use("payment.send") whenever a tool is invoked
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from collections.abc import Callable
from typing import Any, Optional

from veritera import Eydii, EydiiSigner

logger = logging.getLogger("eydii_pydantic_ai.execute")


class EydiiExecuteHook:
    """Hook that emits signed receipts for every tool invocation.

    Attach this to your Pydantic AI workflow to automatically track execution.
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
            logger.debug("Receipt submitted: %s (chain_index=%d)", result.receipt_id, result.chain_index)
            return {"receipt_id": result.receipt_id, "chain_index": result.chain_index}
        except Exception as exc:
            logger.warning("Failed to submit receipt: %s", exc)
            return {"error": str(exc)}

    async def on_tool_use_async(self, action_type: str) -> dict:
        """Async version of on_tool_use. Signs and submits a receipt.

        Returns the receipt response dict or an error dict.
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.on_tool_use(action_type),
            )
            return result
        except Exception as exc:
            logger.warning("Failed to submit receipt (async): %s", exc)
            return {"error": str(exc)}


def eydii_execute_wrapper(
    task_id: str,
    agent_id: str,
    api_key: Optional[str] = None,
    signing_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
):
    """Decorator that wraps a Pydantic AI tool to emit Execute receipts.

    After the tool executes successfully, a signed receipt is submitted
    to EYDII Execute with the tool name as the action type.

    Usage::

        @eydii_execute_wrapper(task_id="task_abc...", agent_id="finance-agent")
        async def send_payment(ctx, amount: float, recipient: str) -> str:
            return process_payment(amount, recipient)

    Args:
        task_id: The task identifier for receipt tracking.
        agent_id: The agent identifier for receipt tracking.
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        signing_key: Key for signing receipts (defaults to api_key).
        base_url: EYDII API endpoint.
    """
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Eydii(api_key=key, base_url=base_url, fail_closed=False)
    signer = EydiiSigner(signing_key=signing_key or key)

    def decorator(func: Callable) -> Callable:
        tool_name = getattr(func, "__name__", "unknown")

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Emit receipt after successful execution
            try:
                receipt_data = signer.sign_and_build(tool_name, agent_id, task_id)
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.execute_receipt_sync(**receipt_data),
                )
                logger.debug("Execute receipt emitted for %s", tool_name)
            except Exception as exc:
                logger.warning("Failed to emit Execute receipt for %s: %s", tool_name, exc)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            result = func(*args, **kwargs)

            # Emit receipt after successful execution
            try:
                receipt_data = signer.sign_and_build(tool_name, agent_id, task_id)
                client.execute_receipt_sync(**receipt_data)
                logger.debug("Execute receipt emitted for %s", tool_name)
            except Exception as exc:
                logger.warning("Failed to emit Execute receipt for %s: %s", tool_name, exc)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
