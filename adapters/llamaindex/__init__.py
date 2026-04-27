"""EYDII tools for LlamaIndex.

Two integration points:

1. EydiiVerifyToolSpec — a BaseToolSpec bundle with verify, proof, and health tools
2. EydiiEventHandler — instrumentation handler that audits agent tool calls

Usage:
    from eydii_llamaindex import EydiiVerifyToolSpec

    spec = EydiiVerifyToolSpec(policy="finance-controls")
    tools = spec.to_tool_list()
    agent = FunctionAgent(tools=tools, llm=llm)
"""

__version__ = "0.2.0"

from .tool_spec import EydiiVerifyToolSpec
from .event_handler import EydiiEventHandler
from .execute import EydiiExecuteHandler

__all__ = ["EydiiVerifyToolSpec", "EydiiEventHandler", "EydiiExecuteHandler"]
