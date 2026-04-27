"""EYDII tool for CrewAI agents.

A CrewAI BaseTool that verifies actions through the EYDII /v1/verify API.
Agents use this tool to check whether an action is allowed before executing it.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from veritera import Eydii

logger = logging.getLogger("eydii_crewai")


class EydiiVerifyInput(BaseModel):
    """Input schema for the EYDII tool."""

    action: str = Field(
        ...,
        description="The action to verify (e.g. 'payment.create', 'email.send', 'db.delete')",
    )
    params: str = Field(
        default="{}",
        description=(
            "JSON string of action parameters "
            "(e.g. '{\"amount\": 100, \"to\": \"user@example.com\"}')"
        ),
    )


class EydiiVerifyTool(BaseTool):
    """CrewAI tool that verifies agent actions through EYDII policies.

    This inherits from ``crewai.tools.BaseTool`` so it can be passed directly
    to ``Agent(tools=[...])``.

    Usage::

        from eydii_crewai import EydiiVerifyTool

        tool = EydiiVerifyTool(policy="finance-controls")
        agent = Agent(
            role="Financial Analyst",
            tools=[tool],
        )

    Args:
        api_key: EYDII API key (or set VERITERA_API_KEY env var).
        base_url: EYDII API endpoint.
        agent_id: Identifier for this agent in EYDII audit logs.
        policy: Default policy to evaluate against.
        fail_closed: If True (default), deny when EYDII API is unreachable.
        timeout: HTTP timeout in seconds for EYDII API calls.
    """

    # --- BaseTool required fields ---
    name: str = "eydii_verify"
    description: str = (
        "Verify an AI agent action against security policies before executing it. "
        "Call this BEFORE performing any sensitive action (payments, emails, deletions, API calls). "
        "Returns APPROVED or DENIED with a reason."
    )
    args_schema: Type[BaseModel] = EydiiVerifyInput

    # --- EYDII configuration (excluded from the Pydantic schema shown to the LLM) ---
    _client: Any = None  # EYDII client instance, set in __init__
    _agent_id: str = "crewai-agent"
    _policy: Optional[str] = None
    _fail_closed: bool = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://id.veritera.ai",
        agent_id: str = "crewai-agent",
        policy: Optional[str] = None,
        fail_closed: bool = True,
        timeout: float = 10.0,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
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

    def _run(self, action: str, params: str = "{}") -> str:
        """Verify an action against EYDII policies.

        This is the method CrewAI's ``BaseTool.run()`` delegates to.

        Args:
            action: The action identifier (e.g. 'payment.create').
            params: JSON string of action parameters.

        Returns:
            Verification result string (APPROVED or DENIED with details).
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
