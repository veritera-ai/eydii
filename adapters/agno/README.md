# agno-eydii

[![PyPI version](https://img.shields.io/pypi/v/agno-eydii.svg)](https://pypi.org/project/agno-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

**EYDII Verify tools and middleware for Agno — verify every agent action before execution.**

---

## Why EYDII?

When AI agents act autonomously, you need a way to enforce rules that the agents themselves cannot override. EYDII sits between your agents and their actions — every sensitive operation is verified against your policies in real time, with a cryptographic proof trail. No more hoping the system prompt holds; EYDII gives you external, tamper-proof verification that works even when agents delegate to other agents.

---

## Install

```bash
pip install agno-eydii
```

This installs `eydii_agno` and its dependencies (`veritera` SDK and `agno`).

---

## Prerequisites: Create a Policy

Before using EYDII with Agno, create a policy that defines what your agents are allowed to do. You only need to do this once:

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

A `default` policy is created automatically when you sign up — it blocks dangerous actions like database drops and admin overrides. You can use it immediately with `policy="default"`.

> **Tip:** `pip install veritera` to get the policy management SDK. See the [full policy docs](https://github.com/veritera-ai/eydii-python#policies).

---

## Quick Start

```python
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from eydii_agno import EydiiVerifyTool

os.environ["VERITERA_API_KEY"] = "vt_live_..."
os.environ["OPENAI_API_KEY"] = "sk-..."

# 1. Create a EYDII verification tool
verify = EydiiVerifyTool(policy="finance-controls")  # create this policy first (see above) -- or use "default"

# 2. Give it to your agent
agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[verify],
    instructions=[
        "You are a financial analyst.",
        "ALWAYS verify actions through eydii_verify before executing them.",
    ],
)

# 3. Run the agent — every action is verified
agent.print_response("Process the refund for order #12345 for $500")
```

The agent calls `eydii_verify` before executing sensitive actions. If an action is denied, the agent receives a `DENIED` response and adjusts its plan.

---

## Three Integration Points

### 1. EydiiVerifyTool — Agent Tool for Explicit Verification

The most direct integration. Give agents a callable tool they can use to check whether an action is allowed.

```python
from eydii_agno import EydiiVerifyTool
from agno.agent import Agent

tool = EydiiVerifyTool(
    policy="finance-controls",
    agent_id="analyst-bot",
    fail_closed=True,
)

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[tool],
)
```

**How the agent uses it:**

The agent calls `eydii_verify(action="payment.create", params='{"amount": 500, "currency": "USD"}')` and receives:

- `APPROVED: Allowed | proof_id: fp_abc123 | latency: 42ms` — proceed with the action.
- `DENIED: Amount exceeds $200 limit | proof_id: fp_def456 | Do NOT proceed with this action.` — the agent adjusts its plan.

**Constructor parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key |
| `base_url` | `str` | `https://veritera.ai` | EYDII API endpoint |
| `agent_id` | `str` | `"agno-agent"` | Identifier in audit logs |
| `policy` | `str` | `None` | Policy set to evaluate against |
| `fail_closed` | `bool` | `True` | Deny when API is unreachable |
| `timeout` | `float` | `10.0` | Request timeout in seconds |
| `skip_actions` | `list[str]` | `None` | Actions to skip verification for |
| `on_verified` | `Callable` | `None` | Callback when action is approved |
| `on_blocked` | `Callable` | `None` | Callback when action is denied |

### 2. eydii_wrap_tool() — Decorator for Pre-Execution Verification

Wraps any Agno tool function with automatic EYDII verification. The tool is only executed if EYDII approves the action.

```python
from eydii_agno import eydii_wrap_tool
from agno.agent import Agent

@eydii_wrap_tool(policy="finance-controls")
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)

@eydii_wrap_tool(policy="finance-controls")
def delete_record(record_id: str) -> str:
    """Delete a database record."""
    return db.delete(record_id)

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[send_payment, delete_record],
)
```

**How it works:**

1. The agent calls `send_payment(amount=500, recipient="user@example.com")`.
2. The decorator intercepts the call and sends a verification request to EYDII with action=`send_payment` and the function parameters.
3. If EYDII approves, the original function executes normally.
4. If EYDII denies, the function is NOT called and a denial message is returned.

### 3. EydiiToolkit — Agno Toolkit Class

An Agno `Toolkit` that exposes `verify_action` and `list_policies` as tools the agent can call.

```python
from eydii_agno import EydiiToolkit
from agno.agent import Agent

agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[EydiiToolkit(policy="production-safety")],
    instructions=[
        "You are a production operations agent.",
        "Always verify actions before executing them.",
    ],
)
```

**Tools provided:**

- `verify_action(action, params)` — Verify an action against EYDII policies. Same behavior as `EydiiVerifyTool`.
- `list_policies()` — List available EYDII verification policies.

---

## Execute Receipts

For execution tracking and audit trails, use the Execute integration:

### EydiiExecuteHook — Manual Receipt Emission

```python
from eydii_agno import EydiiExecuteHook

hook = EydiiExecuteHook(task_id="task_abc...", agent_id="research-agent")

# Call whenever a tool is invoked
receipt = hook.on_tool_use("file_read")
# Returns: {"receipt_id": "rx_...", "chain_index": 1}
```

### eydii_execute_wrapper — Automatic Receipt Emission

```python
from eydii_agno import eydii_execute_wrapper

@eydii_execute_wrapper(task_id="task_abc...", agent_id="research-agent")
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return process_payment(amount, recipient)

# Every successful call automatically emits a signed receipt
```

---

## Configuration Reference

| Config | Source | Required | Example |
|--------|--------|----------|---------|
| API key | `VERITERA_API_KEY` env var or `api_key=` parameter | Yes | `vt_live_abc123` |
| Base URL | `base_url=` parameter | No | `https://veritera.ai` |
| Policy | `policy=` parameter | No (but recommended) | `"finance-controls"` |
| Agent ID | `agent_id=` parameter | No | `"my-agno-agent"` |
| Fail closed | `fail_closed=` parameter | No (default: `True`) | `True` or `False` |
| Timeout | `timeout=` parameter | No (default: `10.0`) | `30.0` |

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                   Your Agno Agent                        │
│                                                         │
│  ┌───────────────────────────────────────────────┐      │
│  │              Agent                            │      │
│  │  tools=[eydii_verify, send_payment, ...]      │      │
│  └──────────────────┬────────────────────────────┘      │
│                     │                                   │
│         ┌───────────┼───────────┐                       │
│         │           │           │                       │
│    ┌────▼────┐ ┌────▼────┐ ┌────▼────┐                 │
│    │ Verify  │ │ Wrapped │ │ Toolkit │                 │
│    │  Tool   │ │  Tool   │ │  Tools  │                 │
│    └────┬────┘ └────┬────┘ └────┬────┘                 │
│         │           │           │                       │
└─────────┼───────────┼───────────┼───────────────────────┘
          │           │           │
          ▼           ▼           ▼
    ┌─────────────────────────────────────────┐
    │            EYDII Verify API             │
    │                                         │
    │  Policy Engine  │  Audit Trail  │ Proof │
    └─────────────────────────────────────────┘
```

1. **Agent calls tool** — The verification tool sends a request to the EYDII API.
2. **EYDII evaluates** — The policy engine checks the action and parameters against your defined policies.
3. **Result returned** — `APPROVED` (with proof ID) or `DENIED` (with reason and proof ID).
4. **Agent decides** — On approval, the agent proceeds. On denial, the agent adjusts its plan.
5. **Audit trail recorded** — Every verification produces a `proof_id` linking to a permanent, tamper-proof record.

---

## Error Handling

The package handles three failure modes:

### 1. EYDII API Unreachable

Controlled by `fail_closed`:

```python
# fail_closed=True (default) — deny when EYDII is down
tool = EydiiVerifyTool(policy="controls", fail_closed=True)
# Agent receives: "DENIED: Verification unavailable — ConnectionError(...). Action blocked (fail-closed)."

# fail_closed=False — allow when EYDII is down (use for non-critical paths)
tool = EydiiVerifyTool(policy="controls", fail_closed=False)
```

### 2. Invalid Parameters

If the agent passes malformed JSON as `params`, the tool wraps it safely:

```python
# Agent calls: eydii_verify(action="test", params="not valid json")
# Tool parses it as: {"raw": "not valid json"} and proceeds with verification
```

### 3. Wrapped Tool Denials

When a wrapped tool is denied, the function is not called:

```python
@eydii_wrap_tool(policy="finance-controls")
def send_payment(amount: float, recipient: str) -> str:
    return process_payment(amount, recipient)

# If denied: returns "DENIED: Action 'send_payment' blocked by EYDII: Amount exceeds limit"
# The process_payment function is never called
```

All errors are logged via Python's `logging` module under the `eydii_agno` logger:

```python
import logging
logging.getLogger("eydii_agno").setLevel(logging.DEBUG)
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VERITERA_API_KEY` | Yes (unless passed via `api_key=`) | Your EYDII API key. Get one at [id.veritera.ai/dashboard](https://id.veritera.ai/dashboard). |
| `OPENAI_API_KEY` | Yes (if using OpenAI models) | Your OpenAI key for the underlying language model. |

You can also pass the API key directly to avoid environment variables:

```python
tool = EydiiVerifyTool(api_key="vt_live_...", policy="my-policy")
```

---

## Other EYDII Integrations

EYDII works across the major agent frameworks. Use the same policies and audit trail regardless of which framework you choose.

| Framework | Package | Install |
|-----------|---------|---------|
| **CrewAI** | [crewai-eydii](https://github.com/veritera-ai/eydii-crewai) | `pip install crewai-eydii` |
| **OpenAI Agents SDK** | [eydii-openai](https://github.com/veritera-ai/eydii-openai) | `pip install openai-eydii` |
| **LangGraph** | [eydii-langchain](https://github.com/veritera-ai/eydii-langchain) | `pip install langgraph-eydii` |
| **LlamaIndex** | [eydii-llamaindex](https://github.com/veritera-ai/eydii-llamaindex) | `pip install llamaindex-eydii` |
| **Python SDK** | [veritera](https://github.com/veritera-ai/eydii-python) | `pip install veritera` |
| **JavaScript SDK** | [@veritera/sdk](https://github.com/veritera-ai/eydii-js) | `npm install veritera` |

---

## Resources

- [EYDII Documentation](https://id.veritera.ai/docs)
- [EYDII Dashboard](https://id.veritera.ai/dashboard)
- [Policy Configuration Guide](https://id.veritera.ai/docs/policies)
- [Agno Documentation](https://docs.agno.com)

---

## License

MIT — EYDII by [Veritera AI](https://id.veritera.ai)
