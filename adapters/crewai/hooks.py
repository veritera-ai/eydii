"""Forge LLM call hooks for CrewAI.

Intercept LLM calls at the lowest level — before the model runs and after it responds.

Usage:
    from forge_crewai import forge_before_llm, forge_after_llm

    # Register hooks (they apply globally to all CrewAI agents)
    forge_before_llm(policy="safety-controls")
    forge_after_llm()  # audit all responses
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from veritera import Forge

logger = logging.getLogger("forge_crewai")


def forge_before_llm(
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "crewai-agent",
    policy: Optional[str] = None,
    fail_closed: bool = True,
    max_iterations: Optional[int] = None,
):
    """Register a CrewAI @before_llm_call hook that verifies through Forge.

    This hook runs before every LLM call in the crew. It can block execution
    by returning False.

    Args:
        api_key: Forge API key (or set VERITERA_API_KEY env var).
        policy: Policy to evaluate against.
        fail_closed: If True, block LLM calls when Forge API is unreachable.
        max_iterations: If set, block after this many iterations (safety limit).
    """
    try:
        from crewai.hooks import before_llm_call, LLMCallHookContext
    except ImportError:
        logger.warning("CrewAI hooks not available — requires crewai>=0.80")
        return None

    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Forge(api_key=key, base_url=base_url, fail_closed=fail_closed)

    @before_llm_call
    def _forge_pre_check(context: LLMCallHookContext):
        # Safety limit on iterations
        if max_iterations and hasattr(context, "iterations"):
            if context.iterations > max_iterations:
                logger.warning("Forge: iteration limit exceeded (%d)", context.iterations)
                return False

        agent_role = context.agent.role if hasattr(context, "agent") and context.agent else "unknown"
        task_desc = ""
        if hasattr(context, "task") and context.task:
            task_desc = getattr(context.task, "description", "")[:500]

        try:
            result = client.verify_sync(
                action=f"llm.call.{agent_role}",
                agent_id=agent_id,
                params={
                    "agent_role": agent_role,
                    "task": task_desc,
                    "iterations": getattr(context, "iterations", 0),
                },
                policy=policy,
            )
        except Exception as exc:
            logger.error("Forge before_llm_call error: %s", exc)
            return None if not fail_closed else False

        if not result.verified:
            logger.warning("Forge DENIED LLM call for %s: %s", agent_role, result.reason)
            return False

        return None  # Allow

    return _forge_pre_check


def forge_after_llm(
    api_key: Optional[str] = None,
    base_url: str = "https://forge.veritera.ai",
    agent_id: str = "crewai-agent",
    policy: Optional[str] = None,
):
    """Register a CrewAI @after_llm_call hook that audits responses through Forge.

    This hook logs every LLM response to the Forge audit trail.
    It does not block — use forge_before_llm for blocking.
    """
    try:
        from crewai.hooks import after_llm_call, LLMCallHookContext
    except ImportError:
        logger.warning("CrewAI hooks not available — requires crewai>=0.80")
        return None

    key = api_key or os.environ.get("VERITERA_API_KEY", "")
    client = Forge(api_key=key, base_url=base_url, fail_closed=False)

    @after_llm_call
    def _forge_post_audit(context: LLMCallHookContext):
        response_text = getattr(context, "response", "")
        if response_text:
            response_text = str(response_text)[:2000]

        agent_role = context.agent.role if hasattr(context, "agent") and context.agent else "unknown"

        try:
            client.verify_sync(
                action=f"llm.response.{agent_role}",
                agent_id=agent_id,
                params={
                    "response_preview": response_text[:500],
                    "agent_role": agent_role,
                },
                policy=policy,
            )
        except Exception as exc:
            logger.debug("Forge after_llm_call audit error (non-blocking): %s", exc)

        return None  # Keep original response

    return _forge_post_audit
