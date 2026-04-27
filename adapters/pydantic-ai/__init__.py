"""Forge Verify tools and middleware for Pydantic AI.

Three integration points:

1. ForgeVerifyTool — a verification tool agents can call explicitly
2. forge_tool_wrapper — decorator that wraps any tool with Forge verification
3. ForgeMiddleware — intercepts all tool calls during agent.run()

Usage:
    from forge_pydantic_ai import ForgeVerifyTool, forge_tool_wrapper, ForgeMiddleware

    # Approach 1: Explicit verification tool
    forge_tool = ForgeVerifyTool(policy="finance-controls")
    agent.tool(forge_tool.verify)

    # Approach 2: Decorator wrapper
    @forge_tool_wrapper(policy="finance-controls")
    async def send_payment(ctx, amount: float, recipient: str) -> str:
        return process_payment(amount, recipient)

    # Approach 3: Middleware
    middleware = ForgeMiddleware(policy="finance-controls")
    result = await middleware.run(agent, "Send $500 to vendor")
"""

__version__ = "0.2.0"

from .tool import ForgeVerifyTool, forge_tool_wrapper, ForgeMiddleware
from .execute import ForgeExecuteHook, forge_execute_wrapper

__all__ = [
    "ForgeVerifyTool",
    "forge_tool_wrapper",
    "ForgeMiddleware",
    "ForgeExecuteHook",
    "forge_execute_wrapper",
]
