# google-adk-eydii

[![PyPI version](https://img.shields.io/pypi/v/google-adk-eydii.svg)](https://pypi.org/project/google-adk-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**EYDII tools and callbacks for Google ADK -- verify every agent action before execution.**

---

## Why EYDII?

When AI agents act autonomously, you need a way to enforce rules that the agents themselves cannot override. EYDII sits between your agents and their actions -- every sensitive operation is verified against your policies in real time, with a cryptographic proof trail. No more hoping the system prompt holds; EYDII gives you external, tamper-proof verification that works even when agents delegate to other agents.

---

## Install

```bash
pip install google-adk-eydii
```

This installs `eydii_google_adk` and its dependencies (`veritera` SDK and `google-adk`).

---

## Prerequisites: Create a Policy

Before using EYDII with Google ADK, create a policy that defines what your agents are allowed to do. You only need to do this once:

```python
from veritera import EydiiVerify

eydii = EydiiVerify(api_key="vt_live_...")  # Get your key at id.veritera.ai

# Create a policy from code
eydii.create_policy_sync(
    name="finance-controls",
    description="Controls for multi-agent financial operations",
    rules=[
        {"type": "action_whitelist", "params": {"allowed": ["trade.execute", "refund.process", "report.generate"]}},
        {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
    ],
)

# Or generate one from plain English
eydii.generate_policy_sync(
    "Allow trades under $10,000, refund processing, and report generation. Block all account deletions and unauthorized data exports.",
    save=True,
)
```

A `default` policy is created automatically when you sign up -- it blocks dangerous actions like database drops and admin overrides. You can use it immediately with `policy="default"`.

> **Tip:** `pip install veritera` to get the policy management SDK. See the [full policy docs](https://github.com/veritera-ai/eydii-python#policies).

---

## Quick Start

```python
import os
from google.adk import Agent
from eydii_google_adk import EydiiVerifyTool, eydii_before_tool_callback

os.environ["VERITERA_API_KEY"] = "vt_live_..."

# 1. Create a EYDII verification tool
eydii = EydiiVerifyTool(policy="finance-controls")  # create this policy first (see above) -- or use "default"

# 2. Give it to your agent as an explicit tool
agent = Agent(
    name="finance-bot",
    tools=[eydii.as_tool()],
)

# Or use a callback to verify ALL tool calls automatically
agent = Agent(
    name="finance-bot",
    tools=[send_payment, check_balance],
    before_tool_callback=eydii_before_tool_callback(policy="finance-controls"),
)
```

Every tool call is verified against your EYDII policy. If an action is denied, the agent receives a denial message and adjusts its plan. The tool never executes.

---

## Tutorial: Building a Verified Multi-Agent Workflow

This walkthrough builds a Google ADK agent where tools are protected by EYDII -- with automatic verification catching unauthorized operations.

### The Problem with Autonomous Agents

Google ADK agents make autonomous tool calls. But when agents act on their own:

- **System prompts drift** -- the LLM may ignore or reinterpret safety instructions over long conversations.
- **Inline rules are invisible** -- sub-agents and delegated tasks lose the original guardrails.
- **Chained actions compound risk** -- a data lookup (harmless) feeds an analysis (maybe harmless) that triggers a payment (definitely not harmless).

EYDII solves this by moving verification **outside** the agents. Every action hits the same external policy engine. No matter how the agent reasons, EYDII catches violations.

### Step 1 -- Set Up Your Environment

```python
import os
from google.adk import Agent
from eydii_google_adk import (
    EydiiVerifyTool,
    eydii_before_tool_callback,
    eydii_wrap_tool,
)

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["GOOGLE_API_KEY"] = "..."
```

### Step 2 -- Define Tools with EYDII Verification

```python
# Option A: Wrap individual tools with the decorator
@eydii_wrap_tool(policy="finance-controls")
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return f"Sent ${amount} to {recipient}"

@eydii_wrap_tool(policy="finance-controls")
def delete_records(table: str, condition: str) -> str:
    """Delete records from a database table."""
    return f"Deleted records from {table} where {condition}"

def check_balance(account_id: str) -> str:
    """Check account balance (read-only, no verification needed)."""
    return f"Account {account_id}: $12,340.00"
```

### Step 3 -- Build the Agent

```python
agent = Agent(
    name="finance-bot",
    model="gemini-2.0-flash",
    tools=[send_payment, delete_records, check_balance],
)
```

### Step 4 -- Run It

```python
# Approved scenario
response = agent.run("Send $500 to vendor@acme.com")
# EYDII APPROVED: send_payment -> executes normally

# Denied scenario
response = agent.run("Delete all records from the customers table")
# EYDII DENIED: delete_records -> returns denial message, tool never executes
```

### What Happens at Runtime

1. **Agent decides** to call a tool (e.g., `send_payment`).
2. **EYDII intercepts** -- the wrapper sends a verification request to the EYDII API.
3. **Policy evaluates** -- EYDII checks the action and parameters against your defined policies.
4. **Result returned** -- `APPROVED` (tool executes) or `DENIED` (tool blocked, agent gets denial message).
5. **Audit trail** -- every verification produces a `proof_id` linking to a permanent record.

---

## Three Integration Points

### 1. EydiiVerifyTool -- Explicit Verification Tool

Give agents a tool they can call to check whether an action is allowed.

```python
from eydii_google_adk import EydiiVerifyTool
from google.adk import Agent

eydii = EydiiVerifyTool(
    policy="finance-controls",
    agent_id="finance-bot",
    fail_closed=True,
)

agent = Agent(
    name="finance-bot",
    tools=[eydii.as_tool()],
)
```

The agent calls `eydii_verify(action="payment.create", params='{"amount": 500}')` and receives:

- `APPROVED: Allowed | proof_id: fp_abc123 | latency: 42ms` -- proceed with the action.
- `DENIED: Amount exceeds $200 limit | proof_id: fp_def456 | Do NOT proceed with this action.` -- the agent adjusts its plan.

### 2. eydii_before_tool_callback -- Automatic Pre-Tool Verification

Intercepts every tool call automatically. No changes to your tools required.

```python
from eydii_google_adk import eydii_before_tool_callback
from google.adk import Agent

agent = Agent(
    name="finance-bot",
    tools=[send_payment, check_balance, delete_records],
    before_tool_callback=eydii_before_tool_callback(
        policy="finance-controls",
        agent_id="finance-bot",
        skip_actions=["check_balance"],  # read-only, no verification needed
        on_blocked=lambda action, reason: print(f"BLOCKED: {action} -- {reason}"),
    ),
)
```

**When to use:** Most cases. You want a security layer that works regardless of what the LLM decides to do.

### 3. eydii_wrap_tool -- Decorator for Individual Tools

Wraps specific tool functions with verification. Only the wrapped tools are verified.

```python
from eydii_google_adk import eydii_wrap_tool

@eydii_wrap_tool(policy="finance-controls")
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)

@eydii_wrap_tool(policy="finance-controls")
def delete_records(table: str, condition: str) -> str:
    """Delete records from a database table."""
    return delete_from_table(table, condition)
```

**When to use:** When you want per-tool control, or when some tools need different policies than others.

---

## Configuration Reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key. Starts with `vt_live_` (production) or `vt_test_` (sandbox). |
| `base_url` | `str` | `https://veritera.ai` | EYDII API endpoint. Override for self-hosted deployments. |
| `agent_id` | `str` | `"google-adk-agent"` | Identifier for this agent in EYDII audit logs and dashboards. |
| `policy` | `str` | `None` | Policy name to evaluate actions against. When `None`, the default policy for your API key is used. |
| `fail_closed` | `bool` | `True` | When `True`, actions are denied if the EYDII API is unreachable. When `False`, actions are allowed through on API failure. |
| `timeout` | `float` | `10.0` | HTTP request timeout in seconds for the EYDII API call. |
| `skip_actions` | `list[str]` | `[]` | Tool names that bypass verification entirely. Use for read-only or low-risk tools. |
| `on_verified` | `Callable` | `None` | Callback function `(action: str, result) -> None` called when an action is approved. |
| `on_blocked` | `Callable` | `None` | Callback function `(action: str, reason: str) -> None` called when an action is denied. |

---

## How It Works

```
User message
    |
    v
Google ADK Agent decides to call a tool
    |
    v
EYDII verification layer (callback / wrapper / explicit tool)
    |
    +---> Is tool in skip_actions?
    |         YES --> Execute tool normally
    |         NO  --> Call EYDII /v1/verify
    |                     |
    |                     +---> APPROVED
    |                     |         --> Execute tool normally
    |                     |         --> Call on_verified callback
    |                     |
    |                     +---> DENIED
    |                     |         --> Return denial message
    |                     |         --> Call on_blocked callback
    |                     |         --> Tool NEVER executes
    |                     |
    |                     +---> API ERROR
    |                               --> fail_closed=True?  --> Deny
    |                               --> fail_closed=False? --> Execute tool
    v
Agent receives tool result (or denial message)
    |
    v
Agent responds to user
```

Each verification call sends the following to EYDII:

- **action** -- the tool name (e.g., `"send_payment"`)
- **agent_id** -- which agent is making the call
- **params** -- the tool arguments as a dictionary
- **policy** -- which policy to evaluate against

EYDII evaluates the action and returns a verdict with a `proof_id` for audit trail purposes.

---

## Error Handling

### EYDII API Unreachable

Controlled by `fail_closed`:

```python
# fail_closed=True (default) -- deny the action when EYDII is unreachable
eydii = EydiiVerifyTool(policy="controls", fail_closed=True)

# fail_closed=False -- allow the action through when EYDII is unreachable
eydii = EydiiVerifyTool(policy="controls", fail_closed=False)
```

### Invalid Parameters

If the agent passes malformed JSON as `params`, the tool wraps it safely:

```python
# Agent calls: eydii_verify(action="test", params="not valid json")
# Tool parses it as: {"raw": "not valid json"} and proceeds with verification
```

### Logging

All verification decisions are logged via Python's `logging` module under the `eydii_google_adk` logger:

```python
import logging
logging.getLogger("eydii_google_adk").setLevel(logging.DEBUG)
```

Log output:

```
DEBUG:eydii_google_adk:EYDII APPROVED: send_payment (proof=fp_abc123)
WARNING:eydii_google_adk:EYDII DENIED: delete_records -- Destructive operations blocked
ERROR:eydii_google_adk:EYDII verify error for send_email: Connection timed out
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VERITERA_API_KEY` | Yes (unless passed directly) | Your EYDII API key. Get one at [veritera.ai/dashboard](https://id.veritera.ai/dashboard). |
| `GOOGLE_API_KEY` | For Gemini models | Required if using Gemini models via Google ADK. |

You can also pass the API key directly to avoid environment variables:

```python
eydii = EydiiVerifyTool(api_key="vt_live_...", policy="my-policy")
```

---

## Other EYDII Integrations

EYDII works across the major agent frameworks. Use the same policies and audit trail regardless of which framework you choose.

| Framework | Package | Install |
|-----------|---------|---------|
| **Google ADK** | [google-adk-eydii](https://github.com/veritera-ai/eydii-google-adk) | `pip install google-adk-eydii` |
| **OpenAI Agents SDK** | [eydii-openai](https://github.com/veritera-ai/eydii-openai) | `pip install openai-eydii` |
| **LangGraph** | [langchain-eydii](https://github.com/veritera-ai/langchain-eydii) | `pip install langchain-eydii` |
| **CrewAI** | [crewai-eydii](https://github.com/veritera-ai/eydii-crewai) | `pip install crewai-eydii` |
| **LlamaIndex** | [eydii-llamaindex](https://github.com/veritera-ai/eydii-llamaindex) | `pip install llamaindex-eydii` |
| **Python SDK** | [veritera](https://github.com/veritera-ai/eydii-python) | `pip install veritera` |

---

## Resources

- [EYDII Documentation](https://id.veritera.ai/docs)
- [EYDII Dashboard](https://id.veritera.ai/dashboard)
- [Policy Configuration Guide](https://id.veritera.ai/docs/policies)
- [Google ADK Documentation](https://google.github.io/adk-docs/)

---

## License

MIT -- EYDII by [Veritera AI](https://id.veritera.ai)
