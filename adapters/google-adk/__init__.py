"""EYDII tools and callbacks for Google ADK.

Three integration points:

1. EydiiVerifyTool — a Google ADK tool agents can use to verify actions
2. eydii_before_tool_callback — pre-tool execution callback
3. eydii_wrap_tool — decorator wrapping any tool with verification

Usage:
    from eydii_google_adk import EydiiVerifyTool, eydii_before_tool_callback

    eydii = EydiiVerifyTool(policy="finance-controls")
    agent = Agent(tools=[eydii.as_tool()])

    # Or use a callback for automatic verification
    agent = Agent(
        tools=[...],
        before_tool_callback=eydii_before_tool_callback(policy="finance-controls"),
    )
"""

__version__ = "0.2.0"

from .tool import (
    EydiiVerifyTool,
    eydii_before_tool_callback,
    eydii_after_tool_callback,
    eydii_wrap_tool,
)
from .execute import EydiiExecuteHook, eydii_execute_wrap_tool

__all__ = [
    "EydiiVerifyTool",
    "eydii_before_tool_callback",
    "eydii_after_tool_callback",
    "eydii_wrap_tool",
    "EydiiExecuteHook",
    "eydii_execute_wrap_tool",
]
