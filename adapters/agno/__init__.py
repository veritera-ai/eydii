"""Forge Verify tools and middleware for Agno (formerly Phidata).

Three integration points:

1. ForgeVerifyTool — a callable tool agents can use to verify actions
2. forge_wrap_tool — decorator that wraps any tool function with pre-execution verification
3. ForgeToolkit — an Agno Toolkit class that provides verification tools

Usage:
    from forge_agno import ForgeVerifyTool, forge_wrap_tool, ForgeToolkit
    from agno.agent import Agent

    # Option 1: Give the agent a verification tool
    forge = ForgeVerifyTool(policy="finance-controls")
    agent = Agent(tools=[forge])

    # Option 2: Wrap existing tools with verification
    @forge_wrap_tool(policy="finance-controls")
    def send_payment(amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)

    # Option 3: Use the Toolkit class
    agent = Agent(tools=[ForgeToolkit(policy="production-safety")])
"""

__version__ = "0.1.1"

from .tool import ForgeVerifyTool, forge_wrap_tool, ForgeToolkit
from .execute import ForgeExecuteHook, forge_execute_wrapper

__all__ = [
    "ForgeVerifyTool",
    "forge_wrap_tool",
    "ForgeToolkit",
    "ForgeExecuteHook",
    "forge_execute_wrapper",
]
