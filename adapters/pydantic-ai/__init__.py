"""EYDII tools and middleware for Pydantic AI.

Three integration points:

1. EydiiVerifyTool — a verification tool agents can call explicitly
2. eydii_tool_wrapper — decorator that wraps any tool with EYDII verification
3. EydiiMiddleware — intercepts all tool calls during agent.run()

Usage:
    from eydii_pydantic_ai import EydiiVerifyTool, eydii_tool_wrapper, EydiiMiddleware

    # Approach 1: Explicit verification tool
    eydii_tool = EydiiVerifyTool(policy="finance-controls")
    agent.tool(eydii_tool.verify)

    # Approach 2: Decorator wrapper
    @eydii_tool_wrapper(policy="finance-controls")
    async def send_payment(ctx, amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)

    # Approach 3: Middleware
    middleware = EydiiMiddleware(policy="finance-controls")
    result = await middleware.run(agent, "Send $500 to vendor")
"""

__version__ = "0.2.0"

from .tool import EydiiVerifyTool, eydii_tool_wrapper, EydiiMiddleware
from .execute import EydiiExecuteHook, eydii_execute_wrapper

__all__ = [
    "EydiiVerifyTool",
    "eydii_tool_wrapper",
    "EydiiMiddleware",
    "EydiiExecuteHook",
    "eydii_execute_wrapper",
]
