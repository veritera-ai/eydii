"""Forge Verify tools and callbacks for Google ADK.

Three integration points:

1. ForgeVerifyTool — a Google ADK tool agents can use to verify actions
2. forge_before_tool_callback — pre-tool execution callback
3. forge_wrap_tool — decorator wrapping any tool with verification

Usage:
    from forge_google_adk import ForgeVerifyTool, forge_before_tool_callback

    forge = ForgeVerifyTool(policy="finance-controls")
    agent = Agent(tools=[forge.as_tool()])

    # Or use a callback for automatic verification
    agent = Agent(
        tools=[...],
        before_tool_callback=forge_before_tool_callback(policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .tool import (
    ForgeVerifyTool,
    forge_before_tool_callback,
    forge_after_tool_callback,
    forge_wrap_tool,
)
from .execute import ForgeExecuteHook, forge_execute_wrap_tool

__all__ = [
    "ForgeVerifyTool",
    "forge_before_tool_callback",
    "forge_after_tool_callback",
    "forge_wrap_tool",
    "ForgeExecuteHook",
    "forge_execute_wrap_tool",
]
