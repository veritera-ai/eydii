"""Forge task guardrail for CrewAI.

Validates task output against Forge policies. If the output violates a policy,
the task is retried (up to guardrail_max_retries).

CrewAI guardrails receive either a ``TaskOutput`` or a ``LiteAgentOutput``.
Both have a ``.raw`` attribute; only ``TaskOutput`` has ``.description``.

Usage::

    task = Task(
        description="Process customer refund",
        agent=finance_agent,
        guardrail=forge_task_guardrail(policy="finance-controls"),
        guardrail_max_retries=3,
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Tuple, Union

from veritera import Forge

logger = logging.getLogger("forge_crewai")


def forge_task_guardrail(
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "crewai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
):
    """Create a CrewAI task guardrail that validates output through Forge.

    Returns a function with the signature
    ``(TaskOutput | LiteAgentOutput) -> tuple[bool, Any]``
    which is what ``Task(guardrail=...)`` expects.

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        base_url: Forge API endpoint.
        agent_id: Identifier for this agent in Forge audit logs.
        policy: Policy to evaluate against.
        fail_closed: If True, reject output when Forge API is unreachable.
    """
    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Forge(
        api_key=key,
        base_url=base_url,
        fail_closed=fail_closed,
    )

    def _guardrail(result: Any) -> Tuple[bool, Any]:
        """Validate task output against Forge policies.

        ``result`` is a ``TaskOutput`` (has ``.raw``, ``.description``) or a
        ``LiteAgentOutput`` (has ``.raw`` but NOT ``.description``).

        Returns:
            (True, output) if approved.
            (False, feedback) if denied -- CrewAI will retry the task.
        """
        output_text = result.raw if hasattr(result, "raw") else str(result)

        # TaskOutput has .description; LiteAgentOutput does not.
        description = getattr(result, "description", "") or ""

        try:
            verification = client.verify_sync(
                action="task.complete",
                agent_id=agent_id,
                params={
                    "output": output_text[:3000],
                    "task": description[:500],
                },
                policy=policy,
            )
        except Exception as exc:
            logger.error("Forge task guardrail error: %s", exc)
            if fail_closed:
                return (False, f"Task output blocked — verification unavailable: {exc}")
            return (True, output_text)

        if verification.verified:
            logger.debug("Forge APPROVED task output (proof=%s)", verification.proof_id)
            return (True, output_text)

        reason = verification.reason or "Policy violation"
        logger.warning("Forge DENIED task output: %s", reason)
        return (
            False,
            f"Forge policy violation: {reason}. Please revise your output to comply with the policy.",
        )

    return _guardrail
