"""Forge Verify middleware for LangGraph / LangChain.

Intercepts every tool call and verifies it against Forge policies before execution.

Usage:
    from langgraph.prebuilt import ToolNode, create_react_agent
    from forge_langgraph import ForgeVerifyMiddleware

    middleware = ForgeVerifyMiddleware(policy="finance-controls")

    tool_node = ToolNode(
        [send_payment, read_balance],
        wrap_tool_call=middleware.wrap_tool_call,
    )

    agent = create_react_agent(
        model="gpt-4.1",
        tools=tool_node,
    )
"""

__version__ = "0.2.0"

from .middleware import ForgeVerifyMiddleware, forge_verify_tool
from .execute import ForgeExecuteMiddleware

__all__ = ["ForgeVerifyMiddleware", "forge_verify_tool", "ForgeExecuteMiddleware"]
