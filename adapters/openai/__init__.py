"""EYDII guardrail for OpenAI Agents SDK.

Verify every AI agent tool call against your policies before execution.

Usage:
    from eydii_openai import eydii_tool_guardrail, eydii_protect

    # Option 1: Attach guardrail to individual tools
    guardrail = eydii_tool_guardrail(policy="finance-controls")

    @function_tool(tool_input_guardrails=[guardrail])
    def send_payment(amount: float, to: str) -> str:
        ...

    # Option 2: Protect all tools at once
    agent = Agent(
        name="finance-bot",
        tools=eydii_protect(send_payment, read_balance, policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .guardrail import (
    EydiiGuardrail,
    eydii_tool_guardrail,
    eydii_protect,
    eydii_input_guardrail,
)
from .execute import EydiiExecuteGuardrail

__all__ = [
    "EydiiGuardrail",
    "eydii_tool_guardrail",
    "eydii_protect",
    "eydii_input_guardrail",
    "EydiiExecuteGuardrail",
]
