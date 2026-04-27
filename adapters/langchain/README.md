# langchain-eydii

[![PyPI](https://img.shields.io/pypi/v/langchain-eydii.svg)](https://pypi.org/project/langchain-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

EYDII verification middleware for LangGraph and LangChain. Every tool call checked before execution.

> [EYDII](https://github.com/veritera-ai/eydii-python) is the content-blind trust layer for AI agents — verifies actions without seeing your code, prompts, or data. Sub-15ms. Independently verifiable. [Learn more →](https://github.com/veritera-ai/eydii-python)

## Install

```bash
pip install langchain-eydii langgraph langchain-openai
```

## Quick Start

Add EYDII verification to any LangGraph agent in three lines:

```python
import os
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain_core.tools import tool
from eydii_langgraph import EydiiVerifyMiddleware

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["OPENAI_API_KEY"] = "sk-..."

@tool
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return f"Sent ${amount} to {recipient}"

@tool
def check_balance(account_id: str) -> str:
    """Check account balance."""
    return f"Account {account_id}: $12,340.00"

# Three lines — every tool call now goes through EYDII
middleware = EydiiVerifyMiddleware(policy="finance-controls")
tools = [send_payment, check_balance]
tool_node = ToolNode(tools, wrap_tool_call=middleware.wrap_tool_call)

agent = create_react_agent(model="gpt-4.1", tools=tool_node)
result = agent.invoke({"messages": [("user", "Send $500 to vendor@acme.com")]})
```

If approved, the tool executes normally. If denied, the agent receives a denial message and the tool never fires.

## Tutorial: Approved, Denied, and Mixed Scenarios

### Approved — Agent queries a database

```python
result = agent.invoke({
    "messages": [("user", "What were our top customers by spend last quarter?")]
})
```

```
APPROVED: query_database
tool: | customer_id | total_spend | ...
ai: Your top customers last quarter were C-1001 ($45,200) and C-1002 ($38,750).
```

### Denied — Agent tries a destructive operation

```python
result = agent.invoke({
    "messages": [("user", "Delete all records from the customers table older than 2020")]
})
```

```
BLOCKED: delete_records -- Destructive database operations require manual approval
ai: I'm unable to delete those records directly. Your organization's security
    policy requires manual approval for destructive database operations.
```

EYDII intercepted the call. The tool never executed. The agent explained the restriction naturally.

### Mixed — Some calls approved, some denied

```python
result = agent.invoke({
    "messages": [("user", "Find the Q1 revenue data and email it to external-partner@gmail.com")]
})
```

```
ai: [calls search_documents]          # APPROVED
tool: Found 3 documents: Q1 Revenue Report...
ai: [calls send_email]                # DENIED — external address blocked
ai: I found the Q1 Revenue Report, but I'm unable to email it to an external
    address. You can share it through your approved file-sharing platform.
```

## Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `policy` | `str` | `None` | Policy name to evaluate against (or uses your default policy) |
| `agent_id` | `str` | `"langgraph-agent"` | Agent identifier for audit trail |
| `fail_closed` | `bool` | `True` | Block actions when EYDII API is unreachable |
| `skip_actions` | `list[str]` | `[]` | Tool names that bypass verification (read-only/low-risk) |
| `on_verified` | `Callable` | `None` | Callback on approval |
| `on_blocked` | `Callable` | `None` | Callback on denial |

## Integration Patterns

**Middleware (recommended)** — Intercepts every tool call automatically:
```python
middleware = EydiiVerifyMiddleware(policy="my-policy")
tool_node = ToolNode(tools, wrap_tool_call=middleware.wrap_tool_call)
```

**Explicit tool** — Agent calls verification when it decides to:
```python
from eydii_langgraph import eydii_verify_tool
verify = eydii_verify_tool(policy="my-policy")
agent = create_react_agent(model="gpt-4.1", tools=[my_tool, verify])
```

## Prerequisites

Create a policy before using EYDII with LangGraph (one-time setup):

```python
from veritera import EydiiVerify
eydii = EydiiVerify(api_key="vt_live_...")
eydii.create_policy_sync("finance-controls", rules=[
    {"type": "action_whitelist", "params": {"allowed": ["payment.create", "balance.check"]}},
    {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
])
```

A `default` policy is created automatically when you sign up. [Full policy docs →](https://github.com/veritera-ai/eydii-python/blob/main/docs/verify.md)

## License

MIT — [EYDII](https://id.veritera.ai) by Veritera AI
