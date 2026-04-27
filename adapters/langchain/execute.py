"""EYDII Execute receipt middleware for LangGraph.

**PREVIEW** — Execute receipt submission requires the /v1/execute/receipt
endpoint, which is available in EYDII Enterprise. Contact sales@veritera.ai
for access. The signing and receipt building works locally regardless.

Usage:
    from eydii_langgraph import EydiiExecuteMiddleware

    execute_mw = EydiiExecuteMiddleware(
        task_id="task_abc...",
        agent_id="research-agent",
    )

    # Wrap tool calls to automatically emit receipts
    tool_node = ToolNode(tools, wrap_tool_call=execute_mw.wrap_tool_call)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from veritera import Eydii, EydiiSigner

logger = logging.getLogger("eydii_langgraph.execute")


class EydiiExecuteMiddleware:
    """LangGraph middleware that emits signed receipts for every tool call.

    Wraps tool execution via ToolNode's wrap_tool_call parameter.
    Each tool invocation generates a signed receipt submitted to EYDII Execute.
    """

    def __init__(
        self,
        task_id: str,
        agent_id: str,
        api_key: Optional[str] = None,
        signing_key: Optional[str] = None,
        base_url: str = "https://id.veritera.ai",
    ):
        self.task_id = task_id
        self.agent_id = agent_id
        key = api_key or os.environ.get("VERITERA_API_KEY", "")
        self._client = Eydii(api_key=key, base_url=base_url, fail_closed=False)
        self._signer = EydiiSigner(signing_key=signing_key or key)

    def wrap_tool_call(self, request: Any, handler: Callable) -> Any:
        """Wrap a LangGraph tool call with receipt emission.

        Signature matches LangGraph's ToolCallWrapper protocol:
            (ToolCallRequest, handler) -> ToolMessage

        The receipt is emitted AFTER the tool executes successfully.
        """
        tool_name = getattr(request, "name", None) or getattr(request, "tool_name", "unknown")

        # Execute the tool first
        result = handler(request)

        # Emit receipt after successful execution
        try:
            receipt_data = self._signer.sign_and_build(tool_name, self.agent_id, self.task_id)
            receipt = self._client.execute_receipt_sync(**receipt_data)
            logger.debug("Receipt for %s: %s (chain=%d)", tool_name, receipt.receipt_id, receipt.chain_index)
        except Exception as exc:
            logger.warning("Failed to emit receipt for %s: %s", tool_name, exc)

        return result

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
