# pydantic-ai-eydii

[![PyPI version](https://img.shields.io/pypi/v/pydantic-ai-eydii.svg)](https://pypi.org/project/pydantic-ai-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**EYDII tools and middleware for Pydantic AI -- verify every agent action before execution.**

---

## Why EYDII?

When AI agents act autonomously, you need a way to enforce rules that the agents themselves cannot override. EYDII sits between your agents and their actions -- every sensitive operation is verified against your policies in real time, with a cryptographic proof trail. No more hoping the system prompt holds; EYDII gives you external, tamper-proof verification that works even when agents chain tool calls or operate across multi-step workflows.

---

## Install

```bash
pip install pydantic-ai-eydii
```

This installs `eydii_pydantic_ai` and its dependencies (`veritera` SDK and `pydantic-ai`).

For a complete agent setup, you will also need an LLM provider:

```bash
pip install pydantic-ai-eydii pydantic-ai[openai]
```

---

## Prerequisites: Create a Policy

Before using EYDII with Pydantic AI, create a policy that defines what your agents are allowed to do. You only need to do this once:

```python
from veritera import EydiiVerify

eydii = EydiiVerify(api_key="vt_live_...")  # Get your key at id.veritera.ai

# Create a policy from code
eydii.create_policy_sync(
    name="finance-controls",
    description="Controls for financial and data operations",
    rules=[
        {"type": "action_whitelist", "params": {"allowed": ["payment.send", "balance.check", "report.generate"]}},
        {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
    ],
)

# Or generate one from plain English
eydii.generate_policy_sync(
    "Allow payments under $10,000, balance checks, and report generation. Block all deletions and unauthorized data exports.",
    save=True,
)
```

A `default` policy is created automatically when you sign up -- it blocks dangerous actions like database drops and admin overrides. You can use it immediately with `policy="default"`.

> **Tip:** `pip install veritera` to get the policy management SDK. See the [full policy docs](https://github.com/veritera-ai/eydii-python#policies).

---

## Quick Start

```python
import os
from pydantic_ai import Agent
from eydii_pydantic_ai import EydiiVerifyTool

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["OPENAI_API_KEY"] = "sk-..."

# 1. Create a EYDII verification tool
eydii_tool = EydiiVerifyTool(policy="finance-controls")  # create this policy first (see above) -- or use "default"

# 2. Create your agent and register the tool
agent = Agent('openai:gpt-4o', system_prompt="You are a financial assistant. Verify actions before executing them.")
agent.tool(eydii_tool.verify)

# 3. Run the agent -- it will call eydii_verify before sensitive actions
result = await agent.run("Send $500 to vendor@acme.com")
print(result.data)
```

The agent calls `eydii_verify` before executing sensitive actions. If an action is denied, the agent receives a `DENIED` response and adjusts its plan.

---

## Tutorial: Building a Verified Financial Agent

This walkthrough builds a Pydantic AI agent that handles financial operations -- with EYDII verifying every action before execution.

### The Problem with Unchecked Tool Calls

Pydantic AI agents can call any tool you register. But some actions should not execute without policy checks:

- **Payments above limits** -- a tool that sends $50,000 when the policy caps single transactions at $10,000.
- **Unauthorized data access** -- an agent querying sensitive tables it should not touch.
- **Destructive operations** -- deletions, bulk exports, or admin actions triggered by a misinterpreted prompt.

EYDII solves this by intercepting tool calls **before** they execute. The policy engine runs outside the agent -- the agent cannot bypass, ignore, or modify the rules.

### Step 1 -- Set Up Your Environment

```python
import os
from pydantic_ai import Agent

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["OPENAI_API_KEY"] = "sk-..."
```

### Step 2 -- Define Your Tools

```python
async def send_payment(ctx, amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return f"Sent ${amount} to {recipient}"

async def check_balance(ctx, account_id: str) -> str:
    """Check account balance (read-only)."""
    return f"Account {account_id}: $12,340.00"

async def delete_account(ctx, account_id: str) -> str:
    """Delete a customer account permanently."""
    return f"Account {account_id} deleted"
```

### Step 3 -- Wrap Tools with EYDII Verification

```python
from eydii_pydantic_ai import eydii_tool_wrapper

@eydii_tool_wrapper(
    policy="finance-controls",
    agent_id="finance-bot",
    skip_actions=["check_balance"],  # read-only tool, always allowed
    on_blocked=lambda action, reason: print(f"BLOCKED: {action} -- {reason}"),
    on_verified=lambda action, result: print(f"APPROVED: {action}"),
)
async def send_payment(ctx, amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return f"Sent ${amount} to {recipient}"

@eydii_tool_wrapper(policy="finance-controls", agent_id="finance-bot")
async def delete_account(ctx, account_id: str) -> str:
    """Delete a customer account permanently."""
    return f"Account {account_id} deleted"
```

### Step 4 -- Build and Run the Agent

```python
agent = Agent(
    'openai:gpt-4o',
    system_prompt="You are a financial assistant. Process transactions safely.",
    tools=[send_payment, check_balance, delete_account],
)

# Approved scenario
result = await agent.run("Check balance for account A-1001 and send $500 to vendor@acme.com")
print(result.data)

# Denied scenario
result = await agent.run("Delete account A-1001")
print(result.data)
```

### What Happens at Runtime

1. **check_balance** -- skipped (in `skip_actions`), executes normally.
2. **send_payment** -- EYDII verifies `amount=500, recipient=vendor@acme.com` against `finance-controls` policy. Approved; tool executes.
3. **delete_account** -- EYDII checks `account_id=A-1001`. Denied; tool returns `"Action 'delete_account' denied by EYDII: Destructive account operations require manual approval"`. The agent relays the restriction to the user.

Every verification produces a `proof_id` that links to a tamper-proof audit record in your EYDII dashboard.

---

## Three Integration Approaches

### 1. EydiiVerifyTool -- Explicit Verification Tool

Give the agent a tool it calls to check whether an action is allowed. The agent decides when to verify.

```python
from pydantic_ai import Agent
from eydii_pydantic_ai import EydiiVerifyTool

eydii_tool = EydiiVerifyTool(
    policy="finance-controls",
    agent_id="analyst-bot",
    fail_closed=True,
)

agent = Agent('openai:gpt-4o')
agent.tool(eydii_tool.verify)
```

**How the agent uses it:**

The agent calls `eydii_verify(action="payment.create", params='{"amount": 500, "currency": "USD"}')` and receives:

- `APPROVED: Allowed | proof_id: fp_abc123 | latency: 42ms` -- proceed with the action.
- `DENIED: Amount exceeds $200 limit | proof_id: fp_def456 | Do NOT proceed with this action.` -- the agent adjusts its plan.

**When to use:** When you want the agent to reason about when verification is needed.

### 2. eydii_tool_wrapper -- Decorator Wrapper

Wraps any Pydantic AI tool with automatic EYDII verification. The tool is verified before execution -- no agent reasoning required.

```python
from eydii_pydantic_ai import eydii_tool_wrapper

@eydii_tool_wrapper(
    policy="finance-controls",
    agent_id="finance-bot",
    skip_actions=["check_balance"],
)
async def send_payment(ctx, amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)
```

**When to use:** When you want verification on specific tools without modifying the agent. Best for targeted protection on high-risk tools.

### 3. EydiiMiddleware -- Automatic Verification on All Tools

Wraps `agent.run()` to verify every tool call against EYDII policies. No changes to tool definitions required.

```python
from pydantic_ai import Agent
from eydii_pydantic_ai import EydiiMiddleware

agent = Agent('openai:gpt-4o', tools=[send_payment, check_balance])

middleware = EydiiMiddleware(
    policy="finance-controls",
    agent_id="finance-bot",
    skip_actions=["check_balance"],
)

# All tool calls are verified automatically
result = await middleware.run(agent, "Send $500 to vendor@acme.com")
```

**When to use:** When you want a blanket security layer across all tools. Best for production deployments where every action must be verified.

---

## Configuration Reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key. Starts with `vt_live_` (production) or `vt_test_` (sandbox). |
| `base_url` | `str` | `https://veritera.ai` | EYDII API endpoint. Override for self-hosted deployments. |
| `agent_id` | `str` | `"pydantic-ai-agent"` | Identifier for this agent in EYDII audit logs and dashboards. |
| `policy` | `str` | `None` | Policy name to evaluate actions against. When `None`, the default policy for your API key is used. |
| `fail_closed` | `bool` | `True` | When `True`, actions are denied if the EYDII API is unreachable. When `False`, actions are allowed through on API failure. |
| `timeout` | `float` | `10.0` | HTTP request timeout in seconds for the EYDII API call. |
| `skip_actions` | `list[str]` | `[]` | Tool names that bypass verification entirely. Use for read-only or low-risk tools. |
| `on_verified` | `Callable` | `None` | Callback function `(action: str, result) -> None` called when an action is approved. |
| `on_blocked` | `Callable` | `None` | Callback function `(action: str, reason: str) -> None` called when an action is denied. |

---

## How It Works

```
User prompt
    |
    v
Pydantic AI Agent decides to call a tool
    |
    v
EYDII Verification Layer
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
    |                     |         --> Return denial message to agent
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

## EYDII Execute -- Receipt Tracking

Track every tool execution with cryptographic receipts using EYDII Execute.

### EydiiExecuteHook -- Manual Receipt Emission

```python
from eydii_pydantic_ai import EydiiExecuteHook

hook = EydiiExecuteHook(
    task_id="task_abc123",
    agent_id="finance-agent",
)

# Emit a receipt when a tool is used
receipt = hook.on_tool_use("payment.send")
# {"receipt_id": "rx_...", "chain_index": 42}
```

### eydii_execute_wrapper -- Automatic Receipt Emission

```python
from eydii_pydantic_ai import eydii_execute_wrapper

@eydii_execute_wrapper(task_id="task_abc123", agent_id="finance-agent")
async def send_payment(ctx, amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)
```

Every successful tool execution automatically emits a signed receipt to the EYDII Execute chain.

---

## Combining Verify + Execute

Use both EYDII Verify (pre-execution policy check) and EYDII Execute (post-execution receipt) together:

```python
from eydii_pydantic_ai import eydii_tool_wrapper, eydii_execute_wrapper

@eydii_execute_wrapper(task_id="task_abc123", agent_id="finance-agent")
@eydii_tool_wrapper(policy="finance-controls")
async def send_payment(ctx, amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)
```

The flow:
1. **EYDII Verify** checks the action against your policy -- blocks if denied.
2. The tool executes (only if approved).
3. **EYDII Execute** emits a signed receipt for the completed action.

---

## Links

- [EYDII Documentation](https://id.veritera.ai/docs)
- [EYDII Python SDK](https://github.com/veritera-ai/eydii-python)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [API Reference](https://id.veritera.ai/docs/api)
