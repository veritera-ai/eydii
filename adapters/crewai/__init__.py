"""EYDII tools and guardrails for CrewAI.

Three integration points:

1. EydiiVerifyTool — a CrewAI tool agents can use to verify actions
2. eydii_task_guardrail — validates task output against EYDII policies
3. eydii_before_llm / eydii_after_llm — LLM call hooks for pre/post verification

Usage:
    from eydii_crewai import EydiiVerifyTool, eydii_task_guardrail

    tool = EydiiVerifyTool(policy="finance-controls")
    agent = Agent(role="...", tools=[tool])

    task = Task(
        description="...",
        agent=agent,
        guardrail=eydii_task_guardrail(policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .tool import EydiiVerifyTool
from .guardrail import eydii_task_guardrail
from .hooks import eydii_before_llm, eydii_after_llm
from .execute import EydiiExecuteHook, eydii_execute_task_wrapper

__all__ = [
    "EydiiVerifyTool",
    "eydii_task_guardrail",
    "eydii_before_llm",
    "eydii_after_llm",
    "EydiiExecuteHook",
    "eydii_execute_task_wrapper",
]
