"""Forge Verify guardrail for OpenAI Agents SDK.

Verify every AI agent tool call against your policies before execution.

Usage:
    from forge_openai import forge_tool_guardrail, forge_protect

    # Option 1: Attach guardrail to individual tools
    guardrail = forge_tool_guardrail(policy="finance-controls")

    @function_tool(tool_input_guardrails=[guardrail])
    def send_payment(amount: float, to: str) -> str:
        ...

    # Option 2: Protect all tools at once
    agent = Agent(
        name="finance-bot",
        tools=forge_protect(send_payment, read_balance, policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .guardrail import (
    ForgeGuardrail,
    forge_tool_guardrail,
    forge_protect,
    forge_input_guardrail,
)
from .execute import ForgeExecuteGuardrail

__all__ = [
    "ForgeGuardrail",
    "forge_tool_guardrail",
    "forge_protect",
    "forge_input_guardrail",
    "ForgeExecuteGuardrail",
]
