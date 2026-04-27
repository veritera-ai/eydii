"""Forge Verify tools and guardrails for CrewAI.

Three integration points:

1. ForgeVerifyTool — a CrewAI tool agents can use to verify actions
2. forge_task_guardrail — validates task output against Forge policies
3. forge_before_llm / forge_after_llm — LLM call hooks for pre/post verification

Usage:
    from forge_crewai import ForgeVerifyTool, forge_task_guardrail

    tool = ForgeVerifyTool(policy="finance-controls")
    agent = Agent(role="...", tools=[tool])

    task = Task(
        description="...",
        agent=agent,
        guardrail=forge_task_guardrail(policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .tool import ForgeVerifyTool
from .guardrail import forge_task_guardrail
from .hooks import forge_before_llm, forge_after_llm
from .execute import ForgeExecuteHook, forge_execute_task_wrapper

__all__ = [
    "ForgeVerifyTool",
    "forge_task_guardrail",
    "forge_before_llm",
    "forge_after_llm",
    "ForgeExecuteHook",
    "forge_execute_task_wrapper",
]
