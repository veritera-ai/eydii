# llama-index-tools-eydii

[![PyPI version](https://img.shields.io/pypi/v/llama-index-tools-eydii.svg)](https://pypi.org/project/llama-index-tools-eydii/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/veritera-ai/eydii-llamaindex/actions/workflows/ci.yml/badge.svg)](https://github.com/veritera-ai/eydii-llamaindex/actions/workflows/ci.yml)

**EYDII tools for LlamaIndex -- verify every agent action before execution.**

---

## Why EYDII?

AI agents are taking real-world actions — sending emails, moving money, accessing databases, calling APIs. But there's no independent system verifying what they do.

The agent frameworks (LangChain, CrewAI, OpenAI Agents SDK) provide no enforcement beyond prompt engineering. When an agent goes rogue, you find out from your customers, not from your monitoring. This is like letting employees process transactions with no audit department, no compliance checks, no separation of duties.

EYDII is the independent verification layer for AI agents. It checks every action before execution (**Verify**) and tracks every execution with cryptographic receipts (**Execute**). One SDK. Sub-15ms latency. Works with every major agent framework.

## How EYDII Is Different

### Content-Blind

EYDII never sees your agent's instructions, prompts, code, data, or outputs. It verifies the action type and behavioral pattern only. Your intellectual property stays yours.

Every other tool in this space — Guardrails AI, NeMo Guardrails, LlamaGuard — requires reading your prompts and outputs to make decisions. EYDII doesn't. That's not a feature difference — it's a fundamentally different architecture.

### Trustless Verification

Ed25519 asymmetric cryptography. The agent signs receipts with a private key only it holds. Anyone with the public key can verify independently. You don't trust Veritera. You trust math. No shared secrets. No phone-home. The proof stands on its own.

### Independent Enforcement

Policies are enforced outside the agent. The agent cannot override, bypass, or modify its own guardrails. This is separation of duties — the same principle that prevents an accountant from approving their own expenses.

> EYDII works like a home security system. Your security company doesn't know what's inside your house. They don't inventory your jewelry or read your mail. They monitor doors opening, windows breaking, motion where there shouldn't be motion. They protect the pattern — not the contents. EYDII does the same for your AI agents.

Not just what we verify — but how we verify it. Patent pending.

## What EYDII Stops

These aren't hypothetical. Each is a documented attack pattern against production AI agents.

| Threat | What Happens Without EYDII | How EYDII Stops It |
|--------|---------------------------|-------------------|
| **Prompt Injection** | Injected instructions cause agent to exfiltrate data | Action blocked pre-execution — the unauthorized API call never fires |
| **Agent Drift** | 5 benign steps cascade into a data breach | Cumulative risk scoring detects the escalation pattern |
| **Trust Poisoning** | Compromised agent poisons every agent that trusts it | Agent-to-agent attestation — no agent inherits trust without proof |
| **Tool Shadowing** | Shadow tool mimics your allowlist, steals credentials | Identity-based tool verification at the MCP layer |
| **Hallucinated Completion** | Agent claims it finished work it never started | Receipt chain is empty — no cryptographic proof, no credit |
| **Specification Drift** | Agent builds the wrong features convincingly | ZKP probes verify alignment to the actual specification |
| **Circular Execution** | Agent loops for hours, looks productive, accomplishes nothing | Execution graph analysis detects the cycle |
| **Behavioral Drift** | Agent quietly stops running tests over weeks | Cross-task behavioral baselines catch the regression |

> **[See the interactive demos](https://id.veritera.ai/demos)**

---

## Install

```bash
pip install llama-index-tools-eydii
```

This installs the EYDII verification tools alongside the core `veritera` SDK. You will also need a LlamaIndex LLM provider:

```bash
pip install llama-index-tools-eydii llama-index-llms-openai
```

---

## Prerequisites: Create a Policy

Before using EYDII with LlamaIndex, create a policy that defines what your agent is allowed to do. You only need to do this once:

```python
from veritera import EydiiVerify

eydii = EydiiVerify(api_key="vt_live_...")  # Get your key at id.veritera.ai

# Create a policy from code
eydii.create_policy_sync(
    name="finance-controls",
    description="Controls for document agents with action capabilities",
    rules=[
        {"type": "action_whitelist", "params": {"allowed": ["email.send", "refund.process", "crm.update"]}},
        {"type": "amount_limit", "params": {"max": 10000, "currency": "USD"}},
    ],
)

# Or generate one from plain English
eydii.generate_policy_sync(
    "Allow sending emails, processing refunds under $10,000, and updating CRM records. Block bulk data exports and account deletions.",
    save=True,
)
```

A `default` policy is created automatically when you sign up — it blocks dangerous actions like database drops and admin overrides. You can use it immediately with `policy="default"`.

> **Tip:** `pip install veritera` to get the policy management SDK. See the [full policy docs](https://github.com/veritera-ai/eydii-python#policies).

---

## Quick Start

```python
import os
from llama_index.core.agent import FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from eydii_llamaindex import EydiiVerifyToolSpec

os.environ["VERITERA_API_KEY"] = "vt_live_..."

# Create EYDII verification tools
eydii = EydiiVerifyToolSpec(policy="finance-controls")  # create this policy first (see above) -- or use "default"
eydii_tools = eydii.to_tool_list()

# Your application tools
def send_payment(amount: float, recipient: str) -> str:
    """Send a payment to a recipient."""
    return f"Sent ${amount} to {recipient}"

app_tools = [FunctionTool.from_defaults(fn=send_payment)]

# Create agent with all tools
agent = FunctionAgent(
    tools=eydii_tools + app_tools,
    llm=OpenAI(model="gpt-4.1"),
    system_prompt=(
        "Before executing any sensitive action, ALWAYS call verify_action first. "
        "Only proceed if the result is APPROVED."
    ),
)

response = await agent.run("Send $500 to vendor@acme.com")
print(response)
```

The agent will call `verify_action` before `send_payment`. If the amount exceeds your policy threshold, EYDII denies it and the agent explains why it cannot proceed.

---

## Tutorial: Building a Verified Document Agent

This walkthrough builds a practical RAG + action agent -- an agent that reads documents AND takes real-world actions (sends emails, updates CRM records), with EYDII ensuring every action is authorized.

### Step 1: Define your application tools

These are the tools your agent needs to do its job. Some are read-only (safe), others mutate state (dangerous).

```python
from llama_index.core.tools import FunctionTool


# -- Read-only tools (low risk) --

def search_documents(query: str) -> str:
    """Search the company knowledge base for relevant documents."""
    # In production, this would query a VectorStoreIndex
    return (
        "Policy DOC-2024-118: Refund requests over $1,000 require VP approval. "
        "Requests under $1,000 may be processed by any support agent."
    )


def lookup_customer(customer_id: str) -> str:
    """Look up a customer record by ID."""
    return (
        f"Customer {customer_id}: Acme Corp, tier=enterprise, "
        f"account_manager=sarah@company.com, balance_due=$4,200"
    )


# -- Write/action tools (high risk -- EYDII must verify these) --

def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a customer or internal stakeholder."""
    # Production: calls your email service API
    return f"Email sent to {to}: '{subject}'"


def process_refund(customer_id: str, amount: float, reason: str) -> str:
    """Process a refund for a customer."""
    return f"Refund of ${amount:.2f} processed for customer {customer_id}: {reason}"


def update_crm_record(customer_id: str, field: str, value: str) -> str:
    """Update a field on a customer's CRM record."""
    return f"CRM updated: {customer_id}.{field} = {value}"


app_tools = [
    FunctionTool.from_defaults(fn=search_documents),
    FunctionTool.from_defaults(fn=lookup_customer),
    FunctionTool.from_defaults(fn=send_email),
    FunctionTool.from_defaults(fn=process_refund),
    FunctionTool.from_defaults(fn=update_crm_record),
]
```

### Step 2: Add EYDII verification tools

```python
import os
from eydii_llamaindex import EydiiVerifyToolSpec

os.environ["VERITERA_API_KEY"] = "vt_live_..."

eydii = EydiiVerifyToolSpec(
    agent_id="support-doc-agent",
    policy="customer-support",
)
eydii_tools = eydii.to_tool_list()
```

This gives the agent three additional tools: `verify_action`, `get_proof`, and `check_health`.

### Step 3: Build the agent with a verification-aware system prompt

The system prompt is critical. It tells the agent exactly when and how to use EYDII.

```python
from llama_index.core.agent import FunctionAgent
from llama_index.llms.openai import OpenAI

SYSTEM_PROMPT = """\
You are a customer support agent with access to company documents and customer records.

VERIFICATION RULES -- follow these exactly:
1. Reading documents and looking up customers does NOT require verification.
2. Before calling send_email, process_refund, or update_crm_record, you MUST
   call verify_action first with the action name and a JSON string of the parameters.
3. If verify_action returns APPROVED, proceed with the action.
4. If verify_action returns DENIED, do NOT execute the action. Explain the denial
   to the user and suggest next steps (e.g., escalate to a manager).
5. After completing a sensitive action, note the proof_id for the audit trail.

Example verification call:
  verify_action(action="process_refund", params='{"customer_id": "C-1001", "amount": 750, "reason": "defective product"}')
"""

agent = FunctionAgent(
    tools=eydii_tools + app_tools,
    llm=OpenAI(model="gpt-4.1"),
    system_prompt=SYSTEM_PROMPT,
)
```

### Step 4: Run the agent

```python
import asyncio

async def main():
    # Scenario 1: Small refund -- should be approved
    response = await agent.run(
        "Customer C-1001 (Acme Corp) wants a $400 refund for a defective shipment. "
        "Look up their account, check our refund policy, process the refund, "
        "and email the customer a confirmation."
    )
    print("--- Scenario 1 ---")
    print(response)

    # Scenario 2: Large refund -- should be denied by policy
    response = await agent.run(
        "Process a $5,000 refund for customer C-1001."
    )
    print("\n--- Scenario 2 ---")
    print(response)

asyncio.run(main())
```

### What happens under the hood

**Scenario 1** (approved):
```
1. Agent calls search_documents("refund policy")        --> reads policy (no verification needed)
2. Agent calls lookup_customer("C-1001")                --> reads record (no verification needed)
3. Agent calls verify_action("process_refund", ...)     --> EYDII returns APPROVED + proof_id
4. Agent calls process_refund("C-1001", 400, ...)       --> executes the refund
5. Agent calls verify_action("send_email", ...)         --> EYDII returns APPROVED + proof_id
6. Agent calls send_email("customer@acme.com", ...)     --> sends confirmation
7. Agent responds with summary and proof IDs
```

**Scenario 2** (denied):
```
1. Agent calls verify_action("process_refund", ...)     --> EYDII returns DENIED: "amount exceeds $1,000 limit"
2. Agent does NOT call process_refund
3. Agent responds: "I'm unable to process this refund. The amount exceeds the $1,000
   policy limit. Please escalate to a VP for approval."
```

---

## Two Integration Points

EYDII for LlamaIndex provides two complementary approaches. Use one or both depending on your needs.

### 1. EydiiVerifyToolSpec -- explicit verification tools

`EydiiVerifyToolSpec` is a LlamaIndex `BaseToolSpec` that adds verification tools directly to your agent's toolbox. The agent decides when to call them based on your system prompt.

```python
from eydii_llamaindex import EydiiVerifyToolSpec

spec = EydiiVerifyToolSpec(
    api_key="vt_live_...",           # or set VERITERA_API_KEY env var
    agent_id="my-agent",
    policy="finance-controls",
    fail_closed=True,
)
tools = spec.to_tool_list()
```

**Tools provided:**

| Tool | Purpose |
|---|---|
| `verify_action(action, params)` | Check if an action is allowed by policy before executing it. Returns `APPROVED` or `DENIED` with a proof ID. |
| `get_proof(proof_id)` | Retrieve the full cryptographic proof record for a previous verification. Use for audits and compliance reporting. |
| `check_health()` | Test connectivity to the EYDII service. Useful for startup checks and monitoring dashboards. |

**When to use:** You want the agent to reason about verification explicitly. The agent sees the approval/denial and can adapt its behavior -- explaining denials to users, suggesting alternatives, or noting proof IDs in its response.

### 2. EydiiEventHandler -- automatic audit trail

`EydiiEventHandler` hooks into LlamaIndex's instrumentation system to intercept and verify every tool call automatically. No changes to your agent's prompt or tool list required.

```python
from eydii_llamaindex import EydiiEventHandler
import llama_index.core.instrumentation as instrument

handler = EydiiEventHandler(
    api_key="vt_live_...",           # or set VERITERA_API_KEY env var
    agent_id="my-agent",
    policy="finance-controls",
    block_on_deny=True,              # raise ValueError on denied actions
    fail_closed=True,
)

dispatcher = instrument.get_dispatcher()
dispatcher.add_event_handler(handler)
```

**Behavior:**

- Every tool call the agent makes fires an instrumentation event.
- `EydiiEventHandler` intercepts tool call events and sends them to EYDII for verification.
- If `block_on_deny=True` and EYDII denies the action, a `ValueError` is raised, preventing execution.
- If `block_on_deny=False`, denied actions are logged but still execute (audit-only mode).
- All verifications (approved and denied) are recorded in your EYDII audit log.

**When to use:** You want a safety net that catches everything regardless of what the system prompt says. Useful as a defense-in-depth layer -- even if the agent skips the `verify_action` call, the event handler still catches and blocks unauthorized actions.

---

## Using Both Together

For maximum protection, combine both integration points. The ToolSpec gives the agent awareness of verification (so it can communicate denials gracefully), while the EventHandler acts as a backstop that catches anything the agent misses.

```python
import os
import llama_index.core.instrumentation as instrument
from llama_index.core.agent import FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from eydii_llamaindex import EydiiVerifyToolSpec, EydiiEventHandler

os.environ["VERITERA_API_KEY"] = "vt_live_..."

# --- Layer 1: ToolSpec (agent-aware verification) ---
eydii_spec = EydiiVerifyToolSpec(
    agent_id="billing-agent",
    policy="billing-controls",
)
eydii_tools = eydii_spec.to_tool_list()

# --- Layer 2: EventHandler (automatic backstop) ---
handler = EydiiEventHandler(
    agent_id="billing-agent",
    policy="billing-controls",
    block_on_deny=True,
)
dispatcher = instrument.get_dispatcher()
dispatcher.add_event_handler(handler)

# --- Application tools ---
def charge_customer(customer_id: str, amount: float) -> str:
    """Charge a customer's payment method."""
    return f"Charged ${amount:.2f} to customer {customer_id}"

def issue_credit(customer_id: str, amount: float) -> str:
    """Issue a credit to a customer's account."""
    return f"Issued ${amount:.2f} credit to customer {customer_id}"

app_tools = [
    FunctionTool.from_defaults(fn=charge_customer),
    FunctionTool.from_defaults(fn=issue_credit),
]

# --- Agent with dual protection ---
agent = FunctionAgent(
    tools=eydii_tools + app_tools,
    llm=OpenAI(model="gpt-4.1"),
    system_prompt=(
        "You are a billing agent. Before any charge or credit, call verify_action. "
        "Only proceed if APPROVED. Report the proof_id in your response."
    ),
)

# Even if the LLM ignores the system prompt and calls charge_customer directly,
# the EydiiEventHandler will intercept and block unauthorized actions.
response = await agent.run("Charge customer C-5021 $12,000")
```

**How the two layers interact:**

| Scenario | ToolSpec | EventHandler | Result |
|---|---|---|---|
| Agent calls `verify_action` first, gets APPROVED | Tells agent "approved" | Sees `charge_customer` call, verifies, allows | Action executes with two verification records |
| Agent calls `verify_action` first, gets DENIED | Tells agent "denied" | Never fires (agent stops) | Action blocked gracefully with explanation |
| Agent skips `verify_action`, calls tool directly | Not invoked | Intercepts tool call, verifies, blocks if denied | Safety net catches the gap |

---

## Configuration Reference

### EydiiVerifyToolSpec

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | `None` | EYDII API key. Falls back to `VERITERA_API_KEY` env var. |
| `base_url` | `str` | `https://id.veritera.ai` | EYDII API endpoint. Override for self-hosted deployments. |
| `agent_id` | `str` | `llamaindex-agent` | Identifier for this agent in audit logs. Use a unique name per agent. |
| `policy` | `str` | `None` | Default policy to evaluate actions against. Can be overridden per call. |
| `fail_closed` | `bool` | `True` | If `True`, deny actions when the EYDII API is unreachable. Set to `False` for fail-open (not recommended for production). |
| `timeout` | `float` | `10.0` | HTTP timeout in seconds for EYDII API calls. |

### EydiiEventHandler

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | `None` | EYDII API key. Falls back to `VERITERA_API_KEY` env var. |
| `base_url` | `str` | `https://id.veritera.ai` | EYDII API endpoint. Override for self-hosted deployments. |
| `agent_id` | `str` | `llamaindex-agent` | Identifier for this agent in audit logs. |
| `policy` | `str` | `None` | Policy to evaluate actions against. |
| `block_on_deny` | `bool` | `True` | If `True`, raise `ValueError` when an action is denied, preventing execution. Set to `False` for audit-only mode. |
| `fail_closed` | `bool` | `True` | If `True`, block actions when the EYDII API is unreachable. |

---

## How It Works

```
  User Request
       |
       v
  +-----------+
  |  LlamaIndex |
  |   Agent     |
  +------+------+
         |
    (1) Agent decides to call send_email(...)
         |
    (2) verify_action("send_email", '{"to": "user@co.com"}')
         |                                          |
         v                                          |
  +-------------+                                   |
  | EYDII API   |  <-- evaluates against policy     |
  +------+------+                                   |
         |                                          |
    APPROVED + proof_id                             |
         |                                          |
    (3) Agent proceeds with send_email(...)         |
         |                                          |
    (4) EydiiEventHandler intercepts (backup)  <----+
         |
    (5) Action executes
         |
         v
  Audit log: proof_id, timestamp, action, verdict, agent_id
```

1. The agent receives a user request and plans which tools to call.
2. Following the system prompt, the agent calls `verify_action` with the action name and parameters.
3. EYDII evaluates the action against your configured policy and returns `APPROVED` or `DENIED` with a cryptographic proof ID.
4. If approved, the agent calls the real tool. The `EydiiEventHandler` (if configured) provides a second verification as a safety net.
5. Every verification is recorded in your EYDII audit log with a tamper-proof proof ID for compliance.

---

## Error Handling

### EYDII API unreachable

By default, both `EydiiVerifyToolSpec` and `EydiiEventHandler` operate in **fail-closed** mode. If the EYDII API is unreachable, actions are denied:

```python
# ToolSpec returns an error string the agent can read
"ERROR: Verification unavailable -- ConnectionError: ..."

# EventHandler raises ValueError (if block_on_deny=True)
ValueError("EYDII: Action 'send_email' blocked -- verification unavailable.")
```

To switch to fail-open (not recommended for production):

```python
spec = EydiiVerifyToolSpec(fail_closed=False)
handler = EydiiEventHandler(fail_closed=False, block_on_deny=False)
```

### Invalid JSON in params

If the `params` argument to `verify_action` is not valid JSON, the tool gracefully wraps it:

```python
# This still works -- the raw string is sent as {"raw": "some text"}
verify_action(action="email.send", params="not valid json")
```

### Missing API key

A `ValueError` is raised immediately at initialization if no API key is found:

```python
ValueError("EYDII API key required. Pass api_key= or set VERITERA_API_KEY env var.")
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VERITERA_API_KEY` | Yes (unless passed via `api_key=`) | Your EYDII API key. Get one at [veritera.ai/dashboard](https://id.veritera.ai/dashboard). |
| `OPENAI_API_KEY` | For OpenAI LLM | Required if using `llama-index-llms-openai` as your LLM provider. |

---

## LlamaHub

This package follows the `llama-index-tools-*` naming convention for LlamaIndex community tool integrations. It is compatible with [LlamaHub](https://llamahub.ai) for discovery and can be installed directly from PyPI:

```bash
pip install llama-index-tools-eydii
```

The package registers the `EydiiVerifyToolSpec` tool spec and `EydiiEventHandler` instrumentation handler, both importable from `eydii_llamaindex`:

```python
from eydii_llamaindex import EydiiVerifyToolSpec, EydiiEventHandler
```

---

## V2: EYDII Execute -- Cryptographic Execution Receipts

While V1 (Verify) checks individual actions before they happen, V2 (Execute) monitors entire task executions and provides cryptographic proof that the work was done correctly -- without ever seeing the actual code or output.

Execute works by generating signed receipts at each step of an agent's task. These receipts form a tamper-proof audit trail that proves *what* happened and *in what order*, using mathematical proof. The receipts are submitted to EYDII Execute, which verifies the behavioral pattern matches expectations -- without needing access to the actual instructions, code, or data.

### How Receipts Work

Each tool call triggers a signed receipt containing the action type, timestamp, and a unique nonce — signed with your agent's Ed25519 private key. The receipt proves what action happened and in what order — without containing any code, data, or output. The server verifies the behavioral pattern, not the content. The receipt is submitted to EYDII Execute, which verifies the signature and adds it to the task's receipt chain.

### What Happens on Failure

Receipt emission is non-blocking. If EYDII Execute is unreachable, the error is logged and your agent continues working. A receipt failure should never stop your agent. This is by design — Verify is fail-closed (blocks on error), Execute is fire-and-forget (logs on error).

### Independent Verification

Anyone with your agent's public key can verify the receipt chain independently — no need to contact Veritera, no API call required. The Ed25519 signatures are self-contained mathematical proofs.

### Quick Start

```python
import os
from llama_index.core.agent import FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.instrumentation import get_dispatcher
from llama_index.llms.openai import OpenAI
from eydii_llamaindex import EydiiExecuteHandler

os.environ["VERITERA_API_KEY"] = "vt_live_..."

# Create the Execute handler
handler = EydiiExecuteHandler(
    task_id="task_weekly_report",
    agent_id="analytics-agent",
)

# Register with LlamaIndex's instrumentation system
dispatcher = get_dispatcher()
dispatcher.add_event_handler(handler)

# Your application tools
def run_query(sql: str) -> str:
    """Run a database query."""
    return f"Query executed: {sql}"

def send_report(to: str, data: str) -> str:
    """Send a report via email."""
    return f"Report sent to {to}"

agent = FunctionAgent(
    tools=[
        FunctionTool.from_defaults(fn=run_query),
        FunctionTool.from_defaults(fn=send_report),
    ],
    llm=OpenAI(model="gpt-4.1"),
    system_prompt="You generate weekly analytics reports.",
)

response = await agent.run("Generate the weekly analytics and email it to team@acme.com")
```

The `EydiiExecuteHandler` automatically intercepts tool call events, LLM calls, and retrieval events, emitting signed receipts for each. EYDII Execute verifies the chain of receipts to confirm the task followed the expected behavioral pattern.

### Supported Event Types

The handler automatically maps LlamaIndex instrumentation events to receipt action types:

| LlamaIndex Event | Receipt Action |
|---|---|
| `ToolCallEvent` | `tool_call` (or actual tool name if available) |
| `FunctionCallEvent` | `tool_call` (or actual function name if available) |
| `LLMCompletionStartEvent` | `llm_call` |
| `LLMChatStartEvent` | `llm_call` |
| `RetrievalStartEvent` | `file_read` |
| `QueryStartEvent` | `file_read` |
| `EmbeddingStartEvent` | `llm_call` |

### Manual Receipts

For actions not captured by the instrumentation system, emit receipts manually:

```python
handler = EydiiExecuteHandler(
    task_id="task_data_pipeline",
    agent_id="etl-agent",
)

# Emit a receipt for a custom action
result = handler.emit_receipt("data_extraction_complete")
print(f"Receipt: {result['receipt_id']}, Chain position: {result['chain_index']}")
```

### Using V1 + V2 Together

V1 (Verify) and V2 (Execute) are complementary. V1 checks *permission* before each action. V2 tracks *execution* across the entire task. Use both for complete coverage:

```python
import llama_index.core.instrumentation as instrument
from eydii_llamaindex import EydiiVerifyToolSpec, EydiiEventHandler, EydiiExecuteHandler

# V1: Verification tools + event handler for policy enforcement
eydii_spec = EydiiVerifyToolSpec(policy="finance-controls")
eydii_tools = eydii_spec.to_tool_list()

verify_handler = EydiiEventHandler(
    policy="finance-controls",
    block_on_deny=True,
)

# V2: Execution receipts for audit trail
execute_handler = EydiiExecuteHandler(
    task_id="task_quarterly_close",
    agent_id="finance-agent",
)

# Register both handlers
dispatcher = instrument.get_dispatcher()
dispatcher.add_event_handler(verify_handler)    # V1: blocks unauthorized actions
dispatcher.add_event_handler(execute_handler)   # V2: emits cryptographic receipts

agent = FunctionAgent(
    tools=eydii_tools + app_tools,
    llm=OpenAI(model="gpt-4.1"),
    system_prompt="Before any sensitive action, call verify_action first.",
)
```

### EydiiExecuteHandler Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `task_id` | `str` | Required | Identifier for the task being executed. Links all receipts in the chain. |
| `agent_id` | `str` | Required | Identifier for the agent performing the task. |
| `api_key` | `str` | `VERITERA_API_KEY` env var | Your EYDII API key. |
| `signing_key` | `str` | Same as `api_key` | Key used to sign receipts. Defaults to the API key. |
| `base_url` | `str` | `"https://id.veritera.ai"` | EYDII API endpoint. |

**Methods:**

| Method | Description |
|--------|-------------|
| `handle(event, **kwargs)` | Handle a LlamaIndex instrumentation event. Automatically called by the dispatcher. |
| `emit_receipt(action_type)` | Manually emit a receipt for a custom action. Returns `{"receipt_id": ..., "chain_index": ...}`. |

---

## EYDII Ecosystem

| Package | Framework | What It Does | Install |
|---------|-----------|-------------|---------|
| [veritera](https://github.com/veritera-ai/eydii-python) | Any Python | Core SDK. Verify actions, manage policies, sign and submit receipts. | `pip install veritera` |
| [eydii-openai](https://github.com/veritera-ai/eydii-openai) | OpenAI Agents SDK | `eydii_protect()` wrapper + `EydiiExecuteGuardrail`. Drop-in verification for OpenAI agents. | `pip install eydii-openai` |
| [langchain-eydii](https://github.com/veritera-ai/eydii-langchain) | LangChain / LangGraph | `EydiiVerifyMiddleware` + `EydiiExecuteMiddleware`. Wraps LangGraph tool nodes. | `pip install langchain-eydii` |
| [crewai-eydii](https://github.com/veritera-ai/eydii-crewai) | CrewAI | `EydiiVerifyTool` + guardrails + LLM hooks + `EydiiExecuteHook`. Multi-agent crew support. | `pip install crewai-eydii` |
| **llama-index-tools-eydii** (this package) | LlamaIndex | `EydiiVerifyToolSpec` + event handlers + `EydiiExecuteHandler`. Document agent support. | `pip install llama-index-tools-eydii` |
| [eydii-blog](https://github.com/veritera-ai/eydii-blog) | — | Technical articles on AI agent security and trust verification. | — |

---

## License

MIT -- EYDII by [Veritera AI](https://id.veritera.ai)
