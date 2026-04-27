"""EYDII Execute receipt middleware for Agno (formerly Phidata).

Automatically signs and submits receipts when Agno tools are invoked.

Usage:
    from eydii_agno import EydiiExecuteHook, eydii_execute_wrapper

    # Option 1: Hook for manual receipt emission
    hook = EydiiExecuteHook(task_id="task_abc...", agent_id="research-agent")
    hook.on_tool_use("file_read")

    # Option 2: Decorator that wraps a tool function with receipt emission
    @eydii_execute_wrapper(task_id="task_abc...", agent_id="research-agent")
    def send_payment(amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from typing import Any, Callable, Optional

from veritera import Eydii, EydiiSigner

logger = logging.getLogger("eydii_agno.execute")


class EydiiExecuteHook:
    """Hook that emits signed receipts for every tool invocation.

    Attach this to your Agno workflow to automatically track execution.

    Usage::

        from eydii_agno import EydiiExecuteHook

        hook = EydiiExecuteHook(task_id="task_abc...", agent_id="research-agent")
        # Call hook.on_tool_use("file_read") whenever a tool is invoked
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

    async def aon_tool_use(self, action_type: str) -> dict:
        """Async version of on_tool_use. Runs the sync call in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.on_tool_use, action_type)


def eydii_execute_wrapper(
    task_id: str,
    agent_id: str,
    api_key: Optional[str] = None,
    signing_key: Optional[str] = None,
    base_url: str = "https://veritera.ai",
) -> Callable:
    """Decorator that wraps an Agno tool function with EYDII Execute receipt emission.

    After the wrapped function executes successfully, a signed receipt is
    automatically submitted to the EYDII Execute API.

    Usage::

        from eydii_agno import eydii_execute_wrapper

        @eydii_execute_wrapper(task_id="task_abc...", agent_id="research-agent")
        def send_payment(amount: float, recipient: str) -> str:
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
        action_name = func.__name__

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            result = func(*args, **kwargs)

            # Emit receipt after successful execution
            try:
                receipt_data = signer.sign_and_build(action_name, agent_id, task_id)
                receipt = client.execute_receipt_sync(**receipt_data)
                logger.debug(
                    "Receipt for %s: %s (chain=%d)",
                    action_name,
                    receipt.receipt_id,
                    receipt.chain_index,
                )
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", action_name, exc)

            return result

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the tool first
            result = await func(*args, **kwargs)

            # Emit receipt after successful execution
            try:
                loop = asyncio.get_event_loop()
                receipt_data = await loop.run_in_executor(
                    None,
                    lambda: signer.sign_and_build(action_name, agent_id, task_id),
                )
                receipt = await loop.run_in_executor(
                    None,
                    lambda: client.execute_receipt_sync(**receipt_data),
                )
                logger.debug(
                    "Receipt for %s: %s (chain=%d)",
                    action_name,
                    receipt.receipt_id,
                    receipt.chain_index,
                )
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", action_name, exc)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator
