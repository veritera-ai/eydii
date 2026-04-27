"""Forge Execute receipt middleware for OpenAI Agents SDK.

Automatically signs and submits receipts when agent tools are invoked.

Usage:
    from forge_openai import ForgeExecuteGuardrail

    execute_guard = ForgeExecuteGuardrail(
        task_id="task_abc...",
        agent_id="finance-agent",
    )

    # Use as a tool guardrail that also emits receipts
    @function_tool(tool_input_guardrails=[execute_guard.tool_guardrail()])
    def process_payment(amount: float, recipient: str):
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from veritera import Forge, ReceiptSigner

logger = logging.getLogger("forge_openai.execute")


class ForgeExecuteGuardrail:
    """OpenAI Agents SDK guardrail that emits signed Execute receipts.

    Wraps tool invocations via ToolInputGuardrail. Each allowed tool call
    generates a signed receipt submitted to Forge Execute.
    """

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        api_key: Optional[str] = None,
        signing_key: Optional[str] = None,
        base_url: str = "https://forge.veritera.ai",
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        self._client = Forge(api_key=key, base_url=base_url, fail_closed=False)
        self._signer = ReceiptSigner(signing_key=signing_key or key)

    def tool_guardrail(self):
        """Return a ToolInputGuardrail that emits receipts.

        Usage:
            @function_tool(tool_input_guardrails=[guard.tool_guardrail()])
            def my_tool(...): ...
        """
        from agents import ToolInputGuardrail

        async def _verify_and_receipt(data: Any):
            tool_name = getattr(data, "tool_name", "unknown") if hasattr(data, "tool_name") else "tool_call"

            # Emit receipt
            try:
                receipt_data = self._signer.sign_and_build(tool_name, self.agent_id, self.task_id)
                result = self._client.execute_receipt_sync(**receipt_data)
                logger.debug("Receipt for %s: %s (chain=%d)", tool_name, result.receipt_id, result.chain_index)
            except Exception as exc:
                logger.warning("Failed to emit receipt for %s: %s", tool_name, exc)

            # Allow the tool to proceed
            return data.allow()

        return ToolInputGuardrail(guardrail_function=_verify_and_receipt, name="forge_execute_receipt")

    def emit_receipt(self, action_type: str) -> dict:
        """Manually emit a receipt for a custom action."""
        try:
            receipt_data = self._signer.sign_and_build(action_type, self.agent_id, self.task_id)
            result = self._client.execute_receipt_sync(**receipt_data)
            return {"receipt_id": result.receipt_id, "chain_index": result.chain_index}
        except Exception as exc:
            logger.warning("Failed to emit receipt: %s", exc)
            return {"error": str(exc)}
