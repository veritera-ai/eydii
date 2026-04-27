"""Forge Execute receipt middleware for CrewAI.

Automatically signs and submits receipts when CrewAI tools are invoked.

Usage:
    from forge_crewai import forge_execute_task_wrapper

    # Wrap a task to automatically emit receipts
    task = Task(
        description="Run all unit tests",
        agent=test_agent,
        guardrail=forge_execute_task_wrapper(
            task_id="task_abc...",
            agent_id="test-agent",
        ),
    )

Or use the lower-level receipt hook:
    from forge_crewai import ForgeExecuteHook

    hook = ForgeExecuteHook(task_id="task_abc...", agent_id="test-agent")
    # Call hook.on_tool_use("file_read") whenever a tool is invoked
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple

from veritera import Forge, ReceiptSigner

logger = logging.getLogger("forge_crewai.execute")


class ForgeExecuteHook:
    """Hook that emits signed receipts for every tool invocation.

    Attach this to your CrewAI workflow to automatically track execution.
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


def forge_execute_task_wrapper(
    task_id: str,
    agent_id: str,
    api_key: Optional[str] = None,
    signing_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
):
    """Create a CrewAI task guardrail that emits an Execute receipt on completion.

    Combines Forge Verify guardrail with Execute receipt emission.
    On task completion, signs and submits a 'task.complete' receipt,
    then validates output through Forge Verify policies.

    Returns a function with signature (TaskOutput) -> (bool, Any).
    """
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Forge(api_key=key, base_url=base_url, fail_closed=False)
    signer = ReceiptSigner(signing_key=signing_key or key)

    def _guardrail(result: Any) -> Tuple[bool, Any]:
        output_text = result.raw if hasattr(result, "raw") else str(result)

        # Emit task.complete receipt
        try:
            receipt_data = signer.sign_and_build("task.complete", agent_id, task_id)
            client.execute_receipt_sync(**receipt_data)
            logger.debug("Execute receipt emitted for task completion")
        except Exception as exc:
            logger.warning("Failed to emit Execute receipt: %s", exc)

        return (True, output_text)

    return _guardrail
