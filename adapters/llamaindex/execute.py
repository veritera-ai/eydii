"""EYDII Execute receipt middleware for LlamaIndex.

Automatically signs and submits receipts when LlamaIndex tools are invoked.

Usage:
    from eydii_llamaindex import EydiiExecuteHandler
    from llama_index.core.instrumentation import get_dispatcher

    handler = EydiiExecuteHandler(
        task_id="task_abc...",
        agent_id="research-agent",
    )
    dispatcher = get_dispatcher()
    dispatcher.add_event_handler(handler)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from veritera import Eydii, EydiiSigner

logger = logging.getLogger("eydii_llamaindex.execute")


class EydiiExecuteHandler:
    """LlamaIndex event handler that emits signed receipts for tool calls.

    Hooks into the LlamaIndex instrumentation dispatcher to capture tool
    invocations and emit Execute receipts automatically.
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

    def handle(self, event: Any, **kwargs: Any) -> None:
        """Handle a LlamaIndex instrumentation event.

        Detects tool call events and emits receipts.
        """
        event_type = type(event).__name__

        # Map LlamaIndex event types to receipt action types
        action_map = {
            "ToolCallEvent": "tool_call",
            "FunctionCallEvent": "tool_call",
            "LLMCompletionStartEvent": "llm_call",
            "LLMChatStartEvent": "llm_call",
            "RetrievalStartEvent": "file_read",
            "QueryStartEvent": "file_read",
            "EmbeddingStartEvent": "llm_call",
        }

        action_type = action_map.get(event_type)
        if not action_type:
            return

        # Try to get a more specific action type from the event
        tool_name = getattr(event, "tool_name", None) or getattr(event, "function_name", None)
        if tool_name:
            action_type = tool_name

        try:
            receipt_data = self._signer.sign_and_build(action_type, self.agent_id, self.task_id)
            result = self._client.execute_receipt_sync(**receipt_data)
            logger.debug("Receipt for %s: %s (chain=%d)", action_type, result.receipt_id, result.chain_index)
        except Exception as exc:
            logger.warning("Failed to emit receipt for %s: %s", action_type, exc)

    def emit_receipt(self, action_type: str) -> dict:
        """Manually emit a receipt for a custom action."""
        try:
            receipt_data = self._signer.sign_and_build(action_type, self.agent_id, self.task_id)
            result = self._client.execute_receipt_sync(**receipt_data)
            return {"receipt_id": result.receipt_id, "chain_index": result.chain_index}
        except Exception as exc:
            logger.warning("Failed to emit receipt: %s", exc)
            return {"error": str(exc)}
