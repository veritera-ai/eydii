"""Forge Verify tools for LlamaIndex.

Two integration points:

1. ForgeVerifyToolSpec — a BaseToolSpec bundle with verify, proof, and health tools
2. ForgeEventHandler — instrumentation handler that audits agent tool calls

Usage:
    from forge_llamaindex import ForgeVerifyToolSpec

    spec = ForgeVerifyToolSpec(policy="finance-controls")
    tools = spec.to_tool_list()
    agent = FunctionAgent(tools=tools, llm=llm)
"""

__version__ = "0.2.0"

from .tool_spec import ForgeVerifyToolSpec
from .event_handler import ForgeEventHandler
from .execute import ForgeExecuteHandler

__all__ = ["ForgeVerifyToolSpec", "ForgeEventHandler", "ForgeExecuteHandler"]
