"""EYDII middleware for LangGraph / LangChain.

Intercepts every tool call and verifies it against EYDII policies before execution.

Usage:
    from langgraph.prebuilt import ToolNode, create_react_agent
    from eydii_langgraph import EydiiVerifyMiddleware

    middleware = EydiiVerifyMiddleware(policy="finance-controls")

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

from .middleware import EydiiVerifyMiddleware, eydii_verify_tool
from .execute import EydiiExecuteMiddleware

__all__ = ["EydiiVerifyMiddleware", "eydii_verify_tool", "EydiiExecuteMiddleware"]
