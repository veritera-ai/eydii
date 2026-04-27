"""EYDII tool spec for LlamaIndex.

Provides a BaseToolSpec with verify_action, get_proof, and check_health tools
that LlamaIndex agents can use to verify actions before execution.

Usage:
    from eydii_llamaindex import EydiiVerifyToolSpec
    from llama_index.core.agent import FunctionAgent

    spec = EydiiVerifyToolSpec(policy="finance-controls")
    tools = spec.to_tool_list()

    agent = FunctionAgent(tools=tools + other_tools, llm=llm)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Optional

from veritera import Eydii

from llama_index.core.tools.tool_spec.base import BaseToolSpec

logger = logging.getLogger("eydii_llamaindex")


def _run_async(coro):
    """Run an async coroutine from sync code, handling nested event loops.

    If no event loop is running, uses asyncio.run().
    If an event loop IS running (common in async LlamaIndex agents),
    delegates to a thread pool to avoid 'cannot call asyncio.run()
    from a running event loop'.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(coro)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result(timeout=30)


class EydiiVerifyToolSpec(BaseToolSpec):
    """EYDII tool spec for LlamaIndex agents.

    Exposes three tools:
    - verify_action: Check if an action is allowed by policy
    - get_proof: Retrieve a cryptographic proof for audit
    - check_health: Verify the EYDII service is running

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
    """

    spec_functions = ["verify_action", "get_proof", "check_health"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://id.veritera.ai",
        agent_id: str = "llamaindex-agent",
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

    def verify_action(self, action: str, params: str = "{}") -> str:
        """Verify an AI agent action against EYDII security policies before executing it.

        Call this BEFORE performing any sensitive action (payments, emails, deletions, API calls).
        Returns APPROVED with a proof ID, or DENIED with a reason.

        Args:
            action: The action identifier to verify (e.g. 'payment.create', 'email.send').
            params: JSON string of action parameters (e.g. '{"amount": 100, "to": "user@example.com"}').
        """
        try:
            parsed = json.loads(params) if isinstance(params, str) else params
        except (json.JSONDecodeError, TypeError):
            parsed = {"raw": str(params)}

        try:
            result = self._client.verify_sync(
                action=action,
                agent_id=self._agent_id,
                params=parsed,
                policy=self._policy,
            )
        except Exception as exc:
            logger.error("EYDII verify error: %s", exc)
            return f"ERROR: Verification unavailable — {exc}"

        if result.verified:
            logger.debug("EYDII APPROVED: %s (proof=%s)", action, result.proof_id)
            return (
                f"APPROVED: {result.verdict} | "
                f"proof_id: {result.proof_id} | "
                f"latency: {result.latency_ms}ms | "
                f"You may proceed with this action."
            )

        logger.warning("EYDII DENIED: %s — %s", action, result.reason)
        return (
            f"DENIED: {result.reason} | "
            f"proof_id: {result.proof_id} | "
            f"Do NOT proceed with this action."
        )

    def get_proof(self, proof_id: str) -> str:
        """Retrieve a cryptographic verification proof by ID for audit purposes.

        Args:
            proof_id: The proof ID returned from a previous verify_action call.
        """
        try:
            proof = _run_async(self._client.get_proof(proof_id))
            return json.dumps(proof, indent=2, default=str)
        except Exception as exc:
            logger.error("EYDII get_proof error: %s", exc)
            return f"ERROR: Could not retrieve proof — {exc}"

    def check_health(self) -> str:
        """Check if the EYDII verification service is healthy and responding."""
        try:
            health = _run_async(self._client.health())
            return json.dumps(health, indent=2, default=str)
        except Exception as exc:
            logger.error("EYDII health check error: %s", exc)
            return f"ERROR: Health check failed — {exc}"
