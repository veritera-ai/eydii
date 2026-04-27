"""EYDII tools and middleware for Agno (formerly Phidata).

Three integration points:

1. EydiiVerifyTool — a callable tool agents can use to verify actions
2. eydii_wrap_tool — decorator that wraps any tool function with pre-execution verification
3. EydiiToolkit — an Agno Toolkit class that provides verification tools

Usage:
    from eydii_agno import EydiiVerifyTool, eydii_wrap_tool, EydiiToolkit
    from agno.agent import Agent

    # Option 1: Give the agent a verification tool
    eydii = EydiiVerifyTool(policy="finance-controls")
    agent = Agent(tools=[eydii])

    # Option 2: Wrap existing tools with verification
    @eydii_wrap_tool(policy="finance-controls")
    def send_payment(amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)

    # Option 3: Use the Toolkit class
    agent = Agent(tools=[EydiiToolkit(policy="production-safety")])
"""

__version__ = "0.1.1"

from .tool import EydiiVerifyTool, eydii_wrap_tool, EydiiToolkit
from .execute import EydiiExecuteHook, eydii_execute_wrapper

__all__ = [
    "EydiiVerifyTool",
    "eydii_wrap_tool",
    "EydiiToolkit",
    "EydiiExecuteHook",
    "eydii_execute_wrapper",
]
